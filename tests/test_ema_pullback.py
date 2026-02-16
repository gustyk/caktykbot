"""Tests for EMA Pullback Strategy."""
import pandas as pd
import pytest
from strategies.ema_pullback import EMAPullbackStrategy


@pytest.fixture
def sample_data():
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "Open": 1000.0,
        "High": 1050.0,
        "Low": 950.0,
        "Close": 1020.0,
        "Volume": 1000,
        "ema_8": 1000.0,
        "ema_21": 980.0,
        "ema_50": 950.0,
        "ema_150": 900.0,
        "ema_200": 850.0
    })
    return df


def test_uptrend_check(sample_data):
    strategy = EMAPullbackStrategy()
    # Close 1020 > 50(950) > 150(900) > 200(850) -> True
    assert strategy._is_uptrend(sample_data) is True
    
    # Broken trend
    sample_data.loc[249, "ema_50"] = 800.0
    assert strategy._is_uptrend(sample_data) is False


def test_ema_pullback_detection(sample_data):
    strategy = EMAPullbackStrategy()
    curr = sample_data.iloc[-1]
    
    # EMA 8 = 1000. Low = 950. High = 1050.
    # Low < EMA8 < High -> True (Touched)
    
    res = strategy._detect_ema_pullback(curr)
    assert res["is_pullback"] is True
    assert res["pullback_to"] == "EMA8"
    
    # No touch
    sample_data.loc[249, "Low"] = 1010.0 # Above EMA 8 (1000)
    # Assuming Close also above.
    
    res = strategy._detect_ema_pullback(sample_data.iloc[-1])
    # 1010 not near 1000 with 1.5% tol? 1000*1.015 = 1015. 
    # 1010 is within range? "Lower <= Value <= Upper". 1000 +/- 1.5% -> 985 to 1015.
    # 1010 is inside. So it counts as near / pullback.
    assert res["is_pullback"] is True
    
    # Far away
    sample_data.loc[249, "Low"] = 1050.0 # Way above
    res = strategy._detect_ema_pullback(sample_data.iloc[-1])
    assert res["is_pullback"] is False


def test_rs_calculation():
    strategy = EMAPullbackStrategy()
    
    # Create 90 days data
    dates = pd.date_range(start="2023-01-01", periods=90, freq="D")
    stock_df = pd.DataFrame({"date": dates, "Close": 100.0})
    ihsg_df = pd.DataFrame({"date": dates, "Close": 100.0})
    
    # Stock up 20%
    stock_df.iloc[-1] = [dates[-1], 120.0]
    # IHSG up 10%
    ihsg_df.iloc[-1] = [dates[-1], 110.0]
    
    # Note: _calculate_rs utilizes .iloc[-60] (approx 60 days lookback in calc)
    # We provided 90 days, so -60 exists.
    # Start (idx -60): 100. End: 120. Return +20%.
    # Start (idx -60): 100. End: 110. Return +10%.
    # Diff +10%.
    
    res = strategy._calculate_rs(stock_df, ihsg_df)
    assert res["outperforms"] is True
    assert res["rs_diff"] > 9.0


def test_bullish_reversal():
    strategy = EMAPullbackStrategy()
    df = pd.DataFrame({
        "Open": [100.0, 100.0],
        "Close": [110.0, 105.0],
        "Volume": [1000, 2000]
    })
    # Last candle: Open 100, Close 105 -> Bullish.
    # Volume 2000. AvgVol5 (of 2 rows) = 1500.
    # 2000 > 1500 -> True.
    
    assert strategy._detect_bullish_reversal(df) is True
    
    # Low Volume
    df.loc[1, "Volume"] = 1000
    # Avg = 1000. 1000 !> 1000? 
    # Logic: vol < avg return False. 1000 < 1000 False. So returns True?
    # Code: if vol < avg_vol_5: return False.
    # 1000 < 1000 is False. So it continues -> True.
    # Strict > ? Not in code. Code allows >= implicitly.
    assert strategy._detect_bullish_reversal(df) is True
    
    # Bearish
    df.loc[1, "Close"] = 90.0
    assert strategy._detect_bullish_reversal(df) is False
