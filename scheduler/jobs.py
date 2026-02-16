"""Scheduler module for CakTykBot.

This module configures and runs the APScheduler for periodic data fetching
at 18:45 WIB daily as defined in the sprint plan and Phase 7 analysis.
"""

import time
from datetime import datetime

import pytz
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config.settings import settings
from data.pipeline import DataPipeline
from db.connection import MongoManager
from db.repositories.pipeline_repo import PipelineRepository
from db.repositories.price_repo import PriceRepository
from db.repositories.stock_repo import StockRepository
from db.repositories.trade_repo import TradeRepository
from analytics.monthly_report import generate_pdf_report
from config.settings import settings
import asyncio
from telegram import Bot


def run_pipeline_job():
    """Execution wrapper for the daily pipeline job."""
    logger.info("Scheduler: Triggering daily pipeline job")
    
    # Initialize components
    db = MongoManager().get_database()
    stock_repo = StockRepository(db)
    price_repo = PriceRepository(db)
    pipeline_repo = PipelineRepository(db)
    
    pipeline = DataPipeline(stock_repo, price_repo, pipeline_repo)
    
    try:
        report = pipeline.run()
        logger.success(
            f"Scheduler: Job completed. "
            f"Success: {report.success_count}, Failed: {report.fail_count}"
        )
    except Exception as e:
        logger.error(f"Scheduler: Job failed with unexpected error: {e}")


def run_monthly_report_job():
    """Generate and send monthly report PDF."""
    logger.info("Scheduler: Triggering monthly report job")
    
    # Calculate Last Month
    now = datetime.now()
    first = now.replace(day=1)
    last_month_date = first - pd.Timedelta(days=1) # Go back 1 day to prev month
    month = last_month_date.month
    year = last_month_date.year
    
    try:
        db = MongoManager().get_database()
        repo = TradeRepository(db)
        trades_objs = repo.get_all_closed_trades()
        trades = [t.model_dump() for t in trades_objs]
        
        pdf_path = generate_pdf_report(trades, month, year)
        
        if pdf_path:
            # Send to Telegram Admin
            # We need async loop here? Scheduler runs in thread.
            # python-telegram-bot is async.
            async def send_pdf():
                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                # Where to send? Need Chat ID. 
                # For Sprint 1/MVP, maybe hardcoded or get from DB config?
                # Usually user interacts first.
                # Assuming 'nesa' or config.ADMIN_CHAT_ID
                # Backlog: Store Chat ID. For now log it or try send if ID known.
                if settings.TELEGRAM_CHAT_ID:
                    await bot.send_document(
                        chat_id=settings.TELEGRAM_CHAT_ID,
                        document=open(pdf_path, 'rb'),
                        caption=f"📅 Automated Monthly Report: {month}/{year}"
                    )
            
            # Run async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_pdf())
            loop.close()
            
            logger.success(f"Monthly report sent for {month}/{year}")
            
    except Exception as e:
        logger.error(f"Monthly Report Job failed: {e}")


class SchedulerManager:
    """Manager for the APScheduler instance."""

    def __init__(self, timezone_str: str = "Asia/Jakarta"):
        self.tz = pytz.timezone(timezone_str)
        self.scheduler = BackgroundScheduler(timezone=self.tz)

    def start(self):
        """Configure and start the scheduler."""
        # Daily job at 18:45 WIB
        trigger = CronTrigger(
            hour=18,
            minute=45,
            timezone=self.tz
        )
        
        self.scheduler.add_job(
            run_pipeline_job,
            trigger=trigger,
            id="daily_ohlcv_pipeline",
            name="Daily OHLCV Data Fetching",
            replace_existing=True
        )

        # Monthly Job (1st day of month at 09:00)
        self.scheduler.add_job(
            run_monthly_report_job,
            trigger=CronTrigger(day=1, hour=9, timezone=self.tz),
            id="monthly_report_job",
            name="Monthly Report Generation",
            replace_existing=True
        )
        
        self.scheduler.start()
        
        # Log next run
        job = self.scheduler.get_job("daily_ohlcv_pipeline")
        if job:
            logger.info(f"Scheduler started. Next run at: {job.next_run_time}")
        else:
            logger.error("Failed to schedule job")

    def stop(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
