"""Breakdowns page — performance by strategy, sector, and setup tag."""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from analytics.breakdown import analyze_by_strategy, analyze_by_sector
from dashboard.components.charts import plot_win_rate_bar


def _bar(df: pd.DataFrame, x_col: str, y_col: str, title: str,
         colour: str = "#00ADB5") -> go.Figure:
    """Generic horizontal bar chart."""
    fig = go.Figure(go.Bar(
        x=df[y_col], y=df[x_col],
        orientation="h",
        marker_color=colour,
        text=df[y_col].round(1).astype(str) + ("%" if "rate" in y_col or "pct" in y_col else ""),
        textposition="outside",
    ))
    fig.update_layout(
        title=title, template="plotly_dark",
        height=max(260, len(df) * 50),
        margin=dict(t=40, b=10, l=10, r=60),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def render(trades: list, db=None):
    st.title("🧩 Breakdowns")
    st.caption("Analisis performa berdasarkan strategi, sektor, dan tag setup.")

    if not trades:
        st.info("📭 Belum ada data trade tertutup.")
        return

    # ── By Strategy ───────────────────────────────────────────────────────────
    st.markdown("### 🎯 Per Strategi")
    strat_df = analyze_by_strategy(trades)

    if not strat_df.empty:
        sc1, sc2 = st.columns([3, 2])
        with sc1:
            st.plotly_chart(
                plot_win_rate_bar(strat_df, "strategy", "Win Rate per Strategi"),
                use_container_width=True,
            )
        with sc2:
            # Clean display
            show_cols = [c for c in ["strategy", "total", "win_rate", "avg_pnl"] if c in strat_df.columns]
            disp = strat_df[show_cols].rename(columns={
                "strategy": "Strategi",
                "total":    "Trade",
                "win_rate": "Win Rate %",
                "avg_pnl":  "Avg P&L (Rp)",
            })
            if "Win Rate %" in disp.columns:
                disp["Win Rate %"] = disp["Win Rate %"].apply(lambda x: f"{x:.1f}%")
            if "Avg P&L (Rp)" in disp.columns:
                disp["Avg P&L (Rp)"] = disp["Avg P&L (Rp)"].apply(lambda x: f"Rp {x:+,.0f}")
            st.dataframe(disp, use_container_width=True, hide_index=True)
    else:
        st.info("Data strategi tidak tersedia.")

    st.divider()

    # ── By Setup Tag ─────────────────────────────────────────────────────────
    st.markdown("### 🏷️ Per Setup Tag")
    setup_data = [t for t in trades if t.get("setup_tag")]
    if setup_data:
        df_s = pd.DataFrame(setup_data)
        tag_stats = (
            df_s.groupby("setup_tag")
            .agg(
                total=("pnl_rupiah", "count"),
                win_rate=("pnl_rupiah", lambda x: (x > 0).mean() * 100),
                avg_pnl=("pnl_rupiah", "mean"),
            )
            .reset_index()
            .sort_values("win_rate", ascending=False)
        )
        tc1, tc2 = st.columns([3, 2])
        with tc1:
            st.plotly_chart(
                plot_win_rate_bar(tag_stats, "setup_tag", "Win Rate per Setup Tag"),
                use_container_width=True,
            )
        with tc2:
            disp_t = tag_stats.rename(columns={
                "setup_tag": "Setup", "total": "Trade",
                "win_rate": "Win Rate %", "avg_pnl": "Avg P&L (Rp)",
            })
            disp_t["Win Rate %"]  = disp_t["Win Rate %"].apply(lambda x: f"{x:.1f}%")
            disp_t["Avg P&L (Rp)"]= disp_t["Avg P&L (Rp)"].apply(lambda x: f"Rp {x:+,.0f}")
            st.dataframe(disp_t, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada trade dengan setup tag. Gunakan field 'Setup Tag' saat input trade.")

    st.divider()

    # ── By Sector ─────────────────────────────────────────────────────────────
    st.markdown("### 🏭 Per Sektor")
    # Fetch sector map from DB if available
    sector_map = {}
    if db is not None:
        try:
            for doc in db.sector_map.find({}, {"symbol": 1, "sector": 1, "_id": 0}):
                sector_map[doc["symbol"]] = doc.get("sector", "Other")
        except Exception:
            pass

    sector_df = analyze_by_sector(trades, sector_map)
    if not sector_df.empty:
        show_sc = [c for c in ["sector", "total", "win_rate", "avg_pnl"] if c in sector_df.columns]
        disp_sec = sector_df[show_sc].rename(columns={
            "sector": "Sektor", "total": "Trade",
            "win_rate": "Win Rate %", "avg_pnl": "Avg P&L (Rp)",
        })
        if "Win Rate %" in disp_sec.columns:
            disp_sec["Win Rate %"]   = disp_sec["Win Rate %"].apply(lambda x: f"{x:.1f}%")
        if "Avg P&L (Rp)" in disp_sec.columns:
            disp_sec["Avg P&L (Rp)"] = disp_sec["Avg P&L (Rp)"].apply(lambda x: f"Rp {x:+,.0f}")
        st.dataframe(disp_sec, use_container_width=True, hide_index=True)
    else:
        st.info("Data sektor tidak tersedia (isi kolom sektor di Watchlist Manager terlebih dahulu).")

    st.divider()

    # ── Holding Period Distribution ──────────────────────────────────────────
    st.markdown("### ⏱️ Distribusi Holding Period")
    df_hold = pd.DataFrame(trades)
    if "holding_days" in df_hold.columns and df_hold["holding_days"].notna().any():
        fig_h = go.Figure(go.Histogram(
            x=df_hold["holding_days"].dropna(),
            nbinsx=20,
            marker_color="#00ADB5",
            opacity=0.85,
        ))
        fig_h.update_layout(
            template="plotly_dark", height=280,
            xaxis_title="Holding Days", yaxis_title="Jumlah Trade",
            margin=dict(t=10, b=20),
        )
        st.plotly_chart(fig_h, use_container_width=True)
    else:
        st.info("Data holding days belum tersedia.")
