#!/bin/bash

# Database credentials for Option Chain Monitor
# Source this file to set environment variables: source credentials.sh

# Set database type: 'mysql' or 'sqlserver'
export DB_TYPE="mysql"

export DB_SERVER="192.168.1.164"
export DB_DATABASE="optionchaindb"
export DB_USER="gautam"
export DB_PASSWORD="Gautam1306"
export DB_PORT="3306"  # 3306 for MySQL, 1433 for SQL Server

echo "Database credentials loaded!"
echo "Database Type: $DB_TYPE"
echo "Server: $DB_SERVER"
echo "Port: $DB_PORT"
echo "Database: $DB_DATABASE"
echo "User: $DB_USER"

