
import pytest
from unittest.mock import MagicMock, patch
from monitoring.health_check import check_mongodb, check_yfinance, check_pipeline_status, check_all
from datetime import datetime, timezone, timedelta

@pytest.fixture
def mock_db_ping():
    with patch("monitoring.health_check.get_database") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        yield mock_db

def test_check_mongodb_success(mock_db_ping):
    result = check_mongodb()
    assert result["status"] == "ok"
    assert "latency_ms" in result
    mock_db_ping.command.assert_called_with("ping")

def test_check_mongodb_failure(mock_db_ping):
    mock_db_ping.command.side_effect = Exception("Connection refused")
    result = check_mongodb()
    assert result["status"] == "error"
    assert "Connection refused" in result["message"]

@patch("monitoring.health_check.requests.get")
def test_check_yfinance_success(mock_get):
    result = check_yfinance()
    assert result["status"] == "ok"
    assert "latency_ms" in result

@patch("monitoring.health_check.requests.get")
def test_check_yfinance_failure(mock_get):
    mock_get.side_effect = Exception("Timeout")
    result = check_yfinance()
    assert result["status"] == "error"
    assert "Timeout" in result["message"]

@patch("monitoring.health_check.get_database")
def test_check_pipeline_status_ok(mock_get_db):
    mock_repo = MagicMock()
    # Mock return of get_latest_run
    mock_run = MagicMock()
    mock_run.date = datetime.now(timezone.utc) - timedelta(hours=5)
    mock_run.total_stocks = 10
    mock_run.success_count = 10
    mock_repo.get_latest_run.return_value = mock_run
    
    with patch("monitoring.health_check.PipelineRepository", return_value=mock_repo):
        result = check_pipeline_status()
        assert result["status"] == "ok"
        assert result["hours_since"] == 5.0
        assert result["success_rate"] == "10/10"

@patch("monitoring.health_check.get_database")
def test_check_pipeline_status_warning(mock_get_db):
    mock_repo = MagicMock()
    mock_run = MagicMock()
    mock_run.date = datetime.now(timezone.utc) - timedelta(hours=26)
    mock_run.total_stocks = 10
    mock_run.success_count = 10
    mock_repo.get_latest_run.return_value = mock_run
    
    with patch("monitoring.health_check.PipelineRepository", return_value=mock_repo):
        result = check_pipeline_status()
        assert result["status"] == "warning"

def test_check_all():
    with patch("monitoring.health_check.check_mongodb", return_value={"status": "ok"}), \
         patch("monitoring.health_check.check_yfinance", return_value={"status": "ok"}), \
         patch("monitoring.health_check.check_pipeline_status", return_value={"status": "ok"}):
        
        result = check_all()
        assert "timestamp" in result
        assert result["mongodb"]["status"] == "ok"
