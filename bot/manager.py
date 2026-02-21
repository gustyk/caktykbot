import os
import sys
import asyncio
import time
from telegram import error as tg_error
from telegram.ext import Application, CommandHandler
from telegram.request import HTTPXRequest
from loguru import logger

from config.settings import settings
from bot.handlers.watchlist import (
    handle_add_stock, 
    handle_remove_stock, 
    handle_list_watchlist
)
from bot.handlers.signal_handler import handle_signal_command
from bot.handlers.analyze_handler import handle_analyze_command
from bot.handlers.portfolio_handler import handle_capital_command, handle_risk_command
from bot.handlers.trade_entry_handler import add_trade_handler, close_trade_handler
from bot.handlers.follow_handler import handle_follow_command, handle_confirm_command
from bot.handlers.journal_handler import (
    handle_journal_command, 
    handle_stats_command, 
    handle_trade_detail_command,
    handle_export_command
)
from bot.handlers.sizing_handler import handle_size_command
from bot.handlers.heat_handler import handle_heat_command
from bot.handlers.backtest_handler import backtest_command
from bot.handlers.report_handler import report_command
from bot.handlers.health_handler import health_command
from bot.handlers.bandar_handler import handle_bandar_command
from bot.handlers.insight_handler import handle_bias_command, handle_scores_command


# ── Startup grace period ────────────────────────────────────────────────────────
# Railway starts new container BEFORE killing old one. We wait upfront
# so the old bot instance stops polling before we begin.
_STARTUP_GRACE = int(os.environ.get("BOT_STARTUP_GRACE_SECONDS", "30"))

# Delay injected inside the error handler when Conflict is detected.
# PTB re-tries get_updates after the error handler returns, so sleeping
# here IS the backoff. 30 s is enough for Railway to kill old container.
_CONFLICT_WAIT = int(os.environ.get("BOT_CONFLICT_WAIT_SECONDS", "30"))


async def _error_handler(update, context):
    """Global async error handler for the bot.

    On Conflict we sleep inside the handler before PTB retries — this is
    the correct PTB v20 pattern.  We do NOT call app.stop() / shutdown()
    because those raise RuntimeError if the app is not yet fully running.
    """
    err = context.error
    if isinstance(err, tg_error.Conflict):
        logger.warning(
            f"⚡ Conflict: another bot instance still active. "
            f"Waiting {_CONFLICT_WAIT}s before retry…"
        )
        # Sleep here — PTB will retry get_updates after handler returns.
        await asyncio.sleep(_CONFLICT_WAIT)
    elif isinstance(err, tg_error.NetworkError):
        logger.warning(f"Network error (will retry): {err}")
        await asyncio.sleep(5)
    elif isinstance(err, tg_error.TimedOut):
        logger.warning(f"Request timed out (will retry): {err}")
    else:
        logger.error(f"Unhandled bot error: {err}", exc_info=err)


class BotManager:
    """Manages Telegram bot application and handlers."""

    def __init__(self, db):
        self.db = db
        self.app = (
            Application.builder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .request(HTTPXRequest(connection_pool_size=8, connect_timeout=30.0, read_timeout=30.0))
            .build()
        )
        # Store DB in bot_data for handlers access
        self.app.bot_data["db"] = db
        self._setup_handlers()

    def _setup_handlers(self):
        """Register command handlers."""
        self.app.add_handler(CommandHandler("add", handle_add_stock))
        self.app.add_handler(CommandHandler("remove", handle_remove_stock))
        self.app.add_handler(CommandHandler("watchlist", handle_list_watchlist))
        self.app.add_handler(CommandHandler("signal", handle_signal_command))
        self.app.add_handler(CommandHandler("analyze", handle_analyze_command))
        self.app.add_handler(CommandHandler("capital", handle_capital_command))
        self.app.add_handler(CommandHandler("risk", handle_risk_command))
        self.app.add_handler(CommandHandler("size", handle_size_command))  # Sprint 4
        self.app.add_handler(CommandHandler("heat", handle_heat_command))  # Sprint 4
        self.app.add_handler(CommandHandler("follow", handle_follow_command))
        self.app.add_handler(CommandHandler("confirm", handle_confirm_command))
        self.app.add_handler(CommandHandler("journal", handle_journal_command))
        self.app.add_handler(CommandHandler("stats", handle_stats_command))
        self.app.add_handler(CommandHandler("trade", handle_trade_detail_command))
        self.app.add_handler(CommandHandler("export", handle_export_command))
        self.app.add_handler(add_trade_handler)
        self.app.add_handler(close_trade_handler)
        self.app.add_handler(CommandHandler("backtest", backtest_command))
        self.app.add_handler(CommandHandler("report", report_command))
        self.app.add_handler(CommandHandler("health", health_command))
        self.app.add_handler(CommandHandler("bandar", handle_bandar_command))
        self.app.add_handler(CommandHandler("bias", handle_bias_command))
        self.app.add_handler(CommandHandler("scores", handle_scores_command))

        # Register global error handler
        self.app.add_error_handler(_error_handler)
        logger.info("Bot handlers registered successfully.")

    def run(self):
        """Run the bot with startup grace period + PTB native Conflict handling.

        Strategy:
        1. Wait _STARTUP_GRACE s upfront — avoids Conflict on most deploys.
        2. If Conflict still occurs, the error handler sleeps _CONFLICT_WAIT s
           inside PTB's retry loop (no RuntimeError, no stop/shutdown calls).
        3. run_polling() is blocking and runs indefinitely until SIGTERM.
        """
        # ── Startup grace ───────────────────────────────────────────────────
        if _STARTUP_GRACE > 0:
            logger.info(
                f"⏳ Waiting {_STARTUP_GRACE}s startup grace before polling "
                "(lets old Railway container shut down)…"
            )
            time.sleep(_STARTUP_GRACE)

        logger.info("Starting Telegram bot (polling mode)…")
        try:
            self.app.run_polling(
                drop_pending_updates=True,
                allowed_updates=None,
                close_loop=False,
            )
            logger.info("Bot polling stopped gracefully.")
        except Exception as e:
            logger.critical(f"Bot crashed unexpectedly: {e}")
            sys.exit(1)

    def _rebuild_app(self):
        """Rebuild the Application instance to get fresh connections after Conflict."""
        from config.settings import settings
        self.app = (
            Application.builder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .request(HTTPXRequest(connection_pool_size=8, connect_timeout=30.0, read_timeout=30.0))
            .build()
        )
        self.app.bot_data["db"] = self.db
        self._setup_handlers()

