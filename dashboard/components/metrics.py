"""Shared metric helper components."""
import streamlit as st


def metric_card(label: str, value: str, delta: str = None, delta_colour: str = None):
    """Render a styled Streamlit metric (wraps st.metric for consistency)."""
    # Determine delta colour automatically from sign if not provided
    if delta and delta_colour is None:
        delta_colour = "normal" if not delta.startswith("-") else "inverse"

    st.metric(label=label, value=value, delta=delta, delta_color=delta_colour or "normal")


def pnl_badge(pnl: float) -> str:
    """Return a coloured HTML badge string for P&L value."""
    colour = "#2ecc71" if pnl >= 0 else "#e74c3c"
    sign   = "+" if pnl >= 0 else ""
    return (
        f"<span style='color:{colour};font-weight:700;'>"
        f"Rp {sign}{pnl:,.0f}"
        f"</span>"
    )
