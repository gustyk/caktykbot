"""Tests for database index enforcement."""

from unittest.mock import MagicMock, patch
import pytest
from pymongo.errors import OperationFailure
from db.indexes import (
    setup_indexes, 
    create_stocks_indexes, 
    create_daily_prices_indexes, 
    create_pipeline_runs_indexes,
    list_indexes,
    drop_all_indexes
)

class TestIndexes:
    def test_create_stocks_indexes_success(self):
        mock_db = MagicMock()
        create_stocks_indexes(mock_db)
        mock_db.stocks.create_index.assert_called_once()

    def test_create_stocks_indexes_already_exists(self):
        mock_db = MagicMock()
        mock_db.stocks.create_index.side_effect = OperationFailure("already exists")
        create_stocks_indexes(mock_db)

    def test_create_stocks_indexes_failure(self):
        mock_db = MagicMock()
        mock_db.stocks.create_index.side_effect = OperationFailure("critical error")
        with pytest.raises(OperationFailure):
            create_stocks_indexes(mock_db)

    def test_create_daily_prices_indexes_success(self):
        mock_db = MagicMock()
        create_daily_prices_indexes(mock_db)
        assert mock_db.daily_prices.create_index.call_count == 2

    def test_create_daily_prices_indexes_already_exists(self):
        mock_db = MagicMock()
        mock_db.daily_prices.create_index.side_effect = OperationFailure("already exists")
        create_daily_prices_indexes(mock_db)

    def test_create_daily_prices_indexes_failure(self):
        mock_db = MagicMock()
        mock_db.daily_prices.create_index.side_effect = OperationFailure("critical error")
        with pytest.raises(OperationFailure):
            create_daily_prices_indexes(mock_db)

    def test_create_pipeline_runs_indexes_success(self):
        mock_db = MagicMock()
        create_pipeline_runs_indexes(mock_db)
        mock_db.pipeline_runs.create_index.assert_called_once()

    def test_create_pipeline_runs_indexes_already_exists(self):
        mock_db = MagicMock()
        mock_db.pipeline_runs.create_index.side_effect = OperationFailure("already exists")
        create_pipeline_runs_indexes(mock_db)

    def test_create_pipeline_runs_indexes_failure(self):
        mock_db = MagicMock()
        mock_db.pipeline_runs.create_index.side_effect = OperationFailure("critical error")
        with pytest.raises(OperationFailure):
            create_pipeline_runs_indexes(mock_db)

    @patch("db.indexes.get_database")
    @patch("db.indexes.create_stocks_indexes")
    @patch("db.indexes.create_daily_prices_indexes")
    @patch("db.indexes.create_pipeline_runs_indexes")
    def test_setup_indexes_full(self, m1, m2, m3, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        setup_indexes()
        assert m1.called
        assert m2.called
        assert m3.called

    @patch("db.indexes.get_database")
    def test_list_indexes(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.__getitem__.return_value.list_indexes.return_value = []
        res = list_indexes()
        assert "stocks" in res

    @patch("db.indexes.get_database")
    def test_drop_all_indexes(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_coll = MagicMock()
        mock_db.__getitem__.return_value = mock_coll
        drop_all_indexes()
        assert mock_coll.drop_indexes.called

    @patch("db.indexes.get_database")
    def test_drop_all_indexes_failure(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.stocks.drop_indexes.side_effect = Exception("Drop failed")
        # Should not raise, just log
        drop_all_indexes()
