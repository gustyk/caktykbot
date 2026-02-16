from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np

from strategies.base import BaseStrategy, StrategySignal

class BandarmologiStrategy(BaseStrategy):
    """
    Strategi Bandarmologi: Mendeteksi akumulasi bandar/asing dan breakout dari base.
    """

    def __init__(
        self,
        min_accum_days: int = 5,
        min_broker_value: float = 10_000_000,
        min_foreign_flow_days: int = 3,
        min_foreign_flow_total: float = 50_000_000,
        base_period: int = 10,
        max_atr_pct: float = 5.0
    ):
        self.min_accum_days = min_accum_days
        self.min_broker_value = min_broker_value
        self.min_foreign_flow_days = min_foreign_flow_days
        self.min_foreign_flow_total = min_foreign_flow_total
        self.base_period = base_period
        self.max_atr_pct = max_atr_pct

    def analyze(self, price_data: pd.DataFrame, **kwargs) -> Optional[StrategySignal]:
        """
        Analyze Bandarmologi signal.
        
        Args:
            price_data: OHLCV DataFrame
            kwargs: 
                broker_data: DataFrame with cols [date, broker_code, net_value]
                flow_data: DataFrame with cols [date, foreign_net]
                symbol: Ticker symbol
        """
        broker_data = kwargs.get("broker_data")
        flow_data = kwargs.get("flow_data")
        symbol = kwargs.get("symbol", "UNKNOWN")
        
        if price_data.empty:
            return None

        # 1. Base Formation (Price Action)
        base_info = self.detect_base_formation(price_data)
        if not base_info["is_base_forming"]:
             # If strictly looking for breakout from base
             # Check if we are checking for DISTRIBUTION (Exit) separately?
             # For now, focus on BUY signal.
             pass

        # 2. Broker Accumulation
        accum_info = {"is_accumulating": False, "days": 0, "top_brokers": []}
        if broker_data is not None and not broker_data.empty:
            accum_info = self.detect_accumulation(broker_data)
            
        # 3. Foreign Flow
        foreign_info = {"is_foreign_buying": False, "net_7d": 0.0}
        if flow_data is not None and not flow_data.empty:
            foreign_info = self.detect_foreign_flow(flow_data)

        # 4. Breakout Check / Signal Generation
        # Condition: Base Detected OR Accumulation Strong?
        # Standard: Accumulation + Breakout
        
        # If distribution detected -> SELL signal?
        dist_info = self.detect_distribution(price_data, broker_data, flow_data)
        if dist_info["is_distribution"]:
             current_price = price_data.iloc[-1]["close"]
             return StrategySignal(
                symbol=symbol,
                verdict="SELL",
                entry_price=current_price,
                sl_price=0, tp_price=0, tp2_price=0, rr_ratio=0,
                score=90,
                strategy_name="bandarmologi_distribution",
                reasoning="Distribution detected: High volume stagnation + Net Sell",
                detail=dist_info
             )

        # Buy Signal Logic
        # Requirements:
        # - Broker Accumulating OR Foreign Buying (at least one strong)
        # - Base formation recently or Breakout now
        
        # Check Breakout
        breakout = self.check_breakout(price_data, base_info, accum_info, foreign_info)
        
        if breakout["is_breakout"]:
            entry = breakout["entry_price"]
            sl = base_info.get("support", entry * 0.95)
            tp = entry + (entry - sl) * 2.0
            
            # Additional confidence score logic
            confidence_score = 60
            if accum_info["is_accumulating"]: confidence_score += 20
            if foreign_info["is_foreign_buying"]: confidence_score += 15
            if base_info["is_base_forming"]: confidence_score += 5 # strong base
            
            return StrategySignal(
                symbol=symbol,
                verdict="BUY",
                entry_price=entry,
                sl_price=sl,
                tp_price=tp,
                tp2_price=entry + (entry - sl) * 3.0,
                rr_ratio=2.0,
                score=min(confidence_score, 100),
                strategy_name="bandarmologi_breakout",
                reasoning=f"Breakout with {accum_info['days']}d accum & foreign net {foreign_info['net_7d']/1e6:.0f}M",
                detail={
                    "accumulation": accum_info,
                    "foreign": foreign_info,
                    "base": base_info
                }
            )
            
        return None

    def detect_accumulation(self, broker_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect consistency of top brokers buying.
        Input DF: date, broker_code, net_value
        """
        # Ensure sorted by date ascending for analysis
        df = broker_data.sort_values("date")
        
        # We need to pivot or group by date to see top brokers per day
        # Or if input is list of summary for one symbol
        
        # Logic: Look at last N days.
        # Identify top buyers in the period.
        last_date = df["date"].max()
        start_date = last_date - pd.Timedelta(days=self.min_accum_days + 5) # buffer
        recent_df = df[df["date"] >= start_date]
        
        # Aggregate net value per broker
        broker_totals = recent_df.groupby("broker_code")["net_value"].sum().sort_values(ascending=False)
        
        # Filter for positive buyers only for accumulation check
        top_buyers = broker_totals[broker_totals > 0].head(3)
        
        # Check if top buyers are consistent or meaningful
        is_accumulating = False
        accum_days = 0 
        
        if top_buyers.sum() > self.min_broker_value * self.min_accum_days:
            is_accumulating = True
            accum_days = self.min_accum_days # Placeholder

            
        return {
            "is_accumulating": is_accumulating,
            "days": accum_days,
            "top_brokers": top_buyers.index.tolist(),
            "top_buy_val": float(top_buyers.sum())
        }

    def detect_foreign_flow(self, flow_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect foreign net buy streak.
        Input DF: date, foreign_net
        """
        df = flow_data.sort_values("date")
        recent = df.tail(self.min_foreign_flow_days)
        
        net_total = recent["foreign_net"].sum()
        positive_days = (recent["foreign_net"] > 0).sum()
        
        is_buying = (positive_days >= self.min_foreign_flow_days - 1) and (net_total > self.min_foreign_flow_total)
        
        return {
            "is_foreign_buying": bool(is_buying),
            "net_7d": float(df.tail(7)["foreign_net"].sum()),
            "consecutive_days": int(positive_days)
        }

    def detect_base_formation(self, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect low volatility base (VCP-like or Box).
        """
        df = price_data.tail(self.base_period).copy()
        if len(df) < self.base_period:
             return {"is_base_forming": False, "support": 0, "resistance": 0}
             
        # Calculate ATR or Range
        # Exclude the current candle if we are detecting a base formed *before* today
        # But analyze is called with current data. 
        # Ideally base is formed over [T-10, T-1].
        
        # We'll use the whole period to check volatility, but resistance should be max of the period excluding extreme outliers?
        # Or better: detect_base_formation analyzes the window. 
        # check_breakout should handle the comparison.
        
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.abs(df["high"] - df["close"].shift(1))
        )
        avg_tr = df["tr"].mean()
        avg_close = df["close"].mean()
        atr_pct = (avg_tr / avg_close) * 100
        
        is_base = atr_pct < self.max_atr_pct
        
        return {
            "is_base_forming": bool(is_base),
            "support": float(df["low"].min()),
            "resistance": float(df["high"].max()),
            "atr_pct": float(atr_pct)
        }

    def check_breakout(self, price_data: pd.DataFrame, base: dict, accum: dict, foreign: dict) -> Dict[str, Any]:
        """
        Check if today's price breaks out of the base with validation.
        """
        if len(price_data) < 2:
            return {"is_breakout": False, "entry_price": 0.0}

        last_candle = price_data.iloc[-1]
        
        # Calculate resistance from PREVIOUS candles to avoid breakout candle determining resistance
        # Lookback period for resistance: base_period or 10 days
        lookback = max(self.base_period, 10)
        # Exclude current candle
        prev_data = price_data.iloc[-(lookback+1):-1] 
        
        resistance = prev_data["high"].max() if not prev_data.empty else last_candle["high"]
        
        is_breakout = (last_candle["close"] > resistance) and (last_candle["close"] > last_candle["open"])
        
        # Volume validation (1.5x avg)
        avg_vol = price_data["volume"].iloc[-20:-1].mean()
        vol_surge = last_candle["volume"] > (avg_vol * 1.5)
        
        # Must have accumulation or foreign flow support
        supported = accum["is_accumulating"] or foreign["is_foreign_buying"]
        
        valid_breakout = is_breakout and vol_surge and supported
        
        return {
            "is_breakout": bool(valid_breakout),
            "entry_price": float(last_candle["close"])
        }

    def detect_distribution(self, price_data: pd.DataFrame, broker_data: pd.DataFrame = None, flow_data: pd.DataFrame = None) -> Dict[str, Any]:
        """
        Detect distribution signal (Price stagnation/drop + Net Sell).
        """
        last_candle = price_data.iloc[-1]
        avg_vol = price_data["volume"].iloc[-20:-1].mean()
        
        # Volume spike but price red or doji (churning)
        churning = (last_candle["volume"] > 2 * avg_vol) and (
            (last_candle["close"] < last_candle["open"]) or 
            (abs(last_candle["close"] - last_candle["open"]) / last_candle["open"] < 0.005)
        )
        
        # Check broker selling if available
        is_broker_selling = False
        if broker_data is not None and not broker_data.empty:
             recent = broker_data[broker_data["date"] == broker_data["date"].max()]
             # Check if recent is empty (no data for max date)
             if not recent.empty:
                 net_sales = recent[recent["net_value"] < 0]["net_value"].sum()
                 is_broker_selling = net_sales < -1 * self.min_broker_value
             
        # Check foreign selling
        is_foreign_selling = False
        if flow_data is not None and not flow_data.empty:
            last_flow = flow_data.iloc[-1]
            is_foreign_selling = last_flow["foreign_net"] < -1 * self.min_foreign_flow_total

        is_distribution = churning and (is_broker_selling or is_foreign_selling)
        
        return {
            "is_distribution": bool(is_distribution),
            "churning": bool(churning)
        }
