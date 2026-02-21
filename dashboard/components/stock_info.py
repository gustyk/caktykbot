"""Dashboard utility — fetch stock info and price levels from yfinance.

Compatible with yfinance >= 0.2.36 AND yfinance 1.x:
  - Uses yf.Ticker(sym).history() for OHLCV (always flat columns, all versions)
  - Uses yf.Ticker(sym).fast_info for live quote (available since 0.2.x)
  - Falls back gracefully if fast_info attributes are missing
  - Does NOT use yf.download() since MultiIndex handling differs by version

S/R algorithm: 4-method combination
  1. Classic Pivot Points    — daily S1/S2/R1/R2
  2. EMA 21/50/200           — dynamic support/resistance
  3. Fibonacci Retracement   — 38.2%, 50%, 61.8% from period swing
  4. Swing Highs / Lows      — local extrema (window=5 bars)
"""
from __future__ import annotations

import time
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from loguru import logger


# ── constants ─────────────────────────────────────────────────────────────────

_SECTOR_MAP: dict[str, str] = {
    "Financial Services":     "Finance",
    "Finance":                "Finance",
    "Banking":                "Banking",
    "Consumer Defensive":     "Consumer Goods",
    "Consumer Cyclical":      "Consumer Cyclical",
    "Industrials":            "Industrials",
    "Energy":                 "Energy",
    "Healthcare":             "Healthcare",
    "Technology":             "Technology",
    "Communication Services": "Telco",
    "Real Estate":            "Property",
    "Basic Materials":        "Mining",
    "Utilities":              "Infrastructure",
}
_MC_THR = {"large": 10_000_000_000_000, "mid": 1_000_000_000_000}


# ── internal: fetch OHLCV via Ticker.history() ────────────────────────────────

def _history(symbol: str, period: str = "6mo", retries: int = 2) -> pd.DataFrame:
    """Fetch flat-column OHLCV using Ticker.history().

    Ticker.history() always returns a simple (non-MultiIndex) DataFrame
    regardless of yfinance version — the safest approach for .JK tickers.
    """
    for attempt in range(1, retries + 2):
        try:
            df = yf.Ticker(symbol).history(period=period)
            if df.empty:
                if attempt <= retries:
                    wait = 3 * attempt
                    logger.warning(
                        f"Empty history for {symbol} attempt {attempt}, "
                        f"retrying in {wait}s…"
                    )
                    time.sleep(wait)
                    continue
                logger.warning(f"Ticker.history: empty result for {symbol}")
                return pd.DataFrame()

            # Drop timezone from index (simplifies downstream handling)
            if hasattr(df.index, "tz") and df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            logger.debug(
                f"_history {symbol}: {len(df)} rows  cols={df.columns.tolist()}"
            )
            return df

        except Exception as e:
            logger.error(f"_history {symbol} attempt {attempt}: {e}")
            if attempt <= retries:
                time.sleep(3 * attempt)

    return pd.DataFrame()


# ── public: metadata ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_meta(symbol: str) -> dict:
    """Company name, sector, market_cap via Ticker.info."""
    out = {"name": None, "sector": None, "market_cap": "small", "found": False}
    try:
        info = yf.Ticker(symbol).info or {}

        name = (info.get("longName") or info.get("shortName") or "").strip()
        out["name"] = name or None

        raw = info.get("sector") or info.get("industry") or ""
        out["sector"] = _SECTOR_MAP.get(raw, "Other") if raw else None

        mc = info.get("marketCap") or 0
        # .JK: Yahoo usually returns IDR (large number). Fallback convert from USD.
        mc_idr = mc if mc > 1_000_000_000 else mc * 15_900
        if mc_idr >= _MC_THR["large"]:
            out["market_cap"] = "large"
        elif mc_idr >= _MC_THR["mid"]:
            out["market_cap"] = "mid"

        out["found"] = bool(out["name"])
        logger.debug(f"meta {symbol}: name={out['name']} sector={out['sector']} mc={out['market_cap']}")

    except Exception as e:
        logger.warning(f"fetch_stock_meta {symbol}: {e}")
    return out


# ── public: live quote ────────────────────────────────────────────────────────

@st.cache_data(ttl=180, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """Latest price + change% — fast_info first, history fallback."""
    out = {"price": None, "change_pct": None, "volume": None}
    try:
        # Attempt 1: fast_info (lightweight, no full data download)
        fi    = yf.Ticker(symbol).fast_info
        price = getattr(fi, "last_price", None)
        prev  = getattr(fi, "previous_close", None)
        if price and float(price) > 0:
            out["price"] = float(price)
            if prev and float(prev) > 0:
                out["change_pct"] = (float(price) - float(prev)) / float(prev) * 100
            logger.debug(f"fast_info {symbol}: price={price:.0f}")
            return out
    except Exception:
        pass

    # Attempt 2: 5d history
    try:
        df = _history(symbol, period="5d")
        if df.empty or "Close" not in df.columns:
            return out
        closes = df["Close"].dropna()
        if len(closes) == 0:
            return out
        price  = float(closes.iloc[-1])
        prev   = float(closes.iloc[-2]) if len(closes) >= 2 else price
        out["price"]      = price
        out["change_pct"] = (price - prev) / prev * 100 if prev else None
        if "Volume" in df.columns:
            out["volume"] = int(df["Volume"].dropna().iloc[-1])
    except Exception as e:
        logger.warning(f"fetch_live_quote {symbol} history fallback: {e}")

    return out


# ── public: batch live prices (cached) ───────────────────────────────────────

@st.cache_data(ttl=180, show_spinner=False)
def batch_live_prices(symbols: tuple) -> dict[str, dict]:
    """Fetch latest close + change% for multiple tickers.

    Args:
        symbols: *Tuple* of ticker strings (tuple required for st.cache_data).
    """
    result: dict[str, dict] = {}
    if not symbols:
        return result

    for sym in symbols:
        try:
            df = _history(sym, period="5d")
            if df.empty or "Close" not in df.columns:
                result[sym] = {"price": None, "change_pct": None}
                continue
            closes = df["Close"].dropna()
            if len(closes) == 0:
                result[sym] = {"price": None, "change_pct": None}
                continue
            price = float(closes.iloc[-1])
            prev  = float(closes.iloc[-2]) if len(closes) >= 2 else price
            result[sym] = {
                "price":      price,
                "change_pct": (price - prev) / prev * 100 if prev else None,
            }
        except Exception as e:
            logger.warning(f"batch_live_prices {sym}: {e}")
            result[sym] = {"price": None, "change_pct": None}

    return result


# ── public: support & resistance (4-method) ───────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_support_resistance(symbol: str, period: str = "6mo") -> dict:
    """Multi-method S/R (Pivot + EMA + Fibonacci + Swing Highs/Lows).

    Returns:
        dict: current_price, support, resistance,
              buy_low, buy_high, sell_target, method_details
    """
    empty = {
        "current_price": None, "support": None, "resistance": None,
        "buy_low": None, "buy_high": None, "sell_target": None,
        "method_details": [],
    }

    try:
        df = _history(symbol, period=period)
        if df.empty or len(df) < 30:
            logger.warning(f"S/R {symbol}: only {len(df)} rows (need ≥30)")
            return empty

        for col in ("High", "Low", "Close"):
            if col not in df.columns:
                logger.error(f"S/R {symbol}: missing column '{col}' — cols={df.columns.tolist()}")
                return empty

        close = df["Close"].ffill()
        high  = df["High"].ffill()
        low   = df["Low"].ffill()
        cur   = float(close.iloc[-1])

        details: list[str] = []
        supports: list[float]    = []
        resistances: list[float] = []

        # ── 1. Classic Pivot Points ───────────────────────────────────────────
        pH = float(high.iloc[-2])
        pL = float(low.iloc[-2])
        pC = float(close.iloc[-2])
        P  = (pH + pL + pC) / 3
        R1 = 2 * P - pL;   R2 = P + (pH - pL)
        S1 = 2 * P - pH;   S2 = P - (pH - pL)
        supports.extend([S1, S2])
        resistances.extend([R1, R2])
        details.append(
            f"📌 Pivot: P={P:.0f} | S1={S1:.0f}  S2={S2:.0f} | R1={R1:.0f}  R2={R2:.0f}"
        )

        # ── 2. EMA Levels (21, 50, 200) ──────────────────────────────────────
        for span in (21, 50, 200):
            if len(close) >= span:
                ema = float(close.ewm(span=span, adjust=False).mean().iloc[-1])
                (supports if ema < cur else resistances).append(ema)
                flag = "↓support" if ema < cur else "↑resist"
                details.append(f"📈 EMA{span} = {ema:.0f} ({flag})")

        # ── 3. Fibonacci Retracement ──────────────────────────────────────────
        swing_hi = float(high.max())
        swing_lo = float(low.min())
        diff = swing_hi - swing_lo
        if diff > 0:
            fibs = {
                "38.2%": swing_hi - 0.382 * diff,
                "50.0%": swing_hi - 0.500 * diff,
                "61.8%": swing_hi - 0.618 * diff,
            }
            for label, lvl in fibs.items():
                (supports if lvl < cur else resistances).append(lvl)
            details.append(
                "📐 Fibonacci: " + "  ".join(f"{k}={v:.0f}" for k, v in fibs.items())
            )

        # ── 4. Swing Highs / Lows (window=5) ─────────────────────────────────
        win  = 5
        lo_v = low.values
        hi_v = high.values
        n    = len(df)
        sw_lo: list[float] = []
        sw_hi: list[float] = []
        for i in range(win, n - win):
            if lo_v[i] == float(np.min(lo_v[i - win: i + win + 1])):
                sw_lo.append(float(lo_v[i]))
            if hi_v[i] == float(np.max(hi_v[i - win: i + win + 1])):
                sw_hi.append(float(hi_v[i]))
        for v in sw_lo[-10:]:
            if v < cur:
                supports.append(v)
        for v in sw_hi[-10:]:
            if v > cur:
                resistances.append(v)
        details.append(f"🕯️ Swing lows  (recent 5): {[round(x) for x in sw_lo[-5:]]}")
        details.append(f"🕯️ Swing highs (recent 5): {[round(x) for x in sw_hi[-5:]]}")

        # ── Pick nearest support below / resistance above ─────────────────────
        s_below = [v for v in supports    if v < cur]
        r_above = [v for v in resistances if v > cur]
        support    = float(max(s_below)) if s_below else S1
        resistance = float(min(r_above)) if r_above else R1

        # Guard: if spread too tight (< 1%), widen to next-best S2/R2
        if resistance > 0 and (resistance - support) / resistance < 0.01:
            support    = S2 if S2 < support    else support
            resistance = R2 if R2 > resistance else resistance
            logger.info(
                f"S/R {symbol}: spread too tight, widened to S2/R2 → "
                f"support={support:.0f} resistance={resistance:.0f}"
            )

        # buy_high must always be strictly below sell_target
        # Cap at 99.5 % of resistance so the buy zone never overlaps
        raw_buy_high = support * 1.015
        buy_high = min(raw_buy_high, resistance * 0.995)

        # If that still inverts (ultra-tight stock), just use midpoint
        midpoint = (support + resistance) / 2
        if buy_high >= resistance:
            buy_high = midpoint

        logger.info(
            f"S/R {symbol}: price={cur:.0f} | support={support:.0f} | "
            f"buy_high={buy_high:.0f} | resistance={resistance:.0f}"
        )

        return {
            "current_price": round(cur, 0),
            "support":       round(support, 0),
            "resistance":    round(resistance, 0),
            "buy_low":       round(support, 0),
            "buy_high":      round(buy_high, 0),
            "sell_target":   round(resistance, 0),
            "method_details": details,
        }

    except Exception as e:
        logger.error(f"fetch_support_resistance {symbol}: {e}", exc_info=True)
        return empty
