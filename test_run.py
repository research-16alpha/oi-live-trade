"""
Test script to verify database connection and query execution.
Run this before starting the full automation to ensure everything works.
"""

import sys
import os
from automate_oi_monitor import OptionChainMonitor
from config import get_connection_config, get_db_type

def test_connection(connection_config: dict):
    """Test database connection."""
    print("=" * 60)
    print("TEST 1: Database Connection")
    print("=" * 60)
    try:
        db_type = connection_config['type']
        if db_type == 'mysql':
            import pymysql
            conn = pymysql.connect(
                host=connection_config['host'],
                port=connection_config['port'],
                user=connection_config['user'],
                password=connection_config['password'],
                database=connection_config['database'],
                connect_timeout=connection_config['connect_timeout']
            )
        else:  # SQL Server
            import pyodbc
            from config import get_connection_string
            conn = pyodbc.connect(get_connection_string())
        print("✓ Database connection successful!")
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def test_latest_snapshot(monitor: OptionChainMonitor):
    """Test fetching latest snapshot ID."""
    print("\n" + "=" * 60)
    print("TEST 2: Fetch Latest Snapshot ID")
    print("=" * 60)
    try:
        snapshot_id = monitor.get_latest_snapshot_id()
        if snapshot_id:
            print(f"✓ Latest snapshot ID: {snapshot_id}")
            return snapshot_id
        else:
            print("✗ No snapshots found in database")
            return None
    except Exception as e:
        print(f"✗ Error fetching latest snapshot: {e}")
        return None

def test_snapshot_ids(monitor: OptionChainMonitor):
    """Test fetching multiple snapshot IDs."""
    print("\n" + "=" * 60)
    print("TEST 3: Fetch Last 3 Snapshot IDs")
    print("=" * 60)
    try:
        snapshot_ids = monitor.get_snapshot_ids(limit=3)
        if snapshot_ids:
            print(f"✓ Found {len(snapshot_ids)} snapshot(s): {snapshot_ids}")
            return snapshot_ids
        else:
            print("✗ No snapshots found")
            return []
    except Exception as e:
        print(f"✗ Error fetching snapshot IDs: {e}")
        return []

def test_query_execution(monitor: OptionChainMonitor, snapshot_id: int):
    """Test executing the main query."""
    print("\n" + "=" * 60)
    print(f"TEST 4: Execute Query for Snapshot {snapshot_id}")
    print("=" * 60)
    try:
        results = monitor.execute_query_for_snapshot(snapshot_id)
        if results:
            print(f"✓ Query executed successfully!")
            print(f"  Rows returned: {len(results)}")
            print(f"\n  Sample data (first row):")
            if results:
                first_row = results[0]
                for key, value in list(first_row.items())[:5]:  # Show first 5 columns
                    print(f"    {key}: {value}")
                if len(first_row) > 5:
                    print(f"    ... and {len(first_row) - 5} more columns")
            return True
        else:
            print(f"✗ Query returned no results for snapshot {snapshot_id}")
            return False
    except Exception as e:
        print(f"✗ Error executing query: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_save_results(monitor: OptionChainMonitor, snapshot_id: int):
    """Test saving results to CSV."""
    print("\n" + "=" * 60)
    print(f"TEST 5: Save Results to CSV for Snapshot {snapshot_id}")
    print("=" * 60)
    try:
        results = monitor.execute_query_for_snapshot(snapshot_id)
        if results:
            monitor.save_results(results, snapshot_id)
            print(f"✓ Results saved successfully!")
            return True
        else:
            print(f"✗ No results to save")
            return False
    except Exception as e:
        print(f"✗ Error saving results: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_save_results_last_three(monitor: OptionChainMonitor, snapshot_ids: list):
    """Fetch and save the last N snapshots into a single CSV."""
    print("\n" + "=" * 60)
    print(f"TEST 5B: Save Combined Results for Snapshots {snapshot_ids}")
    print("=" * 60)
    if not snapshot_ids:
        print("✗ No snapshot IDs to process")
        return False
    try:
        results = monitor.execute_query_for_snapshots(snapshot_ids)
        if results:
            # use most recent snapshot id for filename reference
            monitor.save_results(results, snapshot_ids[0])
            print(f"✓ Combined results saved successfully!")
            return True
        else:
            print(f"✗ No results to save")
            return False
    except Exception as e:
        print(f"✗ Error saving combined results: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("OPTION CHAIN MONITOR - TEST RUN")
    print("=" * 60)
    print("\nThis script will test your database connection and query execution.")
    print("Make sure you have set your database credentials in environment variables")
    print("or in config.py before running this test.\n")
    
    # Get configuration
    try:
        connection_config = get_connection_config()
        db_type = get_db_type()
        ticker = os.getenv('TICKER', 'NIFTY')
        print(f"Database Type: {db_type.upper()}")
        print(f"Ticker: {ticker}")
        print(f"Server: {connection_config['host']}")
        print(f"Database: {connection_config['database']}")
        print(f"User: {connection_config['user']}")
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        print("\nPlease set the following environment variables:")
        print("  - DB_TYPE (optional: 'mysql' or 'sqlserver', default: 'mysql')")
        print("  - DB_SERVER")
        print("  - DB_DATABASE")
        print("  - DB_USER")
        print("  - DB_PASSWORD")
        print("  - DB_PORT (optional: 3306 for MySQL, 1433 for SQL Server)")
        sys.exit(1)
    
    # Run tests
    results = {
        'connection': False,
        'latest_snapshot': False,
        'snapshot_ids': False,
        'query': False,
        'save': False
    }
    
    # Test 1: Connection
    if not test_connection(connection_config):
        print("\n" + "=" * 60)
        print("TEST FAILED: Cannot proceed without database connection")
        print("=" * 60)
        sys.exit(1)
    results['connection'] = True
    
    # Create monitor instance
    monitor = OptionChainMonitor(connection_config, ticker=ticker)
    
    # Test 2: Latest snapshot
    latest_snapshot = test_latest_snapshot(monitor)
    if latest_snapshot:
        results['latest_snapshot'] = True
    else:
        print("\n" + "=" * 60)
        print("WARNING: No snapshots found. Some tests will be skipped.")
        print("=" * 60)
        print("\nAll tests completed (with warnings).")
        sys.exit(0)
    
    # Test 3: Multiple snapshots
    snapshot_ids = test_snapshot_ids(monitor)
    if snapshot_ids:
        results['snapshot_ids'] = True
    
    # Test 4: Query execution (use latest snapshot)
    if latest_snapshot:
        if test_query_execution(monitor, latest_snapshot):
            results['query'] = True
    
    # Test 5A: Save latest snapshot only
    if latest_snapshot:
        if test_save_results(monitor, latest_snapshot):
            results['save'] = True

    # Test 5B: Save combined last 3 snapshots (if available)
    combined_saved = False
    if snapshot_ids:
        combined_saved = test_save_results_last_three(monitor, snapshot_ids)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Database Connection:     {'✓ PASS' if results['connection'] else '✗ FAIL'}")
    print(f"Latest Snapshot:         {'✓ PASS' if results['latest_snapshot'] else '✗ FAIL'}")
    print(f"Multiple Snapshots:      {'✓ PASS' if results['snapshot_ids'] else '✗ FAIL'}")
    print(f"Query Execution:         {'✓ PASS' if results['query'] else '✗ FAIL'}")
    print(f"Save to CSV:             {'✓ PASS' if results['save'] else '✗ FAIL'}")
    
    all_passed = all(results.values())
    if all_passed:
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nYou can now run the full automation with:")
        print("  python automate_oi_monitor.py")
    else:
        print("\n" + "=" * 60)
        print("✗ SOME TESTS FAILED")
        print("=" * 60)
        print("\nPlease fix the issues above before running the full automation.")
        sys.exit(1)

if __name__ == '__main__':
    main()

