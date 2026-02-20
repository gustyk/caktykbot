"""Report generation for backtest results."""
from typing import Dict, Any


def generate_backtest_report(run, metrics: Dict[str, Any]) -> str:
    """Generate a text summary of the backtest.

    Args:
        run: BacktestRun object (Pydantic model) or dict.
        metrics: Performance metrics dictionary from calculate_metrics().
    """
    # Support both Pydantic model and plain dict
    if hasattr(run, "strategy"):
        strategy = run.strategy
        start_date = run.start_date
        end_date = run.end_date
        initial_capital = run.initial_capital
    else:
        # fallback: dict
        strategy = run.get("strategy", "Unknown")
        start_date = run.get("start_date")
        end_date = run.get("end_date")
        initial_capital = run.get("initial_capital", 0)

    # Safe date formatting (handles datetime object or None)
    def fmt_date(d):
        if d is None:
            return "N/A"
        if hasattr(d, "strftime"):
            return d.strftime("%Y-%m-%d")
        return str(d)[:10]

    total_trades = metrics.get("total_trades", 0)

    if total_trades == 0:
        summary = (
            f"📊 *Backtest Report — {strategy.upper()}*\n"
            f"Periode: {fmt_date(start_date)} → {fmt_date(end_date)}\n\n"
            f"⚠️ *Tidak ada trade yang dieksekusi.*\n\n"
            f"Kemungkinan penyebab:\n"
            f"• Data historis tidak memadai di database\n"
            f"• Kriteria sinyal strategi terlalu ketat\n"
            f"• Untuk *bandarmologi*: data broker/foreign tidak tersedia di mode backtest\n"
            f"  (hanya price-action yang digunakan)"
        )
        return summary

    summary = (
        f"📊 *Backtest Report — {strategy.upper()}*\n"
        f"Periode: {fmt_date(start_date)} → {fmt_date(end_date)}\n\n"
        f"*📈 Performance:*\n"
        f"• Return: `{metrics.get('total_return', 0):.2f}%`\n"
        f"• Win Rate: `{metrics.get('win_rate', 0):.1f}%`\n"
        f"• Total Trade: `{total_trades}`\n"
        f"• Profit Factor: `{metrics.get('profit_factor', 0)}`\n"
        f"• Max Drawdown: `{metrics.get('max_drawdown', 0):.2f}%`\n"
        f"• Sharpe Ratio: `{metrics.get('sharpe_ratio', 0)}`\n\n"
        f"*📉 Rata-rata Trade:*\n"
        f"• Avg Profit: `{metrics.get('avg_profit', 0):.2f}%`\n"
        f"• Avg Loss: `{metrics.get('avg_loss', 0):.2f}%`\n"
        f"• Best Trade: `{metrics.get('best_trade', 0):.2f}%`\n"
        f"• Worst Trade: `{metrics.get('worst_trade', 0):.2f}%`\n"
        f"• R/R: `1:{metrics.get('risk_reward', 0)}`\n\n"
        f"*💰 Modal:*\n"
        f"• Awal: `Rp {initial_capital:,.0f}`\n"
        f"• Akhir: `Rp {metrics.get('final_capital', initial_capital):,.0f}`"
    )
    return summary.strip()


def format_telegram_message(run_id: str, summary: str) -> str:
    """Format the report for Telegram."""
    return f"{summary}\n\n🆔 Run ID: `{run_id}`"
