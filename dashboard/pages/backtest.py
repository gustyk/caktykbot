"""Backtest results page."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from db.repositories.backtest_repo import BacktestRepository
from db.connection import get_database
from dashboard.components.charts import _TEAL, _GREEN, _RED, _LAYOUT_BASE


def render(db=None):
    st.title("🧪 Backtest")
    st.caption("Hasil uji strategi terhadap data historis. Jalankan via `/backtest vcp` di Telegram.")

    if db is None:
        db = get_database()

    repo = BacktestRepository(db)
    runs = repo.get_all_runs()

    if not runs:
        st.info(
            "📭 Belum ada hasil backtest.\n\n"
            "Gunakan perintah Telegram:\n"
            "- `/backtest vcp` — backtest strategi VCP\n"
            "- `/backtest ema` — backtest strategi EMA Pullback"
        )
        return

    # ── Run selector ──────────────────────────────────────────────────────────
    run_options = {
        f"{r.strategy.upper()} — {r.created_at.strftime('%d %b %Y %H:%M')}": r
        for r in sorted(runs, key=lambda r: r.created_at, reverse=True)
    }
    selected_label = st.selectbox(
        "📂 Pilih Hasil Backtest",
        list(run_options.keys()),
        key="bt_run_sel",
    )
    run = run_options[selected_label]

    # ── Summary header ────────────────────────────────────────────────────────
    st.markdown(f"### {run.strategy.upper()} — Hasil Backtest")
    st.caption(
        f"Periode: **{run.start_date.date()}** s/d **{run.end_date.date()}** | "
        f"Durasi: {run.duration_seconds:.1f}s | "
        f"Modal Awal: Rp {run.initial_capital:,.0f}"
    )

    metrics = run.metrics

    # Row 1
    m1, m2, m3, m4 = st.columns(4)
    total_ret = metrics.get("total_return", 0)
    m1.metric("📈 Total Return",    f"{total_ret:.2f}%",
              delta=f"{total_ret:+.2f}%" if total_ret else None)
    m2.metric("🏆 Win Rate",        f"{metrics.get('win_rate', 0):.1f}%")
    m3.metric("⚡ Profit Factor",   f"{metrics.get('profit_factor', 0):.2f}")
    m4.metric("📊 Total Trade",     metrics.get("total_trades", 0))

    # Row 2
    m5, m6, m7, m8 = st.columns(4)
    mdd = metrics.get("max_drawdown", 0)
    m5.metric("📉 Max Drawdown",    f"{mdd:.2f}%",
              delta=f"{mdd:.2f}%", delta_color="inverse")
    m6.metric("📐 Sharpe Ratio",    f"{metrics.get('sharpe_ratio', 0):.2f}")
    m7.metric("✅ Avg Profit",      f"{metrics.get('avg_profit', 0):.2f}%")
    m8.metric("❌ Avg Loss",        f"{metrics.get('avg_loss', 0):.2f}%")

    st.divider()

    # ── Equity Curve ──────────────────────────────────────────────────────────
    trades = repo.get_trades_by_run(run.id)

    if not trades:
        st.warning("Tidak ada trade dalam hasil backtest ini.")
        return

    df = pd.DataFrame([t.model_dump() for t in trades])
    df["exit_date"] = pd.to_datetime(df["exit_date"], errors="coerce")
    df = df.sort_values("exit_date")
    df["cumulative_pnl"] = df["pnl_rupiah"].cumsum()
    df["equity"]         = run.initial_capital + df["cumulative_pnl"]
    df["peak"]           = df["equity"].cummax()
    df["drawdown_pct"]   = (df["equity"] - df["peak"]) / df["peak"] * 100

    st.markdown("### 📈 Equity Curve")
    fig = go.Figure()

    # Drawdown fill
    fig.add_trace(go.Scatter(
        x=df["exit_date"], y=df["drawdown_pct"],
        mode="lines", name="Drawdown %",
        fill="tozeroy",
        line=dict(color=_RED, width=1),
        fillcolor="rgba(231,76,60,0.12)",
        yaxis="y2",
    ))
    # Equity line
    fig.add_trace(go.Scatter(
        x=df["exit_date"], y=df["equity"],
        mode="lines", name="Equity",
        line=dict(color=_TEAL, width=2.5),
        fill="tozeroy",
        fillcolor="rgba(0,173,181,0.08)",
    ))
    # Win/Loss markers
    wins   = df[df["pnl_rupiah"] > 0]
    losses = df[df["pnl_rupiah"] <= 0]
    fig.add_trace(go.Scatter(
        x=wins["exit_date"], y=wins["equity"],
        mode="markers", name="Win",
        marker=dict(color=_GREEN, size=7, symbol="circle"),
    ))
    fig.add_trace(go.Scatter(
        x=losses["exit_date"], y=losses["equity"],
        mode="markers", name="Loss",
        marker=dict(color=_RED, size=7, symbol="x"),
    ))

    fig.update_layout(
        **_LAYOUT_BASE,
        height=400,
        xaxis_title="Tanggal",
        yaxis=dict(title="Equity (Rp)", tickformat=",.0f"),
        yaxis2=dict(
            title="Drawdown %",
            overlaying="y", side="right",
            showgrid=False, ticksuffix="%",
        ),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.08, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Trade Table ───────────────────────────────────────────────────────────
    st.markdown("### 📋 Detail Trade")

    show_cols = [c for c in [
        "symbol", "entry_date", "exit_date", "entry_price",
        "exit_price", "qty", "pnl_rupiah", "pnl_percent", "exit_reason"
    ] if c in df.columns]

    disp = df[show_cols].rename(columns={
        "symbol":       "Ticker",
        "entry_date":   "Tgl Entry",
        "exit_date":    "Tgl Exit",
        "entry_price":  "Entry (Rp)",
        "exit_price":   "Exit (Rp)",
        "qty":          "Qty",
        "pnl_rupiah":   "P&L (Rp)",
        "pnl_percent":  "P&L %",
        "exit_reason":  "Alasan Exit",
    })

    for numcol in ["Entry (Rp)", "Exit (Rp)"]:
        if numcol in disp.columns:
            disp[numcol] = disp[numcol].apply(
                lambda x: f"Rp {x:,.0f}" if pd.notna(x) else "-"
            )
    if "P&L (Rp)" in disp.columns:
        disp["P&L (Rp)"] = disp["P&L (Rp)"].apply(
            lambda x: f"Rp {x:+,.0f}" if pd.notna(x) else "-"
        )
    if "P&L %" in disp.columns:
        disp["P&L %"] = disp["P&L %"].apply(
            lambda x: f"{x:+.2f}%" if pd.notna(x) else "-"
        )
    for dc in ["Tgl Entry", "Tgl Exit"]:
        if dc in disp.columns:
            disp[dc] = pd.to_datetime(disp[dc], errors="coerce").dt.strftime("%d %b %Y").fillna("-")

    st.dataframe(disp, use_container_width=True, hide_index=True)
