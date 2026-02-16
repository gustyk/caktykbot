"""Telegram bot handlers for watchlist management."""

from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

from db.repositories.stock_repo import StockRepository
from db.schemas import StockCreate
from utils.exceptions import (
    StockRepoError, 
    WatchlistFullError, 
    DuplicateStockError, 
    InvalidSymbolError
)

async def handle_add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command to add a stock to the watchlist."""
    if not update.message or not context.args:
        await update.message.reply_text("Format salah. Gunakan: /add SYMBOL.JK\nContoh: /add BBCA.JK")
        return

    symbol = context.args[0].upper()
    db = context.application.bot_data["db"]
    repo = StockRepository(db)

    try:
        # Pydantic validation via StockCreate
        # Note: We use the symbol as name as well for simplicity in quick /add
        name = symbol.split('.')[0]
        stock_data = StockCreate(symbol=symbol, name=name)
        repo.add_stock(stock_data)
        
        logger.info(f"User added stock: {symbol}")
        await update.message.reply_text(f"✅ {symbol} berhasil ditambahkan ke watchlist.")
        
    except (WatchlistFullError, DuplicateStockError, InvalidSymbolError) as e:
        await update.message.reply_text(f"❌ Gagal: {str(e)}")
    except Exception as e:
        logger.error(f"Error in /add {symbol}: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan internal saat menambah stock.")

async def handle_remove_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove command to deactivate a stock."""
    if not update.message or not context.args:
        await update.message.reply_text("Format salah. Gunakan: /remove SYMBOL.JK")
        return

    symbol = context.args[0].upper()
    db = context.application.bot_data["db"]
    repo = StockRepository(db)

    try:
        repo.deactivate_stock(symbol)
        logger.info(f"User removed stock: {symbol}")
        await update.message.reply_text(f"🗑️ {symbol} telah dihapus dari watchlist aktif.")
        
    except StockRepoError as e:
        await update.message.reply_text(f"❌ Gagal: {str(e)}")
    except Exception as e:
        logger.error(f"Error in /remove {symbol}: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan internal saat menghapus stock.")

async def handle_list_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /watchlist command to show active stocks."""
    if not update.message:
        return
        
    db = context.application.bot_data["db"]
    repo = StockRepository(db)

    try:
        stocks = repo.get_all_stocks(only_active=True)
        if not stocks:
            await update.message.reply_text("Watchlist kosong. Gunakan /add untuk menambah stock.")
            return

        message = "📋 *Watchlist Aktif:*\n\n"
        for i, stock in enumerate(stocks, 1):
            # Escaping for MarkdownV2 is complex, using simple markdown or escaping dots
            safe_symbol = stock.symbol.replace(".", "\\.")
            message += f"{i}\\. `{safe_symbol}`\n"
        
        await update.message.reply_text(message, parse_mode="MarkdownV2")
        
    except Exception as e:
        logger.error(f"Error in /watchlist: {e}")
        await update.message.reply_text("❌ Gagal mengambil data watchlist.")
