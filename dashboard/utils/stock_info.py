"""Dashboard utility — fetch stock info and price levels from yfinance.

All functions are synchronous (yfinance is sync) and cached via
st.cache_data so repeated calls within a Streamlit session are free.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from loguru import logger


# ── sector mapping: yfinance -> our internal sector labels ───────────────────

_SECTOR_MAP: dict[str, str] = {
    "Financial Services": "Finance",
    "Finance": "Finance",
    "Banking": "Banking",
    "Consumer Defensive": "Consumer Goods",
    "Consumer Cyclical": "Consumer Cyclical",
    "Industrials": "Industrials",
    "Energy": "Energy",
    "Healthcare": "Healthcare",
    "Technology": "Technology",
    "Communication Services": "Telco",
    "Real Estate": "Property",
    "Basic Materials": "Mining",
    "Utilities": "Infrastructure",
}

_MARKET_CAP_THRESHOLDS = {
    "large":  10_000_000_000_000,  # ≥ 10 T IDR → large cap
    "mid":     1_000_000_000_000,  # ≥  1 T IDR → mid cap
}                                  # else        → small cap


# ── public helpers ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_meta(symbol: str) -> dict:
    """Look up company name, sector, and market cap via yfinance.

    Args:
        symbol: Normalised ticker, e.g. "BBCA.JK"

    Returns:
        dict with keys: name, sector, market_cap ("large"|"mid"|"small"),
        found (bool)
    """
    result = {"name": None, "sector": None, "market_cap": "small", "found": False}
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.info or {}

        # Name
        name = info.get("longName") or info.get("shortName") or ""
        result["name"] = name.strip() if name else None

        # Sector
        raw_sector = info.get("sector") or info.get("industry") or ""
        result["sector"] = _SECTOR_MAP.get(raw_sector, "Other") if raw_sector else None

        # Market cap (yfinance returns USD for .JK stocks converted by YF)
        mc_usd = info.get("marketCap") or 0
        # Yahoo Finance returns mc in USD; approximate IDR ≈ 15 900
        mc_idr = mc_usd * 15_900
        if mc_idr >= _MARKET_CAP_THRESHOLDS["large"]:
            result["market_cap"] = "large"
        elif mc_idr >= _MARKET_CAP_THRESHOLDS["mid"]:
            result["market_cap"] = "mid"
        else:
            result["market_cap"] = "small"

        result["found"] = bool(result["name"])

    except Exception as exc:
        logger.warning(f"yfinance meta lookup failed for {symbol}: {exc}")

    return result


@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """Fetch latest price for a single ticker.

    Returns:
        dict: price (float|None), change_pct (float|None), volume (int|None)
    """
    out = {"price": None, "change_pct": None, "volume": None}
    try:
        ticker  = yf.Ticker(symbol)
        fast    = ticker.fast_info
        price   = getattr(fast, "last_price", None)
        prev    = getattr(fast, "previous_close", None)
        volume  = getattr(fast, "three_month_average_volume", None)

        out["price"]  = float(price) if price else None
        out["volume"] = int(volume)  if volume else None
        if price and prev:
            out["change_pct"] = (price - prev) / prev * 100
    except Exception as exc:
        logger.debug(f"live quote failed for {symbol}: {exc}")
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_support_resistance(symbol: str, period: str = "6mo") -> dict:
    """Calculate key support and resistance levels from recent price history.

    Method:
      - Pivot points (Classic): P, R1, R2, S1, S2
      - Swing highs / lows over last 20 sessions (local extrema method)
      - Buy range  = [S1, S2 midpoint]  → nearest support + buffer
      - Sell target = R1 (nearest resistance)

    Returns:
        dict: support (float|None), resistance (float|None),
              buy_low (float|None), buy_high (float|None),
              sell_target (float|None), current_price (float|None)
    """
    out: dict = {
        "support": None, "resistance": None,
        "buy_low": None, "buy_high": None,
        "sell_target": None, "current_price": None,
    }
    try:
        df = yf.download(symbol, period=period, progress=False, threads=False)
        if df.empty or len(df) < 20:
            return out

        # Flatten MultiIndex if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        # ── Classic pivot from last complete session ───────────────────────────
        last = df.iloc[-2]  # previous closed session
        H, L, C = float(last["High"]), float(last["Low"]), float(last["Close"])
        P  = (H + L + C) / 3
        R1 = 2 * P - L
        R2 = P + (H - L)
        S1 = 2 * P - H
        S2 = P - (H - L)

        cur_price = float(df["Close"].iloc[-1])
        out["current_price"] = cur_price

        # ── Swing lows / highs (last 60 bars, window = 5) ────────────────────
        window = 5
        close  = df["Close"].values
        low_s  = df["Low"].values
        high_s = df["High"].values

        swing_lows  = []
        swing_highs = []
        for i in range(window, len(df) - window):
            if low_s[i]  == min(low_s[i-window:i+window+1]):
                swing_lows.append(low_s[i])
            if high_s[i] == max(high_s[i-window:i+window+1]):
                swing_highs.append(high_s[i])

        # closest support below current price
        supports_below = [v for v in ([S1, S2] + swing_lows) if v < cur_price]
        resist_above   = [v for v in ([R1, R2] + swing_highs) if v > cur_price]

        support    = max(supports_below) if supports_below else S1
        resistance = min(resist_above)   if resist_above   else R1

        out["support"]     = round(support, 0)
        out["resistance"]  = round(resistance, 0)

        # Buy range: 0–3 % above support
        out["buy_low"]     = round(support, 0)
        out["buy_high"]    = round(support * 1.03, 0)

        # Sell target: nearest resistance
        out["sell_target"] = round(resistance, 0)

    except Exception as exc:
        logger.warning(f"support/resistance calc failed for {symbol}: {exc}")

    return out


def batch_live_prices(symbols: list[str]) -> dict[str, dict]:
    """Fetch live prices for multiple symbols efficiently using yf.download."""
    if not symbols:
        return {}
    try:
        if len(symbols) == 1:
            data = yf.download(symbols[0], period="2d", progress=False, threads=False)
            if data.empty:
                return {symbols[0]: {"price": None, "change_pct": None}}
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)
            price = float(data["Close"].iloc[-1])
            prev  = float(data["Close"].iloc[-2]) if len(data) > 1 else price
            pct   = (price - prev) / prev * 100
            return {symbols[0]: {"price": price, "change_pct": pct}}

        data = yf.download(symbols, period="2d", progress=False, threads=False)
        if data.empty:
            return {s: {"price": None, "change_pct": None} for s in symbols}

        closes = data["Close"] if "Close" in data.columns else data.xs("Close", axis=1, level=0)
        result = {}
        for sym in symbols:
            try:
                prices = closes[sym].dropna()
                price  = float(prices.iloc[-1])
                prev   = float(prices.iloc[-2]) if len(prices) > 1 else price
                result[sym] = {
                    "price":      price,
                    "change_pct": (price - prev) / prev * 100,
                }
            except Exception:
                result[sym] = {"price": None, "change_pct": None}
        return result

    except Exception as exc:
        logger.warning(f"batch_live_prices failed: {exc}")
        return {s: {"price": None, "change_pct": None} for s in symbols}
