import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from strategies.base import StrategySignal
from engine.signal_generator import SignalGenerator

@pytest.fixture
def mock_db():
    db = MagicMock()
    # Mock trades collection find
    cursor = AsyncMock()
    # Return 5 winning trades for "vcp" -> High Score
    trades = [
        {"strategy": "vcp", "pnl_rupiah": 1000, "exit_date": datetime.now(), "entry_date": datetime.now()} 
        for _ in range(5)
    ]
    cursor.to_list.return_value = trades
    db.trades.find.return_value = cursor
    
    # Mock CB
    db.circuit_breaker_events.find_one = AsyncMock(return_value=None)
    
    return db

@pytest.mark.asyncio
async def test_adaptive_score_boost(mock_db):
    # Mock repos
    mock_portfolio_repo = AsyncMock()
    mock_config = MagicMock()
    mock_config.user = "nesa"
    mock_portfolio_repo.get_config.return_value = mock_config
    
    mock_trade_repo = AsyncMock()
    mock_trade_repo.get_open_trades.return_value = []
    
    # Pass Repos
    gen = SignalGenerator(portfolio_repo=mock_portfolio_repo, trade_repo=mock_trade_repo, db=mock_db)
    
    # Create a VCP signal
    sig = StrategySignal(
        symbol="TEST.JK", verdict="BUY", entry_price=1000, sl_price=900,
        tp_price=1200, tp2_price=None, rr_ratio=2.0, score=70.0,
        strategy_name="vcp", reasoning="Test", detail={}
    )
    
    # Run Generate
    # We patch risk_validator because we didn't setup its dependencies perfectly
    with patch("caktykbot.risk.risk_validator.RiskValidator.validate", new_callable=AsyncMock) as mock_validate:
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.warnings = []
        mock_validate.return_value = mock_result
        
        final = await gen.generate("TEST.JK", [sig])
        
        # Check if score influenced
        # Base tech score for 70 + RR 2.0 etc ~ 50-60.
        # Adaptive Score for 5 wins 0 losses -> 100?
        # Composite = Base*0.7 + Adaptive*0.3
        
        assert "Adaptive Score" in final.reasoning
        # We expect a high score update
        assert final.tech_score > 0
        print(f"Final Score: {final.tech_score}")
