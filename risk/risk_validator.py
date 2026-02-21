"""Risk Validator Orchestrator (FR-06)."""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd

from loguru import logger

from db.schemas import PortfolioConfig, SignalInDB
from risk.constants import (
    MAX_RISK_PER_TRADE,
    DEFAULT_RISK_PER_TRADE,
)
from risk.circuit_breaker import CircuitBreaker
from risk.heat_monitor import calculate_portfolio_heat, project_heat_with_new_trade
from risk.position_sizer import calculate_position_size
from risk.sector_mapper import check_sector_limit, get_sector_info
from risk.correlation import calculate_correlation, should_reduce_size_by_correlation


@dataclass
class RiskValidationResult:
    passed: bool
    verdict_override: Optional[str] = None   # "WAIT" | "SUSPENDED" | None
    lot_size: Optional[int] = None
    exposure_pct: Optional[float] = None
    heat_before: float = 0.0
    heat_after: float = 0.0
    warnings: List[str] = field(default_factory=list)
    block_reason: Optional[str] = None


class RiskValidator:
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        
    def validate(
        self,
        signal: Dict[str, Any],
        open_trades: List[Dict],
        portfolio_config: PortfolioConfig,
        stock_returns: Optional[pd.Series] = None,
        ihsg_returns: Optional[pd.Series] = None,
        active_cb_event: Optional[Dict] = None,
        closed_trades: Optional[List[Dict]] = None,
        db=None
    ) -> RiskValidationResult:
        """
        Run ALL risk management rules sequentially.
        
        Args:
            signal: The trading signal (dict)
            open_trades: List of currently open trades
            portfolio_config: Portfolio configuration settings
            stock_returns: Historical returns for the signal's symbol
            ihsg_returns: Historical returns for IHSG
            active_cb_event: Currently active circuit breaker event (if any)
            closed_trades: List of closed trades (for CB check)
            db: Optional database instance for sector checks
            
        Returns:
            RiskValidationResult object
        """
        symbol = signal["symbol"]
        entry = signal["entry_price"]
        sl = signal["sl_price"]
        capital = portfolio_config.total_capital
        
        warnings = []
        
        # 1. Circuit Breaker Check (RR-010)
        # If no explicit closed_trades passed, we might skip or warn. 
        # Ideally caller handles fetching.
        cb_status = self.circuit_breaker.check(
            closed_trades or [], 
            capital, 
            active_suspension=active_cb_event
        )
        
        current_risk_per_trade = portfolio_config.risk_per_trade
        
        if cb_status["is_active"]:
            # If suspended, hard block
            if cb_status.get("trigger_type"):
                 # It's an active suspension
                 return RiskValidationResult(
                     passed=False,
                     verdict_override="SUSPENDED",
                     block_reason=cb_status["message"],
                     warnings=[cb_status["message"]]
                 )
            
            # If validated (e.g. risk reduced), override risk
            if cb_status.get("risk_override"):
                current_risk_per_trade = cb_status["risk_override"]
                warnings.append(f"Risk reduced to {current_risk_per_trade:.2%} due to recent drawdown/losses.")
        
        # 2. Portfolio Heat Check (RR-001)
        heat_status = calculate_portfolio_heat(
            open_trades, 
            capital, 
            max_heat_limit=portfolio_config.max_heat
        )
        heat_before = heat_status["current_heat"]
        
        if heat_status["status"] == "limit":
             return RiskValidationResult(
                 passed=False,
                 verdict_override="WAIT",
                 block_reason=f"Portfolio Heat Limit ({heat_before:.1%}) reached. Close positions first.",
                 heat_before=heat_before
             )
        elif heat_status["status"] == "warning":
            warnings.append(f"Portfolio Heat {heat_before:.1%} is high (Limit {portfolio_config.max_heat:.1%})")
            
        # 3. Cash Reserve Check (RR-006)
        if not heat_status["cash_reserve_ok"]:
             warnings.append(f"Cash Reserve {heat_status['cash_reserve_pct']:.1%} below target {portfolio_config.cash_reserve_target:.1%}")
             
        # 4. Sector Diversification (RR-005)
        # We need sector info for the symbol
        sector, market_cap = get_sector_info(symbol, db=db)
        sector_check = check_sector_limit(
            symbol, 
            sector, 
            open_trades,
            db=db
        )
        
        if not sector_check["allowed"]:
            return RiskValidationResult(
                passed=False,
                verdict_override="WAIT",
                block_reason=sector_check["message"],
                heat_before=heat_before
            )
            
        # 5. Position Sizing (RR-003)
        # Calculate size based on (possibly reduced) risk
        is_small_cap = market_cap == "small" or market_cap == "mid" # Treat mid as small? Plan said: "small-cap detected... max exposure 15%"
        # Plan criteria: "market cap proxy < Rp 5T" -> small. 
        # Our seed data has "large", "mid", "small". 
        # Let's treat "small" as small-cap. Mid might be safe?
        # Let's align with config: default max_small_cap_exposure usually applies to small caps.
        # If we want to be conservative, maybe treat MID as small?
        # Let's stick to 'small' for now.
        
        sizing = calculate_position_size(
            capital=capital,
            risk_pct=current_risk_per_trade,
            entry_price=entry,
            sl_price=sl,
            is_small_cap=(market_cap == "small")
        )
        
        if "error" in sizing:
             return RiskValidationResult(
                 passed=False,
                 verdict_override="WAIT",
                 block_reason=f"Sizing Error: {sizing['error']}",
                 heat_before=heat_before
             )
             
        # Collect sizing warnings (SL too wide, etc)
        warnings.extend(sizing.get("warnings", []))
        
        # 6. Correlation Filter (RR-007)
        exposure_pct = sizing["exposure_pct"]
        lot_size = sizing["lots"]
        shares = sizing["shares"]
        
        if stock_returns is not None and ihsg_returns is not None:
            corr = calculate_correlation(stock_returns, ihsg_returns)
            if should_reduce_size_by_correlation(corr):
                # Reduce max exposure by 50%
                # Wait, sizing function already checks max exposure. 
                # But here we dynamically reduce the LIMIT.
                # Or just reduce the resulting size?
                # "max exposure dikurangi 50% (dari 25% max -> 12.5% max)"
                # So we should re-run sizing with lower max exposure limit?
                # Or just cut shares by half?
                # "reduce position size 50%" vs "max exposure dikurangi 50%"
                # Plan says: "max exposure reduced to 12.5%".
                # If current size uses 5% exposure, it's fine.
                # If current size uses 20% exposure, it needs to be cut.
                
                # Let's re-calculate if needed, or simplistically cut size.
                # To be precise, we should pass a lower max_limit to calculate_position_size,
                # but that function takes explicit is_small_cap flag for limits.
                # Let's handle it manually here.
                
                reduced_limit = portfolio_config.max_exposure_pct * 0.5
                if exposure_pct > reduced_limit:
                     warnings.append(f"High Correlation ({corr:.2f}). Max exposure reduced to {reduced_limit:.1%}.")
                     
                     # Recalculate caps
                     max_allowed_rupiah = capital * reduced_limit
                     max_allowed_shares = int(max_allowed_rupiah / entry)
                     shares = (max_allowed_shares // 100) * 100
                     lot_size = shares // 100
                     
                     exposure_rupiah = shares * entry
                     exposure_pct = exposure_rupiah / capital
        
        # 7. Final Exposure Check (RR-004)
        # Already done in sizing, but we might have modified shares.
        # Just double check? No need if logic is sound.
        
        # 8. Projected Heat Check (RR-002)
        # Calculate new risk with final size
        # Risk amount = shares * (entry - sl) ?
        # Or risk amount = capital * risk_pct?
        # If we capped size due to exposure, risk amount is LOWER than target.
        # We should recalculate actual risk taken.
        
        actual_risk_rupiah = shares * (entry - sl)
        actual_risk_pct = actual_risk_rupiah / capital
        
        heat_proj = project_heat_with_new_trade(
            heat_before,
            actual_risk_pct,
            max_heat_limit=portfolio_config.max_heat
        )
        
        if heat_proj["would_exceed"]:
             return RiskValidationResult(
                 passed=False,
                 verdict_override="WAIT",
                 block_reason=f"Heat Limit Reached ({heat_proj['projected_heat']:.1%}).",
                 heat_before=heat_before,
                 heat_after=heat_proj["projected_heat"]
             )
             
        if "message" in heat_proj and heat_proj["message"]:
             # Verify this logic, seems redundant if we block on exceed
             # But maybe warning?
             pass 
             
        # All Checks Passed
        return RiskValidationResult(
            passed=True,
            lot_size=lot_size,
            exposure_pct=exposure_pct,
            heat_before=heat_before,
            heat_after=heat_proj["projected_heat"],
            warnings=warnings
        )
