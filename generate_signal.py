"""
Generate Buy/Sell/No Signal from the latest combined snapshot CSV.

It loads the most recent file in output/, expects it to contain the last 3
snapshots (combined), runs the provided signal rules, and prints the signal.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Dict, List, Optional

import numpy as np
import pandas as pd

# ---------------------------
# Config / Default Parameters
# ---------------------------
DEFAULT_STRIKE_STEP = 50
# User-specified strategy params
DEFAULT_STOP_LOSS_PCT = 0.5
DEFAULT_MIN_HOLD_SNAPS = 7
DEFAULT_COOLDOWN = 20


# ---------------------------
# Data Preparation
# ---------------------------
def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = [
        "DOWNLOAD_DATE", "DOWNLOAD_TIME", "SNAPSHOT_ID",
        "EXPIRY", "STRIKE", "c_OI", "c_LTP", "p_OI", "p_LTP", "UNDERLYING_VALUE"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df["DOWNLOAD_DATE"] = pd.to_datetime(df["DOWNLOAD_DATE"]).dt.date
    df["DOWNLOAD_TIME"] = pd.to_datetime(df["DOWNLOAD_TIME"], format="%H:%M:%S").dt.time
    df["TIMESTAMP"] = pd.to_datetime(
        df["DOWNLOAD_DATE"].astype(str) + " " + df["DOWNLOAD_TIME"].astype(str)
    )
    # Sort by TIMESTAMP to ensure chronological order (not SNAPSHOT_ID)
    df = df.sort_values(["TIMESTAMP", "STRIKE"]).reset_index(drop=True)

    # Create snapshot sequence based on chronological order
    snap_keys = df[["DOWNLOAD_DATE", "SNAPSHOT_ID", "TIMESTAMP"]].drop_duplicates().reset_index(drop=True)
    snap_keys = snap_keys.sort_values("TIMESTAMP").reset_index(drop=True)
    snap_keys["SNAPSHOT_SEQ"] = range(len(snap_keys))
    df = df.merge(snap_keys[["DOWNLOAD_DATE", "SNAPSHOT_ID", "SNAPSHOT_SEQ"]],
                  on=["DOWNLOAD_DATE", "SNAPSHOT_ID"], how="left")

    df["STRIKE"] = df["STRIKE"].astype(float)
    df["EXPIRY"] = df["EXPIRY"].astype(str)
    df = df.set_index(["SNAPSHOT_SEQ", "EXPIRY", "STRIKE"]).sort_index()
    return df


def aggregate_to_3min_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate high-frequency snapshots into 3-minute synthetic snapshots.
    This recreates the original 3-minute interval structure your strategy was built on.
    Groups snapshots into 3-minute windows and takes the last row in each window.
    """
    required_cols = [
        "DOWNLOAD_DATE", "DOWNLOAD_TIME", "SNAPSHOT_ID",
        "EXPIRY", "STRIKE", "c_OI", "c_LTP", "p_OI", "p_LTP", "UNDERLYING_VALUE",
        "c_CHNG_IN_OI", "c_VOLUME", "p_CHNG_IN_OI", "p_VOLUME"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns for aggregation: {missing}")

    df_r = df.copy()
    df_r["DOWNLOAD_DATE"] = pd.to_datetime(df_r["DOWNLOAD_DATE"]).dt.date
    df_r["DOWNLOAD_TIME"] = pd.to_datetime(df_r["DOWNLOAD_TIME"], format="%H:%M:%S").dt.time
    df_r["TIMESTAMP"] = pd.to_datetime(
        df_r["DOWNLOAD_DATE"].astype(str) + " " + df_r["DOWNLOAD_TIME"].astype(str)
    )

    # Sort chronologically
    df_r = df_r.sort_values("TIMESTAMP").reset_index(drop=True)

    # Define 3-minute windows (180 seconds) starting from first timestamp
    t0 = df_r["TIMESTAMP"].iloc[0]
    df_r["WINDOW"] = ((df_r["TIMESTAMP"] - t0).dt.total_seconds() // 180).astype(int)

    aggregated_rows = []
    for window_id in sorted(df_r["WINDOW"].unique()):
        window_data = df_r[df_r["WINDOW"] == window_id]
        if window_data.empty:
            continue
        # Take the last timestamp in this 3-minute window
        last_row = window_data.sort_values("TIMESTAMP").iloc[-1]
        aggregated_rows.append(last_row[required_cols])

    df_agg = pd.DataFrame(aggregated_rows)
    # Reuse prepare_data to build SNAPSHOT_SEQ and index
    return prepare_data(df_agg)


# ---------------------------
# Signal Generation
# ---------------------------
def generate_signals(df: pd.DataFrame, strike_step=DEFAULT_STRIKE_STEP, cooldown=DEFAULT_COOLDOWN, debug=False):
    """
    Generate call/put buy signals over the snapshot sequence.
    Now checks all strikes in the dataframe, not just ATM±1.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    call_buy_signals, put_buy_signals = {}, {}
    df_r = df.reset_index()
    snap_list = sorted(df_r["SNAPSHOT_SEQ"].unique())
    under_by_snap = df_r.groupby("SNAPSHOT_SEQ")["UNDERLYING_VALUE"].first()
    exps_by_snap = df_r.groupby("SNAPSHOT_SEQ")["EXPIRY"].unique()
    last_call_entry_snap = -9999
    last_put_entry_snap = -9999

    if len(snap_list) < 3:
        logger.info(f"Not enough snapshots for signal generation: {len(snap_list)} < 3")
        return call_buy_signals, put_buy_signals

    logger.info(f"Generating signals across {len(snap_list)} snapshots: {snap_list}")

    for idx in range(len(snap_list) - 2):
        t0, t1, t2 = snap_list[idx], snap_list[idx + 1], snap_list[idx + 2]
        try:
            u0, u1, u2 = under_by_snap.loc[t0], under_by_snap.loc[t1], under_by_snap.loc[t2]
            underlying_increasing = (u2 > u0)  # For CALL: underlying should increase
            underlying_decreasing = (u2 < u0)  # For PUT: underlying should decrease
            logger.info(f"Snapshot sequence {t0}->{t1}->{t2}: Underlying {u0:.2f}->{u1:.2f}->{u2:.2f}, "
                       f"Increasing={underlying_increasing}, Decreasing={underlying_decreasing}")
        except KeyError:
            underlying_increasing = False
            underlying_decreasing = False
            logger.warning(f"Missing underlying data for snapshots {t0}, {t1}, or {t2}")
            continue

        for exp in exps_by_snap.loc[t0]:
            # Get all available strikes for this expiry at t0
            t0_strikes = df_r[(df_r["SNAPSHOT_SEQ"] == t0) & (df_r["EXPIRY"] == exp)]["STRIKE"].unique()
            logger.info(f"Checking {len(t0_strikes)} strikes for expiry {exp} across snapshots {t0}->{t1}->{t2}")
            
            for strike in t0_strikes:
                key0, key1, key2 = (t0, exp, strike), (t1, exp, strike), (t2, exp, strike)
                if key0 not in df.index or key1 not in df.index or key2 not in df.index:
                    continue
                r0, r1, r2 = df.loc[key0], df.loc[key1], df.loc[key2]

                # CALL ENTRY - requires underlying to increase (t2 > t0)
                if underlying_increasing:
                    call_conditions = {
                        "underlying_increasing": underlying_increasing,
                        "ltp_increasing": r2["c_LTP"] > r1["c_LTP"] > r0["c_LTP"],
                        "ltp_3pct_move": r2["c_LTP"] >= r0["c_LTP"] * 1.03,
                        "oi_5pct_growth": r2["c_OI"] >= r1["c_OI"] * 1.05,
                        "ltp_gt_5": r0["c_LTP"] > 5,
                        "cooldown_ok": t2 - last_call_entry_snap > cooldown
                    }
                    
                    # Log detailed condition check
                    ltp_move_pct = ((r2["c_LTP"] / r0["c_LTP"]) - 1) * 100 if r0["c_LTP"] > 0 else 0
                    oi_growth_pct = ((r2["c_OI"] / r1["c_OI"]) - 1) * 100 if r1["c_OI"] > 0 else 0
                    
                    failed_conditions = [k for k, v in call_conditions.items() if not v]
                    
                    # Only log strikes that are close to meeting conditions (to reduce noise)
                    # Log if LTP is increasing OR if OI growth is positive (even if not 5%)
                    should_log = (r2["c_LTP"] > r1["c_LTP"] > r0["c_LTP"]) or (r2["c_OI"] > r1["c_OI"])
                    
                    if failed_conditions and should_log:
                        logger.info(f"CALL {strike}: FAILED - {failed_conditions}")
                        logger.info(f"  LTP: {r0['c_LTP']:.2f}->{r1['c_LTP']:.2f}->{r2['c_LTP']:.2f} "
                                   f"({ltp_move_pct:.2f}% move, need >=3%)")
                        logger.info(f"  OI: {r0['c_OI']:.0f}->{r1['c_OI']:.0f}->{r2['c_OI']:.0f} "
                                   f"({oi_growth_pct:.2f}% growth t1->t2, need >=5%)")
                    elif not failed_conditions:
                        logger.info(f"CALL {strike}: ALL CONDITIONS MET!")
                        logger.info(f"  LTP: {r0['c_LTP']:.2f}->{r1['c_LTP']:.2f}->{r2['c_LTP']:.2f} "
                                  f"({ltp_move_pct:.2f}% move)")
                        logger.info(f"  OI: {r0['c_OI']:.0f}->{r1['c_OI']:.0f}->{r2['c_OI']:.0f} "
                                  f"({oi_growth_pct:.2f}% growth t1->t2)")
                    
                    if all(call_conditions.values()):
                        call_buy_signals[t2] = (exp, strike)
                        last_call_entry_snap = t2
                        logger.info(f"✓ CALL BUY signal generated at snapshot {t2}: {exp} {strike}, LTP={r2['c_LTP']:.2f}")

                # PUT ENTRY - requires underlying to decrease (t2 < t0)
                if underlying_decreasing:
                    put_conditions = {
                        "underlying_decreasing": underlying_decreasing,
                        "ltp_increasing": r2["p_LTP"] > r1["p_LTP"] > r0["p_LTP"],
                        "ltp_3pct_move": r2["p_LTP"] >= r0["p_LTP"] * 1.03,
                        "oi_5pct_growth": r2["p_OI"] >= r1["p_OI"] * 1.05,
                        "ltp_gt_5": r0["p_LTP"] > 5,
                        "cooldown_ok": t2 - last_put_entry_snap > cooldown
                    }
                    
                    # Log detailed condition check
                    ltp_move_pct = ((r2["p_LTP"] / r0["p_LTP"]) - 1) * 100 if r0["p_LTP"] > 0 else 0
                    oi_growth_pct = ((r2["p_OI"] / r1["p_OI"]) - 1) * 100 if r1["p_OI"] > 0 else 0
                    
                    failed_conditions = [k for k, v in put_conditions.items() if not v]
                    
                    # Only log strikes that are close to meeting conditions (to reduce noise)
                    # Log if LTP is increasing OR if OI growth is positive (even if not 5%)
                    should_log = (r2["p_LTP"] > r1["p_LTP"] > r0["p_LTP"]) or (r2["p_OI"] > r1["p_OI"])
                    
                    if failed_conditions and should_log:
                        logger.info(f"PUT {strike}: FAILED - {failed_conditions}")
                        logger.info(f"  LTP: {r0['p_LTP']:.2f}->{r1['p_LTP']:.2f}->{r2['p_LTP']:.2f} "
                                   f"({ltp_move_pct:.2f}% move, need >=3%)")
                        logger.info(f"  OI: {r0['p_OI']:.0f}->{r1['p_OI']:.0f}->{r2['p_OI']:.0f} "
                                   f"({oi_growth_pct:.2f}% growth t1->t2, need >=5%)")
                    elif not failed_conditions:
                        logger.info(f"PUT {strike}: ALL CONDITIONS MET!")
                        logger.info(f"  LTP: {r0['p_LTP']:.2f}->{r1['p_LTP']:.2f}->{r2['p_LTP']:.2f} "
                                  f"({ltp_move_pct:.2f}% move)")
                        logger.info(f"  OI: {r0['p_OI']:.0f}->{r1['p_OI']:.0f}->{r2['p_OI']:.0f} "
                                  f"({oi_growth_pct:.2f}% growth t1->t2)")
                    
                    if all(put_conditions.values()):
                        put_buy_signals[t2] = (exp, strike)
                        last_put_entry_snap = t2
                        logger.info(f"✓ PUT BUY signal generated at snapshot {t2}: {exp} {strike}, LTP={r2['p_LTP']:.2f}")

    if not call_buy_signals and not put_buy_signals:
        logger.info(f"No signals generated. Checked {len(t0_strikes)} strikes across {len(snap_list)} snapshots")
    
    return call_buy_signals, put_buy_signals


def evaluate_exit_condition(
    df: pd.DataFrame,
    position_type: str,
    position_expiry: str,
    position_strike: float,
    entry_price: float,
    entry_snapshot_seq: int,
    current_snapshot_seq: int,
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
    min_hold_snaps: int = DEFAULT_MIN_HOLD_SNAPS
) -> Tuple[bool, str, Optional[float]]:
    """
    Evaluate exit conditions for an open position based on backtest logic.
    
    Exit conditions:
    1. Stop loss: curr_ltp <= entry_price * (1 - stop_loss_pct)
    2. Sell signal: (current_snap - entry_snap) >= min_hold_snaps AND 
                    curr_ltp < prev_ltp AND curr_oi < prev_oi
    
    Args:
        df: Prepared dataframe
        position_type: "BUY_CALL" or "BUY_PUT"
        position_expiry: Expiry of position
        position_strike: Strike of position
        entry_price: Entry price
        entry_snapshot_seq: Snapshot sequence when entered
        current_snapshot_seq: Current snapshot sequence
        stop_loss_pct: Stop loss percentage (default 0.5 for 50%)
        min_hold_snaps: Minimum hold snapshots (default 7)
        
    Returns:
        Tuple of (should_exit, reason, current_ltp)
    """
    # Check if position exists in current snapshot
    key = (current_snapshot_seq, position_expiry, position_strike)
    if key not in df.index:
        return False, "Position not found in current snapshot", None
    
    curr = df.loc[key]
    
    # Determine LTP and OI columns based on position type
    if position_type == "BUY_CALL":
        ltp_col = "c_LTP"
        oi_col = "c_OI"
    elif position_type == "BUY_PUT":
        ltp_col = "p_LTP"
        oi_col = "p_OI"
    else:
        return False, f"Unknown position type: {position_type}", None
    
    curr_ltp = curr[ltp_col]
    curr_oi = curr[oi_col]
    
    # Calculate stop loss price
    stop_loss_price = entry_price * (1 - stop_loss_pct)
    
    # Check stop loss condition
    if curr_ltp <= stop_loss_price:
        pnl_pct = ((curr_ltp - entry_price) / entry_price) * 100
        return True, f"Stop loss: {pnl_pct:.2f}%", curr_ltp
    
    # Check minimum hold period
    snapshots_held = current_snapshot_seq - entry_snapshot_seq
    if snapshots_held < min_hold_snaps:
        return False, f"Minimum hold not met ({snapshots_held}/{min_hold_snaps})", curr_ltp
    
    # Get previous snapshot data for sell signal check
    df_r = df.reset_index()
    snap_list = sorted(df_r["SNAPSHOT_SEQ"].unique())
    current_idx = snap_list.index(current_snapshot_seq)
    
    if current_idx > 0:
        prev_snapshot_seq = snap_list[current_idx - 1]
        prev_key = (prev_snapshot_seq, position_expiry, position_strike)
        
        if prev_key in df.index:
            prev = df.loc[prev_key]
            prev_ltp = prev[ltp_col]
            prev_oi = prev[oi_col]
            
            # Check sell signal condition: curr_ltp < prev_ltp AND curr_oi < prev_oi
            if curr_ltp < prev_ltp and curr_oi < prev_oi:
                pnl_pct = ((curr_ltp - entry_price) / entry_price) * 100
                return True, f"Sell signal: Price and OI falling (P&L: {pnl_pct:.2f}%)", curr_ltp
        else:
            # If previous snapshot not found, use current as fallback
            prev_ltp = curr_ltp
            prev_oi = curr_oi
    else:
        # First snapshot, no previous data
        return False, "No previous snapshot for comparison", curr_ltp
    
    # No exit condition met
    pnl_pct = ((curr_ltp - entry_price) / entry_price) * 100
    return False, f"Hold: P&L={pnl_pct:.2f}%, Snapshots={snapshots_held}", curr_ltp


# ---------------------------
# Signal evaluation for latest snapshot sequence
# ---------------------------
def evaluate_signal(
    df: pd.DataFrame, 
    has_open_position: bool = False, 
    position_type: Optional[str] = None, 
    position_expiry: Optional[str] = None, 
    position_strike: Optional[float] = None,
    entry_price: Optional[float] = None,
    entry_snapshot_seq: Optional[int] = None,
    last_buy_snapshot_seq: Optional[int] = None,
    cooldown: int = DEFAULT_COOLDOWN
) -> Dict:
    """
    Evaluate Buy/Sell/No signal using the last 3 snapshots in the dataframe.
    Returns a dict with signal info.
    
    Args:
        df: Prepared dataframe
        has_open_position: Whether there's an open position
        position_type: Type of open position ("BUY_CALL" or "BUY_PUT")
        position_expiry: Expiry of open position
        position_strike: Strike of open position
    """
    # Ensure we have at least 3 snapshot sequences
    snap_seqs = sorted(df.reset_index()["SNAPSHOT_SEQ"].unique())
    if len(snap_seqs) < 3:
        return {"signal": "NO_SIGNAL", "reason": "Less than 3 snapshot sequences"}

    latest_seq = snap_seqs[-1]
    
    # If there's an open position, check for exit conditions
    if has_open_position and position_type and position_expiry and position_strike and entry_price is not None and entry_snapshot_seq is not None:
        should_exit, exit_reason, current_ltp = evaluate_exit_condition(
            df,
            position_type,
            position_expiry,
            position_strike,
            entry_price,
            entry_snapshot_seq,
            latest_seq
        )
        
        if should_exit:
            # Get snapshot ID
            try:
                key = (latest_seq, position_expiry, position_strike)
                if key in df.index:
                    row = df.loc[key]
                    snapshot_id = row.get("SNAPSHOT_ID", None)
                else:
                    df_r = df.reset_index()
                    row = df_r[(df_r["SNAPSHOT_SEQ"] == latest_seq) & 
                               (df_r["EXPIRY"] == position_expiry) & 
                               (df_r["STRIKE"] == position_strike)]
                    snapshot_id = row.iloc[0].get("SNAPSHOT_ID", None) if not row.empty else None
            except Exception:
                snapshot_id = None
            
            signal_type = "SELL_CALL" if position_type == "BUY_CALL" else "SELL_PUT"
            return {
                "signal": signal_type,
                "snapshot_seq": latest_seq,
                "expiry": position_expiry,
                "strike": position_strike,
                "ltp": current_ltp,
                "snapshot_id": snapshot_id,
                "reason": exit_reason
            }
        else:
            return {"signal": "NO_SIGNAL", "reason": exit_reason}
    
    # If no open position, check for buy signals
    if has_open_position:
        return {"signal": "NO_SIGNAL", "reason": "Position already open"}

    # Check cooldown from last buy snapshot
    if last_buy_snapshot_seq is not None:
        snapshots_since_last_buy = latest_seq - last_buy_snapshot_seq
        if snapshots_since_last_buy <= cooldown:
            return {"signal": "NO_SIGNAL", "reason": f"Cooldown active: {snapshots_since_last_buy}/{cooldown} snapshots since last buy"}

    call_sigs, put_sigs = generate_signals(df, debug=True)

    if latest_seq in call_sigs:
        exp, strike = call_sigs[latest_seq]
        # Get LTP from latest snapshot
        try:
            key = (latest_seq, exp, strike)
            if key in df.index:
                row = df.loc[key]
                ltp = row["c_LTP"]
                snapshot_id = row.get("SNAPSHOT_ID", None)
            else:
                # Fallback: get from reset index
                df_r = df.reset_index()
                row = df_r[(df_r["SNAPSHOT_SEQ"] == latest_seq) & (df_r["EXPIRY"] == exp) & (df_r["STRIKE"] == strike)]
                if not row.empty:
                    ltp = row.iloc[0]["c_LTP"]
                    snapshot_id = row.iloc[0].get("SNAPSHOT_ID", None)
                else:
                    ltp = None
                    snapshot_id = None
        except Exception as e:
            ltp = None
            snapshot_id = None
        
        return {
            "signal": "BUY_CALL",
            "snapshot_seq": latest_seq,
            "expiry": exp,
            "strike": strike,
            "ltp": ltp,
            "snapshot_id": snapshot_id,
        }
    if latest_seq in put_sigs:
        exp, strike = put_sigs[latest_seq]
        # Get LTP from latest snapshot
        try:
            key = (latest_seq, exp, strike)
            if key in df.index:
                row = df.loc[key]
                ltp = row["p_LTP"]
                snapshot_id = row.get("SNAPSHOT_ID", None)
            else:
                # Fallback: get from reset index
                df_r = df.reset_index()
                row = df_r[(df_r["SNAPSHOT_SEQ"] == latest_seq) & (df_r["EXPIRY"] == exp) & (df_r["STRIKE"] == strike)]
                if not row.empty:
                    ltp = row.iloc[0]["p_LTP"]
                    snapshot_id = row.iloc[0].get("SNAPSHOT_ID", None)
                else:
                    ltp = None
                    snapshot_id = None
        except Exception as e:
            ltp = None
            snapshot_id = None
        
        return {
            "signal": "BUY_PUT",
            "snapshot_seq": latest_seq,
            "expiry": exp,
            "strike": strike,
            "ltp": ltp,
            "snapshot_id": snapshot_id,
        }
    return {"signal": "NO_SIGNAL", "reason": "No call/put trigger on latest snapshot"}


# ---------------------------
# Helpers
# ---------------------------
def latest_output_file(output_dir: Path) -> Path:
    files = sorted(output_dir.glob("snapshot_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No snapshot files found in {output_dir}")
    return files[0]


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


def get_current_ltp(df: pd.DataFrame, expiry: str, strike: float, signal_type: str, snapshot_seq: Optional[int] = None) -> Optional[float]:
    """
    Get current LTP for a given expiry, strike, and signal type from the latest snapshot.
    
    Args:
        df: Prepared dataframe
        expiry: Expiry date
        strike: Strike price
        signal_type: "BUY_CALL" or "BUY_PUT"
        snapshot_seq: Optional snapshot sequence (uses latest if not provided)
        
    Returns:
        Current LTP or None if not found
    """
    df_r = df.reset_index()
    
    if snapshot_seq is None:
        snap_seqs = sorted(df_r["SNAPSHOT_SEQ"].unique())
        if not snap_seqs:
            return None
        snapshot_seq = snap_seqs[-1]
    
    row = df_r[(df_r["SNAPSHOT_SEQ"] == snapshot_seq) & 
               (df_r["EXPIRY"] == expiry) & 
               (df_r["STRIKE"] == strike)]
    
    if row.empty:
        return None
    
    if signal_type == "BUY_CALL":
        return row.iloc[0].get("c_LTP")
    elif signal_type == "BUY_PUT":
        return row.iloc[0].get("p_LTP")
    
    return None


# ---------------------------
# Main
# ---------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate signal from latest combined snapshot file.")
    parser.add_argument("--file", type=str, default=None, help="Path to snapshot CSV (default: latest in output/)")
    parser.add_argument("--output-json", type=str, default=None, help="Optional path to write signal JSON")
    parser.add_argument("--has-open-position", action="store_true", help="Set if a position is already open to block new signals")
    args = parser.parse_args()

    output_dir = Path("output")
    if args.file:
        csv_path = Path(args.file)
    else:
        csv_path = latest_output_file(output_dir)

    print(f"Using snapshot file: {csv_path}")

    df_raw = load_csv(csv_path)
    df_prep = prepare_data(df_raw)
    result = evaluate_signal(df_prep, has_open_position=args.has_open_position)

    print("\n=== SIGNAL RESULT ===")
    print(json.dumps(result, indent=2))

    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nSignal written to {args.output_json}")


if __name__ == "__main__":
    main()

