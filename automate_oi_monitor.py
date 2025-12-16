"""
Automated Option Chain Monitor
Monitors MySQL or SQL Server for new snapshots and extracts data when changes are detected.
"""

import time
import logging
from datetime import datetime, time as dt_time
from typing import Optional, List, Dict
from pathlib import Path

# Import timezone handling
try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    HAS_PYTZ = False

# Import database connectors conditionally
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False

try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('oi_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Trading hours configuration
TRADING_START_TIME = dt_time(9, 15)   # 9:15 AM IST
TRADING_END_TIME = dt_time(15, 29)     # 3:29 PM IST (last minute of trading)
TRADING_STOP_TIME = dt_time(15, 30)    # 3:30 PM IST (stop monitoring after this)
IST_TIMEZONE = 'Asia/Kolkata'


def get_ist_timezone():
    """Get IST timezone object."""
    if HAS_PYTZ:
        return pytz.timezone(IST_TIMEZONE)
    else:
        # Fallback: Use UTC offset (not ideal, but works)
        from datetime import timedelta, timezone
        return timezone(timedelta(hours=5, minutes=30))


def check_pytz_installed():
    """Check if pytz is installed and log warning if not."""
    if not HAS_PYTZ:
        logger.warning("pytz not installed. Timezone handling may be inaccurate. Install with: pip install pytz")


def get_ist_now():
    """Get current time in IST."""
    if HAS_PYTZ:
        return datetime.now(pytz.timezone(IST_TIMEZONE))
    else:
        from datetime import timedelta, timezone
        ist = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(ist)


def is_trading_day():
    """Check if today is a trading day (Monday-Friday)."""
    ist_now = get_ist_now()
    weekday = ist_now.weekday()  # 0=Monday, 6=Sunday
    return weekday < 5  # Monday to Friday (0-4)


def is_trading_time():
    """Check if current time is within trading hours (9:15 AM - 3:29 PM IST, Mon-Fri)."""
    if not is_trading_day():
        return False
    
    ist_now = get_ist_now()
    current_time = ist_now.time()
    # Trading hours: 9:15 AM to 3:29 PM (inclusive of 3:29:00)
    # Include 3:29:00 PM but exclude anything after
    return TRADING_START_TIME <= current_time <= TRADING_END_TIME


def should_stop_trading():
    """Check if we should stop trading (after 3:29 PM IST, i.e., at or after 3:30 PM)."""
    if not is_trading_day():
        return True  # Stop on weekends
    
    ist_now = get_ist_now()
    current_time = ist_now.time()
    # Stop if current time is at or after 3:30 PM
    # This allows trading until 3:29:59 PM, then stops at 3:30:00 PM
    return current_time >= TRADING_STOP_TIME


class OptionChainMonitor:
    """Monitors option chain snapshots and extracts data when new snapshots are available."""
    
    def __init__(self, connection_config: Dict, ticker: str = 'NIFTY'):
        """
        Initialize the monitor.
        
        Args:
            connection_config: Database connection configuration dictionary
            ticker: Ticker symbol to monitor (default: 'NIFTY')
        """
        self.config = connection_config
        self.db_type = connection_config['type']
        self.ticker = ticker
        self.last_snapshot_id: Optional[int] = None
        
        # SQL Server query (uses TOP and ? parameters)
        # Fetches last 3 snapshots in a single query
        self.query_template_sqlserver = """
WITH Last3Snapshots AS (
    SELECT DISTINCT TOP 3 SNAPSHOT_ID
    FROM optionchain_combined
    WHERE TICKER = ?
    ORDER BY SNAPSHOT_ID DESC
),
ClosestExpiry AS (
    SELECT
        oc.DOWNLOAD_DATE,
        oc.DOWNLOAD_TIME,
        oc.SNAPSHOT_ID,
        oc.EXPIRY,
        oc.STRIKE,
        oc.UNDERLYING_VALUE,
        oc.c_OI,
        oc.c_CHNG_IN_OI,
        oc.c_LTP,
        oc.c_VOLUME,
        oc.p_OI,
        oc.p_CHNG_IN_OI,
        oc.p_LTP,
        oc.p_VOLUME,
        DENSE_RANK() OVER (
            PARTITION BY oc.SNAPSHOT_ID
            ORDER BY ABS(DATEDIFF(day, oc.EXPIRY, oc.DOWNLOAD_DATE))
        ) AS expiry_rank
    FROM optionchain_combined oc
    JOIN Last3Snapshots l3
        ON oc.SNAPSHOT_ID = l3.SNAPSHOT_ID
    WHERE oc.TICKER = ?
),
FilteredExpiry AS (
    SELECT *
    FROM ClosestExpiry
    WHERE expiry_rank = 1
),
StrikesAboveBelow AS (
    SELECT *,
        CASE
            WHEN STRIKE >= UNDERLYING_VALUE THEN
                ROW_NUMBER() OVER (
                    PARTITION BY SNAPSHOT_ID
                    ORDER BY
                        CASE WHEN STRIKE >= UNDERLYING_VALUE THEN 0 ELSE 1 END,
                        STRIKE ASC
                )
            ELSE NULL
        END AS above_rank,
        CASE
            WHEN STRIKE < UNDERLYING_VALUE THEN
                ROW_NUMBER() OVER (
                    PARTITION BY SNAPSHOT_ID
                    ORDER BY
                        CASE WHEN STRIKE < UNDERLYING_VALUE THEN 0 ELSE 1 END,
                        STRIKE DESC
                )
            ELSE NULL
        END AS below_rank
    FROM FilteredExpiry
)
SELECT
    DOWNLOAD_DATE,
    DOWNLOAD_TIME,
    SNAPSHOT_ID,
    EXPIRY,
    STRIKE,
    UNDERLYING_VALUE,
    c_OI,
    c_CHNG_IN_OI,
    c_LTP,
    c_VOLUME,
    p_OI,
    p_CHNG_IN_OI,
    p_LTP,
    p_VOLUME,
    above_rank,
    below_rank
FROM StrikesAboveBelow
WHERE above_rank < 10 OR below_rank < 10
ORDER BY SNAPSHOT_ID, STRIKE
"""
        
        # MySQL query (uses LIMIT and %s parameters, DATEDIFF syntax)
        # Fetches last 3 snapshots in a single query
        self.query_template_mysql = """
WITH Last3Snapshots AS (
    SELECT DISTINCT SNAPSHOT_ID
    FROM optionchain_combined
    WHERE TICKER = %s
    ORDER BY SNAPSHOT_ID DESC
    LIMIT 3
),
ClosestExpiry AS (
    SELECT
        oc.DOWNLOAD_DATE,
        oc.DOWNLOAD_TIME,
        oc.SNAPSHOT_ID,
        oc.EXPIRY,
        oc.STRIKE,
        oc.UNDERLYING_VALUE,
        oc.c_OI,
        oc.c_CHNG_IN_OI,
        oc.c_LTP,
        oc.c_VOLUME,
        oc.p_OI,
        oc.p_CHNG_IN_OI,
        oc.p_LTP,
        oc.p_VOLUME,
        DENSE_RANK() OVER (
            PARTITION BY oc.SNAPSHOT_ID
            ORDER BY ABS(DATEDIFF(oc.EXPIRY, oc.DOWNLOAD_DATE))
        ) AS expiry_rank
    FROM optionchain_combined oc
    JOIN Last3Snapshots l3
        ON oc.SNAPSHOT_ID = l3.SNAPSHOT_ID
    WHERE oc.TICKER = %s
),
FilteredExpiry AS (
    SELECT *
    FROM ClosestExpiry
    WHERE expiry_rank = 1
),
StrikesAboveBelow AS (
    SELECT *,
        CASE
            WHEN STRIKE >= UNDERLYING_VALUE THEN
                ROW_NUMBER() OVER (
                    PARTITION BY SNAPSHOT_ID
                    ORDER BY
                        CASE WHEN STRIKE >= UNDERLYING_VALUE THEN 0 ELSE 1 END,
                        STRIKE ASC
                )
            ELSE NULL
        END AS above_rank,
        CASE
            WHEN STRIKE < UNDERLYING_VALUE THEN
                ROW_NUMBER() OVER (
                    PARTITION BY SNAPSHOT_ID
                    ORDER BY
                        CASE WHEN STRIKE < UNDERLYING_VALUE THEN 0 ELSE 1 END,
                        STRIKE DESC
                )
            ELSE NULL
        END AS below_rank
    FROM FilteredExpiry
)
SELECT
    DOWNLOAD_DATE,
    DOWNLOAD_TIME,
    SNAPSHOT_ID,
    EXPIRY,
    STRIKE,
    UNDERLYING_VALUE,
    c_OI,
    c_CHNG_IN_OI,
    c_LTP,
    c_VOLUME,
    p_OI,
    p_CHNG_IN_OI,
    p_LTP,
    p_VOLUME,
    above_rank,
    below_rank
FROM StrikesAboveBelow
WHERE above_rank < 10 OR below_rank < 10
ORDER BY SNAPSHOT_ID, STRIKE
"""
    
    @property
    def query_template(self):
        """Get the appropriate query template based on database type."""
        if self.db_type == 'mysql':
            return self.query_template_mysql
        else:
            return self.query_template_sqlserver
    
    def get_connection(self):
        """Create and return a database connection."""
        try:
            if self.db_type == 'mysql':
                if not HAS_PYMYSQL:
                    raise ImportError("pymysql is required for MySQL connections. Install it with: pip install pymysql")
                conn = pymysql.connect(
                    host=self.config['host'],
                    port=self.config['port'],
                    user=self.config['user'],
                    password=self.config['password'],
                    database=self.config['database'],
                    connect_timeout=self.config['connect_timeout'],
                    cursorclass=pymysql.cursors.DictCursor
                )
            else:  # SQL Server
                if not HAS_PYODBC:
                    raise ImportError("pyodbc is required for SQL Server connections. Install it with: pip install pyodbc")
                from config import get_connection_string
                conn = pyodbc.connect(get_connection_string())
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def get_latest_snapshot_id(self) -> Optional[int]:
        """
        Get the latest snapshot ID for the ticker from optionchain_combined.
        
        Returns:
            Latest snapshot ID or None if no snapshots found
        """
        if self.db_type == 'mysql':
            query = """
            SELECT SNAPSHOT_ID
            FROM optionchain_combined
            WHERE TICKER = %s
            ORDER BY SNAPSHOT_ID DESC
            LIMIT 1
            """
            params = (self.ticker,)
        else:  # SQL Server
            query = """
            SELECT TOP 1 SNAPSHOT_ID
            FROM optionchain_combined
            WHERE TICKER = ?
            ORDER BY SNAPSHOT_ID DESC
            """
            params = (self.ticker,)
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.close()
            
            if row:
                # Handle different cursor types
                if self.db_type == 'mysql':
                    snapshot_id = row['SNAPSHOT_ID']
                else:
                    snapshot_id = row[0]
                logger.debug(f"Latest snapshot ID: {snapshot_id}")
                return snapshot_id
            else:
                logger.warning(f"No snapshots found for ticker {self.ticker}")
                return None
        except Exception as e:
            logger.error(f"Error getting latest snapshot ID: {e}")
            return None
    
    def get_snapshot_ids(self, limit: int = 3) -> List[int]:
        """
        Get the last N snapshot IDs for the ticker from optionchain_combined.
        
        Args:
            limit: Number of snapshot IDs to retrieve
            
        Returns:
            List of snapshot IDs (most recent first)
        """
        if self.db_type == 'mysql':
            query = """
            SELECT DISTINCT SNAPSHOT_ID
            FROM optionchain_combined
            WHERE TICKER = %s
            ORDER BY SNAPSHOT_ID DESC
            LIMIT %s
            """
            params = (self.ticker, limit)
        else:  # SQL Server
            query = f"""
            SELECT DISTINCT TOP {limit} SNAPSHOT_ID
            FROM optionchain_combined
            WHERE TICKER = ?
            ORDER BY SNAPSHOT_ID DESC
            """
            params = (self.ticker,)
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            if self.db_type == 'mysql':
                snapshot_ids = [row['SNAPSHOT_ID'] for row in rows]
            else:
                snapshot_ids = [row[0] for row in rows]
            logger.debug(f"Retrieved {len(snapshot_ids)} snapshot IDs: {snapshot_ids}")
            return snapshot_ids
        except Exception as e:
            logger.error(f"Error getting snapshot IDs: {e}")
            return []
    
    def execute_query_for_snapshot(self, snapshot_id: int) -> List[Dict]:
        """
        Execute the main query for a specific snapshot ID.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            params = (self.ticker, snapshot_id)
            cursor.execute(self.query_template, params)
            rows = cursor.fetchall()
            results = []
            if self.db_type == 'mysql':
                results = list(rows)
            else:
                columns = [column[0] for column in cursor.description]
                for row in rows:
                    result_dict = dict(zip(columns, row))
                    results.append(result_dict)
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Error executing query for snapshot {snapshot_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def execute_query_for_snapshots(self, snapshot_ids: List[int]) -> List[Dict]:
        """
        Fetch data for last 3 snapshots using a single query.
        The query automatically gets the last 3 snapshots, so snapshot_ids parameter
        is kept for compatibility but not used in the query.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # Query automatically gets last 3 snapshots, only needs ticker parameter
            params = (self.ticker, self.ticker) if self.db_type == 'mysql' else (self.ticker, self.ticker)
            cursor.execute(self.query_template, params)
            rows = cursor.fetchall()
            results = []
            if self.db_type == 'mysql':
                results = list(rows)
            else:
                columns = [column[0] for column in cursor.description]
                for row in rows:
                    result_dict = dict(zip(columns, row))
                    results.append(result_dict)
            conn.close()
            logger.info(f"Retrieved {len(results)} total rows for last 3 snapshots")
            return results
        except Exception as e:
            logger.error(f"Error executing query for snapshots: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def save_results(self, results: List[Dict], snapshot_id: int):
        """
        Save query results to a CSV file.
        
        Args:
            results: List of dictionaries containing query results
            snapshot_id: The snapshot ID for filename
        """
        if not results:
            logger.warning(f"No results to save for snapshot {snapshot_id}")
            return
        
        import csv
        
        # Create output directory if it doesn't exist
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = output_dir / f"snapshot_{snapshot_id}_{timestamp}.csv"
        
        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = results[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        logger.info(f"Saved {len(results)} rows to {filename}")
    
    def process_snapshots(self, snapshot_ids: List[int]):
        """
        Process multiple snapshots and save their data in a single combined file.
        Always processes all provided snapshots together - never saves individual snapshots.
        """
        if not snapshot_ids:
            logger.warning("No snapshot IDs provided to process.")
            return
        logger.info(f"Processing snapshots (combined): {snapshot_ids}")
        # Always combine multiple snapshots - never save individual snapshots
        results = self.execute_query_for_snapshots(snapshot_ids)
        if results:
            # use the most recent snapshot id for filename reference
            latest_id = snapshot_ids[0]
            self.save_results(results, latest_id)
            
            # Process signals and execute trades
            self.process_signals_and_trades(snapshot_ids, latest_id)
    
    def update_portfolio_status(self):
        """
        Update portfolio status every minute and push to GitHub.
        This runs even when there are no new snapshots to keep portfolio value current.
        """
        try:
            from portfolio_manager import PortfolioManager
            from generate_signal import latest_output_file, load_csv, prepare_data, get_current_ltp
            from pathlib import Path
            
            portfolio = PortfolioManager()
            open_position = portfolio.get_open_position()
            
            if open_position:
                # Get latest CSV to calculate current LTP
                try:
                    output_dir = Path('output')
                    csv_path = latest_output_file(output_dir)
                    df_raw = load_csv(csv_path)
                    df_prep = prepare_data(df_raw)
                    
                    current_ltp = get_current_ltp(
                        df_prep,
                        open_position['expiry'],
                        open_position['strike'],
                        open_position['type']
                    )
                    
                    if current_ltp:
                        # Update portfolio summary (this triggers git sync)
                        summary = portfolio.get_portfolio_summary(current_ltp)
                        logger.info(f"Portfolio Update: Cash={summary['cash']:.2f}, Position={summary['position_value']:.2f}, Total={summary['total_value']:.2f} (Unrealized P&L: {summary['unrealized_pnl']:.2f} ({summary['unrealized_pnl_pct']:.2f}%))")
                        # Force save to trigger git sync
                        portfolio._save_portfolio()
                    else:
                        # No LTP available, just log cash balance
                        summary = portfolio.get_portfolio_summary()
                        logger.info(f"Portfolio Update: Cash={summary['cash']:.2f} (Position LTP unavailable)")
                        portfolio._save_portfolio()
                except FileNotFoundError:
                    # No CSV file yet, just log cash balance
                    summary = portfolio.get_portfolio_summary()
                    logger.info(f"Portfolio Update: Cash={summary['cash']:.2f} (No data file available)")
                    portfolio._save_portfolio()
                except Exception as e:
                    logger.debug(f"Error updating portfolio status: {e}")
            else:
                # No open position, just log cash balance and sync
                summary = portfolio.get_portfolio_summary()
                logger.info(f"Portfolio Update: Cash={summary['cash']:.2f}, Total={summary['total_value']:.2f} (No open position)")
                portfolio._save_portfolio()
        except Exception as e:
            logger.debug(f"Error in portfolio status update: {e}")
    
    def process_signals_and_trades(self, snapshot_ids: List[int], latest_snapshot_id: int):
        """
        Generate signals from the latest CSV and execute trades via portfolio manager.
        """
        try:
            from portfolio_manager import PortfolioManager
            from generate_signal import latest_output_file, load_csv, prepare_data, evaluate_signal, get_current_ltp
            from pathlib import Path
            
            # Initialize portfolio manager
            portfolio = PortfolioManager()
            
            # Get the latest CSV file (should be the one we just saved)
            output_dir = Path('output')
            csv_path = latest_output_file(output_dir)
            
            logger.info(f"Processing signals from: {csv_path}")
            
            # Log initial portfolio value
            summary = portfolio.get_portfolio_summary()
            logger.info(f"Portfolio Value: {summary['total_value']:.2f} (Cash: {summary['cash']:.2f})")
            
            # Load and prepare data
            df_raw = load_csv(csv_path)
            df_prep = prepare_data(df_raw)
            
            # Check for open position - if exists, evaluate exit conditions
            open_position = portfolio.get_open_position()
            current_ltp = None
            if open_position:
                logger.info(f"Open position: {open_position['type']} {open_position['expiry']} {open_position['strike']}")
                
                # Get current LTP for portfolio value calculation
                current_ltp = get_current_ltp(
                    df_prep,
                    open_position['expiry'],
                    open_position['strike'],
                    open_position['type']
                )
                
                # Get current snapshot_seq from dataframe (latest snapshot)
                snap_seqs = sorted(df_prep.reset_index()["SNAPSHOT_SEQ"].unique())
                current_snapshot_seq = snap_seqs[-1] if snap_seqs else open_position.get('snapshot_seq', 0)
                
                # Evaluate exit conditions using the backtest logic
                signal_result = evaluate_signal(
                    df_prep,
                    has_open_position=True,
                    position_type=open_position['type'],
                    position_expiry=open_position['expiry'],
                    position_strike=open_position['strike'],
                    entry_price=open_position['entry_price'],
                    entry_snapshot_seq=open_position.get('snapshot_seq', 0)
                )
                
                # Log portfolio value (cash + position value)
                if current_ltp:
                    summary = portfolio.get_portfolio_summary(current_ltp)
                    logger.info(f"Portfolio Value: Cash={summary['cash']:.2f}, Position={summary['position_value']:.2f}, Total={summary['total_value']:.2f} (Unrealized P&L: {summary['unrealized_pnl']:.2f} ({summary['unrealized_pnl_pct']:.2f}%))")
                
                # If sell signal is generated, execute the trade
                if signal_result['signal'] in ['SELL_CALL', 'SELL_PUT']:
                    ltp = signal_result.get('ltp')
                    if ltp:
                        success, message = portfolio.sell(
                            ltp,
                            latest_snapshot_id,
                            current_snapshot_seq
                        )
                        if success:
                            logger.info(f"SELL executed: {signal_result.get('reason', 'Exit condition met')} - {message}")
                            # Log portfolio value after sell
                            summary = portfolio.get_portfolio_summary()
                            logger.info(f"Portfolio Value: {summary['total_value']:.2f} (Cash: {summary['cash']:.2f})")
                        else:
                            logger.warning(f"SELL failed: {message}")
                    else:
                        logger.warning(f"SELL signal generated but LTP not available")
                else:
                    # No exit condition met
                    logger.debug(f"Position held: {signal_result.get('reason', 'No exit condition')}")
            
            # Evaluate new buy signals (only if no open position)
            if not portfolio.has_open_position():
                # Get last buy snapshot for cooldown check
                last_buy_snapshot_seq = portfolio.get_last_buy_snapshot_seq()
                signal_result = evaluate_signal(
                    df_prep, 
                    has_open_position=False,
                    last_buy_snapshot_seq=last_buy_snapshot_seq
                )
                
                if signal_result['signal'] in ['BUY_CALL', 'BUY_PUT']:
                    ltp = signal_result.get('ltp')
                    if ltp:
                        # Get current snapshot_seq for the buy
                        snap_seqs = sorted(df_prep.reset_index()["SNAPSHOT_SEQ"].unique())
                        current_snapshot_seq = snap_seqs[-1] if snap_seqs else 0
                        
                        success, message = portfolio.buy(
                            signal_result['signal'],
                            signal_result['expiry'],
                            signal_result['strike'],
                            ltp,
                            latest_snapshot_id,
                            signal_result.get('snapshot_seq', current_snapshot_seq)
                        )
                        if success:
                            logger.info(f"BUY executed: {message}")
                            # Log portfolio value after buy (cash only, position value will be logged next cycle)
                            summary = portfolio.get_portfolio_summary()
                            logger.info(f"Portfolio Value: {summary['total_value']:.2f} (Cash: {summary['cash']:.2f}, Position: {summary['position_value']:.2f})")
                        else:
                            logger.warning(f"BUY failed: {message}")
                    else:
                        logger.warning(f"BUY signal generated but LTP not available")
                elif signal_result['signal'] == 'NO_SIGNAL':
                    logger.debug(f"No signal: {signal_result.get('reason', 'Unknown')}")
                    # Log portfolio value even when no signal
                    summary = portfolio.get_portfolio_summary()
                    logger.info(f"Portfolio Value: {summary['total_value']:.2f} (Cash: {summary['cash']:.2f})")
            else:
                logger.debug("Skipping buy signal evaluation - position already open")
                
        except ImportError as e:
            logger.warning(f"Portfolio/signal modules not available: {e}")
        except Exception as e:
            logger.error(f"Error processing signals and trades: {e}", exc_info=True)
    
    def run(self, check_interval: int = 60):
        """
        Main monitoring loop with trading hours enforcement.
        
        Args:
            check_interval: Time in seconds between checks (default: 60 seconds)
        """
        check_pytz_installed()
        
        ist_now = get_ist_now()
        logger.info(f"Starting Option Chain Monitor for {self.ticker}")
        logger.info(f"Current IST time: {ist_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"Check interval: {check_interval} seconds")
        logger.info(f"Trading hours: {TRADING_START_TIME.strftime('%H:%M')} - {TRADING_END_TIME.strftime('%H:%M')} IST (Monday-Friday)")
        logger.info(f"Monitor will stop after {TRADING_END_TIME.strftime('%H:%M')} IST (at {TRADING_STOP_TIME.strftime('%H:%M')} IST)")
        
        # Check if trading hours
        if not is_trading_time():
            ist_now = get_ist_now()
            if not is_trading_day():
                logger.warning(f"Outside trading days. Current day: {ist_now.strftime('%A')}")
            else:
                logger.warning(f"Outside trading hours. Current time: {ist_now.strftime('%H:%M:%S %Z')}")
            logger.info("Exiting. Will start again at 9:15 AM IST on next trading day.")
            return
        
        # Check for open positions from previous session
        try:
            from portfolio_manager import PortfolioManager
            portfolio = PortfolioManager()
            open_position = portfolio.get_open_position()
            if open_position:
                logger.info(f"Resuming with open position: {open_position['type']} {open_position['expiry']} {open_position['strike']}")
                logger.info(f"Position entered: {open_position.get('entry_time', 'Unknown')}")
        except Exception as e:
            logger.debug(f"Could not check portfolio: {e}")
        
        # Initialize with current latest snapshot
        self.last_snapshot_id = self.get_latest_snapshot_id()
        if self.last_snapshot_id is not None:
            logger.info(f"Initial snapshot ID: {self.last_snapshot_id}")
        else:
            logger.warning("No initial snapshot found. Will check again on next iteration.")
        
        try:
            while True:
                # Check if still in trading hours
                if not is_trading_time():
                    ist_now = get_ist_now()
                    if should_stop_trading():
                        logger.info(f"Market close time reached (after 3:29 PM IST). Current time: {ist_now.strftime('%H:%M:%S %Z')}")
                        
                        # Check if there's an open position to carry forward (no forced sells)
                        try:
                            from portfolio_manager import PortfolioManager
                            portfolio = PortfolioManager()
                            open_position = portfolio.get_open_position()
                            if open_position:
                                logger.info(f"Carrying forward open position: {open_position['type']} {open_position['expiry']} {open_position['strike']}")
                                logger.info(f"Position entered at: {open_position.get('entry_time', 'Unknown')}")
                                logger.info(f"Position will be monitored when trading resumes next day at 9:15 AM IST.")
                        except Exception:
                            pass
                        
                        logger.info("Stopping monitor. Will resume at 9:15 AM IST on next trading day (Monday-Friday).")
                        break
                    else:
                        logger.info(f"Outside trading hours. Current time: {ist_now.strftime('%H:%M:%S %Z')}")
                        logger.info("Stopping monitor. Will resume at 9:15 AM IST on next trading day.")
                        break
                # Check for new snapshot
                current_snapshot_id = self.get_latest_snapshot_id()
                
                if current_snapshot_id is None:
                    logger.warning("No snapshots found. Waiting...")
                    time.sleep(check_interval)
                    continue
                
                # Check if snapshot has changed
                if current_snapshot_id != self.last_snapshot_id:
                    logger.info(f"New snapshot detected! Previous: {self.last_snapshot_id}, Current: {current_snapshot_id}")
                    
                    # Get last 3 snapshots
                    snapshot_ids = self.get_snapshot_ids(limit=3)
                    
                    if snapshot_ids:
                        logger.info(f"Processing last {len(snapshot_ids)} snapshots: {snapshot_ids}")
                        self.process_snapshots(snapshot_ids)
                    else:
                        logger.warning("No snapshots to process")
                    
                    # Update last snapshot ID
                    self.last_snapshot_id = current_snapshot_id
                else:
                    logger.debug(f"No change detected. Current snapshot: {current_snapshot_id}")
                
                # Update portfolio status every minute (even without new snapshots)
                self.update_portfolio_status()
                
                # Wait before next check
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Unexpected error in monitoring loop: {e}", exc_info=True)
            raise


def main():
    """Main entry point."""
    import os
    from config import get_connection_config
    
    # Get connection config from config
    connection_config = get_connection_config()
    
    # Get ticker from environment or use default
    ticker = os.getenv('TICKER', 'NIFTY')
    
    # Get check interval from environment or use default (60 seconds)
    check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
    
    # Create and run monitor
    monitor = OptionChainMonitor(connection_config, ticker=ticker)
    monitor.run(check_interval=check_interval)


if __name__ == '__main__':
    main()

