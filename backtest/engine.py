"""Backtesting Engine for CakTykBot."""
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Type, Optional

from db.schemas import Trade, BacktestRun, BacktestTrade
from db.repositories.price_repo import PriceRepository
from db.repositories.stock_repo import StockRepository
from db.repositories.backtest_repo import BacktestRepository
from strategies.base import BaseStrategy
from strategies.vcp import VCPStrategy
from strategies.ema_pullback import EMAPullbackStrategy
from strategies.bandarmologi import BandarmologiStrategy
from backtest.metrics import calculate_metrics

logger = logging.getLogger(__name__)

class BacktestEngine:
    """Event-driven backtesting engine."""
    
    STRATEGIES = {
        "vcp": VCPStrategy,
        "ema_pullback": EMAPullbackStrategy,
        "bandarmologi": BandarmologiStrategy
    }

    def __init__(self, db, strategy_name: str, start_date: datetime, end_date: datetime, 
                 initial_capital: float = 1_000_000_000, risk_per_trade: float = 0.01):
        self.db = db
        self.strategy_name = strategy_name.lower()
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.risk_per_trade = risk_per_trade
        
        self.price_repo = PriceRepository(db)
        self.stock_repo = StockRepository(db)
        self.backtest_repo = BacktestRepository(db)
        
        # Strategy Instance
        strategy_class = self.STRATEGIES.get(self.strategy_name)
        if not strategy_class:
             raise ValueError(f"Unknown strategy: {self.strategy_name}")
        self.strategy = strategy_class()
        
        # State
        self.capital = initial_capital
        self.positions: List[Dict] = [] # List of open trades
        self.closed_trades: List[Dict] = []
        self.price_cache = {} # symbol -> DataFrame

    def load_data(self):
        """Pre-load historical data for all active stocks."""
        logger.info("Loading historical data...")
        stocks = self.stock_repo.get_active_stocks()
        
        for stock in stocks:
            # Check if we have data in range
            prices = self.price_repo.get_historical_prices(stock.symbol, limit=2000, start_date=self.start_date - timedelta(days=365))
            if prices:
                df = pd.DataFrame([p.model_dump() for p in prices])
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
                df.set_index('date', inplace=True)
                self.price_cache[stock.symbol] = df
        
        logger.info(f"Loaded data for {len(self.price_cache)} stocks.")

    def run(self) -> str:
        """Execute the backtest."""
        start_time = datetime.now()
        self.load_data()
        
        current_date = self.start_date
        while current_date <= self.end_date:
            # Skip weekends logic if needed, but data check handles it
            self._process_day(current_date)
            current_date += timedelta(days=1)
            
        # Close all remaining positions at end date
        self._close_all_positions(self.end_date)
        
        # Calculate Metrics
        duration = (datetime.now() - start_time).total_seconds()
        metrics = calculate_metrics(self.closed_trades, self.initial_capital)
        
        # Save Results
        run = BacktestRun(
            strategy=self.strategy_name,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            risk_per_trade=self.risk_per_trade,
            total_trades=len(self.closed_trades),
            metrics=metrics,
            duration_seconds=duration
        )
        
        run_id = self.backtest_repo.create_run(run)
        
        # Save Trades
        db_trades = []
        for t in self.closed_trades:
            bt_trade = BacktestTrade(
                run_id=run_id,
                strategy=self.strategy_name,
                symbol=t['symbol'],
                entry_date=t['entry_date'],
                entry_price=t['entry_price'],
                exit_date=t['exit_date'],
                exit_price=t['exit_price'],
                qty=t['qty'],
                pnl_rupiah=t['pnl_rupiah'],
                pnl_percent=t['pnl_percent'],
                hold_days=t['hold_days'],
                exit_reason=t['exit_reason']
            )
            db_trades.append(bt_trade)
            
        self.backtest_repo.save_trades(db_trades)
        logger.info(f"Backtest completed. Run ID: {run_id}")
        return run_id

    def _process_day(self, date: datetime):
        """Simulate one trading day."""
        # 1. Manage Open Positions (Check SL/TP)
        # We iterate a copy to allow removal
        for trade in self.positions[:]:
            symbol = trade['symbol']
            df = self.price_cache.get(symbol)
            
            # If no data for this date, skip
            if df is None or date not in df.index:
                continue
                
            daily_data = df.loc[date]
            low = daily_data['low']
            high = daily_data['high']
            close = daily_data['close']
            
            # Check Exit Conditions
            exit_price = None
            exit_reason = None
            
            # SL Hit
            if low <= trade['sl_price']:
                exit_price = min(daily_data['open'], trade['sl_price']) # Gap down protection? Assumes Fill at worst/SL
                # Optimistic SL: trade['sl_price']. Pessimistic: low. Realistic: max(open, sl) if gap down
                exit_price = trade['sl_price'] if daily_data['open'] > trade['sl_price'] else daily_data['open']
                exit_reason = "SL"
                
            # TP Hit
            elif high >= trade['tp_price']:
                exit_price = trade['tp_price'] if daily_data['open'] < trade['tp_price'] else daily_data['open']
                exit_reason = "TP"
                
            # Time Exit (90 days)
            elif (date - trade['entry_date']).days > 90:
                exit_price = close
                exit_reason = "TIMEOUT"
            
            if exit_price:
                self._close_position(trade, exit_price, date, exit_reason)

        # 2. Look for New Signals
        self._scan_for_signals(date)

    def _scan_for_signals(self, date: datetime):
        """Run strategy analysis on candidate stocks."""
        # Only scan if we have capital
        # Simplified cash check (start with simplistic accumulation of PnL later)
        # For accurate portfolio simulation, we need to track available cash.
        # Let's deduct cost from capital on entry, add back on exit.
        
        for symbol, df in self.price_cache.items():
            if date not in df.index:
                continue
                
            # Slice data up to THIS date (inclusive)
            # Strategy needs historical context (e.g. 200 days)
            # data_slice = df.loc[:date] # This is slow if done repeatedly?
            # Optimization: pass index location
            
            idx_loc = df.index.get_loc(date)
            if idx_loc < 200: # Insufficient history
                continue
                
            # Optimize: Only pass last 250 rows to strategy
            start_loc = max(0, idx_loc - 250)
            data_slice = df.iloc[start_loc : idx_loc + 1]
            
            # Run Analyze
            # Note: Bandarmologi needs broker data, which we might not have in price_cache
            # For now, Bandarmologi might fail or return None if only price passed
            try:
                signal = self.strategy.analyze(data_slice)
            except Exception as e:
                # logger.error(f"Strategy error on {symbol} {date}: {e}")
                continue
                
            if signal and signal.verdict == "BUY":
                self._open_position(signal, date)

    def _open_position(self, signal, date):
        """Execute a BUY signal."""
        # Position Sizing
        risk_amount = self.capital * self.risk_per_trade
        risk_per_share = signal.entry_price - signal.sl_price
        
        if risk_per_share <= 0:
            return

        qty = int(risk_amount / risk_per_share)
        cost = qty * signal.entry_price
        
        # Check if enough cash (assuming 20% max allocation per stock for diversification)
        if cost > self.capital * 0.2: 
            qty = int((self.capital * 0.2) / signal.entry_price)
            cost = qty * signal.entry_price
            
        if cost > self.capital: # Check absolute cash
            qty = int(self.capital / signal.entry_price)
        
        if qty <= 0:
            return

        trade = {
            "symbol": signal.symbol,
            "entry_date": date,
            "entry_price": signal.entry_price,
            "sl_price": signal.sl_price,
            "tp_price": signal.tp_price,
            "qty": qty,
            "cost": cost
        }
        
        self.positions.append(trade)
        self.capital -= cost # Deduct cash

    def _close_position(self, trade, exit_price, date, reason):
        """Close a trade."""
        revenue = trade['qty'] * exit_price
        pnl_rupiah = revenue - trade['cost']
        pnl_percent = (pnl_rupiah / trade['cost']) * 100
        
        closed_trade = {
            **trade,
            "exit_date": date,
            "exit_price": exit_price,
            "pnl_rupiah": pnl_rupiah,
            "pnl_percent": pnl_percent,
            "hold_days": (date - trade['entry_date']).days,
            "exit_reason": reason
        }
        
        self.closed_trades.append(closed_trade)
        self.positions.remove(trade)
        self.capital += revenue # Add cash back

    def _close_all_positions(self, date):
        """Force close at end of backtest."""
        for trade in self.positions[:]:
            symbol = trade['symbol']
            df = self.price_cache.get(symbol)
            
            close_price = trade['entry_price'] # Fallback
            if df is not None and date in df.index:
                close_price = df.loc[date]['close']
            elif df is not None:
                # Use last available price
                close_price = df.iloc[-1]['close']
                
            self._close_position(trade, close_price, date, "END_OF_BACKTEST")
