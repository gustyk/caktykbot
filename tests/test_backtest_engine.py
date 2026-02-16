
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
import pandas as pd
from backtest.engine import BacktestEngine
from db.schemas import StockInDB, DailyPriceInDB

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_repos(mock_db):
    with patch("backtest.engine.PriceRepository") as MockPriceRepo, \
         patch("backtest.engine.StockRepository") as MockStockRepo, \
         patch("backtest.engine.BacktestRepository") as MockBacktestRepo:
        
        price_repo = MockPriceRepo.return_value
        stock_repo = MockStockRepo.return_value
        backtest_repo = MockBacktestRepo.return_value
        
        yield price_repo, stock_repo, backtest_repo

def test_backtest_engine_init(mock_db, mock_repos):
    engine = BacktestEngine(mock_db, "vcp", datetime(2023, 1, 1), datetime(2023, 1, 31))
    assert engine.strategy_name == "vcp"
    assert engine.initial_capital == 1_000_000_000

def test_backtest_engine_load_data(mock_db, mock_repos):
    price_repo, stock_repo, _ = mock_repos
    
    # Mock Data
    stock_repo.get_active_stocks.return_value = [
        StockInDB(symbol="BBCA.JK", name="BCA", market_cap="large")
    ]
    
    price_repo.get_historical_prices.return_value = [
        DailyPriceInDB(
            symbol="BBCA.JK", date=datetime(2023, 1, 1), 
            open=1000, high=1100, low=900, close=1050, volume=1000, adjusted_close=1050
        ),
        DailyPriceInDB(
            symbol="BBCA.JK", date=datetime(2023, 1, 2), 
            open=1050, high=1150, low=1000, close=1100, volume=1000, adjusted_close=1100
        )
    ]
    
    engine = BacktestEngine(mock_db, "vcp", datetime(2023, 1, 1), datetime(2023, 1, 31))
    engine.load_data()
    
    assert "BBCA.JK" in engine.price_cache
    assert len(engine.price_cache["BBCA.JK"]) == 2

def test_backtest_engine_execution(mock_db, mock_repos):
    price_repo, stock_repo, backtest_repo = mock_repos
    
    # Mock Repos
    stock_repo.get_active_stocks.return_value = [
        StockInDB(symbol="TEST.JK", name="Test", market_cap="mid")
    ]
    
    # Create fake price history
    dates = pd.date_range(start="2023-01-01", periods=10)
    prices = []
    for d in dates:
        prices.append(DailyPriceInDB(
            symbol="TEST.JK", date=d, 
            open=1000, high=1050, low=950, close=1000, volume=1000, adjusted_close=1000
        ))
    price_repo.get_historical_prices.return_value = prices

    # Mock Strategy to return a signal
    with patch("backtest.engine.VCPStrategy") as MockStrategy:
        strategy_instance = MockStrategy.return_value
        
        # Signal on day 5
        from strategies.base import StrategySignal
        signal = StrategySignal(
            symbol="TEST.JK", verdict="BUY", 
            entry_price=1010, sl_price=900, tp_price=1200, tp2_price=None,
            rr_ratio=2.0, score=80, strategy_name="vcp", reasoning="Test", detail={}
        )
        
        # Make strategy return signal only once
        strategy_instance.analyze.side_effect = [None, None, None, None, signal, None, None, None, None, None]

        engine = BacktestEngine(mock_db, "vcp", datetime(2023, 1, 1), datetime(2023, 1, 10))
        
        # Override process_day to mock price lookup or let it use cache
        # Actually load_data uses repo, so we good.
        
        # Run
        backtest_repo.create_run.return_value = "run_123"
        run_id = engine.run()
        
        assert run_id == "run_123"
        # Since we mocked strategy to buy, we expect a trade if price action allows
        # But our price data is flat (1000-1050), entry is 1010.
        # If entry logic is "limit" or "market", engine uses `signal.entry_price`.
        # Engine checks if we have capital.
        # Wait, run() calls load_data() which populates cache.
        # Then _process_day iterates.
        
        # We need to ensure _scan_for_signals finds the signal.
        # It passes data slice to analyze.
        
        assert backtest_repo.create_run.called
        assert backtest_repo.save_trades.called
