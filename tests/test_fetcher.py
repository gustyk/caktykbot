"""Unit tests for the data fetcher module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pydantic import ValidationError

from data.fetcher import (
    DataQualityValidator,
    NetworkHealthMonitor,
    RateLimiter,
    YFinanceFetcher,
)
from utils.exceptions import (
    CircuitBreakerError,
    DataQualityError,
    InvalidTickerError,
    NetworkError,
    RateLimitError,
)


@pytest.fixture
def valid_ohlcv_df():
    """Create a valid sample DataFrame."""
    dates = pd.date_range(start="2023-01-01", periods=5, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [105.0, 106.0, 107.0, 108.0, 109.0],
            "Low": [95.0, 96.0, 97.0, 98.0, 99.0],
            "Close": [102.0, 103.0, 104.0, 105.0, 106.0],
            "Volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=dates,
    )
    return df


class TestRateLimiter:
    """Test RateLimiter functionality."""

    @patch("time.sleep")
    def test_rate_limit_wait(self, mock_sleep):
        """Test that rate limiter triggers sleep when limit reached."""
        limiter = RateLimiter(max_requests=2, window_seconds=10)
        
        # First two requests should not wait
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        assert mock_sleep.call_count == 0
        
        # Third request should trigger wait
        limiter.wait_if_needed()
        assert mock_sleep.call_count == 1

    @patch("time.sleep")
    def test_ban_logic(self, mock_sleep):
        """Test that ban registers and triggers sleep."""
        limiter = RateLimiter()
        limiter.register_ban(duration_minutes=1)
        
        assert limiter.ban_until is not None
        limiter.wait_if_needed()
        assert mock_sleep.call_count == 1
        assert limiter.ban_until is None  # Reset after wait


class TestNetworkHealthMonitor:
    """Test NetworkHealthMonitor (Circuit Breaker)."""

    def test_circuit_opens_on_failures(self):
        """Test that circuit opens after threshold reached."""
        monitor = NetworkHealthMonitor(failure_threshold=2, recovery_timeout_seconds=60)
        
        assert monitor.is_circuit_open() is False
        
        monitor.record_failure()
        assert monitor.is_circuit_open() is False
        
        monitor.record_failure()
        assert monitor.is_circuit_open() is True
        
    def test_reset_on_success(self):
        """Test success resets the failure count."""
        monitor = NetworkHealthMonitor(failure_threshold=2)
        monitor.record_failure()
        monitor.record_success()
        monitor.record_failure()
        assert monitor.is_circuit_open() is False


class TestDataQualityValidator:
    """Test DataQualityValidator rules."""

    def test_validate_valid(self, valid_ohlcv_df):
        """Test valid data passes."""
        DataQualityValidator.validate(valid_ohlcv_df, "TEST.JK")

    def test_validate_empty(self):
        """Test empty df raises error."""
        with pytest.raises(DataQualityError, match="Empty"):
            DataQualityValidator.validate(pd.DataFrame(), "TEST.JK")

    def test_validate_missing_columns(self):
        """Test missing columns detection."""
        df = pd.DataFrame({"Open": [100.0]})
        with pytest.raises(DataQualityError, match="Missing columns"):
            DataQualityValidator.validate(df, "TEST.JK")

    def test_validate_negative_prices(self):
        """Test negative price detection."""
        df = pd.DataFrame({
            "Open": [-100.0], "High": [110.0], "Low": [90.0], "Close": [105.0], "Volume": [1000]
        }, index=pd.date_range("2023-01-01", periods=1))
        with pytest.raises(DataQualityError, match="Negative prices"):
            DataQualityValidator.validate(df, "TEST.JK")

    def test_validate_invalid_ohlc(self):
        """Test OHLC relationship validation (High < Low)."""
        df = pd.DataFrame({
            "Open": [100.0], "High": [90.0], "Low": [95.0], "Close": [105.0], "Volume": [1000]
        }, index=pd.date_range("2023-01-01", periods=1))
        with pytest.raises(DataQualityError, match="Invalid OHLC"):
            DataQualityValidator.validate(df, "TEST.JK")

    def test_validate_future_date(self):
        """Test future date detection."""
        future_date = datetime.now(timezone.utc) + timedelta(days=5)
        df = pd.DataFrame({
            "Open": [100.0], "High": [110.0], "Low": [90.0], "Close": [105.0], "Volume": [1000]
        }, index=pd.DatetimeIndex([future_date]))
        with pytest.raises(DataQualityError, match="Future dates"):
            DataQualityValidator.validate(df, "TEST.JK")


class TestYFinanceFetcher:
    """Integrated tests for YFinanceFetcher."""

    @pytest.fixture
    def fetcher(self):
        """Fetcher with minimal delays for testing."""
        return YFinanceFetcher(max_retries=2, retry_delay=0.01)

    @patch("yfinance.download")
    def test_fetch_success(self, mock_download, fetcher, valid_ohlcv_df):
        """Test successful fetch and normalization."""
        mock_download.return_value = valid_ohlcv_df
        
        result = fetcher.fetch_history("BBCA.JK")
        
        assert not result.empty
        assert result.index.tz is not None  # Normalized to WIB
        # Check normalize component (time should be 00:00:00)
        assert result.index[0].hour == 0
        assert result.index[0].minute == 0

    @patch("yfinance.download")
    @patch("yfinance.Ticker")
    def test_fetch_invalid_ticker(self, mock_ticker, mock_download, fetcher):
        """Test handling of invalid tickers."""
        mock_download.return_value = pd.DataFrame() # yfinance returns empty for bad tickers
        # Mock Ticker.history to return empty as well
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        
        with pytest.raises(InvalidTickerError):
            fetcher.fetch_history("INVALID.JK")

    @patch("yfinance.download")
    @patch("time.sleep")
    def test_fetch_retry_on_network_error(self, mock_sleep, mock_download, fetcher, valid_ohlcv_df):
        """Test retry logic on network failure."""
        # Fail once, then succeed
        mock_download.side_effect = [Exception("Connection error"), valid_ohlcv_df]
        
        result = fetcher.fetch_history("BBCA.JK")
        assert not result.empty
        assert mock_download.call_count == 2

    @patch("yfinance.download")
    def test_fetch_circuit_breaker(self, mock_download, fetcher):
        """Test that circuit breaker eventually aborts."""
        # Set threshold to 1 for quick test
        fetcher.network_monitor.failure_threshold = 1
        mock_download.side_effect = Exception("Persistent Network Failure")
        
        # Exhaust retries on first call (will record 1 failure)
        with pytest.raises(NetworkError):
            fetcher.fetch_history("FAIL.JK")
            
        # Circuit should now be open
        assert fetcher.network_monitor.is_circuit_open() is True
        
        # Second call should immediately raise CircuitBreakerError without calling download
        mock_download.reset_mock()
        with pytest.raises(CircuitBreakerError):
            fetcher.fetch_history("FAIL.JK")
        
        assert mock_download.call_count == 0

    @patch("yfinance.download")
    def test_fetch_rate_limit_ban(self, mock_download, fetcher):
        """Test that persistent 429 triggers a ban."""
        mock_download.side_effect = Exception("HTTP 429: Too Many Requests")
        
        with pytest.raises(RateLimitError):
            fetcher.fetch_history("LIMIT.JK")
            
        assert fetcher.rate_limiter.ban_until is not None


    @patch("yfinance.download")
    def test_fetch_unexpected_error(self, mock_download, fetcher):
        """Test handling of unexpected errors."""
        mock_download.side_effect = Exception("Unknown mess")
        with pytest.raises(NetworkError, match="Unexpected failure"):
            fetcher.fetch_history("CRASH.JK")

    def test_circuit_breaker_recovery_attempt(self):
        """Test circuit breaker attempting recovery after timeout."""
        monitor = NetworkHealthMonitor(failure_threshold=1, recovery_timeout_seconds=0)
        monitor.record_failure()
        assert monitor.circuit_open_until is not None
        # Since timeout is 0, it should attempt recovery
        assert monitor.is_circuit_open() is False
        assert monitor.circuit_open_until is None
