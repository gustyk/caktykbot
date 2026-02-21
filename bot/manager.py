"""Bot manager to handle lifecycle and wiring."""

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


# ── Grace period before first poll attempt ────────────────────────────────────
# Railway needs ~15-30 s to kill the old container. We wait upfront so we
# (almost) never hit a Conflict at all. Configurable via env var for testing.
import os
_STARTUP_GRACE = int(os.environ.get("BOT_STARTUP_GRACE_SECONDS", "30"))


async def _error_handler(update, context):
    """Global error handler for the bot.

    On Conflict we stop the application so the run() loop can apply
    a backoff delay before the next attempt — without Railway triggering
    an infinite restart loop.
    """
    err = context.error
    if isinstance(err, tg_error.Conflict):
        logger.warning(
            "⚡ Conflict: another bot instance is still active. "
            "Stopping this attempt — will retry after backoff..."
        )
        # Gracefully stop polling so run() can sleep and retry.
        await context.application.stop()
        await context.application.shutdown()
    elif isinstance(err, tg_error.NetworkError):
        logger.warning(f"Network error (will retry): {err}")
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
        """Run the bot in polling mode with Conflict retry logic.

        Strategy:
        1. Wait _STARTUP_GRACE seconds before the first attempt — this alone
           prevents most Conflicts since Railway kills the old container in ~15s.
        2. If a Conflict does slip through, exponential-backoff retry.
        3. After max_retries, exit(1) so Railway can redeploy cleanly.
        """
        max_retries = 8
        base_delay  = 20   # seconds for first retry

        # ── Startup grace period ──────────────────────────────────────────────
        if _STARTUP_GRACE > 0:
            logger.info(
                f"⏳ Waiting {_STARTUP_GRACE}s startup grace period before polling "
                "(allows old Railway container to shut down)..."
            )
            time.sleep(_STARTUP_GRACE)

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Starting Telegram bot (polling mode, "
                    f"attempt {attempt}/{max_retries})..."
                )
                self.app.run_polling(
                    drop_pending_updates=True,
                    allowed_updates=None,
                    # Close gracefully on stop signal from error handler
                    close_loop=False,
                )
                # run_polling() returned normally → graceful shutdown
                logger.info("Bot polling stopped gracefully.")
                break

            except tg_error.Conflict:
                if attempt >= max_retries:
                    logger.critical(
                        f"❌ Still in Conflict after {max_retries} attempts. "
                        "Another bot instance may be permanently running. Exiting."
                    )
                    sys.exit(1)

                delay = base_delay * (2 ** (attempt - 1))  # 20, 40, 80 ...
                logger.warning(
                    f"⚡ Conflict on attempt {attempt}/{max_retries}. "
                    f"Old container still active — retrying in {delay}s..."
                )
                self._rebuild_app()
                time.sleep(delay)

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

