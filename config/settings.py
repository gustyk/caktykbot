"""Application settings with comprehensive validation.

This module implements enhanced settings management using Pydantic v2,
with all validation requirements from Phase 3 (Module Contract Enforcement).
"""

import re
import sys
from typing import Literal

import pytz
from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from utils.exceptions import InvalidSettingsError


class Settings(BaseSettings):
    """Application settings with validation.

    All settings are loaded from environment variables with comprehensive
    validation to prevent cryptic runtime errors.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # MongoDB Configuration
    MONGO_URI: str = Field(
        ...,
        description="MongoDB connection URI (mongodb:// or mongodb+srv://)",
    )
    MONGO_DB_NAME: str = Field(
        default="caktykbot",
        max_length=64,
        description="MongoDB database name",
    )

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = Field(
        ...,
        description="Telegram bot token from @BotFather",
    )
    TELEGRAM_CHAT_ID: str = Field(
        ...,
        description="Telegram chat ID for notifications",
    )

    # Application Configuration
    MAX_WATCHLIST: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of stocks in watchlist",
    )
    
    # Risk Management Defaults (Sprint 4)
    DEFAULT_MAX_HEAT: float = 0.08
    DEFAULT_HEAT_WARNING: float = 0.06
    DEFAULT_MAX_EXPOSURE: float = 0.25
    DEFAULT_SMALL_CAP_EXPOSURE: float = 0.15
    DEFAULT_CASH_RESERVE: float = 0.30
    DEFAULT_CORRELATION_THRESHOLD: float = 0.7
    DEFAULT_MAX_SECTOR_STOCKS: int = 2
    
    CB_DRAWDOWN_THRESHOLD: float = 0.10      # 10% drawdown
    CB_CONSECUTIVE_LOSS_THRESHOLD: int = 5   # 5 losses
    CB_DRAWDOWN_SUSPEND_DAYS: int = 7
    CB_LOSS_SUSPEND_DAYS: int = 3

    FETCH_RETRY_COUNT: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of retries for failed fetches",
    )
    FETCH_RETRY_DELAY: float = Field(
        default=2.0,
        ge=0.5,
        le=30.0,
        description="Delay between retries in seconds",
    )
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    TIMEZONE: str = Field(
        default="Asia/Jakarta",
        description="Timezone for scheduler (must be valid pytz timezone)",
    )
    ENVIRONMENT: Literal["development", "production", "test"] = Field(
        default="development",
        description="Application environment",
    )

    @field_validator("MONGO_URI")
    @classmethod
    def validate_mongo_uri(cls, v: str) -> str:
        """Validate MongoDB URI format.

        Args:
            v: MongoDB URI string

        Returns:
            Validated URI

        Raises:
            InvalidSettingsError: If URI format is invalid
        """
        if not v:
            raise InvalidSettingsError("MONGO_URI cannot be empty")

        if not v.startswith(("mongodb://", "mongodb+srv://")):
            raise InvalidSettingsError(
                "MONGO_URI must start with 'mongodb://' or 'mongodb+srv://'. "
                f"Got: {v[:20]}..."
            )

        return v

    @field_validator("MONGO_DB_NAME")
    @classmethod
    def validate_mongo_db_name(cls, v: str) -> str:
        """Validate MongoDB database name.

        Args:
            v: Database name

        Returns:
            Validated database name

        Raises:
            InvalidSettingsError: If database name is invalid
        """
        if not v:
            raise InvalidSettingsError("MONGO_DB_NAME cannot be empty")

        # MongoDB database name restrictions
        invalid_chars = r'[/\\. "$*<>:|?]'
        if re.search(invalid_chars, v):
            raise InvalidSettingsError(
                f"MONGO_DB_NAME contains invalid characters. "
                f"Cannot contain: / \\ . \" $ * < > : | ?"
            )

        return v

    @field_validator("TELEGRAM_BOT_TOKEN")
    @classmethod
    def validate_telegram_token(cls, v: str) -> str:
        """Validate Telegram bot token format.

        Expected format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz (35 chars after colon)

        Args:
            v: Telegram bot token

        Returns:
            Validated token

        Raises:
            InvalidSettingsError: If token format is invalid
        """
        if not v:
            raise InvalidSettingsError("TELEGRAM_BOT_TOKEN cannot be empty")

        # Format: <bot_id>:<token>
        # bot_id: digits
        # token: 35 characters (alphanumeric, underscore, hyphen)
        pattern = r"^\d+:[A-Za-z0-9_-]{35}$"
        if not re.match(pattern, v):
            raise InvalidSettingsError(
                "TELEGRAM_BOT_TOKEN format invalid. "
                "Expected format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz (35 chars after colon)"
            )

        return v

    @field_validator("TELEGRAM_CHAT_ID")
    @classmethod
    def validate_telegram_chat_id(cls, v: str) -> str:
        """Validate Telegram chat ID format.

        Args:
            v: Telegram chat ID

        Returns:
            Validated chat ID

        Raises:
            InvalidSettingsError: If chat ID format is invalid
        """
        if not v:
            raise InvalidSettingsError("TELEGRAM_CHAT_ID cannot be empty")

        # Chat ID can be negative (groups) or positive (users)
        if not re.match(r"^-?\d+$", v):
            raise InvalidSettingsError(
                "TELEGRAM_CHAT_ID must be numeric (can be negative for groups)"
            )

        return v

    @field_validator("TIMEZONE")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string.

        Args:
            v: Timezone string

        Returns:
            Validated timezone

        Raises:
            InvalidSettingsError: If timezone is invalid
        """
        if not v:
            raise InvalidSettingsError("TIMEZONE cannot be empty")

        if v not in pytz.all_timezones:
            # Provide helpful error with suggestions
            suggestions = [tz for tz in pytz.all_timezones if "Jakarta" in tz or "Asia" in tz][:5]
            raise InvalidSettingsError(
                f"Invalid timezone: '{v}'. Must be a valid pytz timezone. "
                f"Suggestions: {', '.join(suggestions)}"
            )

        return v

    def get_timezone(self) -> pytz.BaseTzInfo:
        """Get pytz timezone object.

        Returns:
            pytz timezone object
        """
        return pytz.timezone(self.TIMEZONE)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get global settings instance (singleton pattern).

    Returns:
        Settings instance

    Raises:
        InvalidSettingsError: If settings validation fails
        SystemExit: If critical configuration error occurs
    """
    global _settings

    if _settings is None:
        try:
            _settings = Settings()
            logger.info(
                f"Settings loaded successfully (environment: {_settings.ENVIRONMENT}, "
                f"timezone: {_settings.TIMEZONE})"
            )
        except Exception as e:
            logger.critical(f"Failed to load settings: {e}")
            logger.critical("Application cannot start without valid configuration")
            sys.exit(1)

    return _settings


class SettingsProxy:
    """Lazy proxy for settings to prevent initialization on import."""

    def __getattr__(self, name):
        return getattr(get_settings(), name)


# Global settings instance (lazy)
settings: Settings = SettingsProxy()  # type: ignore
