"""Tests for MongoDB repositories."""

import pytest
from datetime import datetime, timezone
from db.repositories.stock_repo import StockRepository
from db.repositories.price_repo import PriceRepository
from db.repositories.pipeline_repo import PipelineRepository
from db.schemas import StockCreate, StockUpdate, DailyPriceBase, PipelineRun
from utils.exceptions import (
    WatchlistFullError, 
    DuplicateStockError, 
    StockNotFoundError,
    ReferentialIntegrityError,
    DuplicatePipelineRunError
)

class TestStockRepository:
    def test_add_stock_success(self, mongo_test_db):
        repo = StockRepository(mongo_test_db, max_watchlist=5)
        stock = StockCreate(symbol="BBCA.JK", name="Bank Central Asia")
        result = repo.add_stock(stock)
        assert result.symbol == "BBCA.JK"
        assert result.name == "Bank Central Asia"
        assert result.added_at is not None

    def test_add_stock_watchlist_full(self, mongo_test_db):
        repo = StockRepository(mongo_test_db, max_watchlist=1)
        repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        with pytest.raises(WatchlistFullError):
            repo.add_stock(StockCreate(symbol="TLKM.JK", name="Telkom"))

    def test_add_stock_duplicate(self, mongo_test_db):
        repo = StockRepository(mongo_test_db)
        repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        with pytest.raises(DuplicateStockError):
            repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))

    def test_get_stock(self, mongo_test_db):
        repo = StockRepository(mongo_test_db)
        repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        stock = repo.get_stock("BBCA.JK")
        assert stock.symbol == "BBCA.JK"
        assert repo.get_stock("NONEXISTENT") is None

    def test_get_all_stocks(self, mongo_test_db):
        repo = StockRepository(mongo_test_db)
        repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        repo.add_stock(StockCreate(symbol="TLKM.JK", name="Telkom", is_active=False))
        
        active_stocks = repo.get_all_stocks(only_active=True)
        assert len(active_stocks) == 1
        assert active_stocks[0].symbol == "BBCA.JK"
        
        all_stocks = repo.get_all_stocks(only_active=False)
        assert len(all_stocks) == 2

    def test_update_stock_success(self, mongo_test_db):
        repo = StockRepository(mongo_test_db)
        repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        
        update = StockUpdate(name="BCA New", is_active=False)
        updated = repo.update_stock("BBCA.JK", update)
        assert updated.name == "BCA New"
        assert updated.is_active is False

    def test_update_stock_not_found(self, mongo_test_db):
        repo = StockRepository(mongo_test_db)
        with pytest.raises(StockNotFoundError):
            repo.update_stock("NONEXISTENT.JK", StockUpdate(name="Test"))

    def test_update_stock_no_changes(self, mongo_test_db):
        repo = StockRepository(mongo_test_db)
        repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        updated = repo.update_stock("BBCA.JK", StockUpdate())
        assert updated.symbol == "BBCA.JK"

    def test_delete_stock(self, mongo_test_db):
        repo = StockRepository(mongo_test_db)
        repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        assert repo.delete_stock("BBCA.JK") is True
        assert repo.delete_stock("BBCA.JK") is False

class TestPriceRepository:
    def test_upsert_price_success(self, mongo_test_db):
        stock_repo = StockRepository(mongo_test_db)
        stock_repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        
        repo = PriceRepository(mongo_test_db)
        price_data = DailyPriceBase(
            symbol="BBCA.JK",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=10000, high=10100, low=9900, close=10050, 
            volume=1000000, adjusted_close=10050
        )
        result = repo.upsert_price(price_data)
        assert result.symbol == "BBCA.JK"
        assert result.close == 10050
        
        # Update existing
        price_data.close = 10100
        updated = repo.upsert_price(price_data)
        assert updated.close == 10100

    def test_upsert_price_referential_integrity(self, mongo_test_db):
        repo = PriceRepository(mongo_test_db)
        price_data = DailyPriceBase(
            symbol="NONEXISTENT.JK",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=10000, high=10100, low=9900, close=10050, 
            volume=1000000, adjusted_close=10050
        )
        with pytest.raises(ReferentialIntegrityError):
            repo.upsert_price(price_data)

    def test_get_latest_price(self, mongo_test_db):
        stock_repo = StockRepository(mongo_test_db)
        stock_repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        
        repo = PriceRepository(mongo_test_db)
        repo.upsert_price(DailyPriceBase(
            symbol="BBCA.JK", date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=10000, high=10100, low=9900, close=10000, 
            volume=1000, adjusted_close=10000
        ))
        repo.upsert_price(DailyPriceBase(
            symbol="BBCA.JK", date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            open=10100, high=10200, low=10000, close=10150, 
            volume=1000, adjusted_close=10150
        ))
        
        latest = repo.get_latest_price("BBCA.JK")
        assert latest.date == datetime(2024, 1, 2, tzinfo=timezone.utc)
        assert repo.get_latest_price("TLKM.JK") is None

    def test_get_historical_prices(self, mongo_test_db):
        stock_repo = StockRepository(mongo_test_db)
        stock_repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        
        repo = PriceRepository(mongo_test_db)
        for i in range(1, 6):
            repo.upsert_price(DailyPriceBase(
                symbol="BBCA.JK", date=datetime(2024, 1, i, tzinfo=timezone.utc),
                open=10000, high=10100, low=9900, close=10000, 
                volume=1000, adjusted_close=10000
            ))
            
        history = repo.get_historical_prices("BBCA.JK", limit=3)
        assert len(history) == 3
        assert history[0].date == datetime(2024, 1, 5, tzinfo=timezone.utc)
        
        history_start = repo.get_historical_prices("BBCA.JK", start_date=datetime(2024, 1, 4, tzinfo=timezone.utc))
        assert len(history_start) == 2

    def test_delete_all_for_stock(self, mongo_test_db):
        stock_repo = StockRepository(mongo_test_db)
        stock_repo.add_stock(StockCreate(symbol="BBCA.JK", name="Bank Central Asia"))
        
        repo = PriceRepository(mongo_test_db)
        repo.upsert_price(DailyPriceBase(
            symbol="BBCA.JK", date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=10000, high=10100, low=9900, close=10000, 
            volume=1000, adjusted_close=10000
        ))
        
        count = repo.delete_all_for_stock("BBCA.JK")
        assert count == 1
        assert repo.get_latest_price("BBCA.JK") is None

class TestPipelineRepository:
    def test_record_run_success(self, mongo_test_db):
        repo = PipelineRepository(mongo_test_db)
        run = PipelineRun(
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            duration=120.5,
            total_stocks=10,
            success_count=10,
            fail_count=0
        )
        result = repo.record_run(run)
        # result.date might be aware if run.date was aware
        assert result.date == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_record_run_duplicate(self, mongo_test_db):
        repo = PipelineRepository(mongo_test_db)
        run = PipelineRun(
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            duration=60,
            total_stocks=5,
            success_count=5,
            fail_count=0
        )
        repo.record_run(run)
        with pytest.raises(DuplicatePipelineRunError):
            repo.record_run(run)

    def test_get_latest_run(self, mongo_test_db):
        repo = PipelineRepository(mongo_test_db)
        repo.record_run(PipelineRun(
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            duration=60, total_stocks=1, success_count=1, fail_count=0
        ))
        repo.record_run(PipelineRun(
            date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            duration=60, total_stocks=1, success_count=1, fail_count=0
        ))
        
        latest = repo.get_latest_run()
        assert latest.date == datetime(2024, 1, 2, tzinfo=timezone.utc)
        
    def test_get_history(self, mongo_test_db):
        repo = PipelineRepository(mongo_test_db)
        for i in range(1, 6):
            repo.record_run(PipelineRun(
                date=datetime(2024, 1, i, tzinfo=timezone.utc),
                duration=60, total_stocks=1, success_count=1, fail_count=0
            ))
            
        history = repo.get_history(limit=3)
        assert len(history) == 3
        # Ensure comparison is aware
        assert history[0].date == datetime(2024, 1, 5, tzinfo=timezone.utc)


