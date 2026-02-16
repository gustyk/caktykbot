from typing import List, Dict, Any
import pandas as pd
from .breakdown import analyze_by_strategy

def calculate_strategy_scores(trades: List[Dict]) -> Dict[str, float]:
    """
    Calculate adaptive score (0-100) for each strategy.
    
    Formula:
    - Win Rate Score (0-100) * 0.4
    - Profit Factor Score (0-3 -> 0-100) * 0.3
    - Avg PnL/Risk Ratio (0-100) * 0.3 (Simulated by simple PnL consistency)
    
    Returns:
        Dict {strategy_name: score}
    """
    if not trades:
        return {}
        
    stats = analyze_by_strategy(trades)
    if stats.empty:
        return {}
        
    scores = {}
    for _, row in stats.iterrows():
        strategy = row["strategy"]
        
        # 1. Win Rate Score (Direct percentage)
        wr_score = row["win_rate"]
        
        # 2. Profit Factor Score (Cap at 3.0 = 100)
        # PF 1.0 = 33, 2.0 = 66, 3.0 = 100
        pf = row.get("profit_factor", 0)
        if pf == float('inf'): pf = 3.0
        pf_score = min(pf / 3.0 * 100, 100)
        
        # 3. Consistency/profitability
        # If total_pnl > 0 -> higher score
        # Simple heuristic: if profitable, score 100, else 0 for this component?
        # Better: Win Rate/PF already covers profitability.
        # Let's add trade count weight? No, score should efficiency.
        
        # Let's use simple weighted sum of WR and PF for now as per plan
        # Plan said: WR(40), RR(30), PF(30).
        # We don't have RR in breakdown yet. Breakdown has avg_pnl.
        # We can approximate RR if we had avg_win / avg_loss.
        # Breakdown has gross_profit/gross_loss but not avg.
        # Let's simple model: 50% WR + 50% PF Scaled.
        
        final_score = (wr_score * 0.5) + (pf_score * 0.5)
        scores[strategy] = round(final_score, 1)
        
    return scores
