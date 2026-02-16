"""Data fetching module using yfinance.

This module provides a robust interface for fetching historical stock data from Yahoo Finance
with enhanced error handling, rate limiting, and data quality validation as defined
in Phase 4 analysis.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import pytz
import yfinance as yf
from loguru import logger

from utils.exceptions import (
    CircuitBreakerError,
    DataQualityError,
    InvalidTickerError,
    NetworkError,
    RateLimitError,
)

# Timezone constant
WIB = pytz.timezone("Asia/Jakarta")


class RateLimiter:
    """Adaptive rate limiting with ban detection."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests: List[datetime] = []
        self.ban_until: Optional[datetime] = None

    def wait_if_needed(self):
        """Wait if rate limit is reached or if ban is active."""
        now = datetime.now()

        # Check if we're banned
        if self.ban_until and now < self.ban_until:
            wait_seconds = (self.ban_until - now).total_seconds()
            logger.critical(f"Rate limit ban active, waiting {wait_seconds:.0f}s")
            time.sleep(wait_seconds)
            self.ban_until = None
            now = datetime.now()

        # Remove old requests outside window
        self.requests = [r for r in self.requests if now - r < self.window]

        # Wait if at limit
        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] + self.window - now).total_seconds()
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
                now = datetime.now()

        self.requests.append(now)

    def register_ban(self, duration_minutes: int = 60):
        """Register a rate limit ban from yfinance."""
        self.ban_until = datetime.now() + timedelta(minutes=duration_minutes)
        logger.critical(f"Rate limit ban registered until {self.ban_until}")


class NetworkHealthMonitor:
    """Circuit breaker for network failures."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout_seconds: int = 300):
        self.consecutive_failures = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        self.circuit_open_until: Optional[datetime] = None

    def record_failure(self):
        """Record a network failure and open circuit if threshold reached."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.circuit_open_until = datetime.now() + self.recovery_timeout
            logger.critical(
                f"Circuit breaker OPEN: {self.consecutive_failures} consecutive failures. "
                f"Retry after {self.circuit_open_until}"
            )

    def record_success(self):
        """Reset failures and close circuit."""
        if self.consecutive_failures > 0:
            logger.info(f"Network recovered after {self.consecutive_failures} failures")
        self.consecutive_failures = 0
        self.circuit_open_until = None

    def is_circuit_open(self) -> bool:
        """Check if circuit is currently open."""
        now = datetime.now()
        if self.circuit_open_until and now < self.circuit_open_until:
            return True
        if self.circuit_open_until and now >= self.circuit_open_until:
            logger.info("Circuit breaker attempting recovery")
            self.circuit_open_until = None
        return False


class DataQualityValidator:
    """Validator for OHLCV DataFrames."""

    @staticmethod
    def validate(df: pd.DataFrame, symbol: str) -> None:
        """
        Validate DataFrame integrity and quality.

        Args:
            df: DataFrame to validate
            symbol: Ticker symbol for logging

        Raises:
            DataQualityError: If data fails checks
        """
        if df is None or df.empty:
            raise DataQualityError(f"Empty or None DataFrame for {symbol}")

        # Column check
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise DataQualityError(f"Missing columns for {symbol}: {missing_cols}")

        # NaN ratio check (stricter: 10% limit)
        total_elements = len(df) * len(required_cols)
        nan_count = df[required_cols].isna().sum().sum()
        nan_ratio = nan_count / total_elements if total_elements > 0 else 0
        if nan_ratio > 0.1:
            raise DataQualityError(f"High NaN ratio ({nan_ratio:.1%}) for {symbol}")

        # Negative price check
        price_cols = ["Open", "High", "Low", "Close"]
        if (df[price_cols] < 0).any().any():
            raise DataQualityError(f"Negative prices detected for {symbol}")

        # OHLC relationship check
        # Use numpy arrays for safety against MultiIndex ambiguity and better performance
        high = df["High"].values
        low = df["Low"].values
        open_p = df["Open"].values
        close = df["Close"].values

        invalid_ohlc = (
            (high < low)
            | (high < open_p)
            | (high < close)
            | (low > open_p)
            | (low > close)
        )
        
        if invalid_ohlc.any():
            # Get indices of invalid rows
            invalid_indices = df.index[invalid_ohlc]
            raise DataQualityError(
                f"Invalid OHLC relationships for {symbol} on dates: {invalid_indices[:5].tolist()}"
            )

        # Future date check
        now_wib = datetime.now(WIB)
        # yfinance index usually contains datetime, normalize if it doesn't have tz
        df_index = df.index
        if df_index.tz is None:
             df_index = df_index.tz_localize("UTC").tz_convert(WIB)
        else:
             df_index = df_index.tz_convert(WIB)
             
        if (df_index > now_wib).any():
            raise DataQualityError(f"Future dates detected for {symbol}")


class YFinanceFetcher:
    """Fetcher class for Yahoo Finance data."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        rate_limit_requests: int = 8,
        rate_limit_window: int = 60,
    ) -> None:
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limiter = RateLimiter(
            max_requests=rate_limit_requests, window_seconds=rate_limit_window
        )
        self.network_monitor = NetworkHealthMonitor()
        self.validator = DataQualityValidator()

    def fetch_history(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        """
        Fetch historical data with retries, rate limiting, and validation.

        Args:
            symbol: Ticker symbol (e.g. 'BBCA.JK')
            period: Duration to fetch (e.g. '2y', '1mo')

        Returns:
            Validated DataFrame

        Raises:
            CircuitBreakerError: If circuit is open
            RateLimitError: If multiple retries fail with 429
            NetworkError: If connection fails
            InvalidTickerError: If ticker is not found
            DataQualityError: If data is corrupted
        """
        if self.network_monitor.is_circuit_open():
            raise CircuitBreakerError(f"Circuit open, skipping {symbol}")

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.rate_limiter.wait_if_needed()

                logger.debug(f"Fetching {symbol} (attempt {attempt}/{self.max_retries})")
                
                # yf.download is the standard method
                # We also need to handle the case where yfinance returns an empty DF for 
                # non-existent tickers instead of raising an error.
                df = yf.download(symbol, period=period, progress=False, threads=False)

                if df.empty:
                    # Specific check for invalid ticker
                    ticker = yf.Ticker(symbol)
                    info = ticker.history(period="1d")
                    if info.empty:
                         raise InvalidTickerError(f"Ticker '{symbol}' not found or no data available")
                    # If info is not empty but df was, it might be a temporary issue
                    raise NetworkError(f"Received empty data for {symbol}")

                # Flatten MultiIndex columns if present (common in recent yfinance)
                if isinstance(df.columns, pd.MultiIndex):
                    try:
                        # Case: (Price, Ticker) -> Drop Ticker level
                        if df.columns.nlevels == 2:
                            # Check if symbol is in level 1
                            if symbol in df.columns.get_level_values(1):
                                df = df.xs(symbol, axis=1, level=1)
                            else:
                                 # Fallback: drop level 1
                                 df.columns = df.columns.droplevel(1)
                    except Exception as e:
                        logger.warning(f"Failed to flatten MultiIndex for {symbol}: {e}")

                # Validate
                self.validator.validate(df, symbol)

                # Normalize Index to WIB and Date-only
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                df.index = df.index.tz_convert(WIB).normalize()

                # Successful fetch
                self.network_monitor.record_success()
                return df

            except (InvalidTickerError, DataQualityError):
                # Don't retry these as they are data/input related
                raise

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                if "429" in error_msg or "rate limit" in error_msg:
                    logger.warning(f"Rate limit hit for {symbol}")
                    if attempt == self.max_retries:
                        self.rate_limiter.register_ban(duration_minutes=60)
                        raise RateLimitError(f"Persistent rate limit for {symbol}") from e
                
                elif "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
                    logger.error(f"Network error for {symbol}: {e}")
                    if attempt == self.max_retries:
                         self.network_monitor.record_failure()
                         raise NetworkError(f"Failed to fetch {symbol} after {attempt} attempts") from e
                
                else:
                    logger.error(f"Unexpected error fetching {symbol}: {e}")
                    if attempt == self.max_retries:
                        raise NetworkError(f"Unexpected failure for {symbol}") from e

                # Wait before retry
                wait_time = self.retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                time.sleep(wait_time)

        # Fallback (should not reach here as we raise in loop if attempt == max_retries)
        raise NetworkError(f"Fetch failed for {symbol}: {last_error}")
