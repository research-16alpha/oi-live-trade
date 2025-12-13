"""
Portfolio Manager for Mock Trading
Tracks portfolio balance and executes buy/sell trades.
"""

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

PORTFOLIO_FILE = Path("portfolio.json")
DEFAULT_INITIAL_BALANCE = 100000.0  # Starting balance
LOT_SIZE = 150  # Number of contracts per trade


class PortfolioManager:
    """Manages mock portfolio balance and positions."""
    
    def __init__(self, portfolio_file: Path = PORTFOLIO_FILE, initial_balance: float = DEFAULT_INITIAL_BALANCE):
        """
        Initialize portfolio manager.
        
        Args:
            portfolio_file: Path to JSON file storing portfolio state
            initial_balance: Initial balance if portfolio doesn't exist
        """
        self.portfolio_file = portfolio_file
        self.initial_balance = initial_balance
        self.portfolio = self._load_portfolio()
    
    def _load_portfolio(self) -> Dict:
        """Load portfolio from file or create new one."""
        if self.portfolio_file.exists():
            try:
                with open(self.portfolio_file, 'r') as f:
                    portfolio = json.load(f)
                logger.info(f"Loaded portfolio: Balance = {portfolio.get('balance', 0):.2f}")
                return portfolio
            except Exception as e:
                logger.warning(f"Error loading portfolio file: {e}. Creating new portfolio.")
        
        # Create new portfolio
        portfolio = {
            "balance": self.initial_balance,
            "positions": [],
            "trade_history": [],
            "last_buy_snapshot_seq": -9999,  # Track last buy snapshot for cooldown
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        self._save_portfolio(portfolio)
        logger.info(f"Created new portfolio with balance: {self.initial_balance:.2f}")
        return portfolio
    
    def _save_portfolio(self, portfolio: Optional[Dict] = None):
        """Save portfolio to file."""
        if portfolio is None:
            portfolio = self.portfolio
        
        portfolio["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.portfolio_file, 'w') as f:
                json.dump(portfolio, f, indent=2)
            logger.info("Portfolio saved successfully")
            
            # Auto-sync to git for Streamlit Cloud
            self._sync_to_git()
        except Exception as e:
            logger.error(f"Error saving portfolio: {e}")
    
    def _sync_to_git(self):
        """
        Automatically commit and push portfolio.json to git for Streamlit Cloud.
        This runs in the background and doesn't block if git operations fail.
        """
        try:
            portfolio_file = self.portfolio_file.resolve()
            repo_dir = portfolio_file.parent
            
            # Check if we're in a git repository
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=repo_dir,
                capture_output=True,
                timeout=2
            )
            if result.returncode != 0:
                logger.debug("Not in a git repository, skipping git sync")
                return
            
            # Check if portfolio.json is tracked
            result = subprocess.run(
                ['git', 'ls-files', '--error-unmatch', str(portfolio_file.name)],
                cwd=repo_dir,
                capture_output=True,
                timeout=2
            )
            if result.returncode != 0:
                logger.debug("portfolio.json not tracked in git, skipping sync")
                return
            
            # Check if there are changes
            result = subprocess.run(
                ['git', 'diff', '--quiet', str(portfolio_file.name)],
                cwd=repo_dir,
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                logger.debug("No changes to portfolio.json, skipping sync")
                return
            
            # Stage the file
            subprocess.run(
                ['git', 'add', str(portfolio_file.name)],
                cwd=repo_dir,
                capture_output=True,
                timeout=2
            )
            
            # Commit
            commit_message = f"Auto-update portfolio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            result = subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=repo_dir,
                capture_output=True,
                timeout=2
            )
            
            if result.returncode == 0:
                logger.info("Portfolio committed to git")
                
                # Push to remote (non-blocking, runs in background)
                subprocess.Popen(
                    ['git', 'push', 'origin', 'main'],
                    cwd=repo_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info("Portfolio push initiated to GitHub (Streamlit will update automatically)")
            else:
                logger.debug(f"Git commit failed (may be no changes): {result.stderr.decode()}")
                
        except subprocess.TimeoutExpired:
            logger.warning("Git sync timed out, continuing without sync")
        except FileNotFoundError:
            logger.debug("Git not found, skipping auto-sync")
        except Exception as e:
            logger.debug(f"Git sync failed (non-critical): {e}")
    
    def get_balance(self) -> float:
        """Get current portfolio balance."""
        return self.portfolio.get("balance", 0.0)
    
    def has_open_position(self) -> bool:
        """Check if there's an open position."""
        positions = self.portfolio.get("positions", [])
        return len([p for p in positions if p.get("status") == "open"]) > 0
    
    def get_open_position(self) -> Optional[Dict]:
        """Get the current open position, if any."""
        positions = self.portfolio.get("positions", [])
        open_positions = [p for p in positions if p.get("status") == "open"]
        return open_positions[0] if open_positions else None
    
    def get_last_buy_snapshot_seq(self) -> int:
        """Get the last buy snapshot sequence for cooldown calculation."""
        return self.portfolio.get("last_buy_snapshot_seq", -9999)
    
    def get_position_value(self, current_ltp: Optional[float] = None) -> float:
        """
        Get current value of open position.
        
        Args:
            current_ltp: Current last traded price (if None, returns 0)
            
        Returns:
            Current position value (LTP * quantity) or 0 if no position
        """
        open_position = self.get_open_position()
        if not open_position or current_ltp is None:
            return 0.0
        return current_ltp * open_position.get("quantity", LOT_SIZE)
    
    def get_total_portfolio_value(self, current_ltp: Optional[float] = None) -> float:
        """
        Get total portfolio value (cash + position value).
        
        Args:
            current_ltp: Current last traded price for open position (if any)
            
        Returns:
            Total portfolio value
        """
        cash = self.get_balance()
        position_value = self.get_position_value(current_ltp)
        return cash + position_value
    
    def buy(self, signal_type: str, expiry: str, strike: float, ltp: float, snapshot_id: int, snapshot_seq: int) -> Tuple[bool, str]:
        """
        Execute a buy trade.
        
        Args:
            signal_type: "BUY_CALL" or "BUY_PUT"
            expiry: Expiry date
            strike: Strike price
            ltp: Last traded price
            snapshot_id: Snapshot ID
            snapshot_seq: Snapshot sequence number
            
        Returns:
            Tuple of (success, message)
        """
        if self.has_open_position():
            return False, "Cannot buy: Position already open"
        
        cost = ltp * LOT_SIZE
        balance = self.get_balance()
        
        if cost > balance:
            return False, f"Insufficient balance: Need {cost:.2f}, have {balance:.2f}"
        
        # Deduct from balance
        new_balance = balance - cost
        
        # Create position
        position = {
            "type": signal_type,
            "expiry": expiry,
            "strike": strike,
            "entry_price": ltp,
            "entry_cost": cost,
            "quantity": LOT_SIZE,
            "snapshot_id": snapshot_id,
            "snapshot_seq": snapshot_seq,
            "entry_time": datetime.now().isoformat(),
            "status": "open"
        }
        
        # Update portfolio
        self.portfolio["balance"] = new_balance
        self.portfolio["positions"].append(position)
        # Track last buy snapshot for cooldown calculation
        self.portfolio["last_buy_snapshot_seq"] = snapshot_seq
        
        # Add to trade history
        trade = {
            "action": "BUY",
            "signal_type": signal_type,
            "expiry": expiry,
            "strike": strike,
            "ltp": ltp,
            "cost": cost,
            "balance_before": balance,
            "balance_after": new_balance,
            "snapshot_id": snapshot_id,
            "snapshot_seq": snapshot_seq,
            "timestamp": datetime.now().isoformat()
        }
        self.portfolio["trade_history"].append(trade)
        
        self._save_portfolio()
        
        logger.info(f"BUY executed: {signal_type} {expiry} {strike} @ {ltp:.2f} = {cost:.2f}. Balance: {balance:.2f} -> {new_balance:.2f}")
        return True, f"Bought {signal_type} {expiry} {strike} @ {ltp:.2f} for {cost:.2f}. New balance: {new_balance:.2f}"
    
    def sell(self, ltp: float, snapshot_id: int, snapshot_seq: int) -> Tuple[bool, str]:
        """
        Execute a sell trade (close open position).
        
        Args:
            ltp: Last traded price
            snapshot_id: Snapshot ID
            snapshot_seq: Snapshot sequence number
            
        Returns:
            Tuple of (success, message)
        """
        position = self.get_open_position()
        if not position:
            return False, "Cannot sell: No open position"
        
        # Calculate proceeds
        proceeds = ltp * LOT_SIZE
        balance = self.get_balance()
        new_balance = balance + proceeds
        
        # Calculate P&L
        entry_cost = position["entry_cost"]
        pnl = proceeds - entry_cost
        pnl_pct = (pnl / entry_cost) * 100 if entry_cost > 0 else 0
        
        # Update position
        position["exit_price"] = ltp
        position["exit_proceeds"] = proceeds
        position["pnl"] = pnl
        position["pnl_pct"] = pnl_pct
        position["exit_time"] = datetime.now().isoformat()
        position["status"] = "closed"
        position["exit_snapshot_id"] = snapshot_id
        position["exit_snapshot_seq"] = snapshot_seq
        
        # Update portfolio
        self.portfolio["balance"] = new_balance
        
        # Add to trade history
        trade = {
            "action": "SELL",
            "signal_type": position["type"],
            "expiry": position["expiry"],
            "strike": position["strike"],
            "entry_price": position["entry_price"],
            "exit_price": ltp,
            "proceeds": proceeds,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "balance_before": balance,
            "balance_after": new_balance,
            "snapshot_id": snapshot_id,
            "snapshot_seq": snapshot_seq,
            "timestamp": datetime.now().isoformat()
        }
        self.portfolio["trade_history"].append(trade)
        
        self._save_portfolio()
        
        logger.info(f"SELL executed: {position['type']} {position['expiry']} {position['strike']} @ {ltp:.2f} = {proceeds:.2f}. P&L: {pnl:.2f} ({pnl_pct:.2f}%). Balance: {balance:.2f} -> {new_balance:.2f}")
        return True, f"Sold {position['type']} {position['expiry']} {position['strike']} @ {ltp:.2f} for {proceeds:.2f}. P&L: {pnl:.2f} ({pnl_pct:.2f}%). New balance: {new_balance:.2f}"
    
    def get_portfolio_summary(self, current_ltp: Optional[float] = None) -> Dict:
        """
        Get portfolio summary including total portfolio value.
        
        Args:
            current_ltp: Current last traded price for open position (if any)
            
        Returns:
            Dictionary with portfolio summary including total value
        """
        open_position = self.get_open_position()
        total_trades = len(self.portfolio.get("trade_history", []))
        closed_positions = [p for p in self.portfolio.get("positions", []) if p.get("status") == "closed"]
        total_pnl = sum(p.get("pnl", 0) for p in closed_positions)
        
        cash = self.get_balance()
        position_value = self.get_position_value(current_ltp)
        total_value = self.get_total_portfolio_value(current_ltp)
        
        # Calculate unrealized P&L if position is open
        unrealized_pnl = 0.0
        unrealized_pnl_pct = 0.0
        if open_position and current_ltp:
            entry_price = open_position.get("entry_price", 0)
            quantity = open_position.get("quantity", LOT_SIZE)
            unrealized_pnl = (current_ltp - entry_price) * quantity
            entry_cost = entry_price * quantity
            unrealized_pnl_pct = (unrealized_pnl / entry_cost) * 100 if entry_cost > 0 else 0
        
        return {
            "cash": cash,
            "position_value": position_value,
            "total_value": total_value,
            "balance": cash,  # Keep for backward compatibility
            "initial_balance": self.initial_balance,
            "total_pnl": total_pnl,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "total_trades": total_trades,
            "open_position": open_position,
            "closed_positions_count": len(closed_positions)
        }

