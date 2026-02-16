import streamlit as st
from analytics.psychology import analyze_emotions
from dashboard.components.charts import plot_win_rate_bar

def render(trades: list):
    st.title("Psychology 🧠")
    
    if not trades:
        st.info("No trades available.")
        return

    st.markdown("### Emotion Impact Analysis")
    emotion_df = analyze_emotions(trades)
    
    if not emotion_df.empty:
         st.plotly_chart(plot_win_rate_bar(emotion_df, "emotion", "Win Rate by Emotion"), use_container_width=True)
         st.dataframe(emotion_df, use_container_width=True)
