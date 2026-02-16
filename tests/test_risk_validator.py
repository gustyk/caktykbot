"""Tests for Risk Validator (Integration of Rules)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from risk.risk_validator import RiskValidator
from db.schemas import PortfolioConfig

class TestRiskValidator:
    
    @pytest.mark.asyncio
    async def test_validate_all_pass(self):
        # Setup
        # Mock dependencies using patches to avoid complex db mocking deep in imports
        # But we refactored to inject db, so we can mock db calls.
        
        # However, check_sector_limit and get_sector_info are called interactively.
        # Better to mock the functions in risk_validator.py imports?
        
        validator = RiskValidator()
        
        config = PortfolioConfig(
            user="123",
            total_capital=100_000_000,
            risk_per_trade=0.01,
            max_heat=0.08,
            max_stocks_per_sector=2,
            max_exposure_pct=0.25
        )
        
        signal = {
            "symbol": "BBCA.JK",
            "entry_price": 5000,
            "sl_price": 4800
        }
        
        # Mock sector info and check
        # We can either mock the DB response OR patch the imported functions.
        # Patching is easier for specific return values.
        
        with patch("caktykbot.risk.risk_validator.get_sector_info", new_callable=AsyncMock) as mock_info, \
             patch("caktykbot.risk.risk_validator.check_sector_limit", new_callable=AsyncMock) as mock_limit, \
             patch("caktykbot.risk.risk_validator.calculate_portfolio_heat") as mock_heat, \
             patch("caktykbot.risk.risk_validator.project_heat_with_new_trade") as mock_proj_heat:
            
            mock_info.return_value = ("Banking", "large")
            mock_limit.return_value = {"allowed": True, "message": ""}
            
            mock_heat.return_value = {
                "current_heat": 0.02,
                "status": "safe",
                "cash_reserve_pct": 0.8,
                "cash_reserve_ok": True,
                "available_heat": 0.06
            }
            
            mock_proj_heat.return_value = {
                "projected_heat": 0.03,
                "would_exceed": False
            }
            
            result = await validator.validate(signal, [], config)
            
            assert result.passed
            assert result.lot_size is not None
            assert result.exposure_pct is not None
            assert not result.warnings

    @pytest.mark.asyncio
    async def test_validate_heat_limit_block(self):
        validator = RiskValidator()
        config = PortfolioConfig(user="1", total_capital=1000, risk_per_trade=0.01)
        
        with patch("caktykbot.risk.risk_validator.calculate_portfolio_heat") as mock_heat:
             mock_heat.return_value = {
                "current_heat": 0.08,
                "status": "limit", # Limit reached
                "cash_reserve_pct": 0.5,
                "cash_reserve_ok": True
             }
             
             result = await validator.validate({"symbol": "A", "entry_price": 100, "sl_price": 90}, [], config)
             
             assert not result.passed
             assert result.verdict_override == "WAIT"
             assert "Heat Limit" in result.block_reason

    @pytest.mark.asyncio
    async def test_validate_circuit_breaker_block(self):
        validator = RiskValidator()
        config = PortfolioConfig(user="1", total_capital=1000, risk_per_trade=0.01)
        
        # Must include suspended_until in future
        from datetime import datetime, timedelta, timezone
        active_cb = {
            "trigger_type": "DRAWDOWN", 
            "suspended_until": datetime.now(timezone.utc) + timedelta(days=1),
            "message": "Suspended via Test"
        }
        
        result = await validator.validate(
            {"symbol": "A", "entry_price": 100, "sl_price": 90}, 
            [], config, 
            active_cb_event=active_cb
        )
        
        assert not result.passed
        assert result.verdict_override == "SUSPENDED"

    @pytest.mark.asyncio
    async def test_validate_correlation_warning(self):
        validator = RiskValidator()
        # Use realistic capital to allow lot sizing (1 lot = 100 shares)
        # Capital 100M. Risk 2% (2M).
        config = PortfolioConfig(user="1", total_capital=100_000_000, risk_per_trade=0.02)
        
        # Patching needs to remain
        with patch("caktykbot.risk.risk_validator.get_sector_info", AsyncMock(return_value=("Basic", "large"))), \
             patch("caktykbot.risk.risk_validator.check_sector_limit", AsyncMock(return_value={"allowed": True})), \
             patch("caktykbot.risk.risk_validator.calculate_portfolio_heat", return_value={"status": "safe", "current_heat": 0, "cash_reserve_ok": True}), \
            patch("caktykbot.risk.risk_validator.project_heat_with_new_trade", return_value={"would_exceed": False, "projected_heat": 0}), \
            patch("caktykbot.risk.risk_validator.calculate_correlation", return_value=0.9): # High correlation
    
            # Entry 1000, SL 900 (10% distance).
            # Risk Amount 2M.
            # Shares = 2M / (1000-900) = 2M / 100 = 20,000 shares = 200 lots.
            # Exposure = 20,000 * 1000 = 20,000,000 (20M).
            # Exposure % = 20M / 100M = 20%.
            # Reduced limit for correlation (0.9 > 0.7) -> 0.25 * 0.5 = 12.5%.
            # 20% > 12.5% -> Warning.
            
            result = await validator.validate(
                {"symbol": "BBRI.JK", "entry_price": 1000, "sl_price": 900},
                [], config,
                stock_returns=[1,2], ihsg_returns=[1,2] # Dummy
            )
    
            assert result.passed
            # Debugging hint: if this fails, check result.warnings
            assert any("High Correlation" in w for w in result.warnings), f"Warnings: {result.warnings} Exposure: {result.exposure_pct}"
