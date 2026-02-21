import streamlit as st
from datetime import datetime
from loguru import logger

from db.connection import get_database
from db.repositories.trade_repo import TradeRepository
from db.repositories.portfolio_repo import PortfolioRepository

from dashboard.pages import overview, breakdowns, psychology, backtest, journal, watchlist

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CakTykBot Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "CakTykBot — IDX Trading Analytics Dashboard",
    }
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Hide auto-generated Streamlit pages/ nav ── */
    [data-testid="stSidebarNavItems"],
    [data-testid="stSidebarNav"],
    section[data-testid="stSidebarNav"] { display: none !important; }

    /* ── Hide default Streamlit footer & hamburger ── */
    #MainMenu, footer, header { visibility: hidden; }

    /* ── Sidebar branding ── */
    .sidebar-brand {
        text-align: center;
        padding: 0.5rem 0 1rem 0;
    }
    .sidebar-brand h1 {
        font-size: 1.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00ADB5, #00e5ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .sidebar-brand p {
        font-size: 0.72rem;
        color: #888;
        margin: 2px 0 0 0;
        letter-spacing: 0.08em;
    }

    /* ── Nav badge ── */
    .nav-badge {
        display: inline-block;
        background: #00ADB5;
        color: #000;
        font-size: 0.65rem;
        font-weight: 700;
        padding: 1px 6px;
        border-radius: 10px;
        margin-left: 6px;
        vertical-align: middle;
    }

    /* ── General card feel ── */
    div[data-testid="metric-container"] {
        background: #1a1a2e;
        border: 1px solid #252545;
        border-radius: 10px;
        padding: 14px 18px;
    }
    div[data-testid="metric-container"] label {
        color: #aaa !important;
        font-size: 0.78rem !important;
    }

    /* ── Dataframe header ── */
    th { background-color: #1a1a2e !important; color: #00ADB5 !important; }

    /* ── Sidebar status dot ── */
    .status-ok  { color: #2ecc71; font-weight: 700; }
    .status-err { color: #e74c3c; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ── DB init ───────────────────────────────────────────────────────────────────
@st.cache_resource
def init_db():
    try:
        db = get_database()
        return db
    except Exception as e:
        logger.error(f"DB Connection failed: {e}")
        return None


# ── Sidebar build ─────────────────────────────────────────────────────────────
def _build_sidebar(open_count: int, db_ok: bool):
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-brand">
            <h1>📊 CakTykBot</h1>
            <p>IDX TRADING ANALYTICS</p>
        </div>
        """, unsafe_allow_html=True)

        page = st.radio(
            "Navigasi",
            [
                "🏠  Overview",
                "📒  Journal",
                "📋  Watchlist",
                "🧩  Breakdowns",
                "🧠  Psychology",
                "🧪  Backtest",
            ],
            label_visibility="collapsed",
        )

        st.divider()

        # Live status panel
        st.markdown("**Status**")
        col_a, col_b = st.columns(2)
        col_a.markdown(
            f"DB: <span class='{'status-ok' if db_ok else 'status-err'}'>{'● LIVE' if db_ok else '● GAGAL'}</span>",
            unsafe_allow_html=True,
        )
        col_b.markdown(
            f"Open: <span class='status-ok'>**{open_count}**</span>",
            unsafe_allow_html=True,
        )

        st.caption(f"🕐 {datetime.now().strftime('%d %b %Y  %H:%M')}")

    # Strip emoji/spacing prefix to get clean page name
    return page.split("  ", 1)[-1].strip()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    db = init_db()
    db_ok = db is not None

    if not db_ok:
        st.error("❌ Koneksi database gagal. Periksa MONGO_URI di Railway.")
        return

    trade_repo     = TradeRepository(db)
    portfolio_repo = PortfolioRepository(db)

    # Fetch only what's needed for non-CRUD pages
    closed_trades   = trade_repo.get_all_closed_trades()
    trade_dicts     = [t.model_dump() for t in closed_trades]
    open_count      = len(trade_repo.get_open_trades())

    config          = portfolio_repo.get_config("nesa")
    initial_capital = config.total_capital if config else 100_000_000

    page = _build_sidebar(open_count, db_ok)

    # ── Routing ───────────────────────────────────────────────────────────────
    if page == "Overview":
        overview.render(trade_dicts, initial_capital)
    elif page == "Journal":
        journal.render(db)
    elif page == "Watchlist":
        watchlist.render(db)
    elif page == "Breakdowns":
        breakdowns.render(trade_dicts, db)
    elif page == "Psychology":
        psychology.render(trade_dicts)
    elif page == "Backtest":
        backtest.render(db)


if __name__ == "__main__":
    main()
