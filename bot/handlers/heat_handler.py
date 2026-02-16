"""Handler for /heat command (FR-09)."""

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from db.repositories.portfolio_repo import PortfolioRepository
from risk.heat_monitor import calculate_portfolio_heat

async def handle_heat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /heat command.
    Show current portfolio heat and open positions risk.
    """
    if not update.message:
        return

    db = context.bot_data["db"]
    repo = PortfolioRepository(db)
    
    config = repo.get_config()
    if not config:
        await update.message.reply_text("⚠️ Configuration not found.")
        return

    # Fetch open trades
    open_trades_cursor = db.trades.find({"status": "open", "user": config.user})
    open_trades = list(open_trades_cursor)
    
    # Calculate heat
    heat_status = calculate_portfolio_heat(open_trades, config.total_capital, config.max_heat)
    
    # Format output
    # 🔥 Portfolio Heat Monitor
    # ──────────────────
    # Current Heat: 2.8% / 8.0%
    # ████░░░░░░░░░░░░░░░░ 🟢 Safe
    # 
    # Open Positions (3):
    #   TLKM.JK  | Risk: 1.0% | Exp: 15%
    #   ...
    # 
    # Available Heat: 5.2%
    # Cash Reserve: 62% (target: 30%) ✅
    
    current = heat_status["current_heat"]
    limit = heat_status["max_heat"]
    pct = min(current / limit, 1.0) if limit > 0 else 0
    bar_len = 20
    filled = int(pct * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    status_emoji = "🟢 Safe"
    if heat_status["status"] == "limit":
        status_emoji = "🔴 LIMIT REACHED"
    elif heat_status["status"] == "warning":
        status_emoji = "🟡 WARNING"
        
    msg = (
        f"🔥 *Portfolio Heat Monitor*\n"
        f"──────────────────\n"
        f"Current Heat: {current:.1%} / {limit:.1%}\n"
        f"`{bar}` {status_emoji}\n\n"
        f"Open Positions ({len(open_trades)}):\n"
    )
    
    for pos in heat_status["positions"]:
        sym = pos["symbol"]
        r = pos["risk"]
        exp_rupiah = pos["exposure"]
        exp_pct = exp_rupiah / config.total_capital if config.total_capital else 0
        msg += f"  `{sym:<8} | R: {r:.1%} | E: {exp_pct:.1%}`\n"
        
    msg += f"\nAvailable Heat: {heat_status['available_heat']:.1%}\n"
    
    cash_ok = "✅" if heat_status["cash_reserve_ok"] else "⚠️"
    msg += f"Cash Reserve: {heat_status['cash_reserve_pct']:.1%} (target: {config.cash_reserve_target:.1%}) {cash_ok}"
    
    await update.message.reply_text(msg, parse_mode="Markdown")
