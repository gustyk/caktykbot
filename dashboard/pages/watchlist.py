"""Watchlist management page for Streamlit dashboard."""
from __future__ import annotations

import re
import pandas as pd
import streamlit as st
from datetime import datetime, timezone

from db.repositories.stock_repo import StockRepository
from db.schemas import StockCreate, StockUpdate, MarketCapCategory
from utils.exceptions import (
    DuplicateStockError,
    WatchlistFullError,
    StockNotFoundError,
)
from dashboard.components.stock_info import (
    fetch_stock_meta,
    fetch_support_resistance,
    batch_live_prices,
)


# ── constants ─────────────────────────────────────────────────────────────────

_SECTORS = [
    "Finance", "Banking", "Consumer Goods", "Consumer Cyclical",
    "Industrials", "Energy", "Healthcare", "Technology",
    "Telco", "Property", "Mining", "Plantation", "Infrastructure", "Other",
]

_MARKET_CAP_LABELS = {
    MarketCapCategory.LARGE: "🔵 Large Cap",
    MarketCapCategory.MID:   "🟡 Mid Cap",
    MarketCapCategory.SMALL: "🔴 Small Cap",
}

_MC_FROM_STR = {"large": MarketCapCategory.LARGE, "mid": MarketCapCategory.MID, "small": MarketCapCategory.SMALL}

_STATUS_ICON = {True: "✅", False: "⛔"}


def _normalise(raw: str) -> str:
    raw = raw.strip().upper()
    return raw if raw.endswith(".JK") else raw + ".JK"


def _valid_symbol(sym: str) -> bool:
    return bool(re.match(r"^[A-Z0-9-]+\.JK$", sym))


def _fmt_price(v) -> str:
    if v is None:
        return "-"
    try:
        return f"Rp {float(v):,.0f}"
    except Exception:
        return "-"


def _fmt_pct(v) -> str:
    if v is None:
        return "-"
    try:
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%"
    except Exception:
        return "-"


# ── page render ───────────────────────────────────────────────────────────────

def render(db):
    """Render the Watchlist CRUD page."""
    repo = StockRepository(db, max_watchlist=100)

    st.title("📋 Watchlist Manager")
    st.caption("Kelola daftar saham pantauan. Perubahan langsung berlaku untuk bot Telegram.")

    def _reload():
        st.cache_data.clear()
        st.rerun()

    # ── fetch stocks ──────────────────────────────────────────────────────────
    all_stocks = repo.get_all_stocks(only_active=False)
    active     = [s for s in all_stocks if s.is_active]
    inactive   = [s for s in all_stocks if not s.is_active]

    # ── summary metrics ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Total Saham", len(all_stocks))
    c2.metric("✅ Aktif",        len(active))
    c3.metric("⛔ Non-aktif",    len(inactive))
    c4.metric("🆓 Slot tersisa", max(0, 100 - len(all_stocks)))

    st.divider()

    tab_list, tab_add, tab_edit = st.tabs(
        ["📋 Daftar Watchlist", "➕ Tambah Saham", "✏️ Edit / Hapus"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 – LIST (dengan harga, range beli, target jual, tombol analyze)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_list:
        if not all_stocks:
            st.info("Watchlist kosong. Gunakan tab **➕ Tambah Saham** untuk mulai.")
        else:
            # ── Filters ──────────────────────────────────────────────────────
            f1, f2, f3 = st.columns(3)
            search   = f1.text_input("🔍 Cari ticker / nama", "").lower()
            fil_stat = f2.selectbox("Status", ["Semua", "Aktif", "Non-aktif"], key="fil_stat")
            fil_mc   = f3.selectbox("Market Cap", ["Semua", "Large Cap", "Mid Cap", "Small Cap"], key="fil_mc")

            filtered = all_stocks
            if search:
                filtered = [s for s in filtered if search in s.symbol.lower() or search in (s.name or "").lower()]
            if fil_stat == "Aktif":
                filtered = [s for s in filtered if s.is_active]
            elif fil_stat == "Non-aktif":
                filtered = [s for s in filtered if not s.is_active]
            if fil_mc != "Semua":
                mc_map = {"Large Cap": "large", "Mid Cap": "mid", "Small Cap": "small"}
                filtered = [s for s in filtered if s.market_cap.value == mc_map[fil_mc]]

            st.caption(f"Menampilkan {len(filtered)} dari {len(all_stocks)} saham")

            # ── Live prices for filtered symbols (batch, cached) ─────────────
            symbols = [s.symbol for s in filtered]
            # Pass as tuple so st.cache_data can hash it
            with st.spinner("🔄 Mengambil harga live…"):
                prices = batch_live_prices(tuple(symbols)) if symbols else {}

            # ── Main watchlist table ──────────────────────────────────────────
            rows = []
            for s in filtered:
                q = prices.get(s.symbol, {})
                price_val  = q.get("price")
                change_val = q.get("change_pct")
                rows.append({
                    "Status":     _STATUS_ICON[s.is_active],
                    "Ticker":     s.symbol,
                    "Nama":       s.name or "-",
                    "Sektor":     s.sector or "-",
                    "Market Cap": _MARKET_CAP_LABELS.get(s.market_cap, "-"),
                    "Harga":      _fmt_price(price_val),
                    "Chg %":     _fmt_pct(change_val),
                })

            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Status":     st.column_config.TextColumn(width="small"),
                        "Ticker":     st.column_config.TextColumn(width="small"),
                        "Harga":      st.column_config.TextColumn(width="medium"),
                        "Chg %":     st.column_config.TextColumn(width="small"),
                    },
                )

            st.divider()

            # ── Per-Ticker Detail Panel ───────────────────────────────────────
            st.markdown("#### 🔍 Detail Ticker — Harga, Support & Resistance")
            st.caption("Pilih ticker untuk melihat harga saat ini, range beli (support), dan target jual (resistance).")

            sym_sel = st.selectbox(
                "Pilih Ticker", ["— pilih —"] + symbols,
                key="detail_sym"
            )

            if sym_sel and sym_sel != "— pilih —":
                stock_obj = next((s for s in filtered if s.symbol == sym_sel), None)

                col_info, col_levels = st.columns([2, 3])

                with col_info:
                    # Live quote
                    q    = prices.get(sym_sel, {})
                    pr   = q.get("price")
                    chg  = q.get("change_pct")
                    icon = "🟢" if (chg or 0) >= 0 else "🔴"

                    st.markdown(f"**{sym_sel}** — {stock_obj.name if stock_obj else ''}")
                    if pr:
                        st.metric(
                            "Harga Terakhir",
                            f"Rp {pr:,.0f}",
                            delta=f"{chg:+.2f}%" if chg is not None else None,
                        )
                    else:
                        st.metric("Harga Terakhir", "N/A")

                    if stock_obj:
                        st.caption(
                            f"📊 {_MARKET_CAP_LABELS.get(stock_obj.market_cap, '-')} | "
                            f"🏭 {stock_obj.sector or '-'}"
                        )

                with col_levels:
                    with st.spinner(f"Menghitung support & resistance untuk {sym_sel}…"):
                        lvl = fetch_support_resistance(sym_sel)

                    if lvl.get("support") is not None:
                        l1, l2, l3 = st.columns(3)
                        l1.metric(
                            "📗 Range Beli",
                            f"Rp {lvl['buy_low']:,.0f}",
                            f"s/d Rp {lvl['buy_high']:,.0f}",
                        )
                        l2.metric(
                            "📗 Support",
                            f"Rp {lvl['support']:,.0f}",
                        )
                        l3.metric(
                            "📕 Target Jual",
                            f"Rp {lvl['sell_target']:,.0f}",
                        )

                        # R/R preview
                        if lvl.get("buy_high") and lvl.get("sell_target") and lvl.get("buy_low"):
                            avg_buy = (lvl["buy_low"] + lvl["buy_high"]) / 2
                            risk    = avg_buy - lvl["support"]
                            reward  = lvl["sell_target"] - avg_buy
                            if risk > 0:
                                rr = reward / risk
                                colour = "#2ecc71" if rr >= 2 else "#f39c12" if rr >= 1 else "#e74c3c"
                                st.markdown(
                                    f"<span style='color:{colour};font-size:1.1em;font-weight:700;'>"
                                    f"⚡ R/R = 1 : {rr:.2f}</span>",
                                    unsafe_allow_html=True,
                                )

                        # Method details (collapsible)
                        if lvl.get("method_details"):
                            with st.expander("📐 Detail perhitungan S/R"):
                                for d in lvl["method_details"]:
                                    st.caption(d)
                    else:
                        st.warning(
                            "⚠️ Support/resistance tidak bisa dihitung.  \n"
                            "Pastikan ticker valid dan coba lagi — Yahoo Finance "
                            "mungkin sedang lambat."
                        )

                # ── Analyze button ────────────────────────────────────────────
                st.divider()
                ac1, ac2, ac3 = st.columns([2, 2, 3])
                if ac1.button(f"🔬 Analisis {sym_sel}", key="btn_analyze", type="primary"):
                    with st.spinner(f"Menjalankan analisis sinyal untuk {sym_sel}…"):
                        try:
                            from data.fetcher import YFinanceFetcher
                            from logic.indicators import IndicatorEngine
                            from strategies.vcp import VCPStrategy
                            from strategies.ema_pullback import EMAPullbackStrategy
                            from engine.signal_generator import SignalGenerator

                            fetcher = YFinanceFetcher()
                            df_raw  = fetcher.fetch_history(sym_sel, period="2y")
                            df      = IndicatorEngine.calculate_all(df_raw)

                            vcp = VCPStrategy()
                            ema = EMAPullbackStrategy()
                            vcp_sig = vcp.analyze(sym_sel, df)
                            ema_sig = ema.analyze(sym_sel, df)

                            engine     = SignalGenerator(db=db)
                            final_sig  = engine.generate(sym_sel, [vcp_sig, ema_sig])

                            verdict_colour = {
                                "BUY": "#2ecc71", "SELL": "#e74c3c",
                                "HOLD": "#f39c12", "WAIT": "#3498db",
                            }.get(final_sig.verdict, "#aaa")

                            st.markdown(
                                f"<div style='background:#1a1a2e;border:1px solid #252545;"
                                f"border-radius:10px;padding:16px 20px;'>"
                                f"<h4 style='margin:0 0 8px 0;color:#00ADB5'>{sym_sel} — Hasil Analisis</h4>"
                                f"<span style='font-size:1.4em;font-weight:800;color:{verdict_colour}'>"
                                f"{final_sig.verdict}</span> &nbsp;"
                                f"<span style='color:#aaa;font-size:0.9em'>({final_sig.confidence} confidence | "
                                f"Skor: {final_sig.tech_score:.0f})</span><br><br>"
                                f"<b>Entry:</b> Rp {final_sig.entry_price:,.0f} &nbsp;|&nbsp;"
                                f"<b>SL:</b> Rp {final_sig.sl_price:,.0f} &nbsp;|&nbsp;"
                                f"<b>TP:</b> Rp {final_sig.tp_price:,.0f} &nbsp;|&nbsp;"
                                f"<b>R/R:</b> 1:{final_sig.rr_ratio:.2f}<br><br>"
                                f"<span style='color:#ccc;font-size:0.88em'>{final_sig.reasoning}</span>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                            if final_sig.risk_blocked:
                                st.warning(f"⚠️ Sinyal diblokir risk: {final_sig.block_reason}")
                            elif final_sig.risk_warnings:
                                for w in final_sig.risk_warnings:
                                    st.warning(f"⚠️ {w}")

                        except Exception as e:
                            st.error(f"❌ Analisis gagal: {e}")

                if ac2.button(f"📊 Chart {sym_sel}", key="btn_chart"):
                    url = f"https://finance.yahoo.com/chart/{sym_sel}"
                    st.markdown(f"[🔗 Buka chart di Yahoo Finance]({url})", unsafe_allow_html=False)

            st.divider()

            # ── Quick action per ticker (toggle active) ───────────────────────
            st.markdown("#### ⚡ Aksi Cepat — Aktifkan / Nonaktifkan / Hapus")
            qa_sym = st.selectbox("Pilih Ticker", ["— pilih —"] + symbols, key="quick_sym")

            if qa_sym and qa_sym != "— pilih —":
                stock = next((s for s in filtered if s.symbol == qa_sym), None)
                if stock:
                    qa1, qa2 = st.columns(2)
                    if stock.is_active:
                        if qa1.button(f"⛔ Nonaktifkan {qa_sym}", key="deact"):
                            repo.update_stock(qa_sym, StockUpdate(is_active=False))
                            st.success(f"⛔ {qa_sym} dinonaktifkan.")
                            _reload()
                    else:
                        if qa1.button(f"✅ Aktifkan {qa_sym}", key="act"):
                            repo.update_stock(qa_sym, StockUpdate(is_active=True))
                            st.success(f"✅ {qa_sym} diaktifkan kembali.")
                            _reload()

                    confirm_del = qa2.checkbox(f"⚠️ Hapus {qa_sym} permanen?", key="chk_del_stock")
                    if confirm_del:
                        if st.button("🗑️ Ya, hapus permanen", key="confirm_del", type="primary"):
                            deleted = repo.delete_stock(qa_sym)
                            if deleted:
                                st.success(f"🗑️ {qa_sym} dihapus.")
                                _reload()
                            else:
                                st.error("Gagal menghapus.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 – ADD (ticker only — auto-lookup nama/sektor/market cap)
    # ══════════════════════════════════════════════════════════════════════════
    with tab_add:
        st.markdown("### ➕ Tambah Saham ke Watchlist")
        st.caption("Cukup masukkan kode ticker — nama, sektor, dan market cap akan otomatis diambil dari Yahoo Finance.")

        # ── Single add ────────────────────────────────────────────────────────
        with st.form("form_add_stock", clear_on_submit=True):
            raw_symbol = st.text_input(
                "Kode Ticker *",
                placeholder="BBCA  atau  BBCA.JK  (suffix .JK otomatis)",
                help="Masukkan kode ticker IDX, contoh: BBCA, BMRI, TLKM",
            )
            submitted = st.form_submit_button("🔍 Cari & Tambahkan", type="primary", use_container_width=True)

        if submitted and raw_symbol.strip():
            symbol = _normalise(raw_symbol)
            if not _valid_symbol(symbol):
                st.error(f"Format ticker tidak valid: `{symbol}`. Contoh: BBCA atau BBCA.JK")
            else:
                with st.spinner(f"Mencari info {symbol} di Yahoo Finance…"):
                    meta = fetch_stock_meta(symbol)

                # Preview card
                col_prev, col_btn = st.columns([3, 1])
                with col_prev:
                    if meta["found"]:
                        mc_label = _MARKET_CAP_LABELS.get(_MC_FROM_STR.get(meta["market_cap"], MarketCapCategory.SMALL), "🔴 Small Cap")
                        st.success(
                            f"**Ditemukan:**  \n"
                            f"🏢 **Nama:** {meta['name'] or '(tidak tersedia)'}  \n"
                            f"🏭 **Sektor:** {meta['sector'] or 'Other'}  \n"
                            f"📊 **Market Cap:** {mc_label}"
                        )
                    else:
                        st.warning(
                            f"⚠️ Info {symbol} tidak ditemukan di Yahoo Finance.  \n"
                            "Saham akan ditambahkan dengan nama = kode ticker dan sektor = Other."
                        )

                # Allow manual override
                with st.expander("✏️ Ubah sebelum menyimpan (opsional)"):
                    ov_name   = st.text_input("Nama Perusahaan", value=meta.get("name") or symbol.split(".")[0])
                    ov_sector = st.selectbox(
                        "Sektor", _SECTORS,
                        index=_SECTORS.index(meta["sector"]) if meta.get("sector") in _SECTORS else _SECTORS.index("Other"),
                    )
                    mc_keys   = list(_MARKET_CAP_LABELS.values())
                    mc_def    = _MARKET_CAP_LABELS.get(_MC_FROM_STR.get(meta.get("market_cap", "small"), MarketCapCategory.SMALL), mc_keys[2])
                    ov_mc     = st.selectbox("Market Cap", mc_keys, index=mc_keys.index(mc_def))

                if st.button("✅ Simpan ke Watchlist", key="btn_save_single", type="primary"):
                    mc_reverse = {v: k for k, v in _MARKET_CAP_LABELS.items()}
                    try:
                        repo.add_stock(StockCreate(
                            symbol=symbol,
                            name=ov_name.strip() or symbol.split(".")[0],
                            sector=ov_sector,
                            market_cap=mc_reverse[ov_mc],
                        ))
                        st.success(f"✅ **{symbol}** — {ov_name} berhasil ditambahkan!")
                        _reload()
                    except DuplicateStockError:
                        st.warning(f"⚠️ {symbol} sudah ada di watchlist.")
                    except WatchlistFullError:
                        st.error("❌ Watchlist penuh (maks 100 saham).")
                    except Exception as e:
                        st.error(f"❌ Gagal: {e}")

        # ── Bulk add ──────────────────────────────────────────────────────────
        st.divider()
        st.markdown("#### 📥 Bulk Add (multi-ticker, tanpa nama)")
        st.caption(
            "Masukkan beberapa kode ticker sekaligus — nama dan sektor akan di-lookup otomatis.\n"
            "Proses sedikit lebih lama karena memanggil Yahoo Finance per ticker."
        )

        with st.form("form_bulk_add", clear_on_submit=True):
            bulk_input = st.text_area(
                "Ticker (satu per baris atau pisah koma)",
                placeholder="BBCA\nBMRI\nTLKM.JK, ASII",
                height=120,
            )
            bulk_submit = st.form_submit_button("➕ Tambah Semua", use_container_width=True)

        if bulk_submit and bulk_input.strip():
            raw_list = re.split(r"[,\n\r]+", bulk_input)
            syms     = [_normalise(r) for r in raw_list if r.strip()]
            valid    = [s for s in syms if _valid_symbol(s)]
            invalid  = [s for s in syms if not _valid_symbol(s)]

            if invalid:
                st.warning(f"Ticker tidak valid (dilewati): {', '.join(invalid)}")

            ok_count = 0
            err_count = 0
            prog = st.progress(0, text="Menambahkan…")

            for idx, sym in enumerate(valid):
                prog.progress((idx + 1) / len(valid), text=f"Memproses {sym}…")
                meta = fetch_stock_meta(sym)
                try:
                    repo.add_stock(StockCreate(
                        symbol=sym,
                        name=meta.get("name") or sym.split(".")[0],
                        sector=meta.get("sector") or "Other",
                        market_cap=_MC_FROM_STR.get(meta.get("market_cap", "small"), MarketCapCategory.SMALL),
                    ))
                    ok_count += 1
                except DuplicateStockError:
                    pass
                except Exception:
                    err_count += 1

            prog.empty()
            if ok_count:
                st.success(f"✅ {ok_count} saham berhasil ditambahkan.")
                _reload()
            if err_count:
                st.error(f"❌ {err_count} saham gagal ditambahkan.")
            if not ok_count and not err_count:
                st.info("Semua ticker sudah ada di watchlist (duplicates dilewati).")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 – EDIT
    # ══════════════════════════════════════════════════════════════════════════
    with tab_edit:
        st.markdown("### ✏️ Edit Data Saham")

        if not all_stocks:
            st.info("Watchlist kosong.")
        else:
            edit_sym = st.selectbox(
                "Pilih ticker yang ingin diedit",
                [s.symbol for s in all_stocks],
                key="edit_sym",
            )
            stock = next((s for s in all_stocks if s.symbol == edit_sym), None)

            if stock:
                st.caption(f"Terakhir diubah: {stock.updated_at.strftime('%d %b %Y %H:%M')}")

                with st.form("form_edit_stock"):
                    e1, e2 = st.columns(2)
                    new_name = e1.text_input("Nama Perusahaan", value=stock.name or "")

                    sector_idx = _SECTORS.index(stock.sector) if stock.sector in _SECTORS else len(_SECTORS) - 1
                    new_sector = e2.selectbox("Sektor", _SECTORS, index=sector_idx)

                    mc_labels        = list(_MARKET_CAP_LABELS.values())
                    current_mc_label = _MARKET_CAP_LABELS.get(stock.market_cap, mc_labels[2])
                    mc_idx           = mc_labels.index(current_mc_label) if current_mc_label in mc_labels else 2
                    new_mc_label     = st.selectbox("Market Cap", mc_labels, index=mc_idx)

                    new_active = st.toggle("Aktif", value=stock.is_active)

                    saved = st.form_submit_button("💾 Simpan Perubahan", type="primary", use_container_width=True)

                if saved:
                    mc_reverse  = {v: k for k, v in _MARKET_CAP_LABELS.items()}
                    update_data = StockUpdate(
                        name=new_name.strip() or None,
                        sector=new_sector,
                        market_cap=mc_reverse[new_mc_label],
                        is_active=new_active,
                    )
                    try:
                        repo.update_stock(edit_sym, update_data)
                        st.success(f"✅ Data **{edit_sym}** berhasil diperbarui.")
                        _reload()
                    except StockNotFoundError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"❌ Gagal: {e}")

                # Re-lookup from Yahoo Finance
                st.divider()
                if st.button("🔄 Refresh info dari Yahoo Finance", key="btn_refresh_meta"):
                    with st.spinner(f"Mengambil info terbaru untuk {edit_sym}…"):
                        st.cache_data.clear()  # clear cached meta
                        meta = fetch_stock_meta(edit_sym)
                    if meta["found"]:
                        st.info(
                            f"**Yahoo Finance info:**  \n"
                            f"Nama: {meta['name']}  |  "
                            f"Sektor: {meta['sector']}  |  "
                            f"Market Cap: {meta['market_cap']}"
                        )
                        if st.button("💾 Terapkan info ini", key="btn_apply_meta"):
                            update_data = StockUpdate(
                                name=meta["name"],
                                sector=meta["sector"],
                                market_cap=_MC_FROM_STR.get(meta["market_cap"], MarketCapCategory.SMALL),
                            )
                            repo.update_stock(edit_sym, update_data)
                            st.success("✅ Info diperbarui.")
                            _reload()
                    else:
                        st.warning("Info tidak ditemukan di Yahoo Finance.")
