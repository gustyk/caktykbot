"""Pure functions for trade calculations."""
from datetime import datetime
from typing import Dict, List, Any


def calculate_pnl(entry_price: float, exit_price: float, qty: int, fees: float = 0.0) -> Dict[str, float]:
    """
    Calculate P&L in Rupiah and Percent.
    
    pnl_rupiah = (Exit - Entry) * Qty - Fees
    pnl_percent = ((Exit - Entry) / Entry) * 100
    Note: Fees affect Rupiah P&L but usually not raw price percentage calculation 
          unless we want net return %. Let's stick to raw price % diff for pnl_percent
          or net? Standard is usually raw price move for % and net for value.
          However, for portfolio performance, Net % is better.
          Let's do: pnl_percent = (pnl_rupiah / (entry * qty)) * 100
    """
    invested = entry_price * qty
    if invested == 0:
        return {"pnl_rupiah": 0.0, "pnl_percent": 0.0}
        
    gross_pnl = (exit_price - entry_price) * qty
    net_pnl = gross_pnl - fees
    
    pnl_percent = (net_pnl / invested) * 100
    
    return {
        "pnl_rupiah": net_pnl,
        "pnl_percent": pnl_percent
    }


def calculate_holding_days(entry_date: datetime, exit_date: datetime) -> int:
    """Calculate holding period in days."""
    delta = exit_date - entry_date
    return max(delta.days, 0)


def determine_win_loss(pnl_rupiah: float) -> str:
    """Determine if trade is WIN, LOSS, or BREAKEVEN."""
    # Breakeven threshold can be small positive/negative near 0
    # But usually > 0 is win.
    if pnl_rupiah > 0:
        return "WIN"
    elif pnl_rupiah < 0:
        return "LOSS"
    else:
        return "BREAKEVEN"


def calculate_rr_actual(entry: float, exit_price: float, sl: float) -> float:
    """Calculate actual Risk:Reward ratio achieved."""
    risk_per_share = abs(entry - sl)
    if risk_per_share == 0:
        return 0.0
        
    reward_per_share = abs(exit_price - entry)
    return round(reward_per_share / risk_per_share, 2)


def aggregate_partial_exists(legs: List[Dict[str, Any]], original_qty: int) -> Dict[str, float]:
    """
    Aggregate legs to get weighted exit price and total P&L.
    """
    total_qty = 0
    total_value = 0.0
    total_fees = 0.0
    total_pnl = 0.0
    
    for leg in legs:
        q = leg["qty"]
        p = leg["exit_price"]
        f = leg.get("fees", 0.0)
        pnl = leg["pnl_rupiah"]
        
        total_qty += q
        total_value += (q * p)
        total_fees += f
        total_pnl += pnl
        
    weighted_exit = total_value / total_qty if total_qty > 0 else 0.0
    
    return {
        "weighted_exit_price": weighted_exit,
        "total_fees": total_fees,
        "total_pnl": total_pnl,
        "total_qty_sold": total_qty
    }
