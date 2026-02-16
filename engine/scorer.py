"""Technical scoring module."""
from typing import Any, Dict

from strategies.base import StrategySignal


class TechnicalScorer:
    """Calculates technical score (0-100) for trading signals."""

    @staticmethod
    def calculate(signal: StrategySignal) -> float:
        """
        Calculate score based on signal attributes.
        
        Scoring Weight Breakdown:
        - Trend & Pattern Quality (Base Score): 40 pts
        - Risk-Reward Ratio: 30 pts
        - Volume/Momentum Confirmation: 30 pts
        """
        score = 0.0
        
        # 1. Base Score from Strategy (Trend/Pattern)
        # Strategies typically return a base score (e.g., 75-85)
        # We normalize it to contribution of 40 pts
        base_score_norm = min(signal.score, 100) / 100 * 40
        score += base_score_norm
        
        # 2. Risk-Reward (Max 30 pts)
        # RR >= 1:3 -> 30 pts
        # RR >= 1:2 -> 20 pts
        # RR < 1:2 -> 0 pts
        rr = signal.rr_ratio
        if rr >= 3.0:
            score += 30
        elif rr >= 2.0:
            score += 20
        else:
            score += 0 # Should be filtered out by strategy, but just in case
            
        # 3. Specific Strategy Bonuses (Max 30 pts)
        detail = signal.detail
        
        if signal.strategy_name == "vcp_breakout":
            # Bonus for number of contractions
            contractions = detail.get("contraction_count", 0)
            if contractions >= 3:
                score += 30
            elif contractions == 2:
                score += 20
        
        elif signal.strategy_name == "ema_pullback":
            # Bonus for RS strength
            rs_diff = detail.get("rs_diff", 0)
            if rs_diff > 10:
                score += 30
            elif rs_diff > 5:
                score += 20
            elif rs_diff > 0:
                score += 10
                
        return min(round(score, 1), 100.0)
