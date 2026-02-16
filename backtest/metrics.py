"""Performance metrics calculator for backtesting."""
import numpy as np
import pandas as pd
from typing import List, Dict, Any

def calculate_metrics(trades: List[Dict[str, Any]], initial_capital: float) -> Dict[str, Any]:
    """
    Calculate performance metrics from a list of trades.
    
    Args:
        trades: List of trade dictionaries containing 'pnl_rupiah', 'pnl_percent', etc.
        initial_capital: Starting capital for the backtest.
        
    Returns:
        Dictionary containing win_rate, profit_factor, max_drawdown, etc.
    """
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_profit": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "risk_reward": 0.0,
            "total_return": 0.0,
            "final_capital": initial_capital,
            "best_trade": 0.0,
            "worst_trade": 0.0
        }

    df = pd.DataFrame(trades)
    
    # Basic Counts
    total_trades = len(df)
    wins = df[df['pnl_rupiah'] > 0]
    losses = df[df['pnl_rupiah'] <= 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    
    # Win Rate
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
    
    # Averages
    avg_profit = wins['pnl_percent'].mean() if not wins.empty else 0.0
    avg_loss = losses['pnl_percent'].mean() if not losses.empty else 0.0
    
    # Profit Factor
    gross_profit = wins['pnl_rupiah'].sum() if not wins.empty else 0.0
    gross_loss = abs(losses['pnl_rupiah'].sum()) if not losses.empty else 0.0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
    
    # Risk Reward
    risk_reward = round(abs(avg_profit / avg_loss), 2) if avg_loss != 0 else 0.0
    
    # Equity Curve & Drawdown
    # We need to sort trades by exit date to calculate running equity
    df['exit_date'] = pd.to_datetime(df['exit_date'])
    df = df.sort_values('exit_date')
    
    equity = [initial_capital]
    current_capital = initial_capital
    
    for pnl in df['pnl_rupiah']:
        current_capital += pnl
        equity.append(current_capital)
        
    equity_curve = np.array(equity)
    peaks = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - peaks) / peaks * 100
    max_drawdown = drawdowns.min()
    
    # Total Return
    total_return_rupiah = current_capital - initial_capital
    total_return_pct = (total_return_rupiah / initial_capital) * 100
    
    # Sharpe Ratio (Simplified using trade returns, ideally should use daily returns)
    # Annualized assuming 252 trading days average, but here we use per-trade sequence
    # This is a rough approximation if we don't have daily equity snapshots
    returns = df['pnl_percent'] / 100
    if len(returns) > 1 and returns.std() > 0:
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(len(returns)) # Annualized? No, this is trade-based Sharpe
        # Let's stick to standard trade-based Sharpe or Sortino
        # Ideally: (Mean Return - Risk Free) / Std Dev
        sharpe_ratio = round(returns.mean() / returns.std(), 2)
    else:
        sharpe_ratio = 0.0

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "avg_profit": round(avg_profit, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": profit_factor,
        "max_drawdown": round(max_drawdown, 2),
        "sharpe_ratio": sharpe_ratio,
        "risk_reward": risk_reward,
        "total_return": round(total_return_pct, 2),
        "final_capital": round(current_capital, 2),
        "best_trade": round(df['pnl_percent'].max(), 2),
        "worst_trade": round(df['pnl_percent'].min(), 2)
    }
