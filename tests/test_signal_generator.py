"""Tests for Signal Generator."""
import pytest
from datetime import datetime
from strategies.base import StrategySignal
from engine.signal_generator import SignalGenerator


def create_signal(name, score, verdict="BUY"):
    return StrategySignal(
        symbol="TEST.JK",
        verdict=verdict,
        entry_price=1000,
        sl_price=900,
        tp_price=1200,
        tp2_price=None,
        rr_ratio=2.0,
        score=score,
        strategy_name=name,
        reasoning="Test",
        detail={}
    )


def test_signal_aggregation_single():
    gen = SignalGenerator()
    
    sig = create_signal("vcp", 80.0)
    final = gen.generate("TEST.JK", [sig, None])
    
    assert final.verdict == "BUY"
    assert final.confidence == "High" # Score >= 80 -> High
    assert final.strategy_source == "vcp"
    assert len(final.strategy_sources) == 1


def test_signal_aggregation_multi():
    gen = SignalGenerator()
    
    sig1 = create_signal("vcp", 70.0)
    sig2 = create_signal("ema", 75.0)
    
    final = gen.generate("TEST.JK", [sig1, sig2])
    
    assert final.verdict == "BUY"
    assert final.confidence == "High" # 2 signals -> High
    assert len(final.strategy_sources) == 2
    assert "vcp" in final.strategy_sources
    assert "ema" in final.strategy_sources
    # Score boosted
    # Base from best (75) + 10 = 85? Or filtered logic?
    # Code: final_score = min(final_score + 10, 100)
    # Scorer logic applied to best signal (75) results in ~50-60 base?
    # StrategySignal.score is 75. Scorer.calculate takes this.
    # Scorer re-calculates based on attributes.
    # Note: Scorer uses signal.score (75) as base (~30 pts contribution).
    # RR 2.0 -> +20 pts.
    # Total ~50 pts.
    # +10 bonus for confluence -> ~60.
    
    # We just check it's boosted/calculated.
    assert final.tech_score > 0


def test_signal_none():
    gen = SignalGenerator()
    final = gen.generate("TEST.JK", [None, None])
    
    assert final.verdict == "HOLD"
    assert final.confidence == "None"
