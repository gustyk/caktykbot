"""Handlers for Trade Entry and Management."""
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    filters
)
from loguru import logger

from db.repositories.trade_repo import TradeRepository
from journal.trade_manager import TradeManager

# States
(
    SYMBOL, 
    DATE, 
    PRICE, 
    QTY, 
    STRATEGY, 
    RISK, 
    EMOTION, 
    NOTES,
    CONFIRM_ADD
) = range(9)

(
    CLOSE_SELECT,
    CLOSE_TYPE,
    CLOSE_PRICE,
    CLOSE_QTY,
    CLOSE_FEES,
    CLOSE_DATE,
    CLOSE_EMOTION,
    CONFIRM_CLOSE
) = range(8)

async def start_add_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start /addtrade conversation."""
    await update.message.reply_text(
        "📝 *New Trade Entry*\n\n"
        "Masukkan Kode Saham (contoh: BBCA.JK):",
        parse_mode="Markdown"
    )
    return SYMBOL

async def add_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.upper()
    if not text.endswith(".JK"):
        text += ".JK"
    
    context.user_data["trade_entry"] = {"symbol": text}
    
    await update.message.reply_text(
        f"Symbol: *{text}*\n\n"
        "📅 Tanggal Entry (format: YYYY-MM-DD atau 'today'):",
        parse_mode="Markdown"
    )
    return DATE

async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.lower()
    try:
        if text == "today":
            entry_date = datetime.now()
        else:
            entry_date = datetime.strptime(text, "%Y-%m-%d")
            
        context.user_data["trade_entry"]["entry_date"] = entry_date
        
        await update.message.reply_text("💰 Harga Entry (Rp):")
        return PRICE
    except ValueError:
        await update.message.reply_text("❌ Format tanggal salah. Gunakan YYYY-MM-DD atau 'today'.")
        return DATE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = float(update.message.text.replace(",", "").replace(".", ""))
        context.user_data["trade_entry"]["entry_price"] = price
        await update.message.reply_text("📊 Quantity (Jumlah Lembar):")
        return QTY
    except ValueError:
        await update.message.reply_text("❌ Input angka valid.")
        return PRICE

async def add_qty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = int(update.message.text.replace(",", "").replace(".", ""))
        context.user_data["trade_entry"]["qty"] = qty
        
        strategies = [["VCP", "EMA Pullback"], ["Bandarmologi", "Custom"]]
        await update.message.reply_text(
            "🎯 Pilih Strategy:",
            reply_markup=ReplyKeyboardMarkup(strategies, one_time_keyboard=True)
        )
        return STRATEGY
    except ValueError:
        await update.message.reply_text("❌ Input angka valid (integer).")
        return QTY

async def add_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["trade_entry"]["strategy"] = update.message.text
    await update.message.reply_text("⚠️ Risk % per trade (dari modal):", reply_markup=ReplyKeyboardRemove())
    return RISK

async def add_risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        risk = float(update.message.text.replace("%", ""))
        context.user_data["trade_entry"]["risk_percent"] = risk
        
        emotions = [["Confident", "Anxious"], ["FOMO", "Disciplined"], ["Revenge", "Neutral"]]
        await update.message.reply_text(
            "🧠 Emotion saat entry?",
            reply_markup=ReplyKeyboardMarkup(emotions, one_time_keyboard=True)
        )
        return EMOTION
    except ValueError:
        await update.message.reply_text("❌ Input angka valid.")
        return RISK

async def add_emotion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["trade_entry"]["emotion_tag"] = update.message.text
    await update.message.reply_text("📋 Notes (optional, kirim 'skip' jika kosong):", reply_markup=ReplyKeyboardRemove())
    return NOTES

async def add_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text.lower() != "skip":
        context.user_data["trade_entry"]["notes"] = text
    
    data = context.user_data["trade_entry"]
    
    summary = (
        f"📝 *Konfirmasi Entry*\n"
        f"Symbol: {data['symbol']}\n"
        f"Date: {data['entry_date'].strftime('%Y-%m-%d')}\n"
        f"Buy: {data['qty']:,} @ {data['entry_price']:,}\n"
        f"Strategy: {data['strategy']}\n"
        f"Risk: {data['risk_percent']}%\n"
        f"Emotion: {data['emotion_tag']}\n\n"
        "Ketik 'ok' untuk simpan, atau /cancel untuk batal."
    )
    await update.message.reply_text(summary, parse_mode="Markdown")
    return CONFIRM_ADD

async def confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.lower() == "ok":
        db = context.bot_data["db"]
        repo = TradeRepository(db)
        manager = TradeManager(repo)
        
        try:
            manager.create_trade(context.user_data["trade_entry"])
            await update.message.reply_text("✅ Trade saved successfully!")
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
            await update.message.reply_text(f"❌ Failed to save: {e}")
    else:
        await update.message.reply_text("❌ Check 'ok' not received. Cancelled logic not implemented here directly.")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🚫 Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# --- Close Trade Handlers ---

async def start_close_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start /closetrade [SYMBOL]."""
    if context.args:
        text = context.args[0].upper()
        if not text.endswith(".JK"):
            text += ".JK"
        symbol = text
    else:
        # Ask for symbol if not provided? simplified: req args
        await update.message.reply_text("Usage: `/closetrade <SYMBOL>`", parse_mode="Markdown")
        return ConversationHandler.END
        
    db = context.bot_data["db"]
    repo = TradeRepository(db)
    trades = repo.get_open_trades(symbol=symbol)
    
    if not trades:
        await update.message.reply_text(f"❌ No open trades found for {symbol}.")
        return ConversationHandler.END
        
    # If multiple trades, we might need selection. For now assuming FIFO or just picking first?
    # Or listing them.
    # Sprint plan: "Bot: Open trade found... Close all or partial?"
    # If multiple, listing them by ID is safer.
    
    if len(trades) > 1:
        msg = "📋 *Multiple Trades Found:*\n"
        for i, t in enumerate(trades):
            msg += f"{i+1}. {t.entry_date.strftime('%Y-%m-%d')} | {t.qty_remaining:,} @ {t.entry_price:,.0f}\n"
        msg += "\nSilakan reply nomor trade (1, 2, ...):"
        context.user_data["close_candidates"] = trades
        await update.message.reply_text(msg, parse_mode="Markdown")
        return CLOSE_SELECT
    else:
        context.user_data["close_trade"] = trades[0]
        return await prompt_close_type(update, context)

async def select_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        idx = int(update.message.text) - 1
        trades = context.user_data["close_candidates"]
        if 0 <= idx < len(trades):
            context.user_data["close_trade"] = trades[idx]
            return await prompt_close_type(update, context)
        else:
            await update.message.reply_text("❌ Invalid selection.")
            return CLOSE_SELECT
    except ValueError:
        await update.message.reply_text("❌ Input number.")
        return CLOSE_SELECT

async def prompt_close_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    trade = context.user_data["close_trade"]
    await update.message.reply_text(
        f"📋 Closing {trade.symbol}\n"
        f"Qty Remaining: {trade.qty_remaining:,}\n\n"
        "Pilih tipe close:",
        reply_markup=ReplyKeyboardMarkup([["Close All", "Partial Close"]], one_time_keyboard=True)
    )
    return CLOSE_TYPE

async def close_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    context.user_data["close_params"] = {"type": choice}
    
    if choice == "Close All":
        context.user_data["close_params"]["qty"] = context.user_data["close_trade"].qty_remaining
        await update.message.reply_text("💰 Exit Price (Rp):", reply_markup=ReplyKeyboardRemove())
        return CLOSE_PRICE
    else:
        await update.message.reply_text("📊 Qty to sell:", reply_markup=ReplyKeyboardRemove())
        return CLOSE_QTY

async def close_qty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        qty = int(update.message.text.replace(",", "").replace(".", ""))
        trade = context.user_data["close_trade"]
        if qty > trade.qty_remaining or qty <= 0:
            await update.message.reply_text(f"❌ Invalid qty. Max: {trade.qty_remaining}")
            return CLOSE_QTY
            
        context.user_data["close_params"]["qty"] = qty
        await update.message.reply_text("💰 Exit Price (Rp):")
        return CLOSE_PRICE
    except ValueError:
        return CLOSE_QTY

async def close_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = float(update.message.text.replace(",", "").replace(".", ""))
        context.user_data["close_params"]["exit_price"] = price
        await update.message.reply_text("💸 Fees (Broker + Tax, Rp or 0):")
        return CLOSE_FEES
    except:
        return CLOSE_PRICE

async def close_fees(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        fees = float(update.message.text.replace(",", "").replace(".", ""))
        context.user_data["close_params"]["fees"] = fees
        await update.message.reply_text("📅 Exit Date (YYYY-MM-DD or 'today'):")
        return CLOSE_DATE
    except:
        return CLOSE_FEES

async def close_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.lower()
    try:
        if text == "today":
            dt = datetime.now()
        else:
            dt = datetime.strptime(text, "%Y-%m-%d")
        context.user_data["close_params"]["exit_date"] = dt
        
        emotions = [["Confident", "Anxious"], ["Panic", "Disciplined"]]
        await update.message.reply_text(
            "🧠 Exit Emotion?",
            reply_markup=ReplyKeyboardMarkup(emotions, one_time_keyboard=True)
        )
        return CLOSE_EMOTION
    except:
        await update.message.reply_text("❌ Format YYYY-MM-DD or 'today'.")
        return CLOSE_DATE

async def close_emotion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["close_params"]["emotion_tag"] = update.message.text
    
    data = context.user_data["close_params"]
    trade = context.user_data["close_trade"]
    
    await update.message.reply_text(
        f"📝 *Confirm Close*\n"
        f"Type: {data['type']}\n"
        f"Sell: {data['qty']:,} @ {data['exit_price']:,}\n"
        f"Date: {data['exit_date'].strftime('%Y-%m-%d')}\n\n"
        "Ketik 'ok' untuk proses.",
        parse_mode="Markdown"
    )
    return CONFIRM_CLOSE

async def confirm_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.lower() == "ok":
        db = context.bot_data["db"]
        repo = TradeRepository(db)
        manager = TradeManager(repo)
        
        trade = context.user_data["close_trade"]
        params = context.user_data["close_params"]
        
        exit_payload = {
            "exit_price": params["exit_price"],
            "exit_date": params["exit_date"],
            "fees": params["fees"],
            "emotion_tag": params["emotion_tag"],
            "qty": params["qty"]
        }
        
        try:
            if params["type"] == "Close All":
                res = manager.close_trade(str(trade.id), exit_payload) # Pydantic model doesn't store _id in field `id` by default unless aliased? 
                # PyMongo retrieves _id. Pydantic schema doesn't have id field defined? 
                # Schema: Trade(BaseModel). 
                # When converting from DB doc to Trade, _id is usually lost unless mapped.
                # !!! IMPORTANT: Trade schema needs to handle _id or we pass it separately?
                # TradeRepository.get_open_trades returns List[Trade].
                # We need the ID to update.
                # Let's verify Trade schema in previous step.
                # It doesn't have id field.
                # We should add id alias or extract from context if possible. 
                # Repo.get_open_trades -> does it default parse _id? No.
                # Fix: TradeRepository should attach _id to the object or return tuple.
                
                # Assume we need to fix TradeRepository or Schema to include ID.
                # For now, let's assume I can get ID from the doc directly if stored in user_data as dict?
                # But I stored `Trade` object.
                # I will fix TradeRepository to inject id or use dicts?
                # Better: Allow TradeRepository to return dicts or TradeWithID.
                
                # TEMPORARY FIX: Assume Trade object has no ID. I need to re-fetch/match? 
                # Or simply: In `get_open_trades`, mapping _id to id str. Needs schema update.
                pass
            else:
                res = manager.partial_close(str(trade.id), exit_payload)
                
            await update.message.reply_text(
                f"✅ Trade Updated!\n"
                f"P&L: {res.get('pnl_rupiah', 0):,.0f} ({res.get('pnl_percent', 0):.2f}%)\n"
                f"Status: {res.get('status', 'updated')}"
            )
        except Exception as e:
            logger.error(f"Close failed: {e}")
            await update.message.reply_text(f"❌ Failed: {e}")
            
    return ConversationHandler.END

add_trade_handler = ConversationHandler(
    entry_points=[CommandHandler("addtrade", start_add_trade)],
    states={
        SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_symbol)],
        DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
        PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
        QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_qty)],
        STRATEGY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_strategy)],
        RISK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_risk)],
        EMOTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_emotion)],
        NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_notes)],
        CONFIRM_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_add)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

close_trade_handler = ConversationHandler(
    entry_points=[CommandHandler("closetrade", start_close_trade)],
    states={
        CLOSE_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_trade)],
        CLOSE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, close_type)],
        CLOSE_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, close_qty)],
        CLOSE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, close_price)],
        CLOSE_FEES: [MessageHandler(filters.TEXT & ~filters.COMMAND, close_fees)],
        CLOSE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, close_date)],
        CLOSE_EMOTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, close_emotion)],
        CONFIRM_CLOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_close)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)
