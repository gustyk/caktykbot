import streamlit as st
from dashboard.components.metrics import metric_card
from dashboard.components.charts import plot_equity_curve
from analytics.equity_curve import calculate_equity_curve

def render(trades: list, initial_capital: float):
    st.title("Overview 📈")
    
    # Metrics Calculation
    total_pnl = sum(t.get("pnl_rupiah", 0) for t in trades)
    wins = [t for t in trades if t.get("pnl_rupiah", 0) > 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Total P&L", f"Rp {total_pnl:,.0f}")
    with col2:
        metric_card("Win Rate", f"{win_rate:.1f}%")
    with col3:
        metric_card("Trades", str(len(trades)))
    with col4:
        metric_card("Capital", f"Rp {initial_capital + total_pnl:,.0f}")
        
    # Equity Curve
    curve = calculate_equity_curve(trades, initial_capital)
    if curve:
        st.plotly_chart(plot_equity_curve(curve), use_container_width=True)
    else:
        st.info("No trades yet to show equity curve.")
