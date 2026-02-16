"""Tests for Portfolio Heat Monitor."""

import pytest
from risk.heat_monitor import calculate_portfolio_heat, project_heat_with_new_trade

class TestHeatMonitor:
    
    def test_calculate_heat(self):
        trades = [
            {"symbol": "A", "risk_percent": 0.01, "qty": 1000, "entry_price": 5000},
            {"symbol": "B", "risk_percent": 0.015, "qty": 2000, "entry_price": 2000}
        ]
        capital = 100_000_000 # 100M
        
        # Exposure A: 5M (5%), Risk 1%
        # Exposure B: 4M (4%), Risk 1.5%
        
        result = calculate_portfolio_heat(trades, capital, max_heat_limit=0.08)
        
        assert result["current_heat"] == 0.025
        assert result["status"] == "safe"
        assert result["total_exposure"] == 9_000_000
        assert result["cash_reserve_pct"] == 0.91 # 91M / 100M
        assert result["cash_reserve_ok"] is True

    def test_heat_limit_status(self):
        trades = [{"symbol": "X", "risk_percent": 0.08, "qty": 1, "entry_price": 1}]
        result = calculate_portfolio_heat(trades, 100, max_heat_limit=0.08)
        assert result["status"] == "limit"
        assert result["available_heat"] == 0.0

    def test_heat_warning_status(self):
        trades = [{"symbol": "X", "risk_percent": 0.065, "qty": 1, "entry_price": 1}] # > 6%
        result = calculate_portfolio_heat(trades, 100, max_heat_limit=0.08)
        assert result["status"] == "warning"

    def test_project_heat(self):
        current = 0.05
        new_risk = 0.01
        limit = 0.08
        
        res = project_heat_with_new_trade(current, new_risk, limit)
        assert res["projected_heat"] == pytest.approx(0.06)
        assert not res["would_exceed"]
        
        # Exceed case
        res_exceed = project_heat_with_new_trade(current, 0.04, limit)
        assert res_exceed["projected_heat"] == pytest.approx(0.09)
        assert res_exceed["would_exceed"]
