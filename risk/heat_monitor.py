"""Portfolio Heat Monitor (FR-09)."""

from typing import List, Dict, Any

from caktykbot.risk.constants import (
    MAX_PORTFOLIO_HEAT,
    HEAT_WARNING_LEVEL,
    MIN_CASH_RESERVE,
    MSG_HEAT_LIMIT
)

def calculate_portfolio_heat(
    open_trades: List[Dict],
    total_capital: float,
    max_heat_limit: float = MAX_PORTFOLIO_HEAT
) -> Dict[str, Any]:
    """
    Calculate current portfolio heat and cash reserve.
    
    Args:
        open_trades: List of open trade dictionaries (must have 'risk_percent' and 'entry_price'/'qty')
        total_capital: Total trading capital
        max_heat_limit: Max allowed heat (decimal)
        
    Returns:
        Dict with current status
    """
    current_heat = 0.0
    total_exposure = 0.0
    
    positions = []
    
    for trade in open_trades:
        # Risk is usually stored as decimal (e.g. 0.01 for 1%)
        # If stored as float, we sum it up.
        risk = trade.get("risk_percent", 0.0)
        current_heat += risk
        
        # Calculate exposure
        qty = trade.get("qty_remaining", trade.get("qty", 0))
        entry_price = trade.get("entry_price", 0.0)
        exposure = qty * entry_price
        total_exposure += exposure
        
        positions.append({
            "symbol": trade.get("symbol"),
            "risk": risk,
            "exposure": exposure
        })
        
    # Cash Reserve
    cash_used = total_exposure
    cash_reserve = total_capital - cash_used
    cash_reserve_pct = cash_reserve / total_capital if total_capital > 0 else 0.0
    
    # Status
    status = "safe"
    if current_heat >= max_heat_limit:
        status = "limit"
    elif current_heat >= HEAT_WARNING_LEVEL:
        status = "warning"
        
    return {
        "current_heat": current_heat,
        "max_heat": max_heat_limit,
        "available_heat": max(0.0, max_heat_limit - current_heat),
        "status": status,
        "positions": positions,
        "total_exposure": total_exposure,
        "cash_reserve_pct": cash_reserve_pct,
        "cash_reserve_ok": cash_reserve_pct >= MIN_CASH_RESERVE
    }

def project_heat_with_new_trade(
    current_heat: float,
    new_trade_risk: float,
    max_heat_limit: float = MAX_PORTFOLIO_HEAT
) -> Dict[str, Any]:
    """
    Project portfolio heat with a new trade.
    
    Returns:
        Dict with projection results
    """
    projected_heat = current_heat + new_trade_risk
    
    would_exceed = projected_heat > max_heat_limit
    
    message = ""
    if would_exceed:
        message = MSG_HEAT_LIMIT.format(projected=projected_heat)
    
    return {
        "projected_heat": projected_heat,
        "would_exceed": would_exceed,
        "message": message
    }
