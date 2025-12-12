#!/bin/bash

# Database credentials for Option Chain Monitor
# Source this file to set environment variables: source credentials.sh

# Set database type: 'mysql' or 'sqlserver'
export DB_TYPE="mysql"

export DB_SERVER="34.93.144.87"
export DB_DATABASE="optionchaindata"
export DB_USER="lakshay"
export DB_PASSWORD="16Alpha!"
export DB_PORT="3306"  # 3306 for MySQL, 1433 for SQL Server

echo "Database credentials loaded!"
echo "Database Type: $DB_TYPE"
echo "Server: $DB_SERVER"
echo "Port: $DB_PORT"
echo "Database: $DB_DATABASE"
echo "User: $DB_USER"

