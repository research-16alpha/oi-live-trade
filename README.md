# Option Chain Monitor - Automated SQL Query Runner

Automatically monitors your MySQL or SQL Server database for new option chain snapshots and extracts data when changes are detected.

## Features

- **Automated Monitoring**: Checks for new snapshots every minute (configurable)
- **Change Detection**: Only processes data when new snapshots are detected
- **Batch Processing**: Retrieves and saves the last 3 snapshots when a change is detected
- **CSV Export**: Automatically saves query results to CSV files
- **Logging**: Comprehensive logging to both file and console
- **Multi-Database Support**: Works with both MySQL and SQL Server

## Prerequisites

1. **Python 3.7+**
2. **MySQL or SQL Server** with the following tables:
   - `optionchain`
   - `optionchain_snapshots`
3. **Database Drivers**:
   - MySQL: `pymysql` (installed automatically)
   - SQL Server: ODBC Driver (install separately)

## Quick Start

### 1. Setup

```bash
# Create virtual environment and install dependencies
./setup.sh

# Or manually:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Database

**Option A: Use credentials.sh (Recommended)**
```bash
# Edit credentials.sh with your database details, then:
source credentials.sh
```

**Option B: Set environment variables**
```bash
export DB_TYPE="mysql"              # or "sqlserver"
export DB_SERVER="your_server"
export DB_DATABASE="your_database"
export DB_USER="your_username"
export DB_PASSWORD="your_password"
export DB_PORT="3306"                # 3306 for MySQL, 1433 for SQL Server
```

### 3. Test Connection

```bash
source venv/bin/activate
python test_connection.py
```

### 4. Run Full Test

```bash
source venv/bin/activate
python test_run.py
```

### 5. Start Monitoring

```bash
# Using helper script (loads credentials automatically)
./run_monitor.sh

# Or manually:
source credentials.sh
source venv/bin/activate
python automate_oi_monitor.py
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_TYPE` | Database type: `mysql` or `sqlserver` | `mysql` |
| `DB_SERVER` | Database hostname or IP | - |
| `DB_DATABASE` | Database name | - |
| `DB_USER` | Database username | - |
| `DB_PASSWORD` | Database password | - |
| `DB_PORT` | Port number | `3306` (MySQL) or `1433` (SQL Server) |
| `TICKER` | Ticker symbol to monitor | `NIFTY50` |
| `CHECK_INTERVAL` | Seconds between checks | `60` |

## Usage

### Helper Scripts

```bash
./run_test.sh      # Test connection and query
./run_monitor.sh   # Start monitoring
```

### Direct Execution

```bash
source venv/bin/activate
python test_run.py           # Test connection and query
python automate_oi_monitor.py  # Start monitoring
```

## Output

- **CSV Files**: Saved in `output/` directory
  - Format: `snapshot_{SNAPSHOT_ID}_{TIMESTAMP}.csv`
- **Log File**: `oi_monitor.log` contains all monitoring activity

## How It Works

1. Checks the latest snapshot ID every minute
2. When a new snapshot is detected, fetches the last 3 snapshots
3. Executes the SQL query for each snapshot
4. Saves results to CSV files
5. Continues monitoring indefinitely

Press `Ctrl+C` to stop monitoring.

## Troubleshooting

### Connection Issues

- **MySQL**: Verify `pymysql` is installed (`pip install pymysql`)
- **SQL Server**: Verify ODBC driver is installed
- Check firewall settings and IP whitelisting (for cloud databases)
- Verify credentials are correct

### No Snapshots Found

- Verify the `optionchain_snapshots` table has data
- Check that the `TICKER` value matches your data
- Ensure `SNAPSHOT_ID > 0` condition is met

### Permission Issues

- Ensure the database user has SELECT permissions on:
  - `optionchain` table
  - `optionchain_snapshots` table

## Files

- `automate_oi_monitor.py` - Main monitoring script
- `config.py` - Database configuration
- `test_connection.py` - Connection test utility
- `test_run.py` - Full test suite
- `credentials.sh` - Database credentials (edit this)
- `setup.sh` - Initial setup script
- `run_monitor.sh` / `run_test.sh` - Helper scripts

## License

This script is provided as-is for automation purposes.
