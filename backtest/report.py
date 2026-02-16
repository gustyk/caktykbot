"""Report generation for backtest results."""
from typing import Dict, Any

def generate_backtest_report(run_data: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    """Generate a text summary of the backtest."""
    
    summary = f"""
📊 **Backtest Report**
Strat: {run_data.get('strategy', 'Unknown').upper()}
Period: {run_data.get('start_date').strftime('%Y-%m-%d')} to {run_data.get('end_date').strftime('%Y-%m-%d')}

**Performance:**
• Return: {metrics['total_return']}%
• Win Rate: {metrics['win_rate']}%
• Trades: {metrics['total_trades']}
• Profit Factor: {metrics['profit_factor']}
• Max DD: {metrics['max_drawdown']}%
• Sharpe: {metrics['sharpe_ratio']}

**Avg Trade:**
• Profit: {metrics['avg_profit']}%
• Loss: {metrics['avg_loss']}%
• R/R: 1:{metrics['risk_reward']}

**Capital:**
• Initial: Rp {run_data.get('initial_capital', 0):,.0f}
• Final: Rp {metrics['final_capital']:,.0f}
"""
    return summary.strip()

def format_telegram_message(run_id: str, summary: str) -> str:
    """Format the report for Telegram."""
    return f"{summary}\n\n🆔 Run ID: `{run_id}`"
