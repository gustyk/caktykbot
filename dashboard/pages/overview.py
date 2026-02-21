"""Overview page — key performance metrics + equity curve."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dashboard.components.charts import plot_equity_curve
from analytics.equity_curve import calculate_equity_curve


def render(trades: list, initial_capital: float):
    st.title("🏠 Overview")
    st.caption("Ringkasan performa trading secara keseluruhan.")

    if not trades:
        st.info(
            "📭 Belum ada data trade.\n\n"
            "Gunakan `/addtrade` di Telegram atau tab **➕ Tambah Trade** di Journal."
        )
        return

    # ── Metrics ───────────────────────────────────────────────────────────────
    total_pnl  = sum(t.get("pnl_rupiah") or 0 for t in trades)
    wins       = [t for t in trades if (t.get("pnl_rupiah") or 0) > 0]
    losses     = [t for t in trades if (t.get("pnl_rupiah") or 0) <= 0]
    win_rate   = (len(wins) / len(trades) * 100) if trades else 0
    best_trade = max(trades, key=lambda t: t.get("pnl_rupiah") or 0)
    worst_trade= min(trades, key=lambda t: t.get("pnl_rupiah") or 0)
    avg_hold   = (
        sum(t.get("holding_days") or 0 for t in trades) / len(trades)
        if trades else 0
    )
    current_cap = initial_capital + total_pnl
    cap_change  = (total_pnl / initial_capital * 100) if initial_capital else 0

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r1c1.metric("💰 Modal Saat Ini",  f"Rp {current_cap:,.0f}", f"{cap_change:+.2f}%")
    r1c2.metric("📊 Total P&L",       f"Rp {total_pnl:+,.0f}")
    r1c3.metric("🏆 Win Rate",        f"{win_rate:.1f}%")
    r1c4.metric("📈 Total Trade",     len(trades))

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    r2c1.metric("⏱️ Avg Hold (hari)", f"{avg_hold:.1f}")
    r2c2.metric("✅ Win",              len(wins))
    r2c3.metric("❌ Loss",             len(losses))

    pf_denom = abs(sum(t.get("pnl_rupiah", 0) for t in losses))
    pf_num   = sum(t.get("pnl_rupiah", 0) for t in wins)
    pf       = pf_num / pf_denom if pf_denom else float("inf")
    r2c4.metric("⚡ Profit Factor", f"{pf:.2f}" if pf != float("inf") else "∞")

    st.divider()

    # ── Equity Curve ──────────────────────────────────────────────────────────
    st.markdown("### 📈 Equity Curve")
    curve = calculate_equity_curve(trades, initial_capital)
    if curve:
        st.plotly_chart(plot_equity_curve(curve), use_container_width=True)
    else:
        st.info("Belum cukup data untuk equity curve.")

    # ── Best / Worst ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🏅 Trade Terbaik & Terburuk")
    bw1, bw2 = st.columns(2)
    with bw1:
        st.success(
            f"🟢 **Best Trade**\n\n"
            f"**{best_trade.get('symbol','-')}** — "
            f"Rp {best_trade.get('pnl_rupiah',0):+,.0f} "
            f"({best_trade.get('pnl_percent',0):+.2f}%) "
            f"via {best_trade.get('strategy','-')}"
        )
    with bw2:
        st.error(
            f"🔴 **Worst Trade**\n\n"
            f"**{worst_trade.get('symbol','-')}** — "
            f"Rp {worst_trade.get('pnl_rupiah',0):+,.0f} "
            f"({worst_trade.get('pnl_percent',0):+.2f}%) "
            f"via {worst_trade.get('strategy','-')}"
        )

    # ── Recent 5 trades ───────────────────────────────────────────────────────
    st.markdown("### 🕐 5 Trade Terakhir")
    recent = sorted(
        trades,
        key=lambda t: t.get("exit_date") or t.get("entry_date") or "",
        reverse=True,
    )[:5]

    rows = []
    for t in recent:
        pnl = t.get("pnl_rupiah") or 0
        rows.append({
            "Ticker":    t.get("symbol", "-"),
            "Strategi":  t.get("strategy", "-"),
            "P&L":       f"Rp {pnl:+,.0f}",
            "P&L %":     f"{t.get('pnl_percent', 0):+.2f}%",
            "Hold (hr)": t.get("holding_days", "-"),
            "Hasil":     "✅ Win" if pnl > 0 else "❌ Loss",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
