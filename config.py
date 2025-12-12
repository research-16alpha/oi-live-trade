"""
Configuration file for database connection.
Supports both SQL Server and MySQL.
"""

import os
from typing import Optional, Dict


def get_db_type() -> str:
    """
    Get database type from environment variable.
    
    Returns:
        'mysql' or 'sqlserver' (default: 'mysql' if not specified)
    """
    db_type = os.getenv('DB_TYPE', 'mysql').lower()
    return db_type if db_type in ['mysql', 'sqlserver'] else 'mysql'


def get_connection_config() -> Dict:
    """
    Get database connection configuration as a dictionary.
    Supports both MySQL and SQL Server.
    
    Environment variables:
        DB_TYPE: 'mysql' or 'sqlserver' (default: 'mysql')
        DB_SERVER: Database hostname or IP
        DB_DATABASE: Database name
        DB_USER: Database username
        DB_PASSWORD: Database password
        DB_PORT: Port number (default: 3306 for MySQL, 1433 for SQL Server)
        DB_DRIVER: ODBC driver for SQL Server (default: 'ODBC Driver 17 for SQL Server')
        DB_TIMEOUT: Connection timeout in seconds (default: 30)
    
    Returns:
        Dictionary with connection parameters
    """
    db_type = get_db_type()
    
    config = {
        'type': db_type,
        'host': os.getenv('DB_SERVER', '34.93.144.87'),
        'database': os.getenv('DB_DATABASE', 'optionchaindata'),
        'user': os.getenv('DB_USER', 'lakshay'),
        'password': os.getenv('DB_PASSWORD', '16Alpha!'),
    }
    
    if db_type == 'mysql':
        config['port'] = int(os.getenv('DB_PORT', '3306'))
        config['connect_timeout'] = int(os.getenv('DB_TIMEOUT', '30'))
    else:  # SQL Server
        config['port'] = os.getenv('DB_PORT', '1433')
        config['driver'] = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        config['timeout'] = os.getenv('DB_TIMEOUT', '30')
    
    return config


def get_connection_string() -> str:
    """
    Get SQL Server connection string from environment variables.
    For MySQL, use get_connection_config() instead.
    
    Returns:
        Connection string for pyodbc (SQL Server only)
    """
    config = get_connection_config()
    
    if config['type'] != 'sqlserver':
        raise ValueError("get_connection_string() is for SQL Server only. Use get_connection_config() for MySQL.")
    
    server = config['host']
    port = config['port']
    
    # Format server:port for SQL Server
    if ':' not in server and ',' not in server:
        server = f"{server},{port}"
    
    # Build connection string
    connection_string = (
        f'DRIVER={{{config["driver"]}}};'
        f'SERVER={server};'
        f'DATABASE={config["database"]};'
        f'UID={config["user"]};'
        f'PWD={config["password"]};'
        f'Connection Timeout={config["timeout"]};'
        'TrustServerCertificate=yes;'
    )
    
    # For Google Cloud SQL, might need encryption
    if 'google' in server.lower() or 'cloud' in server.lower():
        connection_string += 'Encrypt=yes;'
    
    return connection_string


# Alternative: If you prefer to hardcode credentials (NOT RECOMMENDED for production)
# Uncomment and modify the following:
"""
def get_connection_string() -> str:
    server = 'your_server_name'
    database = 'your_database_name'
    username = 'your_username'
    password = 'your_password'
    driver = 'ODBC Driver 17 for SQL Server'
    
    connection_string = (
        f'DRIVER={{{driver}}};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password};'
        'TrustServerCertificate=yes;'
    )
    
    return connection_string
"""

