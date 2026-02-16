"""Tests for custom exception hierarchy."""

import pytest

from utils.exceptions import (
    BotCommandError,
    CakTykBotError,
    CircuitBreakerError,
    ConfigurationError,
    ConnectionError,
    DatabaseError,
    DataFetchError,
    DataQualityError,
    DuplicatePipelineRunError,
    DuplicateStockError,
    IndicatorError,
    InsufficientDataError,
    InvalidDataTypeError,
    InvalidSettingsError,
    InvalidSymbolError,
    InvalidTickerError,
    NetworkError,
    PipelineAbortError,
    PipelineError,
    PriceRepoError,
    RateLimitError,
    ReferentialIntegrityError,
    StockNotFoundError,
    StockRepoError,
    TelegramBotError,
    WatchlistFullError,
)


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_base_exception(self):
        """Test base exception can be raised."""
        with pytest.raises(CakTykBotError):
            raise CakTykBotError("Test error")

    def test_configuration_errors_inherit_from_base(self):
        """Test configuration errors inherit from CakTykBotError."""
        with pytest.raises(CakTykBotError):
            raise ConfigurationError("Config error")

        with pytest.raises(CakTykBotError):
            raise InvalidSettingsError("Invalid settings")

    def test_database_errors_inherit_from_base(self):
        """Test database errors inherit from CakTykBotError."""
        with pytest.raises(CakTykBotError):
            raise DatabaseError("Database error")

        with pytest.raises(CakTykBotError):
            raise ConnectionError("Connection error")

    def test_stock_repo_errors_inherit_from_database_error(self):
        """Test stock repository errors inherit from DatabaseError."""
        with pytest.raises(DatabaseError):
            raise StockRepoError("Stock repo error")

        with pytest.raises(DatabaseError):
            raise DuplicateStockError("Duplicate stock")

        with pytest.raises(DatabaseError):
            raise WatchlistFullError("Watchlist full")

        with pytest.raises(DatabaseError):
            raise StockNotFoundError("Stock not found")

    def test_price_repo_errors_inherit_from_database_error(self):
        """Test price repository errors inherit from DatabaseError."""
        with pytest.raises(DatabaseError):
            raise PriceRepoError("Price repo error")

        with pytest.raises(DatabaseError):
            raise ReferentialIntegrityError("Referential integrity error")

    def test_data_fetch_errors_inherit_from_base(self):
        """Test data fetch errors inherit from CakTykBotError."""
        with pytest.raises(CakTykBotError):
            raise DataFetchError("Data fetch error")

        with pytest.raises(CakTykBotError):
            raise InvalidSymbolError("Invalid symbol")

        with pytest.raises(CakTykBotError):
            raise InvalidTickerError("Invalid ticker")

        with pytest.raises(CakTykBotError):
            raise NetworkError("Network error")

        with pytest.raises(CakTykBotError):
            raise RateLimitError("Rate limit error")

        with pytest.raises(CakTykBotError):
            raise DataQualityError("Data quality error")

    def test_indicator_errors_inherit_from_base(self):
        """Test indicator errors inherit from CakTykBotError."""
        with pytest.raises(CakTykBotError):
            raise IndicatorError("Indicator error")

        with pytest.raises(CakTykBotError):
            raise InsufficientDataError("Insufficient data")

        with pytest.raises(CakTykBotError):
            raise InvalidDataTypeError("Invalid data type")

    def test_pipeline_errors_inherit_from_base(self):
        """Test pipeline errors inherit from CakTykBotError."""
        with pytest.raises(CakTykBotError):
            raise PipelineError("Pipeline error")

        with pytest.raises(CakTykBotError):
            raise DuplicatePipelineRunError("Duplicate pipeline run")

        with pytest.raises(CakTykBotError):
            raise PipelineAbortError("Pipeline abort")

    def test_circuit_breaker_error_inherits_from_base(self):
        """Test circuit breaker error inherits from CakTykBotError."""
        with pytest.raises(CakTykBotError):
            raise CircuitBreakerError("Circuit breaker open")

    def test_telegram_bot_errors_inherit_from_base(self):
        """Test Telegram bot errors inherit from CakTykBotError."""
        with pytest.raises(CakTykBotError):
            raise TelegramBotError("Telegram bot error")

        with pytest.raises(CakTykBotError):
            raise BotCommandError("Bot command error")

    def test_exception_messages(self):
        """Test exceptions can carry custom messages."""
        error_message = "Custom error message"

        try:
            raise InvalidSettingsError(error_message)
        except InvalidSettingsError as e:
            assert str(e) == error_message

    def test_exception_chaining(self):
        """Test exceptions can be chained."""
        original_error = ValueError("Original error")

        try:
            raise ConnectionError("Connection failed") from original_error
        except ConnectionError as e:
            assert e.__cause__ == original_error

    def test_catch_by_base_class(self):
        """Test specific exceptions can be caught by base class."""
        # Catch specific error by base class
        with pytest.raises(DatabaseError):
            raise DuplicateStockError("Duplicate")

        # Catch any error by root base class
        with pytest.raises(CakTykBotError):
            raise InvalidTickerError("Invalid ticker")

    def test_catch_by_specific_class(self):
        """Test exceptions can be caught by specific class."""
        with pytest.raises(DuplicateStockError):
            raise DuplicateStockError("Duplicate stock")

        with pytest.raises(WatchlistFullError):
            raise WatchlistFullError("Watchlist full")
