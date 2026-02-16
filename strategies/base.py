from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class StrategySignal:
    """Output standar dari setiap strategy module."""

    symbol: str
    verdict: Optional[str]  # "BUY" | "SELL" | "HOLD" | "WAIT" | None
    entry_price: float
    sl_price: float
    tp_price: float
    tp2_price: Optional[float]
    rr_ratio: float
    score: float  # 0-100
    strategy_name: str  # "vcp_breakout" | "ema_pullback"
    reasoning: str
    detail: Dict[str, Any]  # Strategy-specific metadata


class BaseStrategy(ABC):
    """Abstract base class — semua strategy HARUS implement ini."""

    @abstractmethod
    def analyze(self, price_data: pd.DataFrame, **kwargs) -> Optional[StrategySignal]:
        """
        Analyze a single symbol and return signal or None.

        Args:
            price_data: DataFrame minimal 200 rows (sorted date asc)
            kwargs: strategy-specific params (e.g., ihsg_data for EMA)

        Returns:
            StrategySignal or None (no signal)

        Classification: PURE FUNCTION (no DB writes)
        """
        pass
