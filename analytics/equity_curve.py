from typing import List, Dict, Any
import pandas as pd
from datetime import datetime

def calculate_equity_curve(trades: List[Dict], initial_capital: float) -> List[Dict[str, Any]]:
    """
    Calculate equity curve and drawdown from trade history.
    
    Args:
        trades: List of trade dictionaries (must contain 'exit_date' and 'pnl_rupiah')
        initial_capital: Starting capital amount
        
    Returns:
        List of daily equity points sorted by date.
    """
    if not trades:
        return []
        
    # Create DataFrame
    df = pd.DataFrame(trades)
    
    # Ensure datetime
    if "exit_date" in df.columns:
        df["exit_date"] = pd.to_datetime(df["exit_date"])
        
    # Sort by exit date
    df = df.sort_values("exit_date")
    
    equity = initial_capital
    peak_equity = initial_capital
    curve = []
    
    # Starting point
    curve.append({
        "date": df["exit_date"].min() - pd.Timedelta(days=1), # Yesterday
        "equity": initial_capital,
        "drawdown_pct": 0.0
    })
    
    for _, trade in df.iterrows():
        pnl = trade.get("pnl_rupiah", 0)
        equity += pnl
        
        peak_equity = max(peak_equity, equity)
        drawdown = (peak_equity - equity) / peak_equity * 100 if peak_equity > 0 else 0
        
        curve.append({
            "date": trade["exit_date"],
            "equity": equity,
            "drawdown_pct": drawdown,
            "trade_pnl": pnl
        })
        
    return curve
