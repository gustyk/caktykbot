"""Tests for Circuit Breaker."""

from datetime import datetime, timedelta, timezone
from caktykbot.risk.circuit_breaker import CircuitBreaker
from caktykbot.risk.constants import (
    CB_DRAWDOWN_TRIGGER, 
    CB_CONSECUTIVE_LOSS_TRIGGER,
    CB_DRAWDOWN_SUSPEND_DAYS,
    CB_LOSS_SUSPEND_DAYS
)

class TestCircuitBreaker:
    
    def test_no_trigger(self):
        cb = CircuitBreaker()
        trades = [{"pnl_rupiah": 100, "exit_date": datetime.now(timezone.utc)}, {"pnl_rupiah": -50, "exit_date": datetime.now(timezone.utc)}]
        capital = 1000
        
        result = cb.check(trades, capital)
        # check(..., closed_trades) calls calculate_monthly_drawdown which uses 'exit_date'.
        # check(..., closed_trades) calls count_consecutive_losses which uses 'exit_date' and 'pnl_rupiah'.
        
        assert not result["is_active"]

    def test_drawdown_trigger(self):
        cb = CircuitBreaker()
        current_capital = 9_000_000
        
        # Drawdown 2M / 11M = 18% > 10%
        now = datetime.now(timezone.utc)
        trades = [
            {"pnl_rupiah": -2_000_000, "exit_date": now, "status": "closed"}
        ]
        
        result = cb.check(trades, current_capital, active_suspension=None)
        
        assert result["is_active"]
        assert result["trigger_type"] is not None # Using enum or string
        assert result["suspended_until"] is not None
        
        # Approximate check for date (could be slightly different due to execution time, strip time)
        expected_date = (now + timedelta(days=CB_DRAWDOWN_SUSPEND_DAYS)).date()
        assert result["suspended_until"].date() == expected_date

    def test_consecutive_loss_trigger(self):
        cb = CircuitBreaker()
        trades = []
        # 5 consecutive losses
        for i in range(5):
            trades.append({"pnl_rupiah": -1, "exit_date": datetime.now(timezone.utc), "status": "closed"})
            
        result = cb.check(trades, 1000)
        assert result["is_active"]
        # Trigger type check
        
        expected_date = (datetime.now(timezone.utc) + timedelta(days=CB_LOSS_SUSPEND_DAYS)).date()
        assert result["suspended_until"].date() == expected_date

    def test_suspension_active(self):
        cb = CircuitBreaker()
        # Suspension active until tomorrow
        suspension = {
            "suspended_until": datetime.now(timezone.utc) + timedelta(days=1),
            "trigger_type": "DRAWDOWN",
            "risk_override": 0.005
        }
        
        result = cb.check([], 1000, active_suspension=suspension)
        assert result["is_active"]
        assert result["risk_override"] == 0.005
        assert "suspended until" in result["message"]

    def test_reset_consecutive(self):
        cb = CircuitBreaker()
        # Loss, Loss, Win, Loss
        now = datetime.now(timezone.utc)
        trades = [
            {"pnl_rupiah": -1, "exit_date": now},     # Most recent
            {"pnl_rupiah": -1, "exit_date": now},
            {"pnl_rupiah": 10, "exit_date": now},     # Reset
            {"pnl_rupiah": -1, "exit_date": now},
        ]
        # Since I used same timestamp, sort order could be unstable. 
        # Better use different times.
        t1 = now
        t2 = now - timedelta(hours=1)
        t3 = now - timedelta(hours=2)
        t4 = now - timedelta(hours=3)
        
        trades = [
             {"pnl_rupiah": -1, "exit_date": t1}, # Newest
             {"pnl_rupiah": -1, "exit_date": t2},
             {"pnl_rupiah": 10, "exit_date": t3}, # Win
             {"pnl_rupiah": -1, "exit_date": t4}  # Old loss
        ]
        
        # Consecutive loss count should be 2. (t1, t2). t3 broke it.
        # Trigger is 5 (default). So inactive.
        
        result = cb.check(trades, 1000)
        assert not result.get("is_active", False)
