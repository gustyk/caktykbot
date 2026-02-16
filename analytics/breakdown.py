from typing import List, Dict, Any
import pandas as pd

def _calculate_metrics(group_df: pd.DataFrame) -> Dict[str, Any]:
    """Helper to calc metrics for a group of trades."""
    total_trades = len(group_df)
    if total_trades == 0:
        return {}
        
    wins = group_df[group_df["pnl_rupiah"] > 0]
    losses = group_df[group_df["pnl_rupiah"] <= 0]
    
    win_rate = (len(wins) / total_trades) * 100
    total_pnl = group_df["pnl_rupiah"].sum()
    avg_pnl = group_df["pnl_rupiah"].mean()
    
    gross_profit = wins["pnl_rupiah"].sum()
    gross_loss = abs(losses["pnl_rupiah"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    return {
        "trades": total_trades,
        "win_rate": round(win_rate, 1),
        "total_pnl": total_pnl,
        "avg_pnl": avg_pnl,
        "profit_factor": round(profit_factor, 2)
    }

def analyze_by_strategy(trades: List[Dict]) -> pd.DataFrame:
    """Breakdown by strategy name."""
    if not trades: return pd.DataFrame()
    df = pd.DataFrame(trades)
    
    results = []
    for strategy, group in df.groupby("strategy"):
        metrics = _calculate_metrics(group)
        metrics["strategy"] = strategy
        results.append(metrics)
        
    return pd.DataFrame(results).sort_values("total_pnl", ascending=False)

def analyze_by_sector(trades: List[Dict], sector_map: Dict[str, str]) -> pd.DataFrame:
    """
    Breakdown by sector.
    Requires sector_map dict {symbol: sector_name}.
    """
    if not trades: return pd.DataFrame()
    df = pd.DataFrame(trades)
    
    # Map sectors
    df["sector"] = df["symbol"].map(sector_map).fillna("Unknown")
    
    results = []
    for sector, group in df.groupby("sector"):
        metrics = _calculate_metrics(group)
        metrics["sector"] = sector
        results.append(metrics)
        
    return pd.DataFrame(results).sort_values("total_pnl", ascending=False)

def analyze_by_holding_period(trades: List[Dict]) -> pd.DataFrame:
    """Breakdown by holding period bins."""
    if not trades: return pd.DataFrame()
    df = pd.DataFrame(trades)
    
    # Ensure holding_days exists
    if "holding_days" not in df.columns:
        # fallback simple calculation if entry/exit dates exist
        pass 
        
    bins = [0, 7, 14, 30, 999]
    labels = ["1-7d", "8-14d", "15-30d", ">30d"]
    
    df["period_bin"] = pd.cut(df["holding_days"], bins=bins, labels=labels)
    
    results = []
    for bin_label, group in df.groupby("period_bin", observed=True):
        metrics = _calculate_metrics(group)
        metrics["period"] = bin_label
        results.append(metrics)
        
    return pd.DataFrame(results)
