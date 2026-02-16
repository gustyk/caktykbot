from typing import List, Dict, Any
import pandas as pd
from .breakdown import _calculate_metrics

def analyze_emotions(trades: List[Dict]) -> pd.DataFrame:
    """
    Analyze performance by emotion tags.
    Returns: DataFrame with emotion, win_rate, avg_pnl.
    """
    if not trades: return pd.DataFrame()
    df = pd.DataFrame(trades)
    
    # Fill None tags
    df["emotion_tag"] = df["emotion_tag"].fillna("No Tag")
    
    results = []
    for emotion, group in df.groupby("emotion_tag"):
        metrics = _calculate_metrics(group)
        metrics["emotion"] = emotion
        results.append(metrics)
        
    return pd.DataFrame(results).sort_values("win_rate", ascending=False)
