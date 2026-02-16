import pytest
import pandas as pd
from datetime import datetime
from analytics.adaptive_scorer import calculate_strategy_scores
from analytics.bias_detector import detect_biases
from analytics.monthly_report import generate_monthly_report

@pytest.fixture
def scoring_trades():
    trades = [
        { # Win VCP
            "exit_date": datetime(2024, 1, 1),
            "entry_date": datetime(2023, 12, 25), # 7 days hold
            "pnl_rupiah": 1000,
            "strategy": "VCP",
            "symbol": "BBCA"
        },
        { # Loss VCP
            "exit_date": datetime(2024, 1, 10),
            "entry_date": datetime(2023, 12, 10), # 31 days hold (Loss Aversion candidate > 2x win)
            "pnl_rupiah": -500,
            "strategy": "VCP",
            "symbol": "TLKM"
        }
    ]
    # Add dummy trades to reach count > 5
    for i in range(4):
        trades.append({
            "exit_date": datetime(2024, 1, 12 + i),
            "entry_date": datetime(2024, 1, 10 + i),
            "pnl_rupiah": 100,
            "strategy": "VCP",
            "symbol": "DUMMY"
        })
    return trades

def test_calculate_strategy_scores(scoring_trades):
    scores = calculate_strategy_scores(scoring_trades)
    
    # Updated Data (includes 4 dummy wins):
    # Total 6 trades. Wins 5. Loss 1. WR 83.3%.
    # GP 1400. GL 500. PF 2.8.
    # Score: WR(83.3)*0.5 + PF(2.8/3.0*100 = 93.3)*0.5 = 41.65 + 46.65 = 88.3
    
    assert "VCP" in scores
    msg = f"Score {scores['VCP']} expected around 88.3"
    assert 85 < scores["VCP"] < 92, msg

def test_detect_biases(scoring_trades):
    # Win hold: 7 days. Loss hold: 31 days.
    # 31 > 2 * 7 (14). Also 31 > 5.
    # Should detect Loss Aversion.
    
    # Need to ensure holding_days logic in detect_biases works or pre-calculate
    # My implementation calculates it if entry/exit dates exist.
    
    biases = detect_biases(scoring_trades)
    assert any("Loss Aversion" in b for b in biases)

def test_generate_monthly_report(scoring_trades):
    report = generate_monthly_report(scoring_trades, 1, 2024)
    assert "# Monthly Trading Report: 1/2024" in report
    assert "## Performance Summary" in report
    assert "## Behavioral Analysis" in report
    assert "Loss Aversion" in report # Should be detected and reported
