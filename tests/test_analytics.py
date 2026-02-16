import pytest
import pandas as pd
from datetime import datetime
from analytics.equity_curve import calculate_equity_curve
from analytics.breakdown import analyze_by_strategy, analyze_by_sector
from analytics.psychology import analyze_emotions

@pytest.fixture
def sample_trades():
    return [
        {
            "exit_date": datetime(2024, 1, 1),
            "pnl_rupiah": 1000,
            "strategy": "VCP",
            "symbol": "BBCA",
            "holding_days": 10,
            "emotion_tag": "Disciplined"
        },
        {
            "exit_date": datetime(2024, 1, 2),
            "pnl_rupiah": -500,
            "strategy": "VCP",
            "symbol": "TLKM",
            "holding_days": 5,
            "emotion_tag": "Anxious"
        },
        {
            "exit_date": datetime(2024, 1, 3),
            "pnl_rupiah": 2000,
            "strategy": "EMA",
            "symbol": "ASII",
            "holding_days": 20,
            "emotion_tag": "Disciplined"
        }
    ]

class TestAnalytics:
    def test_calculate_equity_curve(self, sample_trades):
        initial_capital = 10000
        curve = calculate_equity_curve(sample_trades, initial_capital)
        
        assert len(curve) == 4 # Initial + 3 trades
        assert curve[0]["equity"] == 10000
        assert curve[-1]["equity"] == 12500 # 10000 + 1000 - 500 + 2000
        assert "drawdown_pct" in curve[1]

    def test_analyze_by_strategy(self, sample_trades):
        df = analyze_by_strategy(sample_trades)
        assert len(df) == 2 # VCP, EMA
        # Check VCP
        vcp = df[df["strategy"] == "VCP"].iloc[0]
        assert vcp["trades"] == 2
        assert vcp["total_pnl"] == 500

    def test_analyze_by_sector(self, sample_trades):
        sector_map = {"BBCA": "Finance", "TLKM": "Infra", "ASII": "Auto"}
        df = analyze_by_sector(sample_trades, sector_map)
        assert len(df) == 3
        
    def test_analyze_emotions(self, sample_trades):
        df = analyze_emotions(sample_trades)
        assert len(df) == 2 # Disciplined, Anxious
        
        disc = df[df["emotion"] == "Disciplined"].iloc[0]
        assert disc["trades"] == 2
        assert disc["win_rate"] == 100.0
