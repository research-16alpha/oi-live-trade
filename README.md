# Automated Option Chain Trading System

Automated system that monitors option chain data, generates trading signals, executes trades in a mock portfolio, and displays results on Streamlit.

## Core Features

1. **Database Monitoring**: Extracts option chain data from MySQL/SQL Server using provided credentials
2. **Signal Generation**: Analyzes data to generate buy/sell signals based on technical patterns
3. **Mock Portfolio**: Executes trades and manages portfolio balance automatically
4. **Real-time Updates**: Updates portfolio status every minute and syncs to GitHub
5. **Streamlit Dashboard**: Live portfolio visualization at `portfolio_dashboard.py`

## Setup

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Database

Edit `credentials.sh` (Linux/Mac) or `credentials.bat` (Windows) with your database details:

```bash
export DB_TYPE="mysql"              # or "sqlserver"
export DB_SERVER="your_server"
export DB_DATABASE="your_database"
export DB_USER="your_username"
export DB_PASSWORD="your_password"
export DB_PORT="3306"                # 3306 for MySQL, 1433 for SQL Server
export TICKER="NIFTY"                # Ticker to monitor
```

Then source it:
```bash
source credentials.sh  # On Windows: credentials.bat
```

### 3. Test Connection

```bash
# Make sure credentials are loaded
source credentials.sh  # On Windows: credentials.bat

# Run connection test
python test_connection.py
```

This will test:
- Database connection
- Latest snapshot retrieval
- SQL query execution
- Data retrieval

### 4. Run the Monitor

```bash
python automate_oi_monitor.py
```

The monitor will:
- Run during trading hours (9:15 AM - 3:29 PM IST, Monday-Friday)
- Check for new snapshots every 60 seconds
- Update portfolio every minute (even without new snapshots)
- Auto-sync portfolio.json to GitHub for Streamlit dashboard

### 5. View Dashboard

Run Streamlit dashboard locally:
```bash
streamlit run portfolio_dashboard.py
```

Or deploy to Streamlit Cloud (portfolio.json is auto-synced to GitHub).

## File Structure

- `automate_oi_monitor.py` - Main monitoring and trading system
- `config.py` - Database connection configuration
- `generate_signal.py` - Signal generation logic
- `portfolio_manager.py` - Portfolio management and trade execution
- `portfolio_dashboard.py` - Streamlit dashboard
- `credentials.sh` / `credentials.bat` - Database credentials (not in git)
- `portfolio.json` - Portfolio state (synced to GitHub for Streamlit)

## How It Works

1. **Data Extraction**: Queries `optionchain_combined` table for latest snapshots
2. **Signal Generation**: Analyzes last 3 snapshots for buy/sell patterns
3. **Trade Execution**: Executes trades in mock portfolio (150 contracts per trade)
4. **Portfolio Updates**: Updates portfolio value every minute and pushes to GitHub
5. **Dashboard Display**: Streamlit reads portfolio.json from GitHub and displays live data

## Trading Rules

- **Buy Signals**: Triggered by price and OI increases over 3 snapshots
- **Sell Signals**: Stop loss (50%) or price/OI falling after minimum hold (7 snapshots)
- **Cooldown**: 20 snapshots between buy signals
- **Position Limit**: Only one open position at a time

## Requirements

- Python 3.7+
- MySQL or SQL Server database
- Git (for auto-syncing portfolio.json)

