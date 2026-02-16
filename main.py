"""Main entry point for CakTykBot.

This module provides CLI commands to start the scheduler, run manual syncs,
and verify the application state as defined in Phase 7 implementation.
"""

import argparse
import sys
import time

from loguru import logger


def setup_repositories():
    """Initialize all repositories."""
    from db.connection import MongoManager
    from db.repositories.pipeline_repo import PipelineRepository
    from db.repositories.price_repo import PriceRepository
    from db.repositories.stock_repo import StockRepository
    from db.repositories.signal_repo import SignalRepository
    from db.repositories.portfolio_repo import PortfolioConfigRepository
    from db.repositories.trade_repo import TradeRepository
    
    try:
        db = MongoManager().get_database()
        return {
            "stock": StockRepository(db),
            "price": PriceRepository(db),
            "pipeline": PipelineRepository(db),
            "signal": SignalRepository(db),
            "portfolio": PortfolioConfigRepository(db),
            "trade": TradeRepository(db),
        }
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        sys.exit(1)


def run_sync():
    """Manually run the data pipeline once."""
    from data.pipeline import DataPipeline
    
    logger.info("Starting manual synchronization...")
    repos = setup_repositories()
    pipeline = DataPipeline(
        repos["stock"], 
        repos["price"], 
        repos["pipeline"], 
        signal_repo=repos["signal"],
        portfolio_repo=repos["portfolio"],
        trade_repo=repos["trade"]
    )
    
    try:
        report = pipeline.run()
        logger.success("Manual sync completed successfully")
        print("\n--- Pipeline Report ---")
        print(f"Date: {report.date}")
        print(f"Total: {report.total_stocks}")
        print(f"Success: {report.success_count}")
        print(f"Failed: {report.fail_count}")
        if report.errors:
            print("\nErrors:")
            for err in report.errors[:5]:
                print(f"- {err}")
    except Exception as e:
        logger.error(f"Manual sync failed: {e}")
        sys.exit(1)


def start_app():
    """Start the scheduler and Telegram bot."""
    from scheduler.jobs import SchedulerManager
    from bot.manager import BotManager
    from db.connection import MongoManager
    
    logger.info("Initializing CakTykBot Production Suite...")
    
    try:
        db = MongoManager().get_database()
        
        # 1. Start Scheduler (Background)
        scheduler_manager = SchedulerManager()
        scheduler_manager.start()
        
        # 2. Start Bot (Blocking polling)
        bot_manager = BotManager(db)
        bot_manager.run()
        
    except Exception as e:
        logger.critical(f"Application failed to start: {e}")
        sys.exit(1)


def start_bot():
    """Start only the Telegram bot."""
    from bot.manager import BotManager
    from db.connection import MongoManager
    
    logger.info("Starting Telegram Bot...")
    try:
        db = MongoManager().get_database()
        bot_manager = BotManager(db)
        bot_manager.run()
    except Exception as e:
        logger.critical(f"Bot failed to start: {e}")
        sys.exit(1)


def start_scheduler():
    """Start only the background scheduler."""
    from scheduler.jobs import SchedulerManager
    
    logger.info("Starting Background Scheduler...")
    try:
        scheduler_manager = SchedulerManager()
        scheduler_manager.start()
        # Keep alive since scheduler is background
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler_manager.stop()
    except Exception as e:
        logger.critical(f"Scheduler failed to start: {e}")
        sys.exit(1)


def run_backtest(strategy: str = "all"):
    """Run backtesting engine."""
    from backtest.engine import BacktestEngine
    from datetime import datetime
    
    # Defaults for CLI
    start_date = "2023-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"Starting backtest for {strategy}...")
    try:
        engine = BacktestEngine(strategy, start_date, end_date)
        result = engine.run()
        logger.success(f"Backtest completed: {result['total_trades']} trades")
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="CaktykBot Backend Orchestrator")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Orchestrator
    subparsers.add_parser("start", help="Start BOTH scheduler and bot (default)")
    
    # Components
    subparsers.add_parser("bot", help="Start ONLY the Telegram bot")
    subparsers.add_parser("scheduler", help="Start ONLY the background scheduler")

    # Tools
    subparsers.add_parser("sync", help="Run the data pipeline once now")
    subparsers.add_parser("check", help="Verify configuration and database connection")
    
    # Backtest
    bt_parser = subparsers.add_parser("backtest", help="Run backtesting engine")
    bt_parser.add_argument("--strategy", default="all", help="Strategy to test (vcp, ema_pullback, bandarmologi, all)")

    args = parser.parse_args()

    if args.command == "sync":
        run_sync()
    elif args.command == "start":
        start_app()
    elif args.command == "bot":
        start_bot()
    elif args.command == "scheduler":
        start_scheduler()
    elif args.command == "backtest":
        run_backtest(args.strategy)
    elif args.command == "check":
        setup_repositories()
        logger.success("Environment and Database connection verified")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
