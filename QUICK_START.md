# Quick Start Guide - Automated Trading System

## One-Time Setup

### 1. Install Dependencies
```bash
./setup.sh
```

### 2. Configure Database
Edit `credentials.sh` with your database details, or set environment variables.

### 3. Test Connection
```bash
./run_test.sh
```

### 4. Install Auto-Start Scheduler (Recommended)
```bash
./setup_scheduler.sh
```

That's it! The system will now:
- ✅ Auto-start at 9:15 AM IST on weekdays
- ✅ Auto-stop at 3:30 PM IST
- ✅ Skip weekends automatically
- ✅ Generate signals and execute trades
- ✅ Manage portfolio automatically

## Daily Operations

The system runs automatically. You can:

**Check Status:**
```bash
./check_status.sh
```

**View Logs:**
```bash
tail -f oi_monitor.log
```

**Manual Control (if needed):**
```bash
./start_monitor.sh    # Start now
./stop_monitor.sh     # Stop running monitor
```

## Trading Schedule

- **Monday-Friday**: 9:15 AM - 3:29 PM IST
- **Weekends**: No trading
- **Auto-Stop**: 3:30 PM IST

## Portfolio Management

- **Portfolio File**: `portfolio.json`
- **Check Balance**: Portfolio value logged every minute
- **Trade History**: Stored in `portfolio.json`
- **Positions**: Carried forward to next day if open at market close

## Important Notes

1. **System Timezone**: The scheduler uses your system timezone, but the Python script checks IST internally
2. **Position Carry-Forward**: Open positions at 3:29 PM are NOT force-sold, they carry to next day
3. **Exit Conditions**: Stop loss (50%) and sell signals apply even across days
4. **Cooldown**: 20 snapshots between trades (from buy snapshot, not sell)

## Troubleshooting

**Monitor not starting?**
```bash
./check_status.sh
launchctl list | grep oi.monitor
```

**Check logs:**
```bash
tail -50 oi_monitor.log
tail -50 monitor_error.log
```

**Restart scheduler:**
```bash
./uninstall_scheduler.sh
./setup_scheduler.sh
```

