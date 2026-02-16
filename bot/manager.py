"""Bot manager to handle lifecycle and wiring."""

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
        logger.info("Bot handlers registered successfully.")

    def run(self):
        """Run the bot in polling mode (Sprint 1 default)."""
        logger.info("Starting Telegram bot (polling mode)...")
        # In a real production environment, we might use webhooks on Railway,
        # but for Sprint 1 polling is the chosen implementation.
        self.app.run_polling(drop_pending_updates=True)
