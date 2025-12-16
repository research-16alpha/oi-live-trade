"""
Test database connection and query execution.
Run this to verify your database credentials and connection are working correctly.
"""

import sys
import logging
from config import get_connection_config
from automate_oi_monitor import OptionChainMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_connection():
    """Test database connection."""
    logger.info("=" * 60)
    logger.info("Testing Database Connection")
    logger.info("=" * 60)
    
    try:
        # Get connection config
        connection_config = get_connection_config()
        logger.info(f"Database Type: {connection_config['type']}")
        logger.info(f"Host: {connection_config['host']}")
        logger.info(f"Database: {connection_config['database']}")
        logger.info(f"User: {connection_config['user']}")
        
        # Create monitor instance
        monitor = OptionChainMonitor(connection_config, ticker='NIFTY')
        
        # Test connection
        logger.info("\n1. Testing database connection...")
        conn = monitor.get_connection()
        logger.info("✓ Connection successful!")
        conn.close()
        
        # Test getting latest snapshot ID
        logger.info("\n2. Testing latest snapshot ID retrieval...")
        latest_snapshot_id = monitor.get_latest_snapshot_id()
        if latest_snapshot_id:
            logger.info(f"✓ Latest snapshot ID: {latest_snapshot_id}")
        else:
            logger.warning("⚠ No snapshots found in database")
            return False
        
        # Test getting last 3 snapshot IDs
        logger.info("\n3. Testing last 3 snapshot IDs retrieval...")
        snapshot_ids = monitor.get_snapshot_ids(limit=3)
        if snapshot_ids:
            logger.info(f"✓ Last 3 snapshot IDs: {snapshot_ids}")
        else:
            logger.warning("⚠ No snapshot IDs retrieved")
            return False
        
        # Test executing the main query
        logger.info("\n4. Testing main SQL query execution...")
        logger.info("   (This may take a few seconds...)")
        results = monitor.execute_query_for_snapshots(snapshot_ids)
        
        if results:
            logger.info(f"✓ Query executed successfully!")
            logger.info(f"✓ Retrieved {len(results)} rows")
            
            # Show sample data
            if len(results) > 0:
                logger.info("\n5. Sample data (first row):")
                sample = results[0]
                for key, value in list(sample.items())[:5]:  # Show first 5 columns
                    logger.info(f"   {key}: {value}")
                logger.info(f"   ... ({len(sample)} total columns)")
        else:
            logger.warning("⚠ Query executed but returned no results")
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ All tests passed! Database connection is working correctly.")
        logger.info("=" * 60)
        return True
        
    except ImportError as e:
        logger.error(f"✗ Import error: {e}")
        logger.error("Make sure you have activated your virtual environment:")
        logger.error("  source venv/bin/activate  # Linux/Mac")
        logger.error("  venv\\Scripts\\activate     # Windows")
        return False
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.error("\nTroubleshooting:")
        logger.error("1. Check your credentials in credentials.sh or credentials.bat")
        logger.error("2. Make sure you've sourced the credentials: source credentials.sh")
        logger.error("3. Verify database server is accessible")
        logger.error("4. Check database user has SELECT privileges")
        return False


def main():
    """Main entry point."""
    success = test_connection()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

