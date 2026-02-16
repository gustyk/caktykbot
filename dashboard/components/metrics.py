import streamlit as st

def metric_card(label: str, value: str, delta: str = None):
    """Render a styled metric card."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<div style='font-size: 14px; color: #888;'>{label}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size: 24px; font-weight: bold;'>{value}</div>", unsafe_allow_html=True)
    with col2:
        if delta:
            color = "green" if not delta.startswith("-") else "red"
            st.markdown(f"<div style='color: {color}; font-size: 14px;'>{delta}</div>", unsafe_allow_html=True)
