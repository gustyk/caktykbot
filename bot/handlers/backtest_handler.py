from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from loguru import logger

from db.connection import get_database
from backtest.engine import BacktestEngine
from backtest.report import generate_backtest_report, format_telegram_message

async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /backtest command."""
    # Usage: /backtest vcp [days]
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /backtest <strategy> [days=365]\nStrategies: vcp, ema_pullback, bandarmologi")
        return

    strategy = args[0].lower()
    days = 365
    if len(args) > 1 and args[1].isdigit():
        days = int(args[1])

    # Notify user
    status_msg = await update.message.reply_text(f"⏳ Running backtest for {strategy.upper()} ({days} days)... This may take a moment.")
    
    try:
        db = get_database()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Run Engine
        engine = BacktestEngine(db, strategy, start_date, end_date)
        run_id = engine.run()
        
        # Get Results
        # Accessing engine internals for simplicity, or use repo
        metrics = engine.closed_trades # wait, engine.run returns run_id
        # We can reconstruct metrics or get from engine if we modified run to return it
        # Actually engine.run returns run_id.
        # Let's fetch the run from repo to get metrics
        run = engine.backtest_repo.get_run_by_id(run_id)
        
        if not run:
            await status_msg.edit_text("❌ Error: Backtest run saved but not found.")
            return

        # Generate Report
        report = generate_backtest_report(run.model_dump(), run.metrics)
        msg = format_telegram_message(run_id, report)
        
        await status_msg.edit_text(msg, parse_mode="Markdown")
        
    except ValueError as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        await status_msg.edit_text("❌ An unexpected error occurred during backtest.")
