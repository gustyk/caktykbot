"""Tests for settings validation."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config.settings import Settings
from utils.exceptions import InvalidSettingsError


class TestSettingsValidation:
    """Test settings validation logic."""

    def test_valid_settings(self):
        """Test settings with all valid values."""
        settings = Settings(
            MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net/",
            MONGO_DB_NAME="caktykbot",
            TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
            TELEGRAM_CHAT_ID="123456789",
            MAX_WATCHLIST=20,
            FETCH_RETRY_COUNT=3,
            FETCH_RETRY_DELAY=2.0,
            LOG_LEVEL="INFO",
            TIMEZONE="Asia/Jakarta",
            ENVIRONMENT="development",
        )

        assert settings.MONGO_URI.startswith("mongodb+srv://")
        assert settings.MONGO_DB_NAME == "caktykbot"
        assert settings.MAX_WATCHLIST == 20
        assert settings.TIMEZONE == "Asia/Jakarta"

    def test_mongo_uri_validation_empty(self):
        """Test MONGO_URI cannot be empty."""
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
            )

    def test_mongo_uri_validation_invalid_prefix(self):
        """Test MONGO_URI must start with mongodb:// or mongodb+srv://."""
        with pytest.raises((ValidationError, InvalidSettingsError), match="must start with"):
            Settings(
                MONGO_URI="http://invalid.com",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
            )

    def test_mongo_db_name_validation_invalid_chars(self):
        """Test MONGO_DB_NAME cannot contain invalid characters."""
        with pytest.raises((ValidationError, InvalidSettingsError), match="invalid characters"):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                MONGO_DB_NAME="invalid/name",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
            )

    def test_telegram_bot_token_validation_empty(self):
        """Test TELEGRAM_BOT_TOKEN cannot be empty."""
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="",
                TELEGRAM_CHAT_ID="123456789",
            )

    def test_telegram_bot_token_validation_invalid_format(self):
        """Test TELEGRAM_BOT_TOKEN must match expected format."""
        with pytest.raises((ValidationError, InvalidSettingsError), match="format invalid"):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="invalid_token",
                TELEGRAM_CHAT_ID="123456789",
            )

    def test_telegram_bot_token_validation_short_token(self):
        """Test TELEGRAM_BOT_TOKEN token part must be 35 characters."""
        with pytest.raises((ValidationError, InvalidSettingsError), match="format invalid"):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:SHORT",
                TELEGRAM_CHAT_ID="123456789",
            )

    def test_telegram_chat_id_validation_empty(self):
        """Test TELEGRAM_CHAT_ID cannot be empty."""
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="",
            )

    def test_telegram_chat_id_validation_non_numeric(self):
        """Test TELEGRAM_CHAT_ID must be numeric."""
        with pytest.raises((ValidationError, InvalidSettingsError), match="must be numeric"):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="not_a_number",
            )

    def test_telegram_chat_id_validation_negative(self):
        """Test TELEGRAM_CHAT_ID can be negative (for groups)."""
        settings = Settings(
            MONGO_URI="mongodb://localhost:27017/",
            TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
            TELEGRAM_CHAT_ID="-123456789",
        )
        assert settings.TELEGRAM_CHAT_ID == "-123456789"

    def test_max_watchlist_validation_range(self):
        """Test MAX_WATCHLIST must be between 1 and 100."""
        # Too low
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                MAX_WATCHLIST=0,
            )

        # Too high
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                MAX_WATCHLIST=101,
            )

        # Valid
        settings = Settings(
            MONGO_URI="mongodb://localhost:27017/",
            TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
            TELEGRAM_CHAT_ID="123456789",
            MAX_WATCHLIST=50,
        )
        assert settings.MAX_WATCHLIST == 50

    def test_fetch_retry_count_validation_range(self):
        """Test FETCH_RETRY_COUNT must be between 1 and 10."""
        # Too low
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                FETCH_RETRY_COUNT=0,
            )

        # Too high
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                FETCH_RETRY_COUNT=11,
            )

    def test_fetch_retry_delay_validation_range(self):
        """Test FETCH_RETRY_DELAY must be between 0.5 and 30.0."""
        # Too low
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                FETCH_RETRY_DELAY=0.1,
            )

        # Too high
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                FETCH_RETRY_DELAY=31.0,
            )

    def test_log_level_validation_enum(self):
        """Test LOG_LEVEL must be valid enum value."""
        # Invalid
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                LOG_LEVEL="INVALID",
            )

        # Valid
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                LOG_LEVEL=level,
            )
            assert settings.LOG_LEVEL == level

    def test_timezone_validation_invalid(self):
        """Test TIMEZONE must be valid pytz timezone."""
        with pytest.raises((ValidationError, InvalidSettingsError), match="Invalid timezone"):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                TIMEZONE="Invalid/Timezone",
            )

    def test_timezone_validation_valid(self):
        """Test TIMEZONE accepts valid pytz timezones."""
        for tz in ["Asia/Jakarta", "UTC", "America/New_York", "Europe/London"]:
            settings = Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                TIMEZONE=tz,
            )
            assert settings.TIMEZONE == tz

    def test_environment_validation_enum(self):
        """Test ENVIRONMENT must be valid enum value."""
        # Invalid
        with pytest.raises(ValidationError):
            Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                ENVIRONMENT="invalid",
            )

        # Valid
        for env in ["development", "production", "test"]:
            settings = Settings(
                MONGO_URI="mongodb://localhost:27017/",
                TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
                TELEGRAM_CHAT_ID="123456789",
                ENVIRONMENT=env,
            )
            assert settings.ENVIRONMENT == env

    def test_get_timezone_method(self):
        """Test get_timezone() returns pytz timezone object."""
        settings = Settings(
            MONGO_URI="mongodb://localhost:27017/",
            TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
            TELEGRAM_CHAT_ID="123456789",
            TIMEZONE="Asia/Jakarta",
        )

        tz = settings.get_timezone()
        assert str(tz) == "Asia/Jakarta"

    def test_default_values(self):
        """Test default values are applied correctly."""
        settings = Settings(
            MONGO_URI="mongodb://localhost:27017/",
            TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
            TELEGRAM_CHAT_ID="123456789",
        )

        assert settings.MONGO_DB_NAME == "caktykbot"
        assert settings.MAX_WATCHLIST == 20
        assert settings.FETCH_RETRY_COUNT == 3
        assert settings.FETCH_RETRY_DELAY == 2.0
        assert settings.LOG_LEVEL == "INFO"
        assert settings.TIMEZONE == "Asia/Jakarta"
        assert settings.ENVIRONMENT == "development"
