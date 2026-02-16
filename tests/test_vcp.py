"""Tests for VCP Strategy."""
import pandas as pd
import pytest
from strategies.vcp import VCPStrategy


@pytest.fixture
def sample_data():
    """Create sample price data."""
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "Open": 1000.0,
        "High": 1050.0,
        "Low": 950.0,
        "Close": 1020.0,
        "Volume": 1000000,
        "ema_50": 900.0,
        "ema_150": 850.0,
        "ema_200": 800.0
    })
    return df


def test_stage2_uptrend(sample_data):
    strategy = VCPStrategy()
    
    # Valid Stage 2: Close > 150 > 200, 200 trending up
    # We need to simulate trend of EMA 200
    # In sample_data all rows are identical, so EMA 200 is flat (trending up check might fail/pass depending on logic)
    # Logic: curr > prev. 800 > 800 is False.
    # We need to make it trend up.
    
    sample_data.loc[249, "ema_200"] = 801.0
    sample_data.loc[229, "ema_200"] = 800.0 # 20 days ago
    
    assert strategy._is_stage2_uptrend(sample_data) is True
    
    # Invalid: Close < EMA 150
    sample_data.loc[249, "Close"] = 820.0
    assert strategy._is_stage2_uptrend(sample_data) is False


def test_vcp_detection_logic():
    strategy = VCPStrategy()
    
    # Create a synthetic VCP pattern
    # 60 days of data.
    # Base High at day 0 (index -60) -> not practical.
    # Let's say last 60 days.
    # Day 0-20: Wave 1 (Drop 20%)
    # Day 21-40: Wave 2 (Drop 10%)
    # Day 41-60: Wave 3 (Drop 5%)
    
    dates = pd.date_range(start="2023-01-01", periods=60, freq="D")
    df = pd.DataFrame({"date": dates, "High": 100.0, "Low": 90.0})
    
    # Wave 1: High 100, Low 80 (Depth 20%)
    df.loc[0:19, "High"] = 100.0
    df.loc[0:19, "Low"] = 80.0
    
    # Wave 2: High 100, Low 90 (Depth 10%)
    df.loc[20:39, "High"] = 100.0
    df.loc[20:39, "Low"] = 90.0
    
    # Wave 3: High 100, Low 95 (Depth 5%)
    df.loc[40:59, "High"] = 100.0
    df.loc[40:59, "Low"] = 95.0
    
    result = strategy._detect_vcp(df)
    
    # Logic in _detect_vcp splits 60 days into 3 chunks of 20
    # Seg 1 (0-20): Max 100, Min 80 -> Drop 20%
    # Seg 2 (20-40): Max 100, Min 90 -> Drop 10%
    # Seg 3 (40-60): Max 100, Min 95 -> Drop 5%
    # Check: 5% < 15% (Tight) AND Decreasing (20 > 10 > 5)
    
    assert result["has_vcp"] is True
    assert result["contraction_count"] == 3
    assert result["pivot_high"] == 100.0


def test_retest_entry():
    strategy = VCPStrategy()
    dates = pd.date_range(start="2023-01-01", periods=5, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "Open": 100.0,
        "High": 105.0,
        "Low": 98.0,
        "Close": 102.0
    })
    
    pivot = 100.0
    
    # Current row: Open 100, Close 102 (Bullish). Low 98 (Near pivot 100)
    # Range for retest: 98 to 105. 98 is within tolerance?
    # Logic: 100 * 0.98 = 98. 100 * 1.05 = 105.
    # Low 98 is exactly on low bound.
    
    assert strategy._detect_retest_entry(df, pivot) is True
    
    # Bearish candle
    df.loc[4, "Close"] = 99.0
    assert strategy._detect_retest_entry(df, pivot) is False
