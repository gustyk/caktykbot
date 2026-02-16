"""Custom exception hierarchy for CakTykBot.

This module defines all custom exceptions used throughout the application,
following the analysis from Phase 3 (Module Contract Enforcement).
"""


# Base Exception
class CakTykBotError(Exception):
    """Base exception for all CakTykBot errors."""

    pass


# Configuration Errors
class ConfigurationError(CakTykBotError):
    """Base class for configuration-related errors."""

    pass


class InvalidSettingsError(ConfigurationError, ValueError):
    """Raised when settings validation fails."""

    pass


# Database Errors
class DatabaseError(CakTykBotError):
    """Base class for database-related errors."""

    pass


class ConnectionError(DatabaseError):
    """Raised when MongoDB connection fails."""

    pass


class StockRepoError(DatabaseError):
    """Base class for stock repository errors."""

    pass


class DuplicateStockError(StockRepoError):
    """Raised when attempting to add a duplicate stock."""

    pass


class WatchlistFullError(StockRepoError):
    """Raised when watchlist has reached maximum capacity."""

    pass


class StockNotFoundError(StockRepoError):
    """Raised when stock is not found in watchlist."""

    pass


class PriceRepoError(DatabaseError):
    """Base class for price repository errors."""

    pass


class ReferentialIntegrityError(PriceRepoError):
    """Raised when price data references non-existent stock."""

    pass


# Data Fetching Errors
class DataFetchError(CakTykBotError):
    """Base class for data fetching errors."""

    pass


class InvalidSymbolError(DataFetchError):
    """Raised when stock symbol format is invalid."""

    pass


class InvalidTickerError(DataFetchError):
    """Raised when ticker is not found in yfinance."""

    pass


class NetworkError(DataFetchError):
    """Raised when network request fails."""

    pass


class RateLimitError(DataFetchError):
    """Raised when rate limit is exceeded."""

    pass


class DataQualityError(DataFetchError):
    """Raised when fetched data fails quality checks."""

    pass


# Indicator Calculation Errors
class IndicatorError(CakTykBotError):
    """Base class for indicator calculation errors."""

    pass


class InsufficientDataError(IndicatorError):
    """Raised when insufficient data for indicator calculation."""

    pass


class InvalidDataTypeError(IndicatorError):
    """Raised when data type is invalid for calculation."""

    pass


# Pipeline Errors
class PipelineError(CakTykBotError):
    """Base class for pipeline errors."""

    pass


class DuplicatePipelineRunError(PipelineError):
    """Raised when pipeline is already running or ran today."""

    pass


class PipelineAbortError(PipelineError):
    """Raised when pipeline must abort due to critical error."""

    pass


# Circuit Breaker Errors
class CircuitBreakerError(CakTykBotError):
    """Raised when circuit breaker is open."""

    pass


# Telegram Bot Errors
class TelegramBotError(CakTykBotError):
    """Base class for Telegram bot errors."""

    pass


class BotCommandError(TelegramBotError):
    """Raised when bot command execution fails."""

    pass
