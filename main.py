"""Main entry point for CakTykBot.

This module provides CLI commands to start the scheduler, run manual syncs,
and verify the application state as defined in Phase 7 implementation.
"""

import argparse
import sys
import time
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import json

from loguru import logger

# ── Early env diagnostic (runs before any import that triggers settings) ──────
_REQUIRED_VARS = ["MONGO_URI", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
_present = [v for v in _REQUIRED_VARS if os.environ.get(v)]
_missing = [v for v in _REQUIRED_VARS if not os.environ.get(v)]
print(f"[ENV CHECK] Present: {_present}", flush=True)
if _missing:
    print(f"[ENV CHECK] ⚠️  MISSING vars: {_missing}", flush=True)
else:
    print("[ENV CHECK] ✅ All required env vars found.", flush=True)
# ─────────────────────────────────────────────────────────────────────────────


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks."""
    def do_GET(self):
        # Always flush logs on request for debugging
        sys.stdout.flush()
        sys.stderr.flush()
        
        if self.path == '/':
            # Minimalist check for platform readiness
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"CakTykBot is active")
            return

        if self.path == '/health':
            from monitoring.health_check import check_all
            try:
                results = check_all()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(results).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress noise in logs
        return


def start_health_server():
    """Start the health check server in a background thread."""
    port = int(os.environ.get("PORT", 8080))
    # Use ThreadingHTTPServer to handle concurrent health check probes
    server = ThreadingHTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Health check server listening on port {port}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def setup_repositories():
    """Initialize all repositories."""
    from db.connection import MongoManager
    from db.repositories.pipeline_repo import PipelineRepository
    from db.repositories.price_repo import PriceRepository
    from db.repositories.stock_repo import StockRepository
    from db.repositories.signal_repo import SignalRepository
    from db.repositories.portfolio_repo import PortfolioRepository
    from db.repositories.trade_repo import TradeRepository
    
    try:
        db = MongoManager().get_database()
        return {
            "stock": StockRepository(db),
            "price": PriceRepository(db),
            "pipeline": PipelineRepository(db),
            "signal": SignalRepository(db),
            "portfolio": PortfolioRepository(db),
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


def run_dashboard():
    """Start the Streamlit dashboard."""
    import subprocess
    import os
    
    logger.info("Starting Streamlit Dashboard...")
    # Streamlit natively handles health checks at /
        
    # Run streamlit as a subprocess
    port = os.environ.get("PORT", "8501")
    cmd = [
        "streamlit", "run", "dashboard/app.py",
        "--server.port", port,
        "--server.address", "0.0.0.0"
    ]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        logger.error(f"Dashboard failed: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    print("="*40)
    print("CAKTYKBOT STARTING...")
    print(f"Time: {time.ctime()}")
    print(f"CWD: {os.getcwd()}")
    print("="*40)
    sys.stdout.flush()

    parser = argparse.ArgumentParser(description="CaktykBot Backend Orchestrator")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Orchestrator
    subparsers.add_parser("start", help="Start BOTH scheduler and bot (default)")
    
    # Components
    subparsers.add_parser("bot", help="Start ONLY the Telegram bot")
    subparsers.add_parser("scheduler", help="Start ONLY the background scheduler")
    subparsers.add_parser("dashboard", help="Start the Streamlit dashboard")

    # Tools
    subparsers.add_parser("sync", help="Run the data pipeline once now")
    subparsers.add_parser("check", help="Verify configuration and database connection")
    
    # Backtest
    bt_parser = subparsers.add_parser("backtest", help="Run backtesting engine")
    bt_parser.add_argument("--strategy", default="all", help="Strategy to test (vcp, ema_pullback, bandarmologi, all)")

    args = parser.parse_args()

    # Start health server early for cloud platforms, EXCEPT for dashboard
    # which manages its own HTTP port and health check mechanism.
    if args.command in ["start", "bot", "scheduler"] and "PORT" in os.environ:
        try:
            start_health_server()
        except Exception as e:
            print(f"CRITICAL: Failed to start health server: {e}", file=sys.stderr)

    if args.command == "sync":
        run_sync()
    elif args.command == "start":
        start_app()
    elif args.command == "bot":
        start_bot()
    elif args.command == "scheduler":
        start_scheduler()
    elif args.command == "dashboard":
        run_dashboard()
    elif args.command == "backtest":
        run_backtest(args.strategy)
    elif args.command == "check":
        setup_repositories()
        logger.success("Environment and Database connection verified")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
