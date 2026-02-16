"""EMA (Exponential Moving Average) Pullback Strategy."""
import logging
from typing import Any, Dict, Optional

import pandas as pd

from .base import BaseStrategy, StrategySignal
from .utils import calculate_rr, is_bullish_candle, is_near

logger = logging.getLogger(__name__)


class EMAPullbackStrategy(BaseStrategy):
    """
    EMA 8/21 Pullback Strategy + Relative Strength.

    Signals BUY when:
    1. Uptrend is strong (Price > EMA50 > EMA150 > EMA200).
    2. Price pulls back to EMA 8 or EMA 21.
    3. Stock shows invalid Relative Strength (Price perf > IHSG perf).
    4. Bullish confirmation candle appears.
    """

    def analyze(self, price_data: pd.DataFrame, **kwargs) -> Optional[StrategySignal]:
        symbol = kwargs.get("symbol", "UNKNOWN")
        ihsg_data = kwargs.get("ihsg_data")

        # 1. Data Validation
        if len(price_data) < 200:
            return None

        # Ensure sorted
        df = price_data.sort_values("date", ascending=True).copy()
        current_row = df.iloc[-1]

        # 2. Uptrend Validation (BR-EMA-001)
        if not self._is_uptrend(df):
            return None

        # 3. EMA Pullback Detection (BR-EMA-002)
        pullback_info = self._detect_ema_pullback(current_row)
        if not pullback_info["is_pullback"]:
            return None

        # 4. Relative Strength Calculation (BR-EMA-003)
        rs_info = self._calculate_rs(df, ihsg_data)
        if not rs_info["outperforms"]:
            # RS is crucial for this strategy
            return None

        # 5. Bullish Reversal Entry (BR-EMA-004)
        if not self._detect_bullish_reversal(df):
            return None

        # 6. Risk Management (BR-EMA-005)
        # SL below EMA 21 or Low
        ema21 = current_row.get("ema_21", 0)
        low = current_row["Low"]
        
        # SL logic: min(EMA21, Low) * 0.98 (2% buffer)
        sl_base = min(ema21, low) if ema21 > 0 else low
        risk_calc = self._calculate_risk_reward(current_row["Close"], sl_base)

        if risk_calc["rr"] < 2.0:  # Minimum RR 1:2, target 1:3
            return None

        return StrategySignal(
            symbol=symbol,
            verdict="BUY",
            entry_price=current_row["Close"],
            sl_price=risk_calc["sl"],
            tp_price=risk_calc["tp1"],
            tp2_price=None, # Only 1 TP target for this strategy typically (3R)
            rr_ratio=risk_calc["rr"],
            score=75.0 + (rs_info["rs_diff"] if rs_info["rs_diff"] > 0 else 0),
            strategy_name="ema_pullback",
            reasoning=(
                f"Pullback to {pullback_info['pullback_to']} confirmed. "
                f"RS Strong (+{rs_info['rs_diff']:.1f}% vs IHSG). RR {risk_calc['rr']}:1"
            ),
            detail={**pullback_info, **rs_info},
        )

    def _is_uptrend(self, df: pd.DataFrame) -> bool:
        """
        Check if stock is in a strong uptrend.
        Criteria:
        Price > EMA 50 > EMA 150 > EMA 200
        """
        curr = df.iloc[-1]
        required = ["ema_50", "ema_150", "ema_200"]
        if not all(col in df.columns for col in required):
            return False

        try:
            c1 = curr["Close"] > curr["ema_50"]
            c2 = curr["ema_50"] > curr["ema_150"]
            c3 = curr["ema_150"] > curr["ema_200"]
            return c1 and c2 and c3
        except Exception:
            return False

    def _detect_ema_pullback(self, row: pd.Series) -> Dict[str, Any]:
        """
        Check if current candle Low touches or dips into EMA 8/21 zone.
        """
        ema8 = row.get("ema_8", 0)
        ema21 = row.get("ema_21", 0)
        low = row["Low"]
        high = row["High"]

        if ema8 == 0 or ema21 == 0:
            return {"is_pullback": False}

        # Check pullback to EMA 8 (Super strong trend)
        # Low touches EMA 8 (within 1% tolerance)
        if is_near(low, ema8, 0.015) or (low < ema8 < high):
            return {"is_pullback": True, "pullback_to": "EMA8"}

        # Check pullback to EMA 21 (Normal trend)
        if is_near(low, ema21, 0.015) or (low < ema21 < high):
            return {"is_pullback": True, "pullback_to": "EMA21"}

        return {"is_pullback": False}

    def _calculate_rs(
        self, df: pd.DataFrame, ihsg_df: Optional[pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        Calculate Relative Strength vs IHSG over 90 days (approx 60 candles).
        """
        if ihsg_df is None or len(ihsg_df) < 60:
            # If no IHSG data, we can't calculate RS. 
            # Strategy requires RS.
            # Fail safe: return False or allow pass with warning?
            # Requirement: "Only stocks that outperform market".
            logger.warning("Missing IHSG data for RS calculation")
            return {"outperforms": False, "rs_diff": 0.0}

        period = 60 # Approx 3 months trading days
        
        # Align dates logic is complex if dates mismatch. 
        # Simplified: Calculate % change of last 60 rows available for both.
        
        stock_start = df.iloc[-period]["Close"]
        stock_end = df.iloc[-1]["Close"]
        stock_perf = ((stock_end - stock_start) / stock_start) * 100

        # IHSG alignment (simple tail)
        ihsg_start = ihsg_df.iloc[-period]["Close"]
        ihsg_end = ihsg_df.iloc[-1]["Close"]
        ihsg_perf = ((ihsg_end - ihsg_start) / ihsg_start) * 100

        rs_diff = stock_perf - ihsg_perf
        outperforms = rs_diff > 0

        return {
            "outperforms": outperforms,
            "rs_stock": stock_perf,
            "rs_ihsg": ihsg_perf,
            "rs_diff": rs_diff,
        }

    def _detect_bullish_reversal(self, df: pd.DataFrame) -> bool:
        """
        Check for bullish reversal candle (Hammer, Engulfing, or just strong Close).
        Simplified: Close > Open AND Volume > AvgVol5.
        """
        curr = df.iloc[-1]
        
        # 1. Bullish Candle
        if not is_bullish_candle(curr["Open"], curr["Close"]):
            return False
            
        # 2. Volume Confirmation
        # Check if 'vol_ma_20' exists, or calc on fly
        # Requirement says "Volume > AvgVol5"
        
        vol = curr["Volume"]
        # Calc AvgVol5
        avg_vol_5 = df["Volume"].tail(5).mean()
        
        if vol < avg_vol_5:
            return False
            
        return True

    def _calculate_risk_reward(self, entry: float, sl: float) -> Dict[str, float]:
        """
        Calculate TP based on 3R target.
        """
        # Ensure SL is valid
        if sl >= entry:
            sl = entry * 0.98

        risk = entry - sl
        tp1 = entry + (risk * 3.0) # 1:3 Target
        
        rr = calculate_rr(entry, sl, tp1)
        
        return {"sl": sl, "tp1": tp1, "rr": rr}
