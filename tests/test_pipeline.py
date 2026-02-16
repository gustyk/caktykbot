"""Unit tests for the data pipeline orchestration."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.pipeline import DataPipeline
from db.schemas import PipelineRun, StockInDB
from utils.exceptions import DataQualityError, NetworkError


@pytest.fixture
def mock_repos():
    """Create mock repositories."""
    return {
        "stock": MagicMock(),
        "price": MagicMock(),
        "pipeline": MagicMock(),
    }


@pytest.fixture
def pipeline(mock_repos):
    """Create DataPipeline with mocked repos."""
    return DataPipeline(
        stock_repo=mock_repos["stock"],
        price_repo=mock_repos["price"],
        pipeline_repo=mock_repos["pipeline"],
        max_workers=2,
    )


def test_pipeline_success(pipeline, mock_repos):
    """Test successful pipeline run for multiple stocks."""
    # 1. Setup mocks
    stocks = [
        StockInDB(symbol="BBCA.JK", name="Bank BCA", is_active=True, added_at=datetime.now(timezone.utc)),
        StockInDB(symbol="ASII.JK", name="Astra", is_active=True, added_at=datetime.now(timezone.utc)),
    ]
    mock_repos["stock"].get_all_stocks.return_value = stocks
    
    # Mock DF with enough data for indicators (e.g. 210 days)
    dates = pd.date_range(start="2023-01-01", periods=210, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "Open": [100.0] * 210,
            "High": [110.0] * 210,
            "Low": [90.0] * 210,
            "Close": [105.0] * 210,
            "Volume": [1000] * 210,
        },
        index=dates,
    )

    with patch("data.pipeline.YFinanceFetcher.fetch_history", return_value=df) as mock_fetch:
        # 2. Run pipeline
        report = pipeline.run()
        
        # 3. Verify
        assert report.total_stocks == 2
        assert report.success_count == 2
        assert report.fail_count == 0
        assert mock_fetch.call_count == 2
        assert mock_repos["price"].upsert_price.call_count == 2 * 210
        assert mock_repos["pipeline"].record_run.called


def test_pipeline_partial_failure(pipeline, mock_repos):
    """Test pipeline resiliency when some stocks fail."""
    # 1. Setup mocks
    stocks = [
        StockInDB(symbol="GOOD.JK", name="Good", is_active=True, added_at=datetime.now(timezone.utc)),
        StockInDB(symbol="FAIL.JK", name="Fail", is_active=True, added_at=datetime.now(timezone.utc)),
    ]
    mock_repos["stock"].get_all_stocks.return_value = stocks
    
    # Mock DF for success
    dates = pd.date_range(start="2023-01-01", periods=210, freq="D", tz="UTC")
    df_good = pd.DataFrame({
            "Open": [100.0] * 210, "High": [110.0] * 210, "Low": [90.0] * 210, "Close": [105.0] * 210, "Volume": [1000] * 210,
    }, index=dates)

    with patch("data.pipeline.YFinanceFetcher.fetch_history") as mock_fetch:
        # Side effect: one success, one failure
        mock_fetch.side_effect = [df_good, NetworkError("API Down")]
        
        # 2. Run
        report = pipeline.run()
        
        # 3. Verify
        assert report.total_stocks == 2
        assert report.success_count == 1
        assert report.fail_count == 1
        assert len(report.errors) == 1
        assert "FAIL.JK" in report.errors[0]


def test_pipeline_insufficient_data(pipeline, mock_repos):
    """Test that stocks with too little data are marked as failed."""
    stocks = [StockInDB(symbol="SHORT.JK", name="Short", is_active=True, added_at=datetime.now(timezone.utc))]
    mock_repos["stock"].get_all_stocks.return_value = stocks
    
    # Only 50 days (needs 200)
    df_short = pd.DataFrame({
            "Open": [100.0] * 50, "High": [110.0] * 50, "Low": [90.0] * 50, "Close": [105.0] * 50, "Volume": [1000] * 50,
    }, index=pd.date_range("2023-01-01", periods=50, freq="D"))

    with patch("data.pipeline.YFinanceFetcher.fetch_history", return_value=df_short):
        report = pipeline.run()
        
        assert report.success_count == 0
        assert report.fail_count == 1
        assert "Insufficient data" in report.errors[0]


def test_pipeline_empty_watchlist(pipeline, mock_repos):
    """Test behavior when watchlist is empty."""
    mock_repos["stock"].get_all_stocks.return_value = []
    
    report = pipeline.run()
    
    assert report.total_stocks == 0
    assert "Empty watchlist" in report.errors


def test_pipeline_upsert_error(pipeline, mock_repos):
    """Test pipeline handling individual row upsert errors."""
    stocks = [StockInDB(symbol="ERR.JK", name="Err", is_active=True, added_at=datetime.now(timezone.utc))]
    mock_repos["stock"].get_all_stocks.return_value = stocks
    
    dates = pd.date_range(start="2023-01-01", periods=210, freq="D", tz="UTC")
    df = pd.DataFrame({"Open": [100.0] * 210, "High": [110.0] * 210, "Low": [90.0] * 210, "Close": [105.0] * 210, "Volume": [1000] * 210}, index=dates)

    with patch("data.pipeline.YFinanceFetcher.fetch_history", return_value=df):
        # Mock upsert to fail
        mock_repos["price"].upsert_price.side_effect = Exception("DB Down")
        
        report = pipeline.run()
        # Even if all rows fail, if the stock was "processed" without raising 
        # (it catches Exception in loop), it counts as success for the stock level?
        # Let's check logic: if saved_count > 0: success_count += 1.
        # If all rows fail, saved_count will be 0.
        assert report.success_count == 0
        assert report.fail_count == 1


def test_pipeline_unexpected_process_error(pipeline, mock_repos):
    """Test pipeline handling unexpected error in process_stock."""
    stocks = [StockInDB(symbol="CRASH.JK", name="Crash", is_active=True, added_at=datetime.now(timezone.utc))]
    mock_repos["stock"].get_all_stocks.return_value = stocks
    
    with patch.object(pipeline, "process_stock", side_effect=Exception("Hard Crash")):
        report = pipeline.run()
        assert report.fail_count == 1
        assert "Hard Crash" in report.errors[0]
