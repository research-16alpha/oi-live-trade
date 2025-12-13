# Option Chain Monitor - Automated SQL Query Runner

Automatically monitors your MySQL or SQL Server database for new option chain snapshots and extracts data when changes are detected.

## Features

- **Automated Monitoring**: Checks for new snapshots every minute (configurable)
- **Scheduled Trading Hours**: Auto-starts at 9:15 AM IST, stops at 3:30 PM IST (Monday-Friday)
- **Weekend Detection**: Automatically skips trading on weekends
- **Change Detection**: Only processes data when new snapshots are detected
- **Batch Processing**: Retrieves and saves the last 3 snapshots when a change is detected
- **Signal Generation**: Automatic buy/sell signal generation with portfolio management
- **CSV Export**: Automatically saves query results to CSV files
- **Logging**: Comprehensive logging to both file and console
- **Multi-Database Support**: Works with both MySQL and SQL Server
- **Position Carry-Forward**: Open positions are carried to next trading day (no forced sells)

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

**Option A: Manual Start (for testing)**
```bash
# Using helper script (loads credentials automatically)
./run_monitor.sh

# Or manually:
source credentials.sh
source venv/bin/activate
python automate_oi_monitor.py
```

**Option B: Auto-Start on Weekdays (Recommended)**
```bash
# Install the scheduler to auto-start at 9:15 AM IST on weekdays
./setup_scheduler.sh

# The monitor will now:
# - Auto-start at 9:15 AM IST (Monday-Friday)
# - Auto-stop at 3:30 PM IST (after 3:29 PM trading ends)
# - Skip weekends automatically
```

**Control Commands:**
```bash
./start_monitor.sh    # Start manually
./stop_monitor.sh     # Stop manually
./check_status.sh     # Check if running
./uninstall_scheduler.sh  # Remove auto-start
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

## Auto-Start Scheduler Setup (macOS)

To automatically start monitoring at 9:15 AM IST on weekdays:

```bash
# Install the scheduler
./setup_scheduler.sh

# This will:
# - Install Launch Agent to auto-start at 9:15 AM (Monday-Friday)
# - Monitor will stop automatically at 3:30 PM IST
# - Skip weekends automatically
```

**Verify Installation:**
```bash
# Check if scheduler is installed
launchctl list | grep oi.monitor

# Check monitor status
./check_status.sh
```

**Manual Control:**
```bash
./start_monitor.sh    # Start now (even outside trading hours)
./stop_monitor.sh     # Stop running monitor
./check_status.sh     # Check if running and view logs
```

**Uninstall Scheduler:**
```bash
./uninstall_scheduler.sh
```

**Note**: The scheduler uses your system's timezone. The Python script checks IST time internally, so it will only trade during 9:15 AM - 3:29 PM IST regardless of your system timezone.

## Output

- **CSV Files**: Saved in `output/` directory
  - Format: `snapshot_{SNAPSHOT_ID}_{TIMESTAMP}.csv`
- **Log File**: `oi_monitor.log` contains all monitoring activity
- **Portfolio File**: `portfolio.json` contains portfolio state and trade history

## How It Works

### Trading Schedule
- **Trading Hours**: 9:15 AM - 3:29 PM IST (Monday-Friday)
- **Auto-Start**: 9:15 AM IST on weekdays (if scheduler installed)
- **Auto-Stop**: 3:30 PM IST (after 3:29 PM trading ends)
- **Weekends**: No trading (monitor exits if started)

### Monitoring Process
1. Checks the latest snapshot ID every minute
2. When a new snapshot is detected, fetches the last 3 snapshots
3. Executes the SQL query for each snapshot
4. Saves results to CSV files
5. Generates buy/sell signals based on strategy
6. Executes trades via portfolio manager
7. Stops automatically at 3:30 PM IST

### Position Management
- **Buy Signals**: Executed when criteria met (no open position required)
- **Sell Signals**: Executed after minimum hold (7 snapshots) when exit conditions met
- **Stop Loss**: 50% loss triggers sell (after minimum hold)
- **Position Carry-Forward**: Open positions at market close are carried to next trading day
- **Cooldown**: 20 snapshots between trades (calculated from buy snapshot)

Press `Ctrl+C` to stop monitoring manually.

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

### Core Scripts
- `automate_oi_monitor.py` - Main monitoring script with trading hours
- `generate_signal.py` - Signal generation and evaluation
- `portfolio_manager.py` - Portfolio and trade management
- `config.py` - Database configuration
- `test_connection.py` - Connection test utility
- `test_run.py` - Full test suite

### Setup & Control
- `credentials.sh` - Database credentials (edit this)
- `setup.sh` - Initial setup script
- `run_monitor.sh` - Start monitoring script
- `run_test.sh` - Test script

### Scheduler (Auto-Start)
- `com.oi.monitor.plist` - Launch Agent configuration
- `setup_scheduler.sh` - Install auto-start scheduler
- `start_monitor.sh` - Manual start script
- `stop_monitor.sh` - Manual stop script
- `check_status.sh` - Check monitor status
- `uninstall_scheduler.sh` - Remove auto-start

## License

This script is provided as-is for automation purposes.
