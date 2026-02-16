"""Correlation Logic (RR-007)."""

import pandas as pd
from loguru import logger

from caktykbot.risk.constants import (
    CORRELATION_THRESHOLD
)

def calculate_correlation(
    stock_returns: pd.Series,
    ihsg_returns: pd.Series,
    period: int = 90
) -> float:
    """
    Calculate Pearson correlation between stock and IHSG returns.
    
    Args:
        stock_returns: Series of stock daily returns (pct_change)
        ihsg_returns: Series of IHSG daily returns (pct_change)
        period: Lookback period in days
        
    Returns:
        Correlation coefficient (-1.0 to 1.0).
        Returns 0.0 if insufficient data.
    """
    if len(stock_returns) < period or len(ihsg_returns) < period:
        logger.warning(f"Insufficient data for correlation: Stock={len(stock_returns)}, IHSG={len(ihsg_returns)}, Req={period}")
        return 0.0
        
    # Align data by date index
    df = pd.DataFrame({'stock': stock_returns, 'ihsg': ihsg_returns}).dropna()
    
    if len(df) < period:
        return 0.0
        
    # Slice last 'period' days
    df_slice = df.tail(period)
    
    correlation = df_slice['stock'].corr(df_slice['ihsg'], method='pearson')
    
    return float(correlation)

def should_reduce_size_by_correlation(correlation: float) -> bool:
    """
    Check if position size should be reduced based on correlation.
    
    Args:
        correlation: Calculated correlation coefficient
        
    Returns:
        True if correlation > threshold
    """
    return correlation > CORRELATION_THRESHOLD
