"""Dashboard utility — fetch stock info and price levels from yfinance.

S/R Method (multi-layer, combining 4 approaches):
  1. Pivot Points  (Classic daily)            — intraday / swing anchor
  2. Moving Averages (EMA 50, EMA 200)        — dynamic S/R
  3. Fibonacci Retracement (38.2 / 50 / 61.8%) — measured from 6-month swing
  4. Historical Swing Highs / Lows            — market-memory levels

Final support  = weighted median of all support  candidates below price
Final resist   = weighted median of all resistance candidates above price
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from loguru import logger


# ── sector map ────────────────────────────────────────────────────────────────
_SECTOR_MAP: dict[str, str] = {
    "Financial Services": "Finance",
    "Finance":            "Finance",
    "Banking":            "Banking",
    "Consumer Defensive": "Consumer Goods",
    "Consumer Cyclical":  "Consumer Cyclical",
    "Industrials":        "Industrials",
    "Energy":             "Energy",
    "Healthcare":         "Healthcare",
    "Technology":         "Technology",
    "Communication Services": "Telco",
    "Real Estate":        "Property",
    "Basic Materials":    "Mining",
    "Utilities":          "Infrastructure",
}
_MC_THR = {"large": 10_000_000_000_000, "mid": 1_000_000_000_000}


# ── internal: fetch OHLCV (always flat columns, version-safe) ─────────────────

def _history(symbol: str, period: str = "6mo") -> pd.DataFrame:
    """Use Ticker.history() — never returns MultiIndex, works for .JK."""
    try:
        df = yf.Ticker(symbol).history(period=period, timeout=15)
        if df.empty:
            logger.warning(f"Empty history for {symbol} (period={period})")
        return df
    except Exception as e:
        logger.error(f"_history failed {symbol}: {e}")
        return pd.DataFrame()


# ── public: stock metadata ────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_meta(symbol: str) -> dict:
    """Name, sector, market_cap from yfinance.info."""
    out = {"name": None, "sector": None, "market_cap": "small", "found": False}
    try:
        info = yf.Ticker(symbol).info or {}

        name = (info.get("longName") or info.get("shortName") or "").strip()
        out["name"] = name or None

        raw = info.get("sector") or info.get("industry") or ""
        out["sector"] = _SECTOR_MAP.get(raw, "Other") if raw else None

        mc = info.get("marketCap") or 0
        # Yahoo Finance for .JK: marketCap is in IDR (large number)
        # If suspiciously small (<1B), assume USD and convert
        mc_idr = mc if mc > 1_000_000_000 else mc * 15_900
        if mc_idr >= _MC_THR["large"]:
            out["market_cap"] = "large"
        elif mc_idr >= _MC_THR["mid"]:
            out["market_cap"] = "mid"

        out["found"] = bool(out["name"])
    except Exception as e:
        logger.warning(f"fetch_stock_meta {symbol}: {e}")
    return out


# ── public: live quote ────────────────────────────────────────────────────────

@st.cache_data(ttl=180, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """Latest price + change% for one ticker."""
    out = {"price": None, "change_pct": None, "volume": None}
    try:
        df = _history(symbol, period="5d")
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
    except Exception as e:
        logger.warning(f"fetch_live_quote {symbol}: {e}")
    return out


# ── public: batch live prices (cached) ───────────────────────────────────────

@st.cache_data(ttl=180, show_spinner=False)
def batch_live_prices(symbols: tuple[str, ...]) -> dict[str, dict]:
    """Fetch latest close + change% for multiple symbols.

    NOTE: Pass symbols as a TUPLE (hashable) so st.cache_data works.
    """
    result: dict[str, dict] = {}
    for sym in symbols:
        try:
            df = _history(sym, period="5d")
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
        except Exception as e:
            logger.warning(f"batch_live_prices {sym}: {e}")
            result[sym] = {"price": None, "change_pct": None}
    return result


# ── public: support & resistance (multi-method) ───────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_support_resistance(symbol: str, period: str = "6mo") -> dict:
    """Calculate support & resistance using 4 combined methods.

    Methods:
      1. Classic Pivot Points from last session (P, S1, S2, R1, R2)
      2. EMA 50 and EMA 200 as dynamic S/R
      3. Fibonacci retracement from 6-month swing low → high
         (38.2 %, 50 %, 61.8 % levels)
      4. Swing highs / lows (local extrema, window = 5 bars)

    All candidate levels are collected, split into those below (support) and
    above (resistance) the current price, and the nearest one is selected.

    Returns:
        dict: current_price, support, resistance,
              buy_low, buy_high, sell_target,
              method_details (list[str])
    """
    empty = {
        "current_price": None, "support": None, "resistance": None,
        "buy_low": None, "buy_high": None, "sell_target": None,
        "method_details": [],
    }

    try:
        df = _history(symbol, period=period)
        if df.empty or len(df) < 30:
            logger.warning(f"S/R: insufficient data for {symbol} ({len(df)} rows)")
            return empty

        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col not in df.columns:
                logger.warning(f"S/R: missing column {col} for {symbol}")
                return empty

        close  = df["Close"].ffill()
        high   = df["High"].ffill()
        low    = df["Low"].ffill()

        cur    = float(close.iloc[-1])
        details: list[str] = []
        supports: list[float]    = []
        resistances: list[float] = []

        # ── 1. Classic Pivot Points ───────────────────────────────────────────
        prev_H = float(high.iloc[-2])
        prev_L = float(low.iloc[-2])
        prev_C = float(close.iloc[-2])
        P  = (prev_H + prev_L + prev_C) / 3
        R1 = 2 * P - prev_L
        R2 = P + (prev_H - prev_L)
        S1 = 2 * P - prev_H
        S2 = P - (prev_H - prev_L)
        supports.extend([S1, S2])
        resistances.extend([R1, R2])
        details.append(f"Pivot: P={P:.0f}  S1={S1:.0f}  S2={S2:.0f}  R1={R1:.0f}  R2={R2:.0f}")

        # ── 2. Moving Averages (EMA 50, EMA 200) ─────────────────────────────
        for period_ma in (21, 50, 200):
            if len(close) >= period_ma:
                ema = float(close.ewm(span=period_ma, adjust=False).mean().iloc[-1])
                if ema < cur:
                    supports.append(ema)
                else:
                    resistances.append(ema)
                details.append(f"EMA{period_ma}={ema:.0f}")

        # ── 3. Fibonacci Retracement ──────────────────────────────────────────
        swing_high = float(high.max())
        swing_low  = float(low.min())
        diff       = swing_high - swing_low
        if diff > 0:
            fib_382 = swing_high - 0.382 * diff
            fib_50  = swing_high - 0.500 * diff
            fib_618 = swing_high - 0.618 * diff
            for lvl in [fib_382, fib_50, fib_618]:
                if lvl < cur:
                    supports.append(lvl)
                else:
                    resistances.append(lvl)
            details.append(
                f"Fib: 38.2%={fib_382:.0f}  50%={fib_50:.0f}  61.8%={fib_618:.0f}"
            )

        # ── 4. Swing Highs / Lows (local extrema, window=5) ──────────────────
        win   = 5
        lo_v  = low.values
        hi_v  = high.values
        n     = len(df)
        sw_lo = []
        sw_hi = []
        for i in range(win, n - win):
            if lo_v[i] == float(np.min(lo_v[i - win: i + win + 1])):
                sw_lo.append(float(lo_v[i]))
            if hi_v[i] == float(np.max(hi_v[i - win: i + win + 1])):
                sw_hi.append(float(hi_v[i]))

        # Use only the most recent 10 swing levels to avoid stale data
        for v in sw_lo[-10:]:
            if v < cur:
                supports.append(v)
        for v in sw_hi[-10:]:
            if v > cur:
                resistances.append(v)
        details.append(
            f"Swing lows (recent): {[round(x, 0) for x in sw_lo[-5:]]}"
        )
        details.append(
            f"Swing highs (recent): {[round(x, 0) for x in sw_hi[-5:]]}"
        )

        # ── Select nearest support / resistance ───────────────────────────────
        supports_below    = [v for v in supports    if v < cur]
        resistances_above = [v for v in resistances if v > cur]

        if not supports_below or not resistances_above:
            logger.warning(
                f"S/R: no valid levels for {symbol} "
                f"(price={cur:.0f}, supports={len(supports_below)}, "
                f"resists={len(resistances_above)})"
            )
            # Fallback: use S1/R1 regardless of position
            support    = S1
            resistance = R1
        else:
            support    = float(max(supports_below))    # nearest below
            resistance = float(min(resistances_above)) # nearest above

        logger.info(
            f"S/R {symbol}: price={cur:.0f}  "
            f"support={support:.0f}  resistance={resistance:.0f}"
        )

        return {
            "current_price": round(cur, 0),
            "support":       round(support, 0),
            "resistance":    round(resistance, 0),
            "buy_low":       round(support, 0),
            "buy_high":      round(support * 1.03, 0),   # 3 % buffer above support
            "sell_target":   round(resistance, 0),
            "method_details": details,
        }

    except Exception as e:
        logger.error(f"fetch_support_resistance {symbol}: {e}", exc_info=True)
        return empty
