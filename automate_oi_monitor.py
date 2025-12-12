"""
Automated Option Chain Monitor
Monitors MySQL or SQL Server for new snapshots and extracts data when changes are detected.
"""

import time
import logging
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

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


class OptionChainMonitor:
    """Monitors option chain snapshots and extracts data when new snapshots are available."""
    
    def __init__(self, connection_config: Dict, ticker: str = 'NIFTY50'):
        """
        Initialize the monitor.
        
        Args:
            connection_config: Database connection configuration dictionary
            ticker: Ticker symbol to monitor (default: 'NIFTY50')
        """
        self.config = connection_config
        self.db_type = connection_config['type']
        self.ticker = ticker
        self.last_snapshot_id: Optional[int] = None
        
        # SQL Server query (uses TOP and ? parameters)
        self.query_template_sqlserver = """
WITH ClosestExpiry AS (
    SELECT
        os.DOWNLOAD_DATE,
        os.DOWNLOAD_TIME,
        oc.SNAPSHOT_ID,
        oc.EXPIRY,
        oc.STRIKE,
        os.UNDERLYING_VALUE,
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
            ORDER BY ABS(DATEDIFF(day, oc.EXPIRY, os.DOWNLOAD_DATE))
        ) AS expiry_rank
    FROM optionchain oc
    JOIN optionchain_snapshots os
        ON oc.SNAPSHOT_ID = os.SNAPSHOT_ID
        AND oc.TICKER = os.TICKER
    WHERE oc.TICKER = ?
        AND oc.SNAPSHOT_ID = ?
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
        self.query_template_mysql = """
WITH ClosestExpiry AS (
    SELECT
        os.DOWNLOAD_DATE,
        os.DOWNLOAD_TIME,
        oc.SNAPSHOT_ID,
        oc.EXPIRY,
        oc.STRIKE,
        os.UNDERLYING_VALUE,
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
            ORDER BY ABS(DATEDIFF(oc.EXPIRY, os.DOWNLOAD_DATE))
        ) AS expiry_rank
    FROM optionchain oc
    JOIN optionchain_snapshots os
        ON oc.SNAPSHOT_ID = os.SNAPSHOT_ID
        AND oc.TICKER = os.TICKER
    WHERE oc.TICKER = %s
        AND oc.SNAPSHOT_ID = %s
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
        Get the latest snapshot ID for the ticker.
        
        Returns:
            Latest snapshot ID or None if no snapshots found
        """
        if self.db_type == 'mysql':
            query = """
            SELECT SNAPSHOT_ID
            FROM optionchain_snapshots
            WHERE TICKER = %s
            ORDER BY SNAPSHOT_ID DESC
            LIMIT 1
            """
            params = (self.ticker,)
        else:  # SQL Server
            query = """
            SELECT TOP 1 SNAPSHOT_ID
            FROM optionchain_snapshots
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
        Get the last N snapshot IDs for the ticker.
        
        Args:
            limit: Number of snapshot IDs to retrieve
            
        Returns:
            List of snapshot IDs (most recent first)
        """
        if self.db_type == 'mysql':
            query = """
            SELECT SNAPSHOT_ID
            FROM optionchain_snapshots
            WHERE TICKER = %s
            ORDER BY SNAPSHOT_ID DESC
            LIMIT %s
            """
            params = (self.ticker, limit)
        else:  # SQL Server
            query = f"""
            SELECT TOP {limit} SNAPSHOT_ID
            FROM optionchain_snapshots
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
        Fetch data for multiple snapshot IDs and return combined rows.
        """
        combined = []
        for sid in snapshot_ids:
            rows = self.execute_query_for_snapshot(sid)
            # tag snapshot id explicitly in case column naming differs
            for r in rows:
                r["SNAPSHOT_ID"] = sid
            combined.extend(rows)
        logger.info(f"Retrieved {len(combined)} total rows for snapshots {snapshot_ids}")
        return combined
    
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
        Process multiple snapshots and save their data in a single file.
        """
        if not snapshot_ids:
            logger.warning("No snapshot IDs provided to process.")
            return
        logger.info(f"Processing snapshots (combined): {snapshot_ids}")
        results = self.execute_query_for_snapshots(snapshot_ids)
        if results:
            # use the most recent snapshot id for filename reference
            latest_id = snapshot_ids[0]
            self.save_results(results, latest_id)
    
    def run(self, check_interval: int = 60):
        """
        Main monitoring loop.
        
        Args:
            check_interval: Time in seconds between checks (default: 60 seconds)
        """
        logger.info(f"Starting Option Chain Monitor for {self.ticker}")
        logger.info(f"Check interval: {check_interval} seconds")
        
        # Initialize with current latest snapshot
        self.last_snapshot_id = self.get_latest_snapshot_id()
        if self.last_snapshot_id is not None:
            logger.info(f"Initial snapshot ID: {self.last_snapshot_id}")
        else:
            logger.warning("No initial snapshot found. Will check again on next iteration.")
        
        try:
            while True:
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
    ticker = os.getenv('TICKER', 'NIFTY50')
    
    # Get check interval from environment or use default (60 seconds)
    check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
    
    # Create and run monitor
    monitor = OptionChainMonitor(connection_config, ticker=ticker)
    monitor.run(check_interval=check_interval)


if __name__ == '__main__':
    main()

