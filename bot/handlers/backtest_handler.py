from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from loguru import logger

from db.connection import get_database
from backtest.engine import BacktestEngine
from backtest.report import generate_backtest_report, format_telegram_message

VALID_STRATEGIES = {"vcp", "ema_pullback", "bandarmologi"}


async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /backtest command.

    Usage: /backtest <strategy> [days]
    Example: /backtest bandarmologi 365
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "📊 *Backtest Usage:*\n"
            "`/backtest <strategy> [days=365]`\n\n"
            "*Strategies:*\n"
            "• `vcp` — VCP Breakout\n"
            "• `ema_pullback` — EMA Pullback\n"
            "• `bandarmologi` — Bandarmologi\n\n"
            "_⚠️ Bandarmologi backtest menggunakan price-action only "
            "(data broker/foreign tidak tersedia di historical)_",
            parse_mode="Markdown",
        )
        return

    strategy = args[0].lower()
    if strategy not in VALID_STRATEGIES:
        await update.message.reply_text(
            f"❌ Strategi `{strategy}` tidak dikenal.\n"
            f"Pilihan: `vcp`, `ema_pullback`, `bandarmologi`",
            parse_mode="Markdown",
        )
        return

    days = 365
    if len(args) > 1:
        if args[1].isdigit():
            days = int(args[1])
        else:
            await update.message.reply_text(
                f"❌ `days` harus berupa angka, contoh: `/backtest {strategy} 180`",
                parse_mode="Markdown",
            )
            return

    if days < 30 or days > 1825:
        await update.message.reply_text(
            "❌ `days` harus antara 30 s/d 1825 (5 tahun).", parse_mode="Markdown"
        )
        return

    status_msg = await update.message.reply_text(
        f"⏳ Menjalankan backtest *{strategy.upper()}* selama *{days} hari*...\n\n"
        f"_Proses ini mungkin memakan waktu 1-3 menit._",
        parse_mode="Markdown",
    )

    try:
        db = get_database()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        logger.info(
            f"Starting backtest: strategy={strategy}, days={days}, "
            f"start={start_date.date()}, end={end_date.date()}"
        )

        engine = BacktestEngine(db, strategy, start_date, end_date)
        run_id = engine.run()

        # Fetch the saved run from repo to get persisted metrics
        run = engine.backtest_repo.get_run_by_id(run_id)
        if not run:
            await status_msg.edit_text("❌ Backtest selesai tapi hasilnya tidak tersimpan.")
            return

        # generate_backtest_report now receives the BacktestRun object directly
        report = generate_backtest_report(run, run.metrics)
        msg = format_telegram_message(run_id, report)

        await status_msg.edit_text(msg, parse_mode="Markdown")

    except ValueError as e:
        logger.warning(f"Backtest ValueError: strategy={strategy} days={days}: {e}")
        await status_msg.edit_text(f"❌ Error: {e}", parse_mode="Markdown")
    except Exception as e:
        logger.exception(f"Backtest unexpected error: strategy={strategy} days={days}")
        await status_msg.edit_text(
            f"❌ *Backtest gagal*\n\n"
            f"*Error:* `{type(e).__name__}: {str(e)[:300]}`",
            parse_mode="Markdown",
        )
