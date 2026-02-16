"""VCP (Volatility Contraction Pattern) Breakout Strategy."""
import logging
from typing import Any, Dict, Optional

import pandas as pd
import numpy as np

from .base import BaseStrategy, StrategySignal
from .utils import is_bullish_candle, calculate_rr

logger = logging.getLogger(__name__)


class VCPStrategy(BaseStrategy):
    """
    VCP + Breakout Retest Strategy.
    
    Detects stocks in Stage 2 Uptrend, checks for Volatility Contraction Pattern (VCP),
    and signals BUY on a valid Retest of the breakout level.
    """

    def analyze(self, price_data: pd.DataFrame, **kwargs) -> Optional[StrategySignal]:
        symbol = kwargs.get("symbol", "UNKNOWN")

        # 1. Data Validation
        if len(price_data) < 200:
            logger.warning(
                f"Insufficient data for {symbol}: {len(price_data)} rows. Need > 200."
            )
            return None

        # Ensure data is sorted by date ascending
        df = price_data.sort_values("date", ascending=True).copy()
        current_idx = df.index[-1]
        current_row = df.iloc[-1]

        # 2. Stage 2 Uptrend Detection (BR-VCP-001)
        if not self._is_stage2_uptrend(df):
            return None

        # 3. VCP Pattern Detection (BR-VCP-002)
        vcp_pattern = self._detect_vcp(df)
        if not vcp_pattern["has_vcp"]:
            return None

        pivot_high = vcp_pattern["pivot_high"]
        pivot_low = vcp_pattern["pivot_low"]

        # 4. Retest Entry Detection (BR-VCP-004)
        # We look for a retest of the pivot high
        is_retest = self._detect_retest_entry(df, pivot_high)
        
        if not is_retest:
            return None

        # 5. Risk Management (BR-VCP-005)
        # SL = pivot_low * 0.94 (as per requirements example)
        # Actually requirement says: "SL = 2800 * 0.94" where Pivot Low was 2800.
        risk_calc = self._calculate_risk_reward(current_row["Close"], pivot_low)

        if risk_calc["rr"] < 2.0:
            logger.info(f"Signal skipped for {symbol}: RR {risk_calc['rr']} < 2.0")
            return None

        # Construct Signal
        return StrategySignal(
            symbol=symbol,
            verdict="BUY",
            entry_price=current_row["Close"],
            sl_price=risk_calc["sl"],
            tp_price=risk_calc["tp1"],
            tp2_price=risk_calc["tp2"],
            rr_ratio=risk_calc["rr"],
            score=85.0,  # TODO: Calculate dynamic score based on pattern quality
            strategy_name="vcp_breakout",
            reasoning=(
                f"Stage 2 Uptrend + {vcp_pattern['contraction_count']}T VCP "
                f"+ Retest of {pivot_high}"
            ),
            detail=vcp_pattern,
        )

    def _is_stage2_uptrend(self, df: pd.DataFrame) -> bool:
        """
        Check Mark Minervini's Stage 2 criteria.
        Criteria:
        1. Current Price > EMA 150 > EMA 200
        2. EMA 200 is trending up (current > 1 month ago)
        3. Current Price > EMA 50
        """
        curr = df.iloc[-1]

        # Check for required columns
        required_cols = ["ema_50", "ema_150", "ema_200"]
        if not all(col in df.columns for col in required_cols):
            logger.warning("Missing EMA columns for Stage 2 detection")
            return False

        # 1. Price > EMA 150 > EMA 200
        c1 = curr["Close"] > curr["ema_150"] > curr["ema_200"]

        # 2. EMA 200 trending up (vs 20 days ago)
        lookback = 20
        if len(df) > lookback:
            ema200_prev = df.iloc[-lookback]["ema_200"]
            c2 = curr["ema_200"] > ema200_prev
        else:
            c2 = True  # Not enough data to check trend, assume valid if alignment ok

        # 3. Price > EMA 50
        c3 = curr["Close"] > curr["ema_50"]

        return c1 and c2 and c3

    def _detect_vcp(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect VCP pattern using a heuristic approach.
        Checks for decreasing volatility over 3 segments in the last 60 days.
        """
        lookback = 60
        if len(df) < lookback:
            return {"has_vcp": False}

        recent = df.tail(lookback)

        # Split into 3 segments to check for contraction
        n = len(recent)
        seg_len = n // 3

        seg1 = recent.iloc[:seg_len]      # Oldest
        seg2 = recent.iloc[seg_len : 2 * seg_len]
        seg3 = recent.iloc[2 * seg_len :] # Newest

        def calc_depth(segment):
            if segment.empty:
                return 0.0
            mx = segment["High"].max()
            mn = segment["Low"].min()
            if mx == 0:
                return 0.0
            return (mx - mn) / mx

        d1 = calc_depth(seg1)
        d2 = calc_depth(seg2)
        d3 = calc_depth(seg3)

        # Check decreasing volatility
        # Ideally: d1 > d2 > d3
        # And the last contraction should be tight (< 10-15%)
        # We allow some tolerance, maybe d2 is slightly larger than d1 but d3 is tightest
        
        is_tight = d3 < 0.15  # Last contraction < 15%
        is_contracting = (d3 < d2) or (d3 < d1 and d2 < d1 * 1.1)

        has_vcp = is_tight and is_contracting
        
        # Determine pivots from the last segment (the tightest area usually forms near pivot)
        # Use the max high of the last 20 days as Pivot High (Resistance)
        pivot_high = seg3["High"].max()
        pivot_low = seg3["Low"].min()

        return {
            "has_vcp": has_vcp,
            "contraction_count": 3 if has_vcp else 0,
            "pivot_high": pivot_high,
            "pivot_low": pivot_low,
            "depths": [d1, d2, d3],
        }

    def _detect_retest_entry(self, df: pd.DataFrame, pivot_high: float) -> bool:
        """
        Check for Retest logic:
        1. Price is near pivot_high (within -2% to +5% range).
        2. Candle is Bullish (Close > Open).
        """
        curr = df.iloc[-1]

        # 1. Bullish Candle
        if not is_bullish_candle(curr["Open"], curr["Close"]):
            return False

        # 2. Price near Pivot High (Support area)
        # We accept if Low touches the area or Close is within area
        # "Pullback to area pivot"
        lower_bound = pivot_high * 0.98
        upper_bound = pivot_high * 1.05
        
        in_zone = (lower_bound <= curr["Low"] <= upper_bound) or \
                  (lower_bound <= curr["Close"] <= upper_bound)

        return in_zone

    def _calculate_risk_reward(self, entry: float, pivot_low: float) -> Dict[str, float]:
        """Calculate SL, TP and RR."""
        # SL = pivot_low * 0.94 (6% below pivot low for buffer)
        sl = pivot_low * 0.94
        
        # Ensure SL is below Entry
        if sl >= entry:
             sl = entry * 0.92 # Fallback if pivot is weirdly high
        
        tp1 = entry + (entry - sl) * 2.0  # Aim for 1:2 initially to define TP1
        # US-4.5 Example: TP1 = Entry * 1.20. Let's stick to RR based TPs or fixed %?
        # Requirement example: TP1 = 3000 * 1.20. 
        # But also says "RR = 1:1.63 minimum".
        # Let's use the explicit example logic: TP1 = +20%, TP2 = +40%?
        # Or standard RR?
        # "TP1 = 3000 * 1.20 = 3600" -> This implies Fixed % TP.
        
        # Let's use fixed percentage from example as default, but ensure RR check uses it.
        tp1 = entry * 1.20
        tp2 = entry * 1.40
        
        rr = calculate_rr(entry, sl, tp1)
        
        return {"sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr}
