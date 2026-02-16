"""Signal generation engine."""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
import pandas as pd

from strategies.base import StrategySignal
from .scorer import TechnicalScorer

logger = logging.getLogger(__name__)


@dataclass
class FinalSignal:
    """Consolidated signal ready for persistence and alerting."""
    symbol: str
    date: datetime
    verdict: str  # "BUY" | "SELL" | "HOLD" | "WAIT" | "SUSPENDED"
    strategy_source: str # Primary strategy source
    strategy_sources: List[str] # All valid sources
    entry_price: float
    sl_price: float
    tp_price: float
    rr_ratio: float
    tech_score: float
    confidence: str # "High" | "Medium" | "Low"
    reasoning: str
    
    # Risk Info
    lot_size: Optional[int] = None
    exposure_pct: Optional[float] = None
    heat_before: Optional[float] = None
    heat_after: Optional[float] = None
    risk_warnings: List[str] = None
    risk_blocked: bool = False
    block_reason: Optional[str] = None


class SignalGenerator:
    """Aggregates signals from multiple strategies and applies risk validation."""

    def __init__(self, portfolio_repo=None, trade_repo=None, db=None):
        self.scorer = TechnicalScorer()
        self.portfolio_repo = portfolio_repo
        self.trade_repo = trade_repo
        self.db = db # Fallback if repos not passed
        
        from risk.risk_validator import RiskValidator
        self.risk_validator = RiskValidator()

    async def generate(
        self, 
        symbol: str, 
        strategy_signals: List[Optional[StrategySignal]],
        stock_returns: Optional[pd.Series] = None,
        ihsg_returns: Optional[pd.Series] = None
    ) -> FinalSignal:
        """
        Aggregate signals and run risk validation.
        """
        valid_signals = [s for s in strategy_signals if s is not None]
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Case 1: No valid signals -> HOLD
        if not valid_signals:
            return FinalSignal(
                symbol=symbol,
                date=now,
                verdict="HOLD",
                strategy_source="none",
                strategy_sources=[],
                entry_price=0.0,
                sl_price=0.0,
                tp_price=0.0,
                rr_ratio=0.0,
                tech_score=0.0,
                confidence="None",
                reasoning="No valid setup detected."
            )

        # Case 2: At least one valid signal
        best_signal = max(valid_signals, key=lambda s: s.score)
        final_score = self.scorer.calculate(best_signal)
        
        num_strategies = len(valid_signals)
        sources = [s.strategy_name for s in valid_signals]
        
        if num_strategies >= 2:
            confidence = "High"
            final_score = min(final_score + 10, 100)
            joined_reasoning = " + ".join([s.reasoning for s in valid_signals])
            reasoning = f"CONFLUENCE: {joined_reasoning}"
        else:
            if final_score >= 80:
                confidence = "High"
            elif final_score >= 60:
                confidence = "Medium"
            else:
                confidence = "Low"
            reasoning = best_signal.reasoning
            
        base_signal = FinalSignal(
            symbol=symbol,
            date=now,
            verdict="BUY",
            strategy_source=best_signal.strategy_name,
            strategy_sources=sources,
            entry_price=best_signal.entry_price,
            sl_price=best_signal.sl_price,
            tp_price=best_signal.tp_price,
            rr_ratio=best_signal.rr_ratio,
            tech_score=final_score,
            confidence=confidence,
            reasoning=reasoning
        )
            
        # ---------------------------------------------------------
        # RISK VALIDATION GATE (Sprint 4)
        # ---------------------------------------------------------
        if self.portfolio_repo and self.trade_repo:
            try:
                # 1. Fetch Config
                config = self.portfolio_repo.get_config()
                if not config:
                    logger.warning("Risk validation skipped: No portfolio config.")
                    return base_signal
                    
                # 2. Fetch Open Trades
                open_trades = []
                if hasattr(self.trade_repo, "get_open_trades"):
                    open_trades = self.trade_repo.get_open_trades(config.user)
                elif self.db:
                    cursor = self.db.trades.find({"status": "open", "user": config.user})
                    open_trades = list(cursor)
                
                # 3. Closed Trades (for Circuit Breaker)
                closed_trades = []
                if self.db:
                   cursor = self.db.trades.find({"status": "closed", "user": config.user})
                   closed_trades = list(cursor)
                   
                # 4. Fetch Active CB Event
                active_cb = None
                if self.db:
                    active_cb = self.db.circuit_breaker_events.find_one({"resolved": False})
                
                # ---------------------------------------------------------
                # ADAPTIVE SCORING (Sprint 5)
                # ---------------------------------------------------------
                # Calculate adaptive score for the chosen strategy
                adaptive_score = 50.0 # Default neutral
                if closed_trades:
                    from analytics.adaptive_scorer import calculate_strategy_scores
                    # Convert repo objects to dicts if needed, assuming simple list of dicts or objects
                    # If closed_trades are objects, need conversion.
                    # Assuming they are dicts from direct DB fetch above.
                    scores = calculate_strategy_scores(closed_trades)
                    adaptive_score = scores.get(base_signal.strategy_source, 50.0)
                
                # Update Signal fields
                # We reuse tech_score as the base technical score
                # We can calculate a composite final score
                # Final = Tech(70%) + Adaptive(30%)
                composite_score = (base_signal.tech_score * 0.7) + (adaptive_score * 0.3)
                
                # Store in base_signal (need to ensure FinalSignal has fields or put in metadata)
                # FinalSignal doesn't have adaptive fields in definition above.
                # We can repurpose tech_score or reasoning, or just trust the FinalSignal definition update.
                # Let's update FinalSignal definition first (in next tool call or same).
                # But here we are replacing the logic block only.
                # I will update FinalSignal dataclass in a separate edit or assume I can't change it here easily without replacing the whole file header.
                # I'll append the score info to reasoning for now if I don't update dataclass, 
                # OR I update dataclass too. The file content shows dataclass at top.
                
                # Score update
                base_signal.tech_score = round(composite_score, 1)
                base_signal.reasoning += f" [Adaptive Score: {adaptive_score}]"

                # 5. Run Validation
                risk_result = await self.risk_validator.validate(
                    signal={
                        "symbol": symbol,
                        "entry_price": best_signal.entry_price,
                        "sl_price": best_signal.sl_price
                    },
                    open_trades=open_trades,
                    portfolio_config=config,
                    stock_returns=stock_returns,
                    ihsg_returns=ihsg_returns,
                    active_cb_event=active_cb,
                    closed_trades=closed_trades,
                    db=self.db
                )
                
                # 6. Apply Result
                if not risk_result.passed:
                    base_signal.verdict = risk_result.verdict_override or "WAIT"
                    base_signal.risk_blocked = True
                    base_signal.block_reason = risk_result.block_reason
                    
                base_signal.lot_size = risk_result.lot_size
                base_signal.exposure_pct = risk_result.exposure_pct
                base_signal.heat_before = risk_result.heat_before
                base_signal.heat_after = risk_result.heat_after
                base_signal.risk_warnings = risk_result.warnings
                
            except Exception as e:
                logger.error(f"Risk validation failed for {symbol}: {e}")
                base_signal.risk_warnings = [f"Risk validation error: {str(e)}"]

        return base_signal
