"""Data processing pipeline for CakTykBot.

This module orchestrates the fetching of stock data, calculation of technical
indicators, and persistence to MongoDB using parallel execution and robust
error handling as defined in Phase 6 analysis.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from config.settings import settings
from data.fetcher import YFinanceFetcher
from db.repositories.pipeline_repo import PipelineRepository
from db.repositories.price_repo import PriceRepository
from db.repositories.stock_repo import StockRepository
from db.schemas import DailyPriceBase, PipelineRun, StockInDB
from logic.indicators import IndicatorEngine, validate_sufficient_data
from utils.exceptions import CakTykBotError, NetworkError
from db.repositories.signal_repo import SignalRepository
from db.repositories.portfolio_repo import PortfolioRepository
from db.repositories.trade_repo import TradeRepository
from strategies.vcp import VCPStrategy
from strategies.ema_pullback import EMAPullbackStrategy
from engine.signal_generator import SignalGenerator


class DataPipeline:
    """Orchestrator for the daily data fetching and processing pipeline."""

    def __init__(
        self,
        stock_repo: StockRepository,
        price_repo: PriceRepository,
        pipeline_repo: PipelineRepository,
        signal_repo: Optional[SignalRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        max_workers: int = 5,
    ) -> None:
        self.stock_repo = stock_repo
        self.price_repo = price_repo
        self.pipeline_repo = pipeline_repo
        self.signal_repo = signal_repo
        self.portfolio_repo = portfolio_repo
        self.trade_repo = trade_repo
        self.max_workers = max_workers
        self.fetcher = YFinanceFetcher(
            max_retries=settings.FETCH_RETRY_COUNT,
            retry_delay=settings.FETCH_RETRY_DELAY,
        )

    def process_stock(self, stock: StockInDB) -> Optional[int]:
        """Process a single stock: fetch -> indicators -> save.

        Args:
            stock: Stock document from DB

        Returns:
            Number of price records saved, or None if failed
        """
        symbol = stock.symbol
        try:
            # 1. Fetch history
            # We fetch 2y to ensure EMA200 (200 trading days) has enough buffer
            df = self.fetcher.fetch_history(symbol, period="2y")
            
            # 2. Validate data sufficiency
            validate_sufficient_data(df, required_days=200)

            # 3. Calculate indicators
            df_with_indicators = IndicatorEngine.calculate_all(df)

            # 4. Save to DB (bulk or individual per repository design)
            # We use bulk_upsert for performance (Epic 21)
            
            prices_to_save = []
            
            # Convert DF to list of DailyPriceBase for schema enforcement
            for date, row in df_with_indicators.iterrows():
                try:
                    price_data = DailyPriceBase(
                        symbol=symbol,
                        date=date.to_pydatetime(),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=int(row["Volume"]),
                        adjusted_close=float(row.get("Adj Close", row["Close"])),
                    )
                    
                    price_dict = price_data.model_dump()
                    price_dict.update({
                        "ema_8": float(row["ema_8"]) if pd.notna(row["ema_8"]) else None,
                        "ema_21": float(row["ema_21"]) if pd.notna(row["ema_21"]) else None,
                        "ema_50": float(row["ema_50"]) if pd.notna(row["ema_50"]) else None,
                        "ema_150": float(row["ema_150"]) if pd.notna(row["ema_150"]) else None,
                        "ema_200": float(row["ema_200"]) if pd.notna(row["ema_200"]) else None,
                        "atr_14": float(row["atr_14"]) if pd.notna(row["atr_14"]) else None,
                        "vol_ma_20": float(row["vol_ma_20"]) if pd.notna(row["vol_ma_20"]) else None,
                    })
                    
                    prices_to_save.append(price_dict)
                    
                except Exception as e:
                    logger.warning(f"Failed to process row for {symbol} on {date}: {e}")
                    continue

            if prices_to_save:
                return self.price_repo.bulk_upsert_prices(prices_to_save)
            return 0

        except CakTykBotError as e:
            logger.error(f"Logic failure for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected failure for {symbol}: {e}")
            raise

    def run(self) -> PipelineRun:
        """Execute the full pipeline for all active stocks.

        Returns:
            PipelineRun report
        """
        start_time = time.time()
        logger.info("Starting daily data pipeline")

        # 1. Get watchlist
        stocks = self.stock_repo.get_all_stocks(only_active=True)
        total_stocks = len(stocks)
        
        if total_stocks == 0:
            logger.warning("No active stocks in watchlist")
            return PipelineRun(
                date=datetime.now(timezone.utc),
                duration=0,
                total_stocks=0,
                success_count=0,
                fail_count=0,
                errors=["Empty watchlist"]
            )

        success_count = 0
        fail_count = 0
        errors: List[str] = []

        # 2. Parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_stock = {
                executor.submit(self.process_stock, stock): stock 
                for stock in stocks
            }
            
            for future in as_completed(future_to_stock):
                stock = future_to_stock[future]
                try:
                    saved_count = future.result()
                    if saved_count is not None and saved_count > 0:
                        success_count += 1
                        logger.success(f"Processed {stock.symbol}: {saved_count} records saved")
                    else:
                        fail_count += 1
                        errors.append(f"{stock.symbol}: No records saved")
                except Exception as e:
                    fail_count += 1
                    err_msg = f"{stock.symbol}: {type(e).__name__}: {str(e)}"
                    errors.append(err_msg)
                    logger.error(f"Pipeline failed for {stock.symbol}: {e}")

        duration = time.time() - start_time
        
        # 3. Phase 2: Analysis & Signal Generation
        if self.signal_repo:
             self.run_analysis(stocks)
        
        # 4. Record pipeline run
        run_report = PipelineRun(
            date=datetime.now(timezone.utc),
            duration=duration,
            total_stocks=total_stocks,
            success_count=success_count,
            fail_count=fail_count,
            errors=errors
        )
        
        self.pipeline_repo.record_run(run_report)
        
        logger.info(
            f"Pipeline completed in {duration:.2f}s. "
            f"Success: {success_count}, Failed: {fail_count}"
        )
        
        return run_report

    def run_analysis(self, stocks: List[StockInDB]) -> None:
        """Run analysis on updated data."""
        logger.info("Starting Phase 2: Analysis & Signal Generation")
        
        # Initialize engine and strategies
        vcp = VCPStrategy()
        ema = EMAPullbackStrategy()
        
        # Initialize SignalGenerator with repos for risk validation
        engine = SignalGenerator(
            portfolio_repo=self.portfolio_repo, 
            trade_repo=self.trade_repo,
            db=self.pipeline_repo.db # fallback
        )
        
        # Get IHSG data once for RS calc
        # For Sprint 2 we try to fetch ^JKSE if available, otherwise None
        ihsg_prices = self.price_repo.get_historical_prices("^JKSE", limit=250)
        ihsg_df = None
        if ihsg_prices:
             ihsg_df = pd.DataFrame([p.model_dump() for p in ihsg_prices]).sort_values("date").reset_index(drop=True)
             ihsg_df = ihsg_df.rename(columns={
                "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
             })
        
        analysis_count = 0
        
        for stock in stocks:
            try:
                # Get data
                prices = self.price_repo.get_historical_prices(stock.symbol, limit=250)
                if len(prices) < 200:
                    continue
                    
                df = pd.DataFrame([p.model_dump() for p in prices]).sort_values("date").reset_index(drop=True)
                
                # Standardize column names to TitleCase for strategies
                df = df.rename(columns={
                    "open": "Open", 
                    "high": "High", 
                    "low": "Low", 
                    "close": "Close", 
                    "volume": "Volume"
                })
                
                # Run Strategies
                vcp_sig = vcp.analyze(df, symbol=stock.symbol)
                ema_sig = ema.analyze(df, symbol=stock.symbol, ihsg_data=ihsg_df)
                
                # Generate Final Signal
                final_sig = engine.generate(stock.symbol, [vcp_sig, ema_sig])
                
                # Save
                if self.signal_repo:
                    self.signal_repo.upsert_signal(final_sig)
                analysis_count += 1
                
            except Exception as e:
                logger.error(f"Analysis failed for {stock.symbol}: {e}")
                
        logger.success(f"Analysis completed for {analysis_count} stocks")
