import streamlit as st
from datetime import datetime
import pandas as pd
from loguru import logger

from db.connection import get_database
from db.repositories.trade_repo import TradeRepository
from db.repositories.portfolio_repo import PortfolioRepository

from dashboard.pages import overview, breakdowns, psychology, backtest

# Page Config
st.set_page_config(
    page_title="CakTykBot Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #333;
        text-align: center;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #00ADB5;
    }
    .metric-label {
        font-size: 14px;
        color: #AAAAAA;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_db():
    try:
        db = get_database()
        return db
    except Exception as e:
        logger.error(f"DB Connection failed: {e}")
        return None

def main():
    db = init_db()
    
    if db is None:
        st.error("Database connection failed for CakTykBot.")
        return

    trade_repo = TradeRepository(db)
    portfolio_repo = PortfolioRepository(db)
    
    # Fetch Data
    trades = trade_repo.get_all_closed_trades()
    # Convert Pydantic models to dicts for pandas
    trade_dicts = [t.model_dump() for t in trades]
    
    # Portfolio Config
    config = portfolio_repo.get_config("nesa") # Default user
    initial_capital = config.total_capital if config else 100_000_000
    
    # Sidebar
    st.sidebar.title("CakTykBot 🤖")
    page = st.sidebar.radio("Navigation", ["Overview", "Breakdowns", "Psychology", "Backtest"])
    
    st.sidebar.divider()
    st.sidebar.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Page Routing
    if page == "Overview":
        overview.render(trade_dicts, initial_capital)
    elif page == "Breakdowns":
        breakdowns.render(trade_dicts)
    elif page == "Psychology":
        psychology.render(trade_dicts)
    elif page == "Backtest":
        backtest.render(db)

if __name__ == "__main__":
    main()
