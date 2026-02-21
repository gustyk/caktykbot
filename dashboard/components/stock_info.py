"""Dashboard utility — fetch stock info and price levels from yfinance 1.x.

Key design for yfinance 1.1.0+:
  - Use yf.download(..., multi_level_index=False) → always flat columns,
    no MultiIndex regardless of single/multi-ticker.
  - Do NOT inject custom session — yfinance 1.x manages its own session
    (injecting one triggers a DeprecationWarning and breaks cookie auth).
  - Ticker.fast_info for lightweight live quote; download fallback for S/R.

S/R: 4-method combination (Pivot + EMA + Fibonacci + Swing Highs/Lows).
"""
from __future__ import annotations

import time
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from loguru import logger


# ── sector / market-cap maps ──────────────────────────────────────────────────

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


# ── internal: flat OHLCV download ─────────────────────────────────────────────

def _download(symbol: str, period: str = "6mo", retries: int = 2) -> pd.DataFrame:
    """Flat-column yf.download with retry.

    Uses multi_level_index=False (yfinance 1.x) so columns are always
    ['Close', 'High', 'Low', 'Open', 'Volume'] — no MultiIndex handling needed.
    """
    for attempt in range(1, retries + 2):
        try:
            df = yf.download(
                symbol,
                period=period,
                progress=False,
                threads=False,
                multi_level_index=False,
            )
            if df.empty:
                if attempt <= retries:
                    wait = 3 * attempt
                    logger.warning(
                        f"Empty download for {symbol} attempt {attempt}, "
                        f"retrying in {wait}s…"
                    )
                    time.sleep(wait)
                    continue
                logger.warning(f"yf.download: empty result for {symbol}")
                return pd.DataFrame()

            logger.debug(
                f"_download {symbol}: {len(df)} rows  cols={df.columns.tolist()}"
            )
            return df

        except Exception as e:
            logger.error(f"_download {symbol} attempt {attempt}: {e}")
            if attempt <= retries:
                time.sleep(3 * attempt)

    return pd.DataFrame()


# ── public: metadata ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_meta(symbol: str) -> dict:
    """Company name, sector, market_cap via Ticker.info."""
    out = {"name": None, "sector": None, "market_cap": "small", "found": False}
    try:
        tk   = yf.Ticker(symbol)
        info = tk.info or {}

        name = (info.get("longName") or info.get("shortName") or "").strip()
        out["name"] = name or None

        raw = info.get("sector") or info.get("industry") or ""
        out["sector"] = _SECTOR_MAP.get(raw, "Other") if raw else None

        mc = info.get("marketCap") or 0
        # .JK: Yahoo usually returns IDR (large number). If suspiciously small, assume USD.
        mc_idr = mc if mc > 1_000_000_000 else mc * 15_900
        if mc_idr >= _MC_THR["large"]:
            out["market_cap"] = "large"
        elif mc_idr >= _MC_THR["mid"]:
            out["market_cap"] = "mid"

        out["found"] = bool(out["name"])
        logger.debug(f"meta {symbol}: {out}")

    except Exception as e:
        logger.warning(f"fetch_stock_meta {symbol}: {e}")
    return out


# ── public: live quote ────────────────────────────────────────────────────────

@st.cache_data(ttl=180, show_spinner=False)
def fetch_live_quote(symbol: str) -> dict:
    """Latest price + change% — fast_info first, download fallback."""
    out = {"price": None, "change_pct": None, "volume": None}
    try:
        # Attempt 1: fast_info (no history request needed)
        fi    = yf.Ticker(symbol).fast_info
        price = getattr(fi, "last_price", None)
        prev  = getattr(fi, "previous_close", None)
        if price and float(price) > 0:
            out["price"] = float(price)
            if prev and float(prev) > 0:
                out["change_pct"] = (float(price) - float(prev)) / float(prev) * 100
            logger.debug(f"fast_info {symbol}: price={price}")
            return out
    except Exception:
        pass

    # Attempt 2: download last 5 days
    try:
        df = _download(symbol, period="5d")
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
        logger.warning(f"fetch_live_quote {symbol} fallback: {e}")

    return out


# ── public: batch live prices (cached) ───────────────────────────────────────

@st.cache_data(ttl=180, show_spinner=False)
def batch_live_prices(symbols: tuple) -> dict[str, dict]:
    """Fetch latest close + change% for multiple tickers.

    Pass symbols as a *tuple* so st.cache_data can hash the argument.
    """
    result: dict[str, dict] = {}
    if not symbols:
        return result

    for sym in symbols:
        try:
            df = _download(sym, period="5d")
            if df.empty or "Close" not in df.columns:
                result[sym] = {"price": None, "change_pct": None}
                continue
            closes = df["Close"].dropna()
            if len(closes) == 0:
                result[sym] = {"price": None, "change_pct": None}
                continue
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
        df = _download(symbol, period=period)
        if df.empty or len(df) < 30:
            logger.warning(f"S/R {symbol}: only {len(df)} rows (need ≥30)")
            return empty

        for col in ("High", "Low", "Close"):
            if col not in df.columns:
                logger.error(f"S/R {symbol}: missing column '{col}'")
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

        # ── Pick nearest support/resistance ───────────────────────────────────
        s_below = [v for v in supports    if v < cur]
        r_above = [v for v in resistances if v > cur]
        support    = float(max(s_below)) if s_below else S1
        resistance = float(min(r_above)) if r_above else R1

        logger.info(
            f"S/R {symbol}: price={cur:.0f} | support={support:.0f} | resistance={resistance:.0f}"
        )

        return {
            "current_price": round(cur, 0),
            "support":       round(support, 0),
            "resistance":    round(resistance, 0),
            "buy_low":       round(support, 0),
            "buy_high":      round(support * 1.03, 0),
            "sell_target":   round(resistance, 0),
            "method_details": details,
        }

    except Exception as e:
        logger.error(f"fetch_support_resistance {symbol}: {e}", exc_info=True)
        return empty
