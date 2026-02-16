"""Unit tests for database schemas."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from db.schemas import DailyPriceBase, MarketCapCategory, PipelineRun, StockCreate


class TestStockSchema:
    """Test Stock schema validation."""

    def test_valid_stock(self):
        """Test valid stock creation."""
        stock = StockCreate(
            symbol="BBCA.JK",
            name="Bank Central Asia",
            sector="Finance",
            market_cap=MarketCapCategory.LARGE
        )
        assert stock.symbol == "BBCA.JK"
        assert stock.is_active is True

    def test_invalid_symbol(self):
        """Test invalid symbol pattern (missing .JK)."""
        with pytest.raises(ValidationError):
            StockCreate(symbol="BBCA", name="Test")

    def test_lowercase_symbol(self):
        """Test lowercase symbol (invalid pattern)."""
        with pytest.raises(ValidationError):
            StockCreate(symbol="bbca.jk", name="Test")


class TestDailyPriceSchema:
    """Test DailyPrice schema validation."""

    def test_valid_price(self):
        """Test valid price relationships."""
        price = DailyPriceBase(
            symbol="BBCA.JK",
            date=datetime.now(timezone.utc) - timedelta(days=1),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000000,
            adjusted_close=102.0
        )
        assert price.high >= price.low
        assert price.high >= price.open
        assert price.high >= price.close
        assert price.low <= price.open
        assert price.low <= price.close

    def test_invalid_high_low(self):
        """Test High cannot be lower than Low."""
        with pytest.raises(ValidationError, match="High.*cannot be lower than Low"):
            DailyPriceBase(
                symbol="BBCA.JK",
                date=datetime.now(timezone.utc) - timedelta(days=1),
                open=100.0,
                high=90.0,  # Invalid: Lower than Low
                low=95.0,
                close=98.0,
                volume=1000,
                adjusted_close=98.0
            )

    def test_invalid_high_open(self):
        """Test High cannot be lower than Open."""
        with pytest.raises(ValidationError, match="High.*cannot be lower than Open"):
            DailyPriceBase(
                symbol="BBCA.JK",
                date=datetime.now(timezone.utc) - timedelta(days=1),
                open=100.0,
                high=99.0,  # Invalid
                low=90.0,
                close=95.0,
                volume=1000,
                adjusted_close=95.0
            )

    def test_invalid_low_close(self):
        """Test Low cannot be higher than Close."""
        with pytest.raises(ValidationError, match="Low.*cannot be higher than Close"):
            DailyPriceBase(
                symbol="BBCA.JK",
                date=datetime.now(timezone.utc) - timedelta(days=1),
                open=110.0,  # Valid relative to Low
                high=115.0,
                low=105.0, # Invalid: Higher than Close
                close=100.0,
                volume=1000,
                adjusted_close=100.0
            )

    def test_future_date(self):
        """Test price date cannot be in the future."""
        future_date = datetime.now(timezone.utc) + timedelta(days=1)
        with pytest.raises(ValidationError, match="cannot be in the future"):
            DailyPriceBase(
                symbol="BBCA.JK",
                date=future_date,
                open=100.0,
                high=105.0,
                low=95.0,
                close=100.0,
                volume=1000,
                adjusted_close=100.0
            )


class TestPipelineRunSchema:
    """Test PipelineRun schema validation."""

    def test_valid_run(self):
        """Test valid pipeline run."""
        run = PipelineRun(
            date=datetime.now(timezone.utc),
            duration=120.5,
            total_stocks=10,
            success_count=8,
            fail_count=2,
            errors=[]
        )
        assert run.total_stocks == 10

    def test_invalid_counts(self):
        """Test sum of counts must equal total."""
        with pytest.raises(ValidationError, match="Sum of success.*must equal total"):
            PipelineRun(
                date=datetime.now(timezone.utc),
                duration=100.0,
                total_stocks=10,
                success_count=5,
                fail_count=4,  # Sum is 9, not 10
                errors=[]
            )

    def test_future_run_date(self):
        """Test run date cannot be in the future."""
        future_date = datetime.now(timezone.utc) + timedelta(days=1)
        with pytest.raises(ValidationError, match="cannot be in the future"):
            PipelineRun(
                date=future_date,
                duration=10.0,
                total_stocks=0,
                success_count=0,
                fail_count=0
            )
