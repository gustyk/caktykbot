"""Circuit Breaker Logic (RR-010)."""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple

from db.schemas import CircuitBreakerTriggerType
from risk.constants import (
    CB_DRAWDOWN_TRIGGER,
    CB_CONSECUTIVE_LOSS_TRIGGER,
    CB_DRAWDOWN_SUSPEND_DAYS,
    CB_LOSS_SUSPEND_DAYS,
    CB_REDUCED_RISK,
    MSG_CB_ACTIVE
)

class CircuitBreaker:
    
    def calculate_monthly_drawdown(
        self, 
        trades: List[Dict],
        current_capital: float
    ) -> float:
        """
        Calculate max drawdown for current month.
        Drawdown = (Peak - Trough) / Peak
        
        Note: This is a simplified calculation based on realizing losses in the current month.
        A full equity curve drawdown requires daily snapshotting. 
        For this sprint, we approximate based on realized PnL in current month vs starting month capital.
        """
        now = datetime.now(timezone.utc)
        start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        
        # Filter trades closed this month
        monthly_trades = [
            t for t in trades 
            if t.get("exit_date") and t["exit_date"] >= start_of_month
        ]
        
        # Calculate PnL accumulation
        # Assuming current_capital is the END capital.
        # We work backwards to find peak? 
        # Or just sum up losses?
        # Requirement: "Drawdown bulanan > 10%"
        # Let's define it as: sum of realized losses this month / starting capital of month.
        
        realized_pnl = sum(t.get("pnl_rupiah", 0.0) for t in monthly_trades)
        
        # Start of month capital approx = current - realized_pnl (ignoring deposits/withdrawals)
        start_capital = current_capital - realized_pnl
        
        if start_capital <= 0:
            return 0.0
            
        # Drawdown is usually peak to trough. 
        # If we only track realized losses, we can check if Net PnL is negative.
        # Drawdown = -NetPnL / StartCapital (if NetPnL < 0)
        
        if realized_pnl < 0:
            drawdown = abs(realized_pnl) / start_capital
            return drawdown
            
        return 0.0

    def count_consecutive_losses(self, trades: List[Dict]) -> int:
        """
        Count consecutive losses from the most recent closed trade backwards.
        """
        # Sort by exit date descending
        sorted_trades = sorted(
            [t for t in trades if t.get("exit_date")],
            key=lambda x: x["exit_date"],
            reverse=True
        )
        
        count = 0
        for trade in sorted_trades:
            pnl = trade.get("pnl_rupiah", 0.0)
            if pnl < 0:
                count += 1
            else:
                break
                
        return count

    def check(
        self,
        closed_trades: List[Dict],
        current_capital: float,
        active_suspension: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Check if Circuit Breaker should be active.
        
        Args:
            closed_trades: List of closed trades
            current_capital: Current capital
            active_suspension: Existing active CB event (from DB)
            
        Returns:
            Dict with status
        """
        # If already suspended, check if time to resume
        if active_suspension:
            suspend_until = active_suspension.get("suspended_until")
            if suspend_until and suspend_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                return {
                    "is_active": True,
                    "risk_override": active_suspension.get("risk_override"),
                    "message": f"Trading suspended until {suspend_until}",
                    "trigger_type": active_suspension.get("trigger_type")
                }
        
        # Check triggers
        # 1. Monthly Drawdown
        dd = self.calculate_monthly_drawdown(closed_trades, current_capital)
        if dd >= CB_DRAWDOWN_TRIGGER:
            until = datetime.now(timezone.utc) + timedelta(days=CB_DRAWDOWN_SUSPEND_DAYS)
            return {
                "is_active": True,
                "trigger_type": CircuitBreakerTriggerType.DRAWDOWN_10PCT,
                "trigger_value": dd,
                "suspended_until": until,
                "risk_override": CB_REDUCED_RISK,
                "message": MSG_CB_ACTIVE.format(
                    trigger=f"Monthly Drawdown {dd:.1%}", 
                    until=until.strftime("%Y-%m-%d")
                )
            }
            
        # 2. Consecutive Losses
        losses = self.count_consecutive_losses(closed_trades)
        if losses >= CB_CONSECUTIVE_LOSS_TRIGGER:
            until = datetime.now(timezone.utc) + timedelta(days=CB_LOSS_SUSPEND_DAYS)
            return {
                "is_active": True,
                "trigger_type": CircuitBreakerTriggerType.CONSECUTIVE_LOSS_5,
                "trigger_value": float(losses),
                "suspended_until": until,
                "risk_override": CB_REDUCED_RISK,
                "message": MSG_CB_ACTIVE.format(
                    trigger=f"{losses} Consecutive Losses", 
                    until=until.strftime("%Y-%m-%d")
                )
            }
            
        return {"is_active": False, "message": "Circuit breaker inactive"}
