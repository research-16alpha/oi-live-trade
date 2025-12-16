"""
Test script to verify timed snapshot collection behavior.

This script simulates the new retrieval process:
1. Detect new snapshot
2. Wait 3 minutes
3. Fetch snapshot
4. Wait 3 minutes
5. Fetch snapshot
6. Wait 3 minutes
7. Fetch snapshot
8. Process all 3

Usage:
    python test_timed_collection.py [--gap 180] [--ticker NIFTY]
    
    --gap: Gap between snapshot fetches in seconds (default: 180 = 3 minutes)
    --ticker: Ticker symbol (default: NIFTY)
"""

import sys
import logging
import argparse
from config import get_connection_config
from automate_oi_monitor import OptionChainMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_timed_collection(gap_seconds: int = 180, ticker: str = 'NIFTY'):
    """
    Test the timed collection of 3 snapshots.
    
    Args:
        gap_seconds: Time to wait between fetches (default: 180 = 3 minutes)
        ticker: Ticker symbol to monitor
    """
    logger.info("=" * 70)
    logger.info("Testing Timed Snapshot Collection")
    logger.info("=" * 70)
    logger.info(f"Ticker: {ticker}")
    logger.info(f"Gap between fetches: {gap_seconds} seconds ({gap_seconds/60:.1f} minutes)")
    logger.info(f"Total collection time: ~{gap_seconds*2/60:.1f} minutes (2 waits)")
    logger.info("")
    
    try:
        connection_config = get_connection_config()
        monitor = OptionChainMonitor(connection_config, ticker=ticker)
        
        # Test connection first
        logger.info("1. Testing database connection...")
        conn = monitor.get_connection()
        logger.info("✓ Connection successful!")
        conn.close()
        
        # Get initial snapshot
        logger.info("\n2. Getting initial snapshot ID...")
        initial_snapshot = monitor.get_latest_snapshot_id()
        if initial_snapshot:
            logger.info(f"✓ Initial snapshot ID: {initial_snapshot}")
        else:
            logger.error("✗ No snapshots found in database")
            return False
        
        # Perform timed collection
        logger.info("\n3. Starting timed collection of 3 snapshots...")
        logger.info("   This will:")
        logger.info("   - Fetch snapshot 1 (now)")
        logger.info(f"   - Wait {gap_seconds}s ({gap_seconds/60:.1f} minutes)")
        logger.info("   - Fetch snapshot 2")
        logger.info(f"   - Wait {gap_seconds}s ({gap_seconds/60:.1f} minutes)")
        logger.info("   - Fetch snapshot 3")
        logger.info("")
        
        snapshot_ids = monitor.collect_three_snapshots_timed(gap_seconds=gap_seconds)
        
        if snapshot_ids and len(snapshot_ids) == 3:
            logger.info("\n" + "=" * 70)
            logger.info("✓ SUCCESS: Collected 3 snapshots!")
            logger.info("=" * 70)
            logger.info(f"Snapshot IDs: {snapshot_ids}")
            logger.info(f"  - Snapshot 1 (oldest): {snapshot_ids[2]}")
            logger.info(f"  - Snapshot 2 (middle): {snapshot_ids[1]}")
            logger.info(f"  - Snapshot 3 (newest): {snapshot_ids[0]}")
            logger.info("")
            logger.info("These snapshots are approximately 3 minutes apart.")
            logger.info("They can now be processed for signal generation.")
            return True
        else:
            logger.error("\n" + "=" * 70)
            logger.error("✗ FAILED: Could not collect 3 snapshots")
            logger.error("=" * 70)
            if snapshot_ids:
                logger.error(f"Only collected {len(snapshot_ids)} snapshots: {snapshot_ids}")
            else:
                logger.error("No snapshots collected")
            return False
            
    except ImportError as e:
        logger.error(f"✗ Import error: {e}")
        logger.error("Make sure you have activated your virtual environment:")
        logger.error("  source venv/bin/activate  # Linux/Mac")
        logger.error("  venv\\Scripts\\activate     # Windows")
        return False
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    parser = argparse.ArgumentParser(description='Test timed snapshot collection')
    parser.add_argument('--gap', type=int, default=180,
                        help='Gap between snapshot fetches in seconds (default: 180 = 3 minutes)')
    parser.add_argument('--ticker', type=str, default='NIFTY',
                        help='Ticker symbol to monitor (default: NIFTY)')
    
    args = parser.parse_args()
    
    success = test_timed_collection(gap_seconds=args.gap, ticker=args.ticker)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

