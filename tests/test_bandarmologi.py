import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.bandarmologi import BandarmologiStrategy

@pytest.fixture
def strategy():
    return BandarmologiStrategy(
        min_accum_days=3,
        min_broker_value=1000,
        min_foreign_flow_days=2,
        min_foreign_flow_total=500,
        base_period=5,
        max_atr_pct=10.0 # generous for test data
    )

@pytest.fixture
def mock_price_data():
    dates = pd.date_range(end=datetime.now(), periods=10)
    data = {
        "date": dates,
        "open": [100]*5 + [100, 100, 100, 100, 105], # Base then breakout
        "high": [105]*5 + [102, 102, 102, 102, 110],
        "low": [95]*5 + [98, 98, 98, 98, 100],
        "close": [100]*5 + [100, 100, 100, 100, 108],
        "volume": [1000]*9 + [2000] # Surge at end
    }
    return pd.DataFrame(data)

class TestBandarmologiStrategy:
    def test_detect_accumulation(self, strategy):
        dates = pd.date_range(end=datetime.now(), periods=5)
        # Broker YP buying consistently
        data = []
        for d in dates:
            data.append({"date": d, "broker_code": "YP", "net_value": 2000})
            data.append({"date": d, "broker_code": "KK", "net_value": -1000})
            
        df = pd.DataFrame(data)
        result = strategy.detect_accumulation(df)
        
        assert result["is_accumulating"] is True
        assert "YP" in result["top_brokers"]
        assert result["top_buy_val"] >= 2000 * 3 # min 3 days check in fixture

    def test_detect_foreign_flow(self, strategy):
        dates = pd.date_range(end=datetime.now(), periods=5)
        # Increase values to exceed min_foreign_flow_total (500)
        data = {
            "date": dates,
            "foreign_net": [100, 100, 300, 300, 300]
        }
        df = pd.DataFrame(data)
        result = strategy.detect_foreign_flow(df)
        
        assert result["is_foreign_buying"] is True
        assert result["consecutive_days"] >= 2

    def test_detect_base_formation(self, strategy, mock_price_data):
        # The mock data has a tight range from index 5 to 8 (low volatility)
        # But we pass the whole DF logic uses tail(period)
        
        # Create specifically tight data
        dates = pd.date_range(end=datetime.now(), periods=10)
        data = {
            "open": [100]*10, "high": [101]*10, "low": [99]*10, "close": [100]*10, "volume": [1000]*10,
            "date": dates
        }
        df = pd.DataFrame(data)
        
        result = strategy.detect_base_formation(df)
        assert result["is_base_forming"] is True
        assert result["atr_pct"] < 10.0

    def test_analyze_breakout_signal(self, strategy, mock_price_data):
        dates = pd.date_range(end=datetime.now(), periods=10)
        
        # Broker data supporting
        broker_data = pd.DataFrame([
            {"date": d, "broker_code": "YP", "net_value": 5000} for d in dates
        ])
        
        # Foreign data supporting
        flow_data = pd.DataFrame({
            "date": dates,
            "foreign_net": [1000]*10
        })
        
        signal = strategy.analyze(
            mock_price_data,
            broker_data=broker_data,
            flow_data=flow_data,
            symbol="TEST"
        )
        
        assert signal is not None
        assert signal.verdict == "BUY"
        assert signal.strategy_name == "bandarmologi_breakout"

    def test_analyze_no_breakout(self, strategy, mock_price_data):
        # Remove breakout candle
        df = mock_price_data.iloc[:-1]
        
        broker_data = pd.DataFrame([
            {"date": datetime.now(), "broker_code": "YP", "net_value": 5000}
        ])
        
        signal = strategy.analyze(
            df,
            broker_data=broker_data,
            flow_data=None
        )
        assert signal is None
