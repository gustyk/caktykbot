
import pytest
from backtest.metrics import calculate_metrics

def test_calculate_metrics_empty():
    metrics = calculate_metrics([], 1000)
    assert metrics["total_trades"] == 0
    assert metrics["win_rate"] == 0.0
    assert metrics["profit_factor"] == 0.0
    assert metrics["max_drawdown"] == 0.0

def test_calculate_metrics_basic():
    trades = [
        {"pnl_rupiah": 100, "pnl_percent": 10.0, "exit_date": "2023-01-01"},
        {"pnl_rupiah": -50, "pnl_percent": -5.0, "exit_date": "2023-01-02"},
        {"pnl_rupiah": 200, "pnl_percent": 20.0, "exit_date": "2023-01-03"}
    ]
    initial_capital = 1000.0
    
    metrics = calculate_metrics(trades, initial_capital)
    
    assert metrics["total_trades"] == 3
    assert metrics["win_rate"] == 66.67 # 2 wins out of 3
    
    # Avg Profit: (10+20)/2 = 15. Avg Loss: -5.
    assert metrics["avg_profit"] == 15.0
    assert metrics["avg_loss"] == -5.0
    
    # Profit Factor: Gross Profit 300 / Gross Loss 50 = 6.0
    assert metrics["profit_factor"] == 6.0
    
    # Capital: 1000 + 100 - 50 + 200 = 1250
    assert metrics["final_capital"] == 1250.0
    assert metrics["total_return"] == 25.0
    
    # Drawdown:
    # Equity: 1000 -> 1100 -> 1050 -> 1250
    # Peaks:  1000 -> 1100 -> 1100 -> 1250
    # DD:       0% ->   0% -> -4.54% -> 0%
    # Max DD should be around -4.55%
    assert -4.6 < metrics["max_drawdown"] < -4.5

