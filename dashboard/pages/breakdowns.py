import streamlit as st
from analytics.breakdown import analyze_by_strategy, analyze_by_sector
from dashboard.components.charts import plot_win_rate_bar

def render(trades: list):
    st.title("Breakdowns 🧩")
    
    if not trades:
        st.info("No trades available.")
        return
        
    # Strategy
    st.subheader("By Strategy")
    strat_df = analyze_by_strategy(trades)
    if not strat_df.empty:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.plotly_chart(plot_win_rate_bar(strat_df, "strategy", "Win Rate by Strategy"), use_container_width=True)
        with col2:
            st.dataframe(strat_df, use_container_width=True)
            
    # Sector (Need mapping, tricky without stock repo access or map embedded in trade)
    # Assuming standard mapping or skip for now if map not avail.
    # We can fetch map from DB if needed or just skip.
    st.subheader("By Sector")
    # Placeholder for sector mapping acquisition
    sector_map = {} # In real app, fetch from stock repo
    sector_df = analyze_by_sector(trades, sector_map)
    if not sector_df.empty:
        st.dataframe(sector_df, use_container_width=True)
