from typing import List, Dict, Any, Optional
import pandas as pd

def detect_biases(trades: List[Dict]) -> List[str]:
    """
    Detect behavioral biases from trade history.
    
    Returns:
        List of warning strings describing detected biases.
    """
    biases = []
    if not trades or len(trades) < 5:
        return biases
        
    df = pd.DataFrame(trades)
    df = df.sort_values("exit_date")
    
    # Calculate Holding Periods if not present
    if "holding_days" not in df.columns and "entry_date" in df.columns and "exit_date" in df.columns:
         df["holding_days"] = (pd.to_datetime(df["exit_date"]) - pd.to_datetime(df["entry_date"])).dt.days
    
    # 1. Loss Aversion (Holding Losers > 2x Winners)
    wins = df[df["pnl_rupiah"] > 0]
    losses = df[df["pnl_rupiah"] <= 0]
    
    if not wins.empty and not losses.empty and "holding_days" in df.columns:
        avg_hold_win = wins["holding_days"].mean()
        avg_hold_loss = losses["holding_days"].mean()
        
        if avg_hold_loss > 2 * avg_hold_win and avg_hold_loss > 5:
            biases.append(f"Loss Aversion: Avg hold loss ({avg_hold_loss:.1f}d) is >2x wins ({avg_hold_win:.1f}d).")

    # 2. Revenge Trading (Trading immediately after loss with larger size or frequency)
    # Check if trades shortly after a loss have negative expectation or high frequency
    # Simplified: Check if user made >3 trades in same day after a loss day?
    
    # 3. Overconfidence (Size increase after win streak)
    # Check last 5 trades. If 3 wins streak, check if next trade size > avg.
    # Need 'position_size' or 'capital_at_risk' in trades.
    
    return biases
