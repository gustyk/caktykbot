"""Dashboard utility — fetch stock info and price levels from yfinance.

Design notes
------------
• Use yf.Ticker(sym).history()  →  always returns a flat, non-MultiIndex
  DataFrame regardless of yfinance version.  Reliable for .JK tickers.
• yf.download() is only used for batch (many tickers at once); each result
  is carefully flattened before use.
• All functions are cached via st.cache_data to avoid hammering Yahoo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from loguru import logger


# ── constants ─────────────────────────────────────────────────────────────────

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

_MC_THRESHOLDS = {
    "large": 10_000_000_000_000,   # ≥ 10 T IDR
    "mid":    1_000_000_000_000,   # ≥  1 T IDR
}  # else → small


# ── internal helpers ──────────────────────────────────────────────────────────

def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten yfinance MultiIndex columns to simple column names.

    yfinance ≥ 0.2.x returns (Price, Ticker) MultiIndex for single tickers
    when called via yf.download().  yf.Ticker.history() never does this.
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return df
    # Level 0 = price type (Open/High/Low/Close/Volume)
    # Level 1 = ticker symbol
    # Keep only level-0 labels
    df = df.copy()
    df.columns = df.columns.get_level_values(0)
    # Drop duplicate  column names that appear when only one ticker was fetched
    df = df.loc[:, ~df.columns.duplicated()]
    return df


def _ticker_history(symbol: str, period: str = "6mo") -> pd.DataFrame:
    """Fetch OHLCV via Ticker.history() — always flat, handles .JK reliably."""
    try:
        df = yf.Ticker(symbol).history(period=period)
        if df.empty:
            logger.warning(f"yfinance returned empty history for {symbol}")
        return df
    except Exception as exc:
        logger.warning(f"Ticker.history() failed for {symbol}: {exc}")
        return pd.DataFrame()


# ── public helpers ────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_meta(symbol: str) -> dict:
    """Look up company name, sector, and market cap via yfinance.

    Returns:
        dict: name, sector, market_cap ("large"|"mid"|"small"), found (bool)
    """
    result = {"name": None, "sector": None, "market_cap": "small", "found": False}
    try:
        info = yf.Ticker(symbol).info or {}

        name = info.get("longName") or info.get("shortName") or ""
        result["name"] = name.strip() or None

        raw_sector = info.get("sector") or info.get("industry") or ""
        result["sector"] = _SECTOR_MAP.get(raw_sector, "Other") if raw_sector else None

        # Yahoo Finance returns marketCap in local currency for .JK
        mc = info.get("marketCap") or 0
        # For IDX stocks Yahoo sometimes returns IDR directly, sometimes USD.
        # If mc looks like it's already in IDR (> 1 billion), use directly.
        # Otherwise assume USD and convert @ ~15 900.
        mc_idr = mc if mc > 1_000_000_000 else mc * 15_900

        if mc_idr >= _MC_THRESHOLDS["large"]:
            result["market_cap"] = "large"
        elif mc_idr >= _MC_THRESHOLDS["mid"]:
            result["market_cap"] = "mid"
        else:
            result["market_cap"] = "small"

        result["found"] = bool(result["name"])

    except Exception as exc:
        logger.warning(f"fetch_stock_meta failed for {symbol}: {exc}")

    return result


@st.cache_data(ttl=300, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """Fetch latest price for a single ticker via Ticker.history(5d).

    Returns:
        dict: price (float|None), change_pct (float|None), volume (int|None)
    """
    out = {"price": None, "change_pct": None, "volume": None}
    try:
        df = _ticker_history(symbol, period="5d")
        if df.empty or "Close" not in df.columns:
            return out

        closes = df["Close"].dropna()
        if len(closes) == 0:
            return out

        price = float(closes.iloc[-1])
        prev  = float(closes.iloc[-2]) if len(closes) >= 2 else price

        out["price"]      = price
        out["change_pct"] = (price - prev) / prev * 100 if prev else None
        if "Volume" in df.columns:
            out["volume"] = int(df["Volume"].iloc[-1])

    except Exception as exc:
        logger.warning(f"fetch_live_quote failed for {symbol}: {exc}")

    return out


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_support_resistance(symbol: str, period: str = "6mo") -> dict:
    """Calculate support & resistance levels from recent OHLCV history.

    Method:
      • Classic Pivot Points from the last complete session: P, R1, R2, S1, S2
      • Swing Highs / Lows (local extrema, window = 5 bars)
      • Support  = nearest swing low / pivot below current price
      • Resistance = nearest swing high / pivot above current price
      • Buy range  = support → support × 1.03
      • Sell target = resistance

    Returns:
        dict: support, resistance, buy_low, buy_high, sell_target,
              current_price  (all float or None)
    """
    out = {
        "support": None, "resistance": None,
        "buy_low": None, "buy_high": None,
        "sell_target": None, "current_price": None,
    }
    try:
        df = _ticker_history(symbol, period=period)
        if df.empty or len(df) < 20:
            logger.warning(
                f"fetch_support_resistance: insufficient data for {symbol} "
                f"(rows={len(df)})"
            )
            return out

        # Ensure we have required columns
        for col in ("High", "Low", "Close"):
            if col not in df.columns:
                logger.warning(f"Missing column {col} for {symbol}")
                return out

        # ── Classic Pivot from last complete session ───────────────────────────
        last = df.iloc[-2]
        H  = float(last["High"])
        L  = float(last["Low"])
        C  = float(last["Close"])
        P  = (H + L + C) / 3
        R1 = 2 * P - L
        R2 = P + (H - L)
        S1 = 2 * P - H
        S2 = P - (H - L)

        cur_price = float(df["Close"].dropna().iloc[-1])
        out["current_price"] = cur_price

        # ── Swing highs / lows ─────────────────────────────────────────────────
        window  = 5
        lows    = df["Low"].values.flatten()
        highs   = df["High"].values.flatten()
        n       = len(df)

        swing_lows: list[float]  = []
        swing_highs: list[float] = []

        for i in range(window, n - window):
            if lows[i]  == float(np.min(lows[i - window: i + window + 1])):
                swing_lows.append(float(lows[i]))
            if highs[i] == float(np.max(highs[i - window: i + window + 1])):
                swing_highs.append(float(highs[i]))

        # ── Nearest support below / resistance above current price ────────────
        candidates_support  = [v for v in ([S1, S2] + swing_lows)  if v < cur_price]
        candidates_resist   = [v for v in ([R1, R2] + swing_highs) if v > cur_price]

        support    = float(max(candidates_support)) if candidates_support else S1
        resistance = float(min(candidates_resist))  if candidates_resist  else R1

        out["support"]     = round(support, 0)
        out["resistance"]  = round(resistance, 0)
        out["buy_low"]     = round(support, 0)
        out["buy_high"]    = round(support * 1.03, 0)
        out["sell_target"] = round(resistance, 0)

        logger.debug(
            f"{symbol}: price={cur_price:.0f}  "
            f"support={support:.0f}  resistance={resistance:.0f}"
        )

    except Exception as exc:
        logger.warning(f"fetch_support_resistance failed for {symbol}: {exc}")

    return out


def batch_live_prices(symbols: list[str]) -> dict[str, dict]:
    """Fetch live prices for multiple symbols.

    Uses Ticker.history() per symbol (more reliable for .JK tickers than
    yf.download batch which is fragile with MultiIndex handling).

    Prices are NOT cached here — callers can wrap with st.cache_data if needed.
    """
    result: dict[str, dict] = {}

    if not symbols:
        return result

    # For small lists (≤ 10), Ticker.history() per symbol is fine.
    # For larger lists we fall back to yf.download batch.
    if len(symbols) <= 10:
        for sym in symbols:
            try:
                df = _ticker_history(sym, period="5d")
                if df.empty or "Close" not in df.columns:
                    result[sym] = {"price": None, "change_pct": None}
                    continue
                closes = df["Close"].dropna()
                price  = float(closes.iloc[-1])
                prev   = float(closes.iloc[-2]) if len(closes) >= 2 else price
                result[sym] = {
                    "price":      price,
                    "change_pct": (price - prev) / prev * 100 if prev else None,
                }
            except Exception as exc:
                logger.warning(f"batch_live_prices[single] failed for {sym}: {exc}")
                result[sym] = {"price": None, "change_pct": None}
        return result

    # Batch download for larger watchlists
    try:
        raw = yf.download(symbols, period="5d", progress=False, threads=True)
        if raw.empty:
            return {s: {"price": None, "change_pct": None} for s in symbols}

        raw = _flatten(raw)

        # With multiple tickers, after flattening:
        # columns = MultiIndex (Price, Ticker) → after droplevel(0) → Ticker
        # But _flatten drops level 0, leaving Price names → need xs approach
        # Re-try with proper multi-ticker handling
        raw_orig = yf.download(symbols, period="5d", progress=False, threads=True)
        if isinstance(raw_orig.columns, pd.MultiIndex):
            # (Price, Ticker) — get Close for all tickers
            try:
                closes_df = raw_orig["Close"]
            except KeyError:
                closes_df = raw_orig.xs("Close", axis=1, level=0)
        else:
            closes_df = raw_orig[["Close"]] if "Close" in raw_orig.columns else raw_orig

        for sym in symbols:
            try:
                if sym in closes_df.columns:
                    prices = closes_df[sym].dropna()
                elif len(closes_df.columns) == 1:
                    prices = closes_df.iloc[:, 0].dropna()
                else:
                    result[sym] = {"price": None, "change_pct": None}
                    continue
                price = float(prices.iloc[-1])
                prev  = float(prices.iloc[-2]) if len(prices) >= 2 else price
                result[sym] = {
                    "price":      price,
                    "change_pct": (price - prev) / prev * 100 if prev else None,
                }
            except Exception:
                result[sym] = {"price": None, "change_pct": None}

    except Exception as exc:
        logger.warning(f"batch_live_prices[batch] failed: {exc}")
        result = {s: {"price": None, "change_pct": None} for s in symbols}

    return result
