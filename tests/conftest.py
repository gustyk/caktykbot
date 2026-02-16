"""Shared pytest fixtures for all tests."""

import pytest
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
from config.settings import Settings
try:
    import mongomock
    _HAS_MONGOMOCK = True
except ImportError:
    _HAS_MONGOMOCK = False


@pytest.fixture(scope="session")
def test_settings():
    """Test settings with safe defaults."""
    return Settings(
        MONGO_URI="mongodb://localhost:27017/",
        MONGO_DB_NAME="caktykbot_test",
        TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
        TELEGRAM_CHAT_ID="123456789",
        MAX_WATCHLIST=20,
        FETCH_RETRY_COUNT=3,
        FETCH_RETRY_DELAY=0.1,  # Faster for tests
        LOG_LEVEL="DEBUG",
        TIMEZONE="Asia/Jakarta",
        ENVIRONMENT="test",
    )


@pytest.fixture(scope="session")
def mongo_test_client():
    """MongoDB test client (session-scoped)."""
    if _HAS_MONGOMOCK:
        client = mongomock.MongoClient()
    else:
        # Fallback to local MongoDB if mongomock is not installed
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=1000)
    
    yield client
    client.close()


@pytest.fixture
def mongo_test_db(mongo_test_client):
    """Clean test database for each test."""
    db_name = "caktykbot_test"
    db = mongo_test_client[db_name]
    
    # Clean before test
    mongo_test_client.drop_database(db_name)
    
    # Create indexes
    db.stocks.create_index("symbol", unique=True)
    db.daily_prices.create_index([("symbol", 1), ("date", -1)], unique=True)
    db.daily_prices.create_index("fetched_at")
    db.pipeline_runs.create_index("date")
    
    yield db
    
    # Clean after test
    mongo_test_client.drop_database(db_name)


@pytest.fixture
def sample_stock_data():
    """Sample stock data for testing."""
    return {
        "symbol": "BBCA.JK",
        "name": "Bank Central Asia Tbk",
        "sector": "Banking",
        "market_cap": "large",
        "is_active": True,
        "added_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


@pytest.fixture
def sample_ohlcv_dataframe():
    """Sample OHLCV DataFrame for testing."""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="D")
    
    # Generate realistic price data
    base_price = 10000
    prices = []
    for i in range(200):
        # Random walk
        change = (i % 10 - 5) * 100
        prices.append(base_price + change)
    
    df = pd.DataFrame({
        "Date": dates,
        "Open": [p * 0.99 for p in prices],
        "High": [p * 1.02 for p in prices],
        "Low": [p * 0.98 for p in prices],
        "Close": prices,
        "Volume": [1000000 + (i * 10000) for i in range(200)],
    })
    
    df.set_index("Date", inplace=True)
    return df


@pytest.fixture
def sample_daily_price():
    """Sample daily price record for testing."""
    return {
        "symbol": "BBCA.JK",
        "date": datetime(2024, 2, 13),
        "open": 10000.0,
        "high": 10200.0,
        "low": 9800.0,
        "close": 10100.0,
        "volume": 1500000,
        "adjusted_close": 10100.0,
        "ema_8": 10050.0,
        "ema_21": 10000.0,
        "ema_50": 9950.0,
        "ema_150": 9900.0,
        "ema_200": 9850.0,
        "atr_14": 250.0,
        "vol_ma_20": 1400000.0,
        "fetched_at": datetime.utcnow(),
    }


@pytest.fixture
def invalid_ohlcv_dataframe():
    """Invalid OHLCV DataFrame for testing validation."""
    dates = pd.date_range(start="2024-01-01", periods=10, freq="D")
    
    df = pd.DataFrame({
        "Date": dates,
        "Open": [10000, 10100, -100, 10300, 10400, 10500, 10600, 10700, 10800, 10900],  # Negative price
        "High": [10200, 10300, 10400, 10500, 10600, 10700, 10800, 10900, 11000, 11100],
        "Low": [9800, 9900, 10000, 10100, 10200, 10300, 10400, 10500, 10600, 10700],
        "Close": [10100, 10200, 10300, 10400, 10500, 10600, 10700, 10800, 10900, 11000],
        "Volume": [1000000, 1100000, 1200000, 1300000, 1400000, 1500000, 1600000, 1700000, 1800000, 1900000],
    })
    
    df.set_index("Date", inplace=True)
    return df


@pytest.fixture
def mock_yfinance_response(sample_ohlcv_dataframe):
    """Mock yfinance response for testing."""
    return sample_ohlcv_dataframe


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "benchmark: Performance benchmark tests")
    config.addinivalue_line("markers", "chaos: Chaos engineering tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "unit: Unit tests")
