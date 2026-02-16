"""Unit tests for technical indicators logic."""

import pandas as pd
import pytest

from logic.indicators import IndicatorEngine, validate_sufficient_data
from utils.exceptions import InsufficientDataError


@pytest.fixture
def sample_ohlcv():
    """Create a sample OHLCV DataFrame for 250 days."""
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
    df = pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(250)],
            "High": [105.0 + i for i in range(250)],
            "Low": [95.0 + i for i in range(250)],
            "Close": [102.0 + i for i in range(250)],
            "Volume": [1000 + i for i in range(250)],
        },
        index=dates,
    )
    return df


class TestIndicatorEngine:
    """Test IndicatorEngine logic and properties."""

    def test_calculate_ema_properties(self, sample_ohlcv):
        """Test EMA calculation properties."""
        close = sample_ohlcv["Close"]
        ema_8 = IndicatorEngine.calculate_ema(close, 8)
        
        assert len(ema_8) == len(close)
        assert not ema_8.isna().all()
        # In a trending up series, EMA should be lagging but following
        assert ema_8.iloc[-1] > ema_8.iloc[0]
        # EMA should stay within price range
        assert ema_8.min() >= close.min()
        assert ema_8.max() <= close.max()

    def test_calculate_atr(self, sample_ohlcv):
        """Test ATR calculation."""
        atr = IndicatorEngine.calculate_atr(sample_ohlcv, 14)
        assert len(atr) == len(sample_ohlcv)
        # First row after shift(1) should be NaN or handled
        # Our implementation uses ewm which handles NaN fairly well, 
        # but TR calculation for first item might be problematic if not handled.
        # In our implementation: tr2/tr3 will be NaN for first row.
        # So ATR[0] might be based on just TR1.
        assert not atr.isna().all()
        assert (atr > 0).all() or atr.isna().any()

    def test_calculate_all_columns(self, sample_ohlcv):
        """Test that all required columns are created."""
        result = IndicatorEngine.calculate_all(sample_ohlcv)
        
        expected_cols = [
            "ema_8", "ema_21", "ema_50", "ema_150", "ema_200", 
            "atr_14", "vol_ma_20"
        ]
        for col in expected_cols:
            assert col in result.columns
            assert not result[col].dropna().empty

    def test_insufficient_data_validation(self, sample_ohlcv):
        """Test sufficient data validation logic."""
        # This passes
        validate_sufficient_data(sample_ohlcv, 200)
        
        # This fails
        short_df = sample_ohlcv.iloc[:50]
        with pytest.raises(InsufficientDataError):
            validate_sufficient_data(short_df, 200)

    def test_ema_short_data(self):
        """Test EMA behavior with data shorter than period."""
        short_series = pd.Series([10, 11, 12])
        ema_50 = IndicatorEngine.calculate_ema(short_series, 50)
        assert ema_50.isna().all()
