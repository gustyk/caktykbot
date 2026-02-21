"""Trading Journal page for Streamlit dashboard."""
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime


def _to_df(trades: list, status_filter: str = None) -> pd.DataFrame:
    """Convert list of Trade dicts to a cleaned DataFrame."""
    if not trades:
        return pd.DataFrame()

    filtered = trades if not status_filter else [
        t for t in trades if t.get("status") == status_filter
    ]
    if not filtered:
        return pd.DataFrame()

    df = pd.DataFrame(filtered)
    # Normalise date columns
    for col in ["entry_date", "exit_date", "created_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _colour(val):
    """Return green/red CSS colour string based on sign."""
    if isinstance(val, (int, float)):
        return "color: #2ecc71" if val >= 0 else "color: #e74c3c"
    return ""


def render(all_trades: list):
    """Render the Trading Journal page.

    Args:
        all_trades: All Trade dicts (open + closed) for the current user.
    """
    st.title("📒 Trading Journal")

    if not all_trades:
        st.info(
            "Belum ada trade yang tercatat.\n\n"
            "Gunakan `/addtrade` di Telegram untuk mencatat trade pertamamu."
        )
        return

    open_trades   = [t for t in all_trades if t.get("status") == "open"]
    closed_trades = [t for t in all_trades if t.get("status") == "closed"]
    draft_trades  = [t for t in all_trades if t.get("status") == "draft"]

    # ── Summary metrics ──────────────────────────────────────────────────────
    total_pnl  = sum(t.get("pnl_rupiah") or 0 for t in closed_trades)
    wins       = [t for t in closed_trades if (t.get("pnl_rupiah") or 0) > 0]
    losses     = [t for t in closed_trades if (t.get("pnl_rupiah") or 0) <= 0]
    win_rate   = (len(wins) / len(closed_trades) * 100) if closed_trades else 0
    avg_win    = (sum(t.get("pnl_rupiah", 0) for t in wins) / len(wins)) if wins else 0
    avg_loss   = (sum(t.get("pnl_rupiah", 0) for t in losses) / len(losses)) if losses else 0

    pnl_colour = "#2ecc71" if total_pnl >= 0 else "#e74c3c"

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📊 Total Trade", len(closed_trades))
    col2.metric("🟢 Open Positions", len(open_trades))
    col3.metric("🏆 Win Rate", f"{win_rate:.1f}%")
    col4.metric("💰 Total P&L", f"Rp {total_pnl:+,.0f}")
    col5.metric("📝 Draft", len(draft_trades))

    st.divider()

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_open, tab_closed, tab_stats = st.tabs(
        ["🟢 Open Positions", "📋 Trade History", "📈 Statistik"]
    )

    # ── Tab 1: Open Positions ────────────────────────────────────────────────
    with tab_open:
        if not open_trades:
            st.info("Tidak ada posisi yang sedang terbuka.")
        else:
            df_open = _to_df(open_trades)
            cols_show = [c for c in [
                "symbol", "strategy", "entry_price", "sl_price", "tp_price",
                "qty", "entry_date", "notes"
            ] if c in df_open.columns]

            display = df_open[cols_show].rename(columns={
                "symbol": "Ticker",
                "strategy": "Strategi",
                "entry_price": "Entry (Rp)",
                "sl_price": "Stop Loss",
                "tp_price": "Take Profit",
                "qty": "Lot",
                "entry_date": "Tanggal Entry",
                "notes": "Catatan",
            })

            # Format numbers
            for num_col in ["Entry (Rp)", "Stop Loss", "Take Profit"]:
                if num_col in display.columns:
                    display[num_col] = display[num_col].apply(
                        lambda x: f"Rp {x:,.0f}" if pd.notna(x) else "-"
                    )
            if "Tanggal Entry" in display.columns:
                display["Tanggal Entry"] = display["Tanggal Entry"].dt.strftime(
                    "%d %b %Y"
                ).fillna("-")

            st.dataframe(display, use_container_width=True, hide_index=True)

            # Risk visualisation per position
            st.markdown("#### 🎯 Risk/Reward per Posisi")
            rr_data = []
            for t in open_trades:
                entry = t.get("entry_price") or 0
                sl    = t.get("sl_price") or 0
                tp    = t.get("tp_price") or 0
                if entry and sl and sl < entry:
                    risk   = entry - sl
                    reward = tp - entry if tp > entry else 0
                    rr_data.append({
                        "Ticker": t.get("symbol", "?"),
                        "Risk (Rp)": risk,
                        "Reward (Rp)": reward,
                        "R/R": round(reward / risk, 2) if risk else 0,
                    })
            if rr_data:
                st.dataframe(pd.DataFrame(rr_data), use_container_width=True, hide_index=True)

    # ── Tab 2: Trade History ─────────────────────────────────────────────────
    with tab_closed:
        if not closed_trades:
            st.info("Belum ada trade yang ditutup.")
        else:
            df_cl = _to_df(closed_trades)

            # Filters
            fc1, fc2, fc3 = st.columns(3)
            strategies = ["Semua"] + sorted(df_cl["strategy"].dropna().unique().tolist()) \
                if "strategy" in df_cl.columns else ["Semua"]
            sel_strat = fc1.selectbox("Strategi", strategies, key="hist_strat")

            if "entry_date" in df_cl.columns:
                min_d = df_cl["entry_date"].min()
                max_d = df_cl["entry_date"].max()
                if pd.notna(min_d) and pd.notna(max_d):
                    date_range = fc2.date_input(
                        "Periode", value=(min_d.date(), max_d.date()), key="hist_date"
                    )
                else:
                    date_range = None
            else:
                date_range = None

            result_opts = ["Semua", "Profit", "Loss"]
            sel_result  = fc3.selectbox("Hasil", result_opts, key="hist_result")

            # Apply filters
            filtered = df_cl.copy()
            if sel_strat != "Semua" and "strategy" in filtered.columns:
                filtered = filtered[filtered["strategy"] == sel_strat]
            if date_range and len(date_range) == 2 and "entry_date" in filtered.columns:
                s, e = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
                filtered = filtered[
                    (filtered["entry_date"] >= s) & (filtered["entry_date"] <= e)
                ]
            if sel_result == "Profit" and "pnl_rupiah" in filtered.columns:
                filtered = filtered[filtered["pnl_rupiah"] > 0]
            elif sel_result == "Loss" and "pnl_rupiah" in filtered.columns:
                filtered = filtered[filtered["pnl_rupiah"] <= 0]

            st.caption(f"Menampilkan {len(filtered)} dari {len(df_cl)} trade")

            cols_hist = [c for c in [
                "symbol", "strategy", "entry_price", "exit_price",
                "pnl_rupiah", "pnl_pct", "entry_date", "exit_date",
                "hold_days", "emotion", "notes"
            ] if c in filtered.columns]

            display_hist = filtered[cols_hist].rename(columns={
                "symbol": "Ticker",
                "strategy": "Strategi",
                "entry_price": "Entry",
                "exit_price": "Exit",
                "pnl_rupiah": "P&L (Rp)",
                "pnl_pct": "P&L %",
                "entry_date": "Tgl Entry",
                "exit_date": "Tgl Exit",
                "hold_days": "Hold (hari)",
                "emotion": "Emosi",
                "notes": "Catatan",
            })

            # Format
            for col in ["Entry", "Exit"]:
                if col in display_hist.columns:
                    display_hist[col] = display_hist[col].apply(
                        lambda x: f"Rp {x:,.0f}" if pd.notna(x) else "-"
                    )
            if "P&L (Rp)" in display_hist.columns:
                display_hist["P&L (Rp)"] = display_hist["P&L (Rp)"].apply(
                    lambda x: f"Rp {x:+,.0f}" if pd.notna(x) else "-"
                )
            if "P&L %" in display_hist.columns:
                display_hist["P&L %"] = display_hist["P&L %"].apply(
                    lambda x: f"{x:+.2f}%" if pd.notna(x) else "-"
                )
            for dcol in ["Tgl Entry", "Tgl Exit"]:
                if dcol in display_hist.columns:
                    display_hist[dcol] = pd.to_datetime(
                        display_hist[dcol], errors="coerce"
                    ).dt.strftime("%d %b %Y").fillna("-")

            st.dataframe(display_hist, use_container_width=True, hide_index=True)

            # P&L bar chart
            if "P&L (Rp)" not in filtered.columns and "pnl_rupiah" in filtered.columns:
                pnl_series = filtered["pnl_rupiah"]
            elif "pnl_rupiah" in filtered.columns:
                pnl_series = filtered["pnl_rupiah"]
            else:
                pnl_series = None

            if pnl_series is not None and len(filtered):
                colours = ["#2ecc71" if v >= 0 else "#e74c3c" for v in pnl_series]
                fig = go.Figure(go.Bar(
                    x=filtered.get("symbol", filtered.index).tolist(),
                    y=pnl_series.tolist(),
                    marker_color=colours,
                    text=[f"Rp {v:+,.0f}" for v in pnl_series],
                    textposition="outside",
                ))
                fig.update_layout(
                    title="P&L per Trade", template="plotly_dark",
                    height=350, margin=dict(t=40, b=20),
                    xaxis_title="Ticker", yaxis_title="P&L (Rp)",
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── Tab 3: Statistics ────────────────────────────────────────────────────
    with tab_stats:
        if not closed_trades:
            st.info("Belum ada trade tertutup untuk dihitung statistiknya.")
        else:
            s1, s2 = st.columns(2)

            with s1:
                st.markdown("#### 📊 Ringkasan Performa")
                profit_factor = (
                    abs(sum(t.get("pnl_rupiah", 0) for t in wins) /
                        sum(t.get("pnl_rupiah", 0) for t in losses))
                    if losses and sum(t.get("pnl_rupiah", 0) for t in losses) != 0
                    else float("inf")
                )
                hold_days_vals = [
                    t.get("hold_days") for t in closed_trades if t.get("hold_days")
                ]
                avg_hold = (sum(hold_days_vals) / len(hold_days_vals)) if hold_days_vals else 0

                stats = {
                    "Total Trade": len(closed_trades),
                    "Win": len(wins),
                    "Loss": len(losses),
                    "Win Rate": f"{win_rate:.1f}%",
                    "Avg Win": f"Rp {avg_win:+,.0f}",
                    "Avg Loss": f"Rp {avg_loss:+,.0f}",
                    "Profit Factor": f"{profit_factor:.2f}" if profit_factor != float("inf") else "∞",
                    "Avg Hold (hari)": f"{avg_hold:.1f}",
                    "Total P&L": f"Rp {total_pnl:+,.0f}",
                }
                for k, v in stats.items():
                    st.markdown(
                        f"<div style='display:flex; justify-content:space-between;"
                        f"padding:6px 0; border-bottom:1px solid #333;'>"
                        f"<span style='color:#aaa'>{k}</span>"
                        f"<strong>{v}</strong></div>",
                        unsafe_allow_html=True,
                    )

            with s2:
                st.markdown("#### 🥧 Win/Loss Distribution")
                fig_pie = go.Figure(go.Pie(
                    labels=["Win", "Loss"],
                    values=[len(wins), len(losses)],
                    marker_colors=["#2ecc71", "#e74c3c"],
                    hole=0.45,
                    textinfo="label+percent",
                ))
                fig_pie.update_layout(
                    template="plotly_dark", height=300,
                    margin=dict(t=20, b=20, l=20, r=20),
                    showlegend=False,
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            # Monthly P&L
            st.markdown("#### 📅 P&L Bulanan")
            df_cl2 = _to_df(closed_trades)
            if "exit_date" in df_cl2.columns and "pnl_rupiah" in df_cl2.columns:
                df_cl2["bulan"] = df_cl2["exit_date"].dt.to_period("M").astype(str)
                monthly = df_cl2.groupby("bulan")["pnl_rupiah"].sum().reset_index()
                monthly.columns = ["Bulan", "P&L"]
                colours_m = ["#2ecc71" if v >= 0 else "#e74c3c" for v in monthly["P&L"]]
                fig_m = go.Figure(go.Bar(
                    x=monthly["Bulan"],
                    y=monthly["P&L"],
                    marker_color=colours_m,
                    text=[f"Rp {v:+,.0f}" for v in monthly["P&L"]],
                    textposition="outside",
                ))
                fig_m.update_layout(
                    template="plotly_dark", height=300,
                    margin=dict(t=10, b=20),
                    xaxis_title="Bulan", yaxis_title="P&L (Rp)",
                )
                st.plotly_chart(fig_m, use_container_width=True)
