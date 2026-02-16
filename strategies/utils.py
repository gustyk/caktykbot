"""Shared utility functions for strategies."""
from typing import Optional

import pandas as pd


def is_near(value: float, target: float, tolerance_pct: float = 0.01) -> bool:
    """Check if value is within tolerance percentage of target."""
    if target == 0:
        return False
    lower = target * (1 - tolerance_pct)
    upper = target * (1 + tolerance_pct)
    return lower <= value <= upper


def is_crossover(series1: pd.Series, series2: pd.Series) -> bool:
    """Check if series1 crosses over series2 at the last candle."""
    if len(series1) < 2 or len(series2) < 2:
        return False
    
    prev_1 = series1.iloc[-2]
    curr_1 = series1.iloc[-1]
    prev_2 = series2.iloc[-2]
    curr_2 = series2.iloc[-1]
    
    return prev_1 <= prev_2 and curr_1 > curr_2


def is_bullish_candle(open_price: float, close_price: float) -> bool:
    """Check if candle is bullish (Close > Open)."""
    return close_price > open_price


def calculate_rr(entry: float, sl: float, tp: float) -> float:
    """Calculate Risk-Reward Ratio."""
    risk = entry - sl
    reward = tp - entry
    
    if risk <= 0:
        return 0.0
    
    return round(reward / risk, 2)
