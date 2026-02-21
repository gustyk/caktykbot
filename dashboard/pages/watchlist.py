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


# ── helpers ──────────────────────────────────────────────────────────────────

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

_STATUS_ICON = {True: "✅", False: "⛔"}


def _normalise_symbol(raw: str) -> str:
    """Ensure symbol ends with .JK and is uppercase."""
    raw = raw.strip().upper()
    if not raw.endswith(".JK"):
        raw += ".JK"
    return raw


def _valid_symbol(sym: str) -> bool:
    return bool(re.match(r"^[A-Z0-9-]+\.JK$", sym))


# ── page render ───────────────────────────────────────────────────────────────

def render(db):
    """Render the Watchlist CRUD page.

    Args:
        db: MongoDB database instance
    """
    repo = StockRepository(db, max_watchlist=100)

    st.title("📋 Watchlist Manager")
    st.caption("Kelola daftar saham pantauan. Perubahan langsung berlaku untuk bot Telegram.")

    # ── refresh helper ────────────────────────────────────────────────────────
    def _reload():
        st.cache_data.clear()
        st.rerun()

    # ── fetch data ────────────────────────────────────────────────────────────
    all_stocks  = repo.get_all_stocks(only_active=False)
    active      = [s for s in all_stocks if s.is_active]
    inactive    = [s for s in all_stocks if not s.is_active]

    # ── summary bar ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Total Saham", len(all_stocks))
    c2.metric("✅ Aktif",        len(active))
    c3.metric("⛔ Non-aktif",    len(inactive))
    c4.metric("🆓 Slot tersisa", max(0, 100 - len(all_stocks)))

    st.divider()

    # ── tabs ──────────────────────────────────────────────────────────────────
    tab_list, tab_add, tab_edit = st.tabs(
        ["📋 Daftar Watchlist", "➕ Tambah Saham", "✏️ Edit / Hapus"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 – LIST
    # ══════════════════════════════════════════════════════════════════════════
    with tab_list:
        if not all_stocks:
            st.info("Watchlist kosong. Gunakan tab **➕ Tambah Saham** untuk mulai.")
        else:
            # Filters
            f1, f2, f3 = st.columns(3)
            search   = f1.text_input("🔍 Cari ticker / nama", "").lower()
            fil_stat = f2.selectbox("Status", ["Semua", "Aktif", "Non-aktif"], key="fil_stat")
            fil_mc   = f3.selectbox(
                "Market Cap",
                ["Semua", "Large Cap", "Mid Cap", "Small Cap"],
                key="fil_mc",
            )

            filtered = all_stocks
            if search:
                filtered = [
                    s for s in filtered
                    if search in s.symbol.lower() or search in (s.name or "").lower()
                ]
            if fil_stat == "Aktif":
                filtered = [s for s in filtered if s.is_active]
            elif fil_stat == "Non-aktif":
                filtered = [s for s in filtered if not s.is_active]
            if fil_mc != "Semua":
                mc_map = {"Large Cap": "large", "Mid Cap": "mid", "Small Cap": "small"}
                filtered = [s for s in filtered if s.market_cap.value == mc_map[fil_mc]]

            st.caption(f"Menampilkan {len(filtered)} dari {len(all_stocks)} saham")

            # Table
            rows = []
            for s in filtered:
                rows.append({
                    "Status":     _STATUS_ICON[s.is_active],
                    "Ticker":     s.symbol,
                    "Nama":       s.name,
                    "Sektor":     s.sector or "-",
                    "Market Cap": _MARKET_CAP_LABELS.get(s.market_cap, s.market_cap),
                    "Ditambahkan": s.added_at.strftime("%d %b %Y") if s.added_at else "-",
                })

            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Status": st.column_config.TextColumn(width="small"),
                        "Ticker": st.column_config.TextColumn(width="small"),
                    },
                )

            # Quick-action buttons per ticker (toggle active / delete)
            st.markdown("#### ⚡ Aksi Cepat")
            st.caption("Pilih saham untuk mengaktifkan/menonaktifkan atau menghapus.")

            symbols = [s.symbol for s in filtered]
            selected = st.selectbox("Pilih Ticker", ["— pilih —"] + symbols, key="quick_sym")

            if selected and selected != "— pilih —":
                stock = next((s for s in filtered if s.symbol == selected), None)
                if stock:
                    qa1, qa2, qa3 = st.columns(3)

                    # Toggle active
                    if stock.is_active:
                        if qa1.button(f"⛔ Nonaktifkan {selected}", key="deact"):
                            try:
                                repo.update_stock(selected, StockUpdate(is_active=False))
                                st.success(f"⛔ {selected} dinonaktifkan.")
                                _reload()
                            except StockNotFoundError as e:
                                st.error(str(e))
                    else:
                        if qa1.button(f"✅ Aktifkan {selected}", key="act"):
                            try:
                                repo.update_stock(selected, StockUpdate(is_active=True))
                                st.success(f"✅ {selected} diaktifkan kembali.")
                                _reload()
                            except StockNotFoundError as e:
                                st.error(str(e))

                    # Hard delete (with confirmation via checkbox)
                    with qa2:
                        confirm_del = st.checkbox(
                            f"⚠️ Hapus {selected} permanen?",
                            key="chk_del_stock",
                        )
                    if confirm_del:
                        if qa3.button("Ya, hapus", key="confirm_del", type="primary"):
                            deleted = repo.delete_stock(selected)
                            if deleted:
                                st.success(f"🗑️ {selected} dihapus.")
                                _reload()
                            else:
                                st.error("Gagal menghapus.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 – ADD
    # ══════════════════════════════════════════════════════════════════════════
    with tab_add:
        st.markdown("### ➕ Tambah Saham ke Watchlist")

        with st.form("form_add_stock", clear_on_submit=True):
            a1, a2 = st.columns(2)
            raw_symbol = a1.text_input(
                "Ticker *",
                placeholder="BBCA atau BBCA.JK",
                help="Format: BBCA.JK (suffix .JK otomatis ditambahkan)",
            )
            company_name = a2.text_input(
                "Nama Perusahaan *",
                placeholder="Bank Central Asia",
            )

            b1, b2 = st.columns(2)
            sector = b1.selectbox("Sektor", ["(pilih)"] + _SECTORS)
            market_cap_label = b2.selectbox(
                "Market Cap",
                list(_MARKET_CAP_LABELS.values()),
                index=0,
            )

            submitted = st.form_submit_button("➕ Tambahkan", type="primary", use_container_width=True)

        if submitted:
            # Validate
            errors = []
            symbol = _normalise_symbol(raw_symbol) if raw_symbol else ""
            if not symbol:
                errors.append("Ticker wajib diisi.")
            elif not _valid_symbol(symbol):
                errors.append(f"Format ticker tidak valid: `{symbol}` — gunakan huruf kapital, contoh `BBCA.JK`.")
            if not company_name.strip():
                errors.append("Nama perusahaan wajib diisi.")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                # Resolve market cap enum
                mc_reverse = {v: k for k, v in _MARKET_CAP_LABELS.items()}
                mc_enum = mc_reverse[market_cap_label]

                try:
                    stock_data = StockCreate(
                        symbol=symbol,
                        name=company_name.strip(),
                        sector=sector if sector != "(pilih)" else None,
                        market_cap=mc_enum,
                    )
                    repo.add_stock(stock_data)
                    st.success(f"✅ **{symbol}** berhasil ditambahkan ke watchlist!")
                    _reload()
                except DuplicateStockError:
                    st.warning(f"⚠️ {symbol} sudah ada di watchlist.")
                except WatchlistFullError:
                    st.error("❌ Watchlist penuh (maks 100 saham). Hapus beberapa saham dulu.")
                except Exception as e:
                    st.error(f"❌ Gagal: {e}")

        # Bulk add via text area
        st.divider()
        st.markdown("#### 📥 Bulk Add (multi-ticker)")
        st.caption("Masukkan beberapa ticker sekaligus, satu per baris atau dipisah koma.")

        with st.form("form_bulk_add", clear_on_submit=True):
            bulk_input = st.text_area(
                "Ticker (satu per baris atau pisah koma)",
                placeholder="BBCA\nBMRI\nTLKM.JK, ASII",
                height=120,
            )
            bulk_mc = st.selectbox("Market Cap (untuk semua)", list(_MARKET_CAP_LABELS.values()), key="bulk_mc")
            bulk_submit = st.form_submit_button("➕ Tambah Semua", use_container_width=True)

        if bulk_submit and bulk_input.strip():
            raw_list = re.split(r"[,\n\r]+", bulk_input)
            symbols = [_normalise_symbol(r) for r in raw_list if r.strip()]
            valid   = [s for s in symbols if _valid_symbol(s)]
            invalid = [s for s in symbols if not _valid_symbol(s)]

            if invalid:
                st.warning(f"Ticker tidak valid (dilewati): {', '.join(invalid)}")

            mc_reverse = {v: k for k, v in _MARKET_CAP_LABELS.items()}
            mc_enum = mc_reverse[bulk_mc]

            ok_count = err_msgs = 0
            for sym in valid:
                try:
                    repo.add_stock(StockCreate(
                        symbol=sym,
                        name=sym.split(".")[0],
                        market_cap=mc_enum,
                    ))
                    ok_count += 1
                except DuplicateStockError:
                    pass  # silently skip duplicates
                except Exception as e:
                    err_msgs += 1

            if ok_count:
                st.success(f"✅ {ok_count} saham berhasil ditambahkan.")
                _reload()
            if err_msgs:
                st.error(f"❌ {err_msgs} saham gagal ditambahkan.")

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
                    new_name = e1.text_input("Nama Perusahaan", value=stock.name)

                    sector_idx = _SECTORS.index(stock.sector) if stock.sector in _SECTORS else 0
                    new_sector = e2.selectbox("Sektor", _SECTORS, index=sector_idx)

                    mc_labels       = list(_MARKET_CAP_LABELS.values())
                    current_mc_label = _MARKET_CAP_LABELS.get(stock.market_cap, mc_labels[2])
                    mc_idx          = mc_labels.index(current_mc_label) if current_mc_label in mc_labels else 2
                    new_mc_label    = st.selectbox("Market Cap", mc_labels, index=mc_idx)

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
