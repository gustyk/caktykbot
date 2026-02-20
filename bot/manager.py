"""Bot manager to handle lifecycle and wiring."""

import sys
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


async def _error_handler(update, context):
    """Global error handler for the bot.
    
    NOTE: Conflict errors are handled by the retry loop in BotManager.run(),
    NOT by exiting here. Exiting on Conflict causes Railway to immediately
    restart, which hits the same Conflict — creating an infinite restart loop.
    """
    err = context.error
    if isinstance(err, tg_error.Conflict):
        # Just log — the run() retry loop will handle waiting & retrying.
        logger.warning(
            "⚡ Conflict detected (another instance still active). "
            "Waiting for old container to shut down..."
        )
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
        
        On Railway, a new container starts before the old one is killed.
        This causes a transient Conflict error (~30-60s). We retry with
        a backoff instead of exiting, which would cause an infinite loop.
        """
        max_retries = 10
        retry_delay = 30  # seconds — Railway typically kills old container within 30s

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Starting Telegram bot (polling mode, attempt {attempt}/{max_retries})...")
                # run_polling is blocking. drop_pending_updates clears stale sessions.
                self.app.run_polling(
                    drop_pending_updates=True,
                    allowed_updates=None,
                )
                # If run_polling() returns normally (e.g. graceful shutdown), exit loop
                logger.info("Bot polling stopped gracefully.")
                break

            except tg_error.Conflict:
                if attempt >= max_retries:
                    logger.critical(
                        f"❌ Still in Conflict after {max_retries} attempts. "
                        "Another bot instance may be permanently running. Exiting."
                    )
                    sys.exit(1)

                logger.warning(
                    f"⚡ Conflict on attempt {attempt}/{max_retries}. "
                    f"Old container still active — waiting {retry_delay}s before retry..."
                )
                # Rebuild the Application so we get a fresh HTTP connection pool
                # (the old one may be in a broken state after Conflict)
                self._rebuild_app()
                time.sleep(retry_delay)

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

