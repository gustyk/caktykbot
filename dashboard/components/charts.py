import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def plot_equity_curve(curve_data: list):
    """Plot equity curve with drawdown."""
    if not curve_data:
        return go.Figure()
        
    df = pd.DataFrame(curve_data)
    
    fig = go.Figure()
    
    # Equity Line
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["equity"],
        mode='lines', name='Equity',
        line=dict(color='#00ADB5', width=2)
    ))
    
    # Drawdown Area (optional, maybe on secondary axis or just shaded)
    # For simplicity, just equity line + max drawdown annotation
    
    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Date",
        yaxis_title="Equity (Rp)",
        template="plotly_dark",
        height=400
    )
    return fig

def plot_win_rate_bar(df: pd.DataFrame, x_col: str, title: str):
    """Plot Win Rate bar chart."""
    if df.empty:
         return go.Figure()
         
    fig = px.bar(
        df, x=x_col, y="win_rate",
        title=title,
        color="win_rate",
        color_continuous_scale=["red", "yellow", "green"],
        text="win_rate"
    )
    fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig.update_layout(template="plotly_dark", yaxis_range=[0, 100])
    return fig
