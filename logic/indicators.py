"""Technical indicator calculation module.

This module provides high-performance calculation of technical indicators (EMA, ATR, Volume MA)
using pure pandas implementation to ensure stability and zero external dependency
overhead for core calculations.
"""

from typing import List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from utils.exceptions import InsufficientDataError, InvalidDataTypeError


class IndicatorEngine:
    """Engine for calculating technical indicators on OHLCV DataFrames."""

    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average.

        Args:
            series: Data series (usually Close prices)
            period: Smoothing period

        Returns:
            Series containing EMA values
        """
        if len(series) < period:
            # We don't raise here, we just return NaNs
            return pd.Series(index=series.index, dtype=float)
            
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range.

        Args:
            df: DataFrame with OHLC columns
            period: Smoothing period

        Returns:
            Series containing ATR values
        """
        if len(df) < period:
            return pd.Series(index=df.index, dtype=float)

        high = df["High"]
        low = df["Low"]
        close_prev = df["Close"].shift(1)

        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR is usually the EMA of True Range
        return true_range.ewm(span=period, adjust=False).mean()

    @classmethod
    def calculate_all(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators required for CakTykBot.

        Indicator set:
        - EMA: 8, 21, 50, 150, 200
        - ATR: 14
        - Volume MA: 20

        Args:
            df: OHLCV DataFrame

        Returns:
            DataFrame with additional indicator columns

        Raises:
            InvalidDataTypeError: If input is not a DataFrame
        """
        if not isinstance(df, pd.DataFrame):
            raise InvalidDataTypeError("Input must be a pandas DataFrame")

        # Create copy to avoid modifying original
        result = df.copy()

        # EMAs
        for p in [8, 21, 50, 150, 200]:
            result[f"ema_{p}"] = cls.calculate_ema(result["Close"], p)

        # ATR
        result["atr_14"] = cls.calculate_atr(result, 14)

        # Volume MA
        result["vol_ma_20"] = result["Volume"].rolling(window=20).mean()

        return result


def validate_sufficient_data(df: pd.DataFrame, required_days: int = 200) -> None:
    """Validate if DataFrame has enough data for indicators.

    Args:
        df: DataFrame to check
        required_days: Minimum days needed (usually 200 for EMA200)

    Raises:
        InsufficientDataError: If data is shorter than required_days
    """
    if len(df) < required_days:
        message = f"Insufficient data: have {len(df)} rows, need at least {required_days}"
        logger.warning(message)
        raise InsufficientDataError(message)
