"""
Portfolio Manager for Mock Trading
Tracks portfolio balance and executes buy/sell trades.
"""

import json
import logging
import os
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
    
    def _convert_numpy_types(self, obj):
        """Recursively convert numpy types to Python native types for JSON serialization."""
        import numpy as np
        
        if isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        else:
            return obj
    
    def _load_portfolio(self) -> Dict:
        """Load portfolio from file or create new one."""
        if self.portfolio_file.exists():
            try:
                with open(self.portfolio_file, 'r') as f:
                    portfolio = json.load(f)
                
                # Validate portfolio structure
                if not isinstance(portfolio, dict):
                    raise ValueError("Portfolio file is not a valid JSON object")
                
                # Ensure required fields exist
                if "balance" not in portfolio:
                    raise ValueError("Portfolio missing 'balance' field")
                if "positions" not in portfolio:
                    portfolio["positions"] = []
                if "trade_history" not in portfolio:
                    portfolio["trade_history"] = []
                if "last_buy_snapshot_seq" not in portfolio:
                    portfolio["last_buy_snapshot_seq"] = -9999
                
                logger.info(f"Loaded portfolio: Balance = {portfolio.get('balance', 0):.2f}, "
                          f"Positions = {len(portfolio.get('positions', []))}, "
                          f"Trades = {len(portfolio.get('trade_history', []))}")
                return portfolio
            except json.JSONDecodeError as e:
                logger.error(f"Portfolio file is corrupted (invalid JSON): {e}. Attempting backup recovery.")
                # Try to load backup if exists
                backup_file = self.portfolio_file.with_suffix('.json.bak')
                if backup_file.exists():
                    try:
                        with open(backup_file, 'r') as f:
                            portfolio = json.load(f)
                        logger.warning("Loaded portfolio from backup file")
                        return portfolio
                    except:
                        pass
                logger.warning("Creating new portfolio after corruption")
            except Exception as e:
                logger.error(f"Error loading portfolio file: {e}. Creating new portfolio.", exc_info=True)
        
        # Create new portfolio only if file doesn't exist or is corrupted
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
    
    def _save_portfolio(self, portfolio: Optional[Dict] = None) -> bool:
        """
        Save portfolio to file.
        
        Returns:
            True if save was successful, False otherwise
        """
        if portfolio is None:
            portfolio = self.portfolio
        
        # Convert numpy types to Python native types BEFORE saving
        portfolio = self._convert_numpy_types(portfolio.copy())
        
        portfolio["last_updated"] = datetime.now().isoformat()
        
        # Save to temporary file first, then rename (atomic operation)
        temp_file = self.portfolio_file.with_suffix('.json.tmp')
        try:
            # Write to temporary file
            with open(temp_file, 'w') as f:
                json.dump(portfolio, f, indent=2)
            
            # Verify the file was written correctly
            with open(temp_file, 'r') as f:
                saved_data = json.load(f)
                if abs(saved_data.get("balance", 0) - portfolio.get("balance", 0)) > 0.01:
                    raise ValueError("Portfolio data mismatch after save")
            
            # Atomic rename (works on Unix and Windows)
            temp_file.replace(self.portfolio_file)
            
            logger.info("Portfolio saved successfully")
            
            # Update in-memory portfolio with converted types
            self.portfolio = portfolio
            
            # Auto-sync to git for Streamlit Cloud (synchronous)
            self._sync_to_git()
            
            return True
        except Exception as e:
            logger.error(f"Error saving portfolio: {e}", exc_info=True)
            # Clean up temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            return False
    
    def _sync_to_git(self):
        """
        Automatically commit and push portfolio.json to git for Streamlit Cloud.
        Fully automated with conflict resolution - no manual intervention needed.
        """
        try:
            portfolio_file = self.portfolio_file.resolve()
            repo_dir = portfolio_file.parent
            
            # Configure git to avoid prompts and use automated strategies
            env = os.environ.copy()
            env['GIT_TERMINAL_PROMPT'] = '0'  # Disable terminal prompts
            env['GIT_ASKPASS'] = ''  # Disable credential prompts
            
            # Check if we're in a git repository
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=repo_dir,
                capture_output=True,
                timeout=5,
                env=env
            )
            if result.returncode != 0:
                logger.debug("Not in a git repository, skipping git sync")
                return
            
            # Check if portfolio.json is tracked
            result = subprocess.run(
                ['git', 'ls-files', '--error-unmatch', str(portfolio_file.name)],
                cwd=repo_dir,
                capture_output=True,
                timeout=5,
                env=env
            )
            if result.returncode != 0:
                logger.debug("portfolio.json not tracked in git, skipping sync")
                return
            
            # Check if there are changes
            result = subprocess.run(
                ['git', 'diff', '--quiet', str(portfolio_file.name)],
                cwd=repo_dir,
                capture_output=True,
                timeout=5,
                env=env
            )
            if result.returncode == 0:
                logger.debug("No changes to portfolio.json, skipping sync")
                return
            
            # Stage the file
            result = subprocess.run(
                ['git', 'add', str(portfolio_file.name)],
                cwd=repo_dir,
                capture_output=True,
                timeout=5,
                env=env
            )
            if result.returncode != 0:
                logger.warning(f"Failed to stage portfolio.json: {result.stderr.decode()}")
                return
            
            # Commit
            commit_message = f"Auto-update portfolio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            result = subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=repo_dir,
                capture_output=True,
                timeout=5,
                env=env
            )
            
            if result.returncode == 0:
                logger.info("Portfolio committed to git")
                
                # Fetch latest changes first
                fetch_result = subprocess.run(
                    ['git', 'fetch', 'origin', 'main'],
                    cwd=repo_dir,
                    capture_output=True,
                    timeout=30,
                    env=env
                )
                
                # Pull before pushing to sync with remote and avoid non-fast-forward errors
                # Use rebase to keep history clean
                pull_result = subprocess.run(
                    ['git', 'pull', '--rebase', '--autostash', 'origin', 'main'],
                    cwd=repo_dir,
                    capture_output=True,
                    timeout=30,
                    env=env
                )
                
                if pull_result.returncode != 0:
                    error_msg = pull_result.stderr.decode()
                    logger.warning(f"Git pull --rebase failed: {error_msg}")
                    
                    # If rebase fails due to conflicts, resolve by keeping our version
                    if "conflict" in error_msg.lower() or "CONFLICT" in error_msg:
                        logger.info("Resolving merge conflict by keeping local portfolio.json version")
                        # Abort rebase
                        subprocess.run(
                            ['git', 'rebase', '--abort'],
                            cwd=repo_dir,
                            capture_output=True,
                            timeout=10,
                            env=env
                        )
                        # Try pull with merge strategy favoring ours
                        pull_result = subprocess.run(
                            ['git', 'pull', 'origin', 'main', '--no-edit', '-X', 'ours'],
                            cwd=repo_dir,
                            capture_output=True,
                            timeout=30,
                            env=env
                        )
                        if pull_result.returncode != 0:
                            logger.warning(f"Git pull with ours strategy failed: {pull_result.stderr.decode()}")
                    else:
                        # If rebase fails for other reasons, try regular pull
                        pull_result = subprocess.run(
                            ['git', 'pull', 'origin', 'main', '--no-edit'],
                            cwd=repo_dir,
                            capture_output=True,
                            timeout=30,
                            env=env
                        )
                        if pull_result.returncode != 0:
                            logger.warning(f"Git pull failed, attempting push anyway: {pull_result.stderr.decode()}")
                
                # Push to remote (synchronous - wait for completion)
                push_result = subprocess.run(
                    ['git', 'push', 'origin', 'main'],
                    cwd=repo_dir,
                    capture_output=True,
                    timeout=30,
                    env=env
                )
                
                if push_result.returncode == 0:
                    logger.info("Portfolio pushed to GitHub successfully (Streamlit will update)")
                else:
                    error_msg = push_result.stderr.decode()
                    logger.error(f"Git push failed: {error_msg}")
                    
                    # If it's still a non-fast-forward error after pull, force pull and push
                    if "non-fast-forward" in error_msg.lower() or "rejected" in error_msg.lower():
                        logger.info("Attempting to resolve non-fast-forward error with force pull...")
                        # Reset to remote and re-apply our commit
                        subprocess.run(
                            ['git', 'reset', '--hard', 'origin/main'],
                            cwd=repo_dir,
                            capture_output=True,
                            timeout=10,
                            env=env
                        )
                        # Re-stage and commit our changes
                        subprocess.run(
                            ['git', 'add', str(portfolio_file.name)],
                            cwd=repo_dir,
                            capture_output=True,
                            timeout=5,
                            env=env
                        )
                        subprocess.run(
                            ['git', 'commit', '-m', commit_message],
                            cwd=repo_dir,
                            capture_output=True,
                            timeout=5,
                            env=env
                        )
                        # Try push again
                        push_result = subprocess.run(
                            ['git', 'push', 'origin', 'main'],
                            cwd=repo_dir,
                            capture_output=True,
                            timeout=30,
                            env=env
                        )
                        if push_result.returncode == 0:
                            logger.info("Portfolio pushed to GitHub successfully after conflict resolution (Streamlit will update)")
                        else:
                            logger.error(f"Git push failed after conflict resolution: {push_result.stderr.decode()}")
                    else:
                        # Try once more after a short delay (for other errors)
                        import time
                        time.sleep(2)
                        retry_result = subprocess.run(
                            ['git', 'push', 'origin', 'main'],
                            cwd=repo_dir,
                            capture_output=True,
                            timeout=30,
                            env=env
                        )
                        if retry_result.returncode == 0:
                            logger.info("Portfolio pushed to GitHub on retry (Streamlit will update)")
                        else:
                            logger.error(f"Git push failed on retry: {retry_result.stderr.decode()}")
            else:
                logger.debug(f"Git commit failed (may be no changes): {result.stderr.decode()}")
                
        except subprocess.TimeoutExpired:
            logger.warning("Git sync timed out, continuing without sync")
        except FileNotFoundError:
            logger.debug("Git not found, skipping auto-sync")
        except Exception as e:
            logger.warning(f"Git sync failed (non-critical): {e}")
    
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
        
        # Save portfolio and verify it succeeded
        save_success = self._save_portfolio()
        if not save_success:
            logger.error("CRITICAL: Portfolio save failed after BUY! Trade may be lost.")
            # DON'T reload portfolio - that would overwrite our changes!
            # Try saving one more time (maybe type conversion will help)
            logger.warning("Retrying save with explicit type conversion...")
            save_success = self._save_portfolio()
            if not save_success:
                logger.error("CRITICAL: Portfolio save failed on retry! Trade is NOT saved to file.")
                # Log the portfolio state for debugging
                logger.error(f"Portfolio state in memory: balance={self.portfolio.get('balance')}, positions={len(self.portfolio.get('positions', []))}")
        
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
        
        # Save portfolio and verify it succeeded
        save_success = self._save_portfolio()
        if not save_success:
            logger.error("CRITICAL: Portfolio save failed after SELL! Trade may be lost.")
            # DON'T reload portfolio - that would overwrite our changes!
            # Try saving one more time
            logger.warning("Retrying save with explicit type conversion...")
            save_success = self._save_portfolio()
            if not save_success:
                logger.error("CRITICAL: Portfolio save failed on retry! Trade is NOT saved to file.")
                logger.error(f"Portfolio state in memory: balance={self.portfolio.get('balance')}, positions={len(self.portfolio.get('positions', []))}")
        
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

