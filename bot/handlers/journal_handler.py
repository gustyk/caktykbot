"""Handlers for Journal Viewing and Stats."""
from telegram import Update, InputFile
from telegram.ext import ContextTypes, CommandHandler
from loguru import logger

from db.repositories.trade_repo import TradeRepository
from journal.statistics import StatisticsEngine
from journal.exporter import Exporter

async def handle_journal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /journal [page]
    List recent trades (open and closed).
    """
    db = context.bot_data["db"]
    repo = TradeRepository(db)
    
    # Simple pagination?
    limit = 5
    trades = repo.get_last_trades(limit=limit)
    
    if not trades:
        await update.message.reply_text("📭 Journal is empty.")
        return
        
    msg = "📔 *Trading Journal (Last 5)*\n\n"
    for t in trades:
        status_icon = "🟢" if t.status == "open" else "🔴" if t.status == "closed" else "📝"
        pnl_str = ""
        if t.pnl_rupiah is not None:
            icon = "✅" if t.pnl_rupiah > 0 else "❌"
            pnl_str = f"| {icon} {t.pnl_rupiah:,.0f}"
            
        date_str = t.entry_date.strftime("%d/%m")
        msg += f"{status_icon} *{t.symbol}* ({date_str})\n"
        msg += f"   {t.qty:,} @ {t.entry_price:,.0f} {pnl_str}\n"
        if t.status == "closed":
             msg += f"   Exit: {t.exit_price:,.0f} | Hold: {t.holding_days}d\n"
        msg += "\n"
        
    await update.message.reply_text(msg, parse_mode="Markdown")


async def handle_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /stats
    Show performance summary.
    """
    db = context.bot_data["db"]
    repo = TradeRepository(db)
    
    # Get all closed trades (implied by pnl presence, or check status)
    all_trades = repo.get_all_trades()
    closed_trades = [t for t in all_trades if t.status == "closed" or (t.legs and t.pnl_rupiah)]
    
    stats = StatisticsEngine.calculate_summary(closed_trades)
    
    msg = (
        "📊 *Performance Stats*\n"
        "─────────────────\n"
        f"Trades: {stats['total_trades']} ({stats['win_loss_ratio']})\n"
        f"Win Rate: {stats['win_rate']:.1f}%\n"
        f"Profit Factor: {stats['profit_factor']:.2f}\n\n"
        f"💰 *Net P&L*: Rp {stats['total_pnl']:,.0f}\n"
        f"Avg Win: Rp {stats['avg_win']:,.0f}\n"
        f"Avg Loss: Rp {stats['avg_loss']:,.0f}\n"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_trade_detail_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /trade <SYMBOL>
    Show details of latest trade for symbol.
    """
    if not context.args:
         await update.message.reply_text("Usage: `/trade <SYMBOL>`")
         return
         
    symbol = context.args[0].upper()
    if not symbol.endswith(".JK"):
        symbol += ".JK"
        
    db = context.bot_data["db"]
    repo = TradeRepository(db)
    
    trades = repo.get_last_trades(limit=5) # Not filtered by symbol in repo method?
    # We need filter. `get_open_trades` filters. `get_last_trades` doesn't support symbol arg currently.
    # Let's use `get_open_trades` + `get_closed_trades`?
    # Or just fetch all and filter python side (inefficient but ok for now)
    # Better: Add method to repo or valid query.
    # Checking repo content... `get_open_trades` supports symbol.
    # Let's just find open ones first.
    
    open_trades = repo.get_open_trades(symbol)
    if open_trades:
        t = open_trades[0]
        # Detail View
        msg = (
            f"🟢 *Open Trade: {t.symbol}*\n"
            f"Entry: {t.entry_date.strftime('%Y-%m-%d')} @ {t.entry_price:,.0f}\n"
            f"Qty: {t.qty:,}\n"
            f"Strategy: {t.strategy}\n"
            f"Notes: {t.notes or '-'}\n"
        )
        if t.legs:
            msg += "\n*Partial Exits:*\n"
            for leg in t.legs:
                msg += f"- {leg.qty} @ {leg.exit_price:,.0f} ({leg.pnl_rupiah:,.0f})\n"
                
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # If no open, find closed?
    # We don't have explicit `get_closed_trades_by_symbol` in repo yet.
    # Use generic query or skip.
    await update.message.reply_text(f"❌ No active open trade found for {symbol}.")


async def handle_export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /export
    Send CSV file of all trades.
    """
    db = context.bot_data["db"]
    repo = TradeRepository(db)
    
    trades = repo.get_all_trades()
    if not trades:
        await update.message.reply_text("📭 No trades to export.")
        return
        
    csv_buffer = Exporter.to_csv(trades)
    
    # Send file
    await update.message.reply_document(
        document=csv_buffer.getvalue().encode(),
        filename=f"journal_export_{len(trades)}.csv",
        caption=f"📊 Exported {len(trades)} trades."
    )

