"""Statistics calculation module."""
from typing import List, Dict, Any, Optional
from db.schemas import Trade
import pandas as pd

class StatisticsEngine:
    """Calculates trade statistics."""
    
    @staticmethod
    def calculate_summary(trades: List[Trade]) -> Dict[str, Any]:
        """
        Calculate summary stats from a list of trades.
        """
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0
            }
            
        wins = [t for t in trades if (t.pnl_rupiah or 0) > 0]
        losses = [t for t in trades if (t.pnl_rupiah or 0) <= 0]
        
        num_wins = len(wins)
        num_losses = len(losses)
        
        win_rate = (num_wins / total_trades) * 100
        
        gross_profit = sum(t.pnl_rupiah for t in wins if t.pnl_rupiah)
        gross_loss = abs(sum(t.pnl_rupiah for t in losses if t.pnl_rupiah))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        total_pnl = gross_profit - gross_loss
        
        avg_win = gross_profit / num_wins if num_wins > 0 else 0
        avg_loss = gross_loss / num_losses if num_losses > 0 else 0
        
        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "win_loss_ratio": f"{num_wins}:{num_losses}"
        }
        
    @staticmethod
    def calculate_performance_series(trades: List[Trade]) -> pd.DataFrame:
        """
        Returns a time-series of cumulative P&L.
        """
        data = []
        cumulative = 0.0
        
        # Sort by exit date
        # Only closed trades or trades with realized pnl
        valid_trades = [t for t in trades if t.exit_date and t.pnl_rupiah is not None]
        sorted_trades = sorted(valid_trades, key=lambda x: x.exit_date)
        
        for t in sorted_trades:
            pnl = t.pnl_rupiah or 0
            cumulative += pnl
            data.append({
                "date": t.exit_date,
                "pnl": pnl,
                "cumulative_pnl": cumulative
            })
            
        if not data:
            return pd.DataFrame()
            
        return pd.DataFrame(data)
