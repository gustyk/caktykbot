"""Shared chart components — consistent Plotly dark theme."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Shared colour palette
_GREEN  = "#2ecc71"
_RED    = "#e74c3c"
_TEAL   = "#00ADB5"
_YELLOW = "#f1c40f"

_LAYOUT_BASE = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", size=12),
    margin=dict(l=20, r=20, t=40, b=20),
)


def plot_equity_curve(curve_data: list) -> go.Figure:
    """Equity curve with filled drawdown area."""
    if not curve_data:
        return go.Figure()

    df = pd.DataFrame(curve_data)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Running max + drawdown
    df["peak"]     = df["equity"].cummax()
    df["drawdown"] = (df["equity"] - df["peak"]) / df["peak"] * 100

    fig = go.Figure()

    # Drawdown fill (secondary y-axis)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["drawdown"],
        mode="lines",
        name="Drawdown %",
        fill="tozeroy",
        line=dict(color=_RED, width=1),
        fillcolor="rgba(231,76,60,0.15)",
        yaxis="y2",
    ))

    # Equity line
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["equity"],
        mode="lines",
        name="Equity",
        line=dict(color=_TEAL, width=2.5),
        fill="tozeroy",
        fillcolor="rgba(0,173,181,0.08)",
    ))

    fig.update_layout(
        **_LAYOUT_BASE,
        title="Equity Curve & Drawdown",
        height=380,
        xaxis_title="Tanggal",
        yaxis=dict(title="Equity (Rp)", tickformat=",.0f"),
        yaxis2=dict(
            title="Drawdown %",
            overlaying="y",
            side="right",
            showgrid=False,
            ticksuffix="%",
        ),
        legend=dict(orientation="h", y=1.08, x=0),
        hovermode="x unified",
    )
    return fig


def plot_win_rate_bar(df: pd.DataFrame, x_col: str, title: str) -> go.Figure:
    """Horizontal win-rate bar chart with colour gradient."""
    if df.empty or x_col not in df.columns or "win_rate" not in df.columns:
        return go.Figure()

    df_sorted = df.sort_values("win_rate", ascending=True)
    colours   = [_GREEN if v >= 50 else _RED for v in df_sorted["win_rate"]]

    fig = go.Figure(go.Bar(
        x=df_sorted["win_rate"],
        y=df_sorted[x_col],
        orientation="h",
        marker_color=colours,
        text=[f"{v:.1f}%" for v in df_sorted["win_rate"]],
        textposition="outside",
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        title=title,
        height=max(260, len(df) * 55),
        xaxis=dict(range=[0, 115], title="Win Rate %"),
        yaxis=dict(title=""),
    )
    return fig


def plot_pnl_bars(symbols: list, pnl_values: list, title: str = "P&L per Trade") -> go.Figure:
    """Green/red vertical P&L bar chart."""
    colours = [_GREEN if v >= 0 else _RED for v in pnl_values]
    fig = go.Figure(go.Bar(
        x=symbols,
        y=pnl_values,
        marker_color=colours,
        text=[f"Rp {v:+,.0f}" for v in pnl_values],
        textposition="outside",
    ))
    fig.update_layout(
        **_LAYOUT_BASE,
        title=title,
        height=340,
        xaxis_title="Ticker",
        yaxis_title="P&L (Rp)",
        yaxis=dict(tickformat=",.0f"),
    )
    return fig
