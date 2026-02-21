"""Trading Journal page for Streamlit dashboard — with full CRUD."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db.repositories.trade_repo import TradeRepository
from db.schemas import Trade, TradeLeg
from journal.trade_manager import TradeManager


# ── constants ─────────────────────────────────────────────────────────────────

_STRATEGIES   = ["VCP", "EMA Pullback", "Bandarmologi", "Custom"]
_EMOTIONS     = ["Confident", "Disciplined", "Neutral", "Anxious", "FOMO", "Revenge", "Panic"]
_SETUP_TAGS   = ["Breakout", "Pullback", "Reversal", "Momentum", "Accumulation", "Other"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _to_df(trades: list, status_filter: str = None) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    filtered = trades if not status_filter else [
        t for t in trades if t.get("status") == status_filter
    ]
    if not filtered:
        return pd.DataFrame()
    df = pd.DataFrame(filtered)
    for col in ["entry_date", "exit_date", "created_at"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _fmt_rp(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "-"
    return f"Rp {val:+,.0f}"


def _fmt_pct(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "-"
    return f"{val:+.2f}%"


def _reload():
    st.cache_data.clear()
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render(db):
    """Render the Trading Journal page with CRUD.

    Args:
        db: MongoDB database instance (passed from app.py)
    """
    repo    = TradeRepository(db)
    manager = TradeManager(repo)

    st.title("📒 Trading Journal")
    st.caption("Catat, pantau, dan analisis semua trade. Sinkron otomatis dengan bot Telegram.")

    # ── fetch all trades ──────────────────────────────────────────────────────
    all_trades    = [t.model_dump() for t in repo.get_all_trades()]
    open_trades   = [t for t in all_trades if t.get("status") == "open"]
    closed_trades = [t for t in all_trades if t.get("status") == "closed"]
    draft_trades  = [t for t in all_trades if t.get("status") == "draft"]

    # ── summary metrics ───────────────────────────────────────────────────────
    total_pnl = sum(t.get("pnl_rupiah") or 0 for t in closed_trades)
    wins      = [t for t in closed_trades if (t.get("pnl_rupiah") or 0) > 0]
    losses    = [t for t in closed_trades if (t.get("pnl_rupiah") or 0) <= 0]
    win_rate  = (len(wins) / len(closed_trades) * 100) if closed_trades else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📊 Total Trade", len(closed_trades))
    c2.metric("🟢 Open",        len(open_trades))
    c3.metric("🏆 Win Rate",    f"{win_rate:.1f}%")
    c4.metric("💰 Total P&L",   f"Rp {total_pnl:+,.0f}")
    c5.metric("📝 Draft",       len(draft_trades))

    st.divider()

    # ── tabs ──────────────────────────────────────────────────────────────────
    tab_open, tab_hist, tab_stats, tab_add, tab_close, tab_edit = st.tabs([
        "🟢 Posisi Open",
        "📋 Histori Trade",
        "📈 Statistik",
        "➕ Tambah Trade",
        "✅ Tutup Trade",
        "✏️ Edit / Hapus",
    ])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1: OPEN POSITIONS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_open:
        if not open_trades:
            st.info("Tidak ada posisi terbuka saat ini.\n\nGunakan tab **➕ Tambah Trade** untuk mencatat trade baru.")
        else:
            df_open = _to_df(open_trades)
            cols = [c for c in ["symbol","strategy","entry_price","sl_price","tp_price",
                                  "qty_remaining","entry_date","risk_percent","notes"] if c in df_open.columns]
            display = df_open[cols].rename(columns={
                "symbol":"Ticker","strategy":"Strategi","entry_price":"Entry (Rp)",
                "sl_price":"SL","tp_price":"TP","qty_remaining":"Lot Sisa",
                "entry_date":"Tgl Entry","risk_percent":"Risk %","notes":"Catatan",
            })
            for num in ["Entry (Rp)","SL","TP"]:
                if num in display.columns:
                    display[num] = display[num].apply(lambda x: f"Rp {x:,.0f}" if pd.notna(x) else "-")
            if "Tgl Entry" in display.columns:
                display["Tgl Entry"] = display["Tgl Entry"].dt.strftime("%d %b %Y").fillna("-")

            st.dataframe(display, use_container_width=True, hide_index=True)

            # R/R table
            rr_rows = []
            for t in open_trades:
                entry = t.get("entry_price") or 0
                sl    = t.get("sl_price") or 0
                tp    = t.get("tp_price") or 0
                if entry and sl and sl < entry:
                    risk   = entry - sl
                    reward = tp - entry if tp and tp > entry else 0
                    rr_rows.append({
                        "Ticker":     t.get("symbol"),
                        "Risk (Rp)":  f"Rp {risk:,.0f}",
                        "Reward (Rp)": f"Rp {reward:,.0f}" if reward else "-",
                        "R/R":        f"1:{reward/risk:.2f}" if risk and reward else "-",
                    })
            if rr_rows:
                st.markdown("#### 🎯 Risk/Reward per Posisi")
                st.dataframe(pd.DataFrame(rr_rows), use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2: TRADE HISTORY
    # ══════════════════════════════════════════════════════════════════════════
    with tab_hist:
        if not closed_trades:
            st.info("Belum ada trade yang ditutup.")
        else:
            df_cl = _to_df(closed_trades)

            f1, f2, f3 = st.columns(3)
            strategies = ["Semua"] + sorted(df_cl["strategy"].dropna().unique().tolist()) if "strategy" in df_cl.columns else ["Semua"]
            sel_strat  = f1.selectbox("Strategi", strategies, key="h_strat")
            sel_result = f3.selectbox("Hasil", ["Semua", "Profit", "Loss"], key="h_res")

            filtered = df_cl.copy()
            if sel_strat != "Semua" and "strategy" in filtered.columns:
                filtered = filtered[filtered["strategy"] == sel_strat]
            if sel_result == "Profit" and "pnl_rupiah" in filtered.columns:
                filtered = filtered[filtered["pnl_rupiah"] > 0]
            elif sel_result == "Loss" and "pnl_rupiah" in filtered.columns:
                filtered = filtered[filtered["pnl_rupiah"] <= 0]

            st.caption(f"Menampilkan {len(filtered)} trade")

            cols_h = [c for c in ["symbol","strategy","entry_price","exit_price",
                                    "pnl_rupiah","pnl_percent","entry_date","exit_date",
                                    "holding_days","emotion_tag","notes"] if c in filtered.columns]
            disp_h = filtered[cols_h].rename(columns={
                "symbol":"Ticker","strategy":"Strategi","entry_price":"Entry",
                "exit_price":"Exit","pnl_rupiah":"P&L (Rp)","pnl_percent":"P&L %",
                "entry_date":"Tgl Entry","exit_date":"Tgl Exit",
                "holding_days":"Hold (hr)","emotion_tag":"Emosi","notes":"Catatan",
            })
            for col in ["Entry","Exit"]:
                if col in disp_h.columns:
                    disp_h[col] = disp_h[col].apply(lambda x: f"Rp {x:,.0f}" if pd.notna(x) else "-")
            if "P&L (Rp)" in disp_h.columns:
                disp_h["P&L (Rp)"] = disp_h["P&L (Rp)"].apply(lambda x: f"Rp {x:+,.0f}" if pd.notna(x) else "-")
            if "P&L %" in disp_h.columns:
                disp_h["P&L %"] = disp_h["P&L %"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "-")
            for dc in ["Tgl Entry","Tgl Exit"]:
                if dc in disp_h.columns:
                    disp_h[dc] = pd.to_datetime(disp_h[dc], errors="coerce").dt.strftime("%d %b %Y").fillna("-")

            st.dataframe(disp_h, use_container_width=True, hide_index=True)

            # Bar chart
            if "pnl_rupiah" in filtered.columns and len(filtered):
                pnl_s = filtered["pnl_rupiah"].fillna(0)
                fig = go.Figure(go.Bar(
                    x=filtered.get("symbol", filtered.index).tolist(),
                    y=pnl_s.tolist(),
                    marker_color=["#2ecc71" if v >= 0 else "#e74c3c" for v in pnl_s],
                    text=[f"Rp {v:+,.0f}" for v in pnl_s],
                    textposition="outside",
                ))
                fig.update_layout(title="P&L per Trade", template="plotly_dark",
                                   height=320, margin=dict(t=40,b=20))
                st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3: STATISTICS
    # ══════════════════════════════════════════════════════════════════════════
    with tab_stats:
        if not closed_trades:
            st.info("Belum ada trade tertutup.")
        else:
            avg_win  = (sum(t.get("pnl_rupiah",0) for t in wins) / len(wins)) if wins else 0
            avg_loss = (sum(t.get("pnl_rupiah",0) for t in losses) / len(losses)) if losses else 0
            pf_denom = abs(sum(t.get("pnl_rupiah",0) for t in losses))
            pf_num   = sum(t.get("pnl_rupiah",0) for t in wins)
            profit_factor = (pf_num / pf_denom) if pf_denom else float("inf")
            hold_vals = [t.get("holding_days") for t in closed_trades if t.get("holding_days")]
            avg_hold  = sum(hold_vals) / len(hold_vals) if hold_vals else 0

            s1, s2 = st.columns(2)
            with s1:
                st.markdown("#### 📊 Ringkasan")
                for label, val in {
                    "Total Trade":    len(closed_trades),
                    "Win":            len(wins),
                    "Loss":           len(losses),
                    "Win Rate":       f"{win_rate:.1f}%",
                    "Avg Win":        f"Rp {avg_win:+,.0f}",
                    "Avg Loss":       f"Rp {avg_loss:+,.0f}",
                    "Profit Factor":  f"{profit_factor:.2f}" if profit_factor != float("inf") else "∞",
                    "Avg Hold (hari)":f"{avg_hold:.1f}",
                    "Total P&L":      f"Rp {total_pnl:+,.0f}",
                }.items():
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;"
                        f"padding:6px 0;border-bottom:1px solid #333;'>"
                        f"<span style='color:#aaa'>{label}</span><strong>{val}</strong></div>",
                        unsafe_allow_html=True,
                    )
            with s2:
                st.markdown("#### 🥧 Win/Loss")
                fig_pie = go.Figure(go.Pie(
                    labels=["Win","Loss"], values=[len(wins),len(losses)],
                    marker_colors=["#2ecc71","#e74c3c"], hole=0.45,
                    textinfo="label+percent",
                ))
                fig_pie.update_layout(template="plotly_dark", height=280,
                                       margin=dict(t=10,b=10,l=10,r=10), showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)

            # Monthly P&L
            st.markdown("#### 📅 P&L Bulanan")
            df_m = _to_df(closed_trades)
            if "exit_date" in df_m.columns and "pnl_rupiah" in df_m.columns:
                df_m["bulan"] = df_m["exit_date"].dt.to_period("M").astype(str)
                monthly = df_m.groupby("bulan")["pnl_rupiah"].sum().reset_index()
                colours_m = ["#2ecc71" if v >= 0 else "#e74c3c" for v in monthly["pnl_rupiah"]]
                fig_m = go.Figure(go.Bar(
                    x=monthly["bulan"], y=monthly["pnl_rupiah"],
                    marker_color=colours_m,
                    text=[f"Rp {v:+,.0f}" for v in monthly["pnl_rupiah"]],
                    textposition="outside",
                ))
                fig_m.update_layout(template="plotly_dark", height=280,
                                     margin=dict(t=10,b=20))
                st.plotly_chart(fig_m, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4: ADD TRADE
    # ══════════════════════════════════════════════════════════════════════════
    with tab_add:
        st.markdown("### ➕ Tambah Trade Baru")

        with st.form("form_add_trade", clear_on_submit=True):
            r1c1, r1c2, r1c3 = st.columns(3)
            raw_sym    = r1c1.text_input("Ticker *", placeholder="BBCA atau BBCA.JK")
            entry_date = r1c2.date_input("Tanggal Entry *", value=datetime.now().date())
            status_opt = r1c3.selectbox("Status", ["open", "draft"])

            r2c1, r2c2, r2c3 = st.columns(3)
            entry_price = r2c1.number_input("Harga Entry (Rp) *", min_value=1.0, step=10.0, format="%.0f")
            qty         = r2c2.number_input("Qty (lembar) *", min_value=1, step=100)
            risk_pct    = r2c3.number_input("Risk % per trade", min_value=0.1, max_value=100.0, value=2.0, step=0.1)

            r3c1, r3c2 = st.columns(2)
            sl_price  = r3c1.number_input("Stop Loss (Rp, opsional)", min_value=0.0, step=10.0, format="%.0f")
            tp_price  = r3c2.number_input("Take Profit (Rp, opsional)", min_value=0.0, step=10.0, format="%.0f")

            r4c1, r4c2, r4c3 = st.columns(3)
            strategy  = r4c1.selectbox("Strategi *", _STRATEGIES)
            emotion   = r4c2.selectbox("Emosi Entry", ["(tidak diisi)"] + _EMOTIONS)
            setup_tag = r4c3.selectbox("Setup Tag", ["(tidak diisi)"] + _SETUP_TAGS)

            notes     = st.text_area("Catatan / Alasan Masuk", placeholder="Contoh: VCP breakout dengan volume tinggi, RS > IHSG...")

            submitted = st.form_submit_button("➕ Simpan Trade", type="primary", use_container_width=True)

        if submitted:
            sym = raw_sym.strip().upper()
            if not sym.endswith(".JK"):
                sym += ".JK"

            errors = []
            if not sym:          errors.append("Ticker wajib diisi.")
            if entry_price <= 0: errors.append("Harga entry harus > 0.")
            if qty <= 0:         errors.append("Qty harus > 0.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                trade_data = {
                    "symbol":       sym,
                    "entry_date":   datetime.combine(entry_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                    "entry_price":  float(entry_price),
                    "qty":          int(qty),
                    "risk_percent": float(risk_pct),
                    "strategy":     strategy,
                    "status":       status_opt,
                    "sl_price":     float(sl_price) if sl_price > 0 else None,
                    "tp_price":     float(tp_price) if tp_price > 0 else None,
                    "emotion_tag":  emotion if emotion != "(tidak diisi)" else None,
                    "setup_tag":    setup_tag if setup_tag != "(tidak diisi)" else None,
                    "notes":        notes.strip() or None,
                }
                try:
                    trade_id = manager.create_trade(trade_data)
                    st.success(f"✅ Trade **{sym}** berhasil dicatat! (ID: `{trade_id}`)")
                    _reload()
                except Exception as e:
                    st.error(f"❌ Gagal: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 5: CLOSE TRADE
    # ══════════════════════════════════════════════════════════════════════════
    with tab_close:
        st.markdown("### ✅ Tutup Trade")

        if not open_trades:
            st.info("Tidak ada posisi terbuka yang bisa ditutup.")
        else:
            open_labels = {
                f"{t['symbol']} — {int(t.get('qty_remaining',0)):,} lot @ Rp {t.get('entry_price',0):,.0f}": t
                for t in open_trades if t.get("id")
            }
            selected_label = st.selectbox("Pilih posisi yang akan ditutup", list(open_labels.keys()), key="close_sel")
            selected_trade = open_labels[selected_label]
            trade_id       = selected_trade.get("id")
            qty_remaining  = int(selected_trade.get("qty_remaining", 0))

            st.info(
                f"📋 **{selected_trade.get('symbol')}** | "
                f"Entry: Rp {selected_trade.get('entry_price',0):,.0f} | "
                f"Sisa: {qty_remaining:,} lot | "
                f"Strategi: {selected_trade.get('strategy','-')}"
            )

            close_type = st.radio("Tipe Close", ["Close All", "Partial Close"], horizontal=True, key="close_type")

            with st.form("form_close_trade"):
                fc1, fc2, fc3 = st.columns(3)
                exit_price = fc1.number_input("Harga Exit (Rp) *", min_value=1.0, step=10.0, format="%.0f")
                exit_date  = fc2.date_input("Tanggal Exit *", value=datetime.now().date())
                fees       = fc3.number_input("Biaya Broker+Pajak (Rp)", min_value=0.0, step=1000.0, format="%.0f")

                exit_qty   = qty_remaining
                if close_type == "Partial Close":
                    exit_qty = st.number_input(
                        f"Qty yang dijual (maks {qty_remaining:,})",
                        min_value=1, max_value=qty_remaining, step=100, value=min(100, qty_remaining)
                    )

                exit_emotion = st.selectbox("Emosi Exit", ["(tidak diisi)"] + _EMOTIONS, key="close_emo")
                exit_notes   = st.text_area("Catatan Exit", placeholder="Alasan exit, kondisi market...", key="close_notes")

                close_btn = st.form_submit_button("✅ Tutup Trade", type="primary", use_container_width=True)

            if close_btn:
                if exit_price <= 0:
                    st.error("Harga exit harus > 0.")
                else:
                    exit_payload = {
                        "exit_price":  float(exit_price),
                        "exit_date":   datetime.combine(exit_date, datetime.min.time()).replace(tzinfo=timezone.utc),
                        "fees":        float(fees),
                        "qty":         int(exit_qty),
                        "emotion_tag": exit_emotion if exit_emotion != "(tidak diisi)" else None,
                        "notes":       exit_notes.strip() or None,
                    }
                    try:
                        if close_type == "Close All":
                            result = manager.close_trade(trade_id, exit_payload)
                        else:
                            result = manager.partial_close(trade_id, exit_payload)

                        pnl_val = result.get("pnl_rupiah", 0) or 0
                        pnl_pct = result.get("pnl_percent", 0) or 0
                        icon    = "🟢" if pnl_val >= 0 else "🔴"
                        st.success(
                            f"{icon} Trade berhasil ditutup!\n\n"
                            f"**P&L:** Rp {pnl_val:+,.0f} ({pnl_pct:+.2f}%) | "
                            f"**Status:** {result.get('status','closed')}"
                        )
                        _reload()
                    except Exception as e:
                        st.error(f"❌ Gagal: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 6: EDIT / DELETE
    # ══════════════════════════════════════════════════════════════════════════
    with tab_edit:
        st.markdown("### ✏️ Edit atau Hapus Trade")

        if not all_trades:
            st.info("Tidak ada trade.")
        else:
            # Build label → trade mapping
            trade_labels = {}
            for t in all_trades:
                tid = t.get("id")
                if not tid:
                    continue
                label = (
                    f"[{t.get('status','?').upper()}] "
                    f"{t.get('symbol','')} — "
                    f"{(t.get('entry_date') or datetime.now()).strftime('%d %b %Y') if isinstance(t.get('entry_date'), datetime) else str(t.get('entry_date','?'))[:10]} — "
                    f"Rp {t.get('entry_price',0):,.0f}"
                )
                trade_labels[label] = t

            selected_label = st.selectbox("Pilih Trade", list(trade_labels.keys()), key="edit_sel")
            t = trade_labels[selected_label]
            trade_id = t.get("id")

            st.divider()

            # Edit form
            with st.form("form_edit_trade"):
                st.markdown("#### Ubah Data Trade")
                ed1, ed2 = st.columns(2)

                new_strategy = ed1.selectbox(
                    "Strategi",
                    _STRATEGIES,
                    index=_STRATEGIES.index(t.get("strategy")) if t.get("strategy") in _STRATEGIES else 0,
                )
                cur_emotion = t.get("emotion_tag") or "(tidak diisi)"
                emo_opts    = ["(tidak diisi)"] + _EMOTIONS
                new_emotion = ed2.selectbox(
                    "Emosi Entry",
                    emo_opts,
                    index=emo_opts.index(cur_emotion) if cur_emotion in emo_opts else 0,
                )

                new_sl = st.number_input(
                    "Stop Loss (Rp, 0 = hapus)",
                    min_value=0.0, step=10.0, format="%.0f",
                    value=float(t.get("sl_price") or 0),
                )
                new_tp = st.number_input(
                    "Take Profit (Rp, 0 = hapus)",
                    min_value=0.0, step=10.0, format="%.0f",
                    value=float(t.get("tp_price") or 0),
                )
                new_notes = st.text_area("Catatan", value=t.get("notes") or "")

                save_btn = st.form_submit_button("💾 Simpan Perubahan", type="primary", use_container_width=True)

            if save_btn:
                updates = {
                    "strategy":    new_strategy,
                    "emotion_tag": new_emotion if new_emotion != "(tidak diisi)" else None,
                    "sl_price":    float(new_sl) if new_sl > 0 else None,
                    "tp_price":    float(new_tp) if new_tp > 0 else None,
                    "notes":       new_notes.strip() or None,
                }
                try:
                    repo.update_trade_fields(trade_id, updates)
                    st.success("✅ Trade berhasil diperbarui.")
                    _reload()
                except Exception as e:
                    st.error(f"❌ Gagal: {e}")

            # Delete with confirmation
            st.divider()
            st.markdown("#### 🗑️ Hapus Trade")
            st.warning(
                f"Hapus trade **{t.get('symbol')} ({t.get('status')})** secara permanen?"
            )
            with st.popover("🗑️ Hapus Permanen"):
                st.error("Tindakan ini tidak bisa dibatalkan!")
                if st.button("✅ Ya, hapus", key="confirm_del_trade", type="primary"):
                    try:
                        from bson.objectid import ObjectId
                        repo.collection.delete_one({"_id": ObjectId(trade_id)})
                        st.success("🗑️ Trade dihapus.")
                        _reload()
                    except Exception as e:
                        st.error(f"❌ Gagal: {e}")
