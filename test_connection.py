"""
Simple connection test script to diagnose database connection issues.
"""

import os
from config import get_connection_config, get_db_type

def test_connection():
    """Test database connection with detailed error messages."""
    print("=" * 60)
    print("DATABASE CONNECTION TEST")
    print("=" * 60)
    
    # Show configuration
    print("\nConfiguration:")
    print(f"  DB_SERVER: {os.getenv('DB_SERVER', 'Not set')}")
    print(f"  DB_DATABASE: {os.getenv('DB_DATABASE', 'Not set')}")
    print(f"  DB_USER: {os.getenv('DB_USER', 'Not set')}")
    print(f"  DB_PORT: {os.getenv('DB_PORT', 'Not set (will use 1433)')}")
    
    # Get connection config
    try:
        config = get_connection_config()
        db_type = get_db_type()
        print(f"\nDatabase Type: {db_type.upper()}")
        print(f"Host: {config['host']}")
        print(f"Port: {config['port']}")
        print(f"Database: {config['database']}")
        print(f"User: {config['user']}")
    except Exception as e:
        print(f"\n✗ Error building connection config: {e}")
        return False
    
    # Test connection
    print("\n" + "=" * 60)
    print("Attempting connection...")
    print("=" * 60)
    
    try:
        if db_type == 'mysql':
            import pymysql
            conn = pymysql.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['database'],
                connect_timeout=10
            )
            print("✓ Connection successful!")
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            print(f"\n✓ Server version: {version[:100]}...")
        else:  # SQL Server
            import pyodbc
            from config import get_connection_string
            conn_str = get_connection_string()
            conn = pyodbc.connect(conn_str, timeout=10)
            print("✓ Connection successful!")
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            print(f"\n✓ Server version: {version[:100]}...")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n✗ Connection failed!")
        print(f"\nError details:")
        if hasattr(e, 'args') and len(e.args) > 1:
            print(f"  Error code: {e.args[0]}")
            print(f"  Error message: {e.args[1]}")
        else:
            print(f"  Error: {e}")
        
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            print("\n⚠ Timeout error - Possible causes:")
            print("  1. Server address/port is incorrect")
            print("  2. Firewall blocking the connection")
            print("  3. Server is not accessible from this network")
            print("  4. For Google Cloud SQL: Check if IP is whitelisted")
        elif "login" in str(e).lower() or "authentication" in str(e).lower():
            print("\n⚠ Authentication error - Check:")
            print("  1. Username is correct")
            print("  2. Password is correct")
            print("  3. User has proper permissions")
        elif "server" in str(e).lower() or "network" in str(e).lower():
            print("\n⚠ Server/Network error - Check:")
            print("  1. Server name/IP is correct")
            print("  2. Port number is correct (default: 1433)")
            print("  3. Server is running and accessible")
        
        return False

if __name__ == '__main__':
    import sys
    
    # Check if credentials are set
    if not os.getenv('DB_SERVER'):
        print("Error: DB_SERVER environment variable not set")
        print("\nPlease set your database credentials:")
        print("  export DB_SERVER='your_server'")
        print("  export DB_DATABASE='your_database'")
        print("  export DB_USER='your_username'")
        print("  export DB_PASSWORD='your_password'")
        sys.exit(1)
    
    success = test_connection()
    sys.exit(0 if success else 1)

