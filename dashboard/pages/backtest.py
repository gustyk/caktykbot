import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from db.repositories.backtest_repo import BacktestRepository
from db.connection import get_database

def render(db=None):
    st.title("Backtest Results 🧪")
    
    if db is None:
        db = get_database()
        
    repo = BacktestRepository(db)
    
    # 1. List Runs
    runs = repo.get_all_runs()
    
    if not runs:
        st.info("No backtest runs found. Trigger one via Telegram: `/backtest vcp`")
        return
        
    # Sidebar Selection
    run_options = {f"{r.strategy.upper()} ({r.created_at.strftime('%Y-%m-%d %H:%M')})": r.id for r in runs}
    selected_label = st.selectbox("Select Backtest Run:", list(run_options.keys()))
    run_id = run_options[selected_label]
    
    selected_run = next((r for r in runs if r.id == run_id), None)
    
    if not selected_run:
        st.error("Selected run not found.")
        return
        
    # 2. Metrics Display
    metrics = selected_run.metrics
    st.markdown(f"### Strategy: {selected_run.strategy.upper()}")
    st.caption(f"Period: {selected_run.start_date.date()} to {selected_run.end_date.date()} | Duration: {selected_run.duration_seconds:.1f}s")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Return", f"{metrics.get('total_return', 0)}%", delta_color="normal")
    col2.metric("Win Rate", f"{metrics.get('win_rate', 0)}%")
    col3.metric("Profit Factor", f"{metrics.get('profit_factor', 0)}")
    col4.metric("Trades", f"{metrics.get('total_trades', 0)}")
    
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0)}%", delta_color="inverse")
    col6.metric("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0)}")
    col7.metric("Avg Profit", f"{metrics.get('avg_profit', 0)}%")
    col8.metric("Avg Loss", f"{metrics.get('avg_loss', 0)}%")

    # 3. Equity Curve
    # We need trades to plot equity curve.
    trades = repo.get_trades_by_run(run_id)
    if trades:
        trade_dicts = [t.model_dump() for t in trades]
        df = pd.DataFrame(trade_dicts)
        
        # Sort by exit date
        df['exit_date'] = pd.to_datetime(df['exit_date'])
        df = df.sort_values('exit_date')
        
        # Cumulative PnL
        df['cumulative_pnl'] = df['pnl_rupiah'].cumsum()
        df['equity'] = selected_run.initial_capital + df['cumulative_pnl']
        
        # Plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['exit_date'], y=df['equity'], mode='lines', name='Equity', line=dict(color='#00ADB5', width=2)))
        
        # Add markers for Win/Loss
        wins = df[df['pnl_rupiah'] > 0]
        losses = df[df['pnl_rupiah'] <= 0]
        
        fig.add_trace(go.Scatter(x=wins['exit_date'], y=wins['equity'], mode='markers', name='Win', marker=dict(color='green', size=6)))
        fig.add_trace(go.Scatter(x=losses['exit_date'], y=losses['equity'], mode='markers', name='Loss', marker=dict(color='red', size=6)))
        
        fig.update_layout(
            title="Equity Curve",
            xaxis_title="Date",
            yaxis_title="Capital (Rp)",
            template="plotly_dark",
            height=400,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 4. Trades Table
        st.subheader("Trade History")
        st.dataframe(
            df[['symbol', 'entry_date', 'exit_date', 'entry_price', 'exit_price', 'qty', 'pnl_rupiah', 'pnl_percent', 'exit_reason']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.warning("No trades found for this run.")
