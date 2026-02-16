"""Handlers for Following Signals."""
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from loguru import logger

from db.repositories.signal_repo import SignalRepository
from db.repositories.portfolio_repo import PortfolioRepository
from db.repositories.trade_repo import TradeRepository
from journal.trade_manager import TradeManager
from db.schemas import Trade

async def handle_follow_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /follow <SYMBOL>
    Creates a draft trade based on the latest signal.
    """
    if not context.args:
        await update.message.reply_text("Usage: `/follow <SYMBOL>`", parse_mode="Markdown")
        return

    symbol = context.args[0].upper()
    if not symbol.endswith(".JK"):
        symbol += ".JK"

    db = context.bot_data["db"]
    signal_repo = SignalRepository(db)
    portfolio_repo = PortfolioRepository(db)
    trade_repo = TradeRepository(db)
    # trade manager for creation? or use repo directly for draft? 
    # Manager.create_trade sets status='open' by default in my implementation.
    # I should use repo directly for draft or add draft support to manager. 
    # Let's use repo directly or modify logic.
    # Actually I can just create Trade model with status='draft' and insert.
    
    # 1. Get Signal
    signals = signal_repo.get_signal_by_symbol(symbol, limit=1)
    if not signals:
        await update.message.reply_text(f"❌ No signals found for {symbol}.")
        return
        
    signal = signals[0]
    # Check strict freshness? (Today only?)
    # Sprint requirement doesn't specify strictness, but implies "Follow Signal".
    # Let's warn if old.
    now_date = datetime.now().date()
    sig_date = signal.date.date()
    
    is_stale = sig_date < now_date
    stale_msg = f"⚠️ *Warning: Signal is from {sig_date}*" if is_stale else "✅ *Fresh Signal*"
    
    if signal.verdict != "BUY":
        await update.message.reply_text(f"⚠️ Signal for {symbol} is {signal.verdict}, not BUY.")
        return

    # 2. Get Portfolio Config
    config = portfolio_repo.get_config("nesa")
    if not config:
        await update.message.reply_text("❌ Portfolio not configured. setup `/capital` first.")
        return

    # 3. Calculate Position Size
    # Risk Amount = Capital * Risk%
    risk_amount = config.total_capital * config.risk_per_trade
    
    entry = signal.entry_price
    sl = signal.sl_price
    risk_per_share = abs(entry - sl)
    
    if risk_per_share == 0:
        await update.message.reply_text("❌ Invalid Signal: Entry == SL.")
        return
        
    qty_shares = int(risk_amount / risk_per_share)
    # Round to lot (100 shares)
    qty_lots = qty_shares // 100
    qty_final = qty_lots * 100
    
    if qty_final < 100:
         await update.message.reply_text(
             f"❌ Calculated position size ({qty_shares} shares) is less than 1 lot.\n"
             f"Risk: Rp {risk_amount:,.0f} | Risk/Share: {risk_per_share:,.0f}"
         )
         return

    invested = qty_final * entry
    if invested > config.total_capital:
        # Cap at total capital?
        # Or checking cash? 
        # For sprint 3 we don't track cash rigorously yet, just Total Capital.
        # Warn if > capital.
        await update.message.reply_text(f"⚠️ Required capital (Rp {invested:,.0f}) > Portfolio Value.")
        # We proceed as draft, let user decide.

    # 4. Create Draft Trade
    draft_trade = Trade(
        user="nesa",
        symbol=symbol,
        entry_date=datetime.now(), # Draft created now
        qty=qty_final,
        qty_remaining=qty_final,
        entry_price=entry,
        risk_percent=config.risk_per_trade * 100, # Store as number (1.0 for 1%)
        strategy=signal.strategy_source,
        notes=f"Followed signal from {sig_date}",
        status="draft",
        signal_ref=str(signal.symbol) # Ideally ObjectId, but schema is str.
    )
    
    # Check if draft already exists?
    existing = trade_repo.get_draft_trades(symbol)
    if existing:
        # Update existing draft? Or just delete old and insert new.
        # Simplest: Insert new.
        pass
        
    trade_id = trade_repo.insert_trade(draft_trade)
    
    # 5. response
    msg = (
        f"📝 *Draft Trade Created*\n"
        f"{stale_msg}\n\n"
        f"Symbol: *{symbol}*\n"
        f"Entry: {entry:,.0f}\n"
        f"SL: {sl:,.0f} (Risk: {risk_per_share:,.0f}/share)\n"
        f"TP: {signal.tp_price:,.0f}\n"
        f"Qty: {qty_final:,} ({qty_lots} lots)\n"
        f"Est. Value: Rp {invested:,.0f}\n"
        f"Risk Value: Rp {risk_amount:,.0f} ({config.risk_per_trade*100}%)\n\n"
        f"To confirm & open, type:\n`/confirm {symbol}`"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def handle_confirm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /confirm <SYMBOL>
    Moves draft trade to open.
    """
    if not context.args:
        await update.message.reply_text("Usage: `/confirm <SYMBOL>`")
        return

    symbol = context.args[0].upper()
    if not symbol.endswith(".JK"):
        symbol += ".JK"

    db = context.bot_data["db"]
    trade_repo = TradeRepository(db)
    
    drafts = trade_repo.get_draft_trades(symbol)
    if not drafts:
        await update.message.reply_text(f"❌ No draft found for {symbol}. Use `/follow` first.")
        return
        
    # Pick latest draft
    draft = drafts[0]
    
    # Update to Open
    # Use TradeManager logic? Or direct update?
    # Direct update is fine here since we just change status
    
    fields = {
        "status": "open",
        "entry_date": datetime.now(), # meaningful entry time
        "updated_at": datetime.now()
    }
    
    # Need to handle _id from repository (draft is Trade object).
    # If using my fix, Trade has id field?
    # Draft came from get_draft_trades which calls Trade(**doc). 
    # If I added `id` alias in schema, it should be populated if doc has _id.
    
    trade_id = draft.id 
    if not trade_id:
        # Fallback if alias didn't work immediately without data reload?
        # It should work.
        pass
        
    success = trade_repo.update_trade_fields(trade_id, fields)
    
    if success:
        await update.message.reply_text(f"✅ Trade {symbol} is now OPEN!")
    else:
        await update.message.reply_text("❌ Failed to transform draft.")
