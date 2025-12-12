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
from typing import Tuple, Dict, List

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
    df = df.sort_values(["DOWNLOAD_DATE", "SNAPSHOT_ID", "STRIKE"]).reset_index(drop=True)

    snap_keys = df[["DOWNLOAD_DATE", "SNAPSHOT_ID"]].drop_duplicates().reset_index(drop=True)
    snap_keys["SNAPSHOT_SEQ"] = range(len(snap_keys))
    df = df.merge(snap_keys, on=["DOWNLOAD_DATE", "SNAPSHOT_ID"], how="left")

    df["STRIKE"] = df["STRIKE"].astype(float)
    df["EXPIRY"] = df["EXPIRY"].astype(str)
    df = df.set_index(["SNAPSHOT_SEQ", "EXPIRY", "STRIKE"]).sort_index()
    return df


# ---------------------------
# Signal Generation
# ---------------------------
def generate_signals(df: pd.DataFrame, strike_step=DEFAULT_STRIKE_STEP, cooldown=DEFAULT_COOLDOWN):
    """
    Generate call/put buy signals over the snapshot sequence.
    """
    call_buy_signals, put_buy_signals = {}, {}
    df_r = df.reset_index()
    snap_list = sorted(df_r["SNAPSHOT_SEQ"].unique())
    under_by_snap = df_r.groupby("SNAPSHOT_SEQ")["UNDERLYING_VALUE"].first()
    exps_by_snap = df_r.groupby("SNAPSHOT_SEQ")["EXPIRY"].unique()
    last_call_entry_snap = -9999
    last_put_entry_snap = -9999

    for idx in range(len(snap_list) - 2):
        t0, t1, t2 = snap_list[idx], snap_list[idx + 1], snap_list[idx + 2]
        try:
            spot = under_by_snap.loc[t0]
            atm_strike = round(spot / strike_step) * strike_step
        except KeyError:
            continue
        valid_strikes = [atm_strike - strike_step, atm_strike, atm_strike + strike_step]
        try:
            u0, u1, u2 = under_by_snap.loc[t0], under_by_snap.loc[t1], under_by_snap.loc[t2]
            underlying_falling = (u2 < u1 < u0)
        except KeyError:
            underlying_falling = False

        for exp in exps_by_snap.loc[t0]:
            for strike in valid_strikes:
                key0, key1, key2 = (t0, exp, strike), (t1, exp, strike), (t2, exp, strike)
                if key0 not in df.index or key1 not in df.index or key2 not in df.index:
                    continue
                r0, r1, r2 = df.loc[key0], df.loc[key1], df.loc[key2]

                # CALL ENTRY
                if (
                    r2["c_LTP"] > r1["c_LTP"] > r0["c_LTP"] and
                    r2["c_LTP"] >= r0["c_LTP"] * 1.03 and
                    r2["c_OI"] >= r1["c_OI"] * 1.05 and
                    r0["c_LTP"] > 5 and
                    t2 - last_call_entry_snap > cooldown
                ):
                    call_buy_signals[t2] = (exp, strike)
                    last_call_entry_snap = t2

                # PUT ENTRY
                if (
                    underlying_falling and
                    r2["p_LTP"] > r1["p_LTP"] > r0["p_LTP"] and
                    r2["p_LTP"] >= r0["p_LTP"] * 1.03 and
                    r2["p_OI"] >= r1["p_OI"] * 1.05 and
                    r0["p_LTP"] > 5 and
                    t2 - last_put_entry_snap > cooldown
                ):
                    put_buy_signals[t2] = (exp, strike)
                    last_put_entry_snap = t2

    return call_buy_signals, put_buy_signals


# ---------------------------
# Signal evaluation for latest snapshot sequence
# ---------------------------
def evaluate_signal(df: pd.DataFrame, has_open_position: bool = False) -> Dict:
    """
    Evaluate Buy/Sell/No signal using the last 3 snapshots in the dataframe.
    Returns a dict with signal info. If has_open_position=True, we skip new signals.
    """
    if has_open_position:
        return {"signal": "NO_SIGNAL", "reason": "Position already open"}

    # Ensure we have at least 3 snapshot sequences
    snap_seqs = sorted(df.reset_index()["SNAPSHOT_SEQ"].unique())
    if len(snap_seqs) < 3:
        return {"signal": "NO_SIGNAL", "reason": "Less than 3 snapshot sequences"}

    call_sigs, put_sigs = generate_signals(df)
    latest_seq = snap_seqs[-1]

    if latest_seq in call_sigs:
        exp, strike = call_sigs[latest_seq]
        return {
            "signal": "BUY_CALL",
            "snapshot_seq": latest_seq,
            "expiry": exp,
            "strike": strike,
        }
    if latest_seq in put_sigs:
        exp, strike = put_sigs[latest_seq]
        return {
            "signal": "BUY_PUT",
            "snapshot_seq": latest_seq,
            "expiry": exp,
            "strike": strike,
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

