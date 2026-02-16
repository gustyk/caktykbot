"""Tests for scheduler jobs."""

from unittest.mock import MagicMock, patch

import pytest
from scheduler.jobs import SchedulerManager, run_pipeline_job


def test_scheduler_manager_init():
    """Test SchedulerManager initialization."""
    with patch("scheduler.jobs.BackgroundScheduler") as MockScheduler:
        manager = SchedulerManager(timezone_str="UTC")
        assert manager.tz.zone == "UTC"
        MockScheduler.assert_called_once()


def test_scheduler_manager_start():
    """Test starting the scheduler."""
    with patch("scheduler.jobs.BackgroundScheduler") as MockScheduler:
        mock_instance = MockScheduler.return_value
        manager = SchedulerManager()
        manager.start()
        
        # Verify job was added
        mock_instance.add_job.assert_called_once()
        args, kwargs = mock_instance.add_job.call_args
        assert args[0] == run_pipeline_job
        assert kwargs["id"] == "daily_ohlcv_pipeline"
        
        # Verify scheduler started
        mock_instance.start.assert_called_once()


def test_scheduler_manager_stop():
    """Test stopping the scheduler."""
    with patch("scheduler.jobs.BackgroundScheduler") as MockScheduler:
        mock_instance = MockScheduler.return_value
        mock_instance.running = True
        manager = SchedulerManager()
        manager.stop()
        
        mock_instance.shutdown.assert_called_once()


@patch("scheduler.jobs.MongoManager")
@patch("scheduler.jobs.StockRepository")
@patch("scheduler.jobs.PriceRepository")
@patch("scheduler.jobs.PipelineRepository")
@patch("scheduler.jobs.DataPipeline")
def test_run_pipeline_job(
    MockPipeline,
    MockPipelineRepo,
    MockPriceRepo,
    MockStockRepo,
    MockMongoManager
):
    """Test the pipeline job execution wrapper."""
    mock_db = MagicMock()
    MockMongoManager.return_value.get_database.return_value = mock_db
    
    mock_pipeline_inst = MockPipeline.return_value
    mock_report = MagicMock()
    mock_report.success_count = 10
    mock_report.fail_count = 0
    mock_pipeline_inst.run.return_value = mock_report
    
    # Run the job
    run_pipeline_job()
    
    # Verify components initialization
    MockMongoManager.assert_called_once()
    MockStockRepo.assert_called_once_with(mock_db)
    MockPriceRepo.assert_called_once_with(mock_db)
    MockPipelineRepo.assert_called_once_with(mock_db)
    
    # Verify pipeline run
    mock_pipeline_inst.run.assert_called_once()
