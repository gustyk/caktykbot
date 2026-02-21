"""Psychology page — emotional pattern analysis."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from analytics.psychology import analyze_emotions
from dashboard.components.charts import plot_win_rate_bar


def render(trades: list):
    st.title("🧠 Psychology")
    st.caption("Analisis dampak emosi terhadap performa trading.")

    if not trades:
        st.info("📭 Belum ada data trade. Catat emosi saat entry/exit via bot atau Journal.")
        return

    # ── Emotion Impact ────────────────────────────────────────────────────────
    st.markdown("### 🎭 Dampak Emosi terhadap Win Rate")
    emotion_df = analyze_emotions(trades)

    if not emotion_df.empty:
        ec1, ec2 = st.columns([3, 2])
        with ec1:
            st.plotly_chart(
                plot_win_rate_bar(emotion_df, "emotion", "Win Rate per Emosi"),
                use_container_width=True,
            )
        with ec2:
            show_cols = [c for c in ["emotion", "total", "win_rate", "avg_pnl"] if c in emotion_df.columns]
            disp = emotion_df[show_cols].rename(columns={
                "emotion":  "Emosi",
                "total":    "Trade",
                "win_rate": "Win Rate %",
                "avg_pnl":  "Avg P&L (Rp)",
            })
            if "Win Rate %" in disp.columns:
                disp["Win Rate %"] = disp["Win Rate %"].apply(lambda x: f"{x:.1f}%")
            if "Avg P&L (Rp)" in disp.columns:
                disp["Avg P&L (Rp)"] = disp["Avg P&L (Rp)"].apply(lambda x: f"Rp {x:+,.0f}")
            st.dataframe(disp, use_container_width=True, hide_index=True)

        # ── Insight callouts ──────────────────────────────────────────────────
        if "win_rate" in emotion_df.columns and len(emotion_df) > 1:
            st.divider()
            best_emo  = emotion_df.loc[emotion_df["win_rate"].idxmax(), "emotion"]
            worst_emo = emotion_df.loc[emotion_df["win_rate"].idxmin(), "emotion"]
            st.success(f"✅ Emosi terbaik: **{best_emo}** — win rate tertinggi")
            st.error(f"⚠️ Emosi terburuk: **{worst_emo}** — win rate terendah")
    else:
        st.info("Belum ada trade dengan tag emosi. Tambahkan emosi saat mencatat trade.")

    st.divider()

    # ── Emotion Distribution Pie ──────────────────────────────────────────────
    st.markdown("### 🥧 Distribusi Emosi Entry")
    df_all = pd.DataFrame(trades)
    if "emotion_tag" in df_all.columns:
        emo_counts = df_all["emotion_tag"].dropna().value_counts().reset_index()
        emo_counts.columns = ["Emosi", "Jumlah"]

        if not emo_counts.empty:
            colours = [
                "#2ecc71", "#3498db", "#9b59b6", "#f39c12",
                "#e74c3c", "#1abc9c", "#e67e22", "#95a5a6",
            ]
            fig_pie = go.Figure(go.Pie(
                labels=emo_counts["Emosi"],
                values=emo_counts["Jumlah"],
                marker_colors=colours[:len(emo_counts)],
                hole=0.42,
                textinfo="label+percent",
            ))
            fig_pie.update_layout(
                template="plotly_dark", height=300,
                margin=dict(t=10, b=10, l=20, r=20),
                showlegend=True,
                legend=dict(orientation="v", x=1.02, y=0.5),
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Tidak ada data emosi.")
    else:
        st.info("Data emosi belum tersedia.")

    st.divider()

    # ── Trade frequency heatmap by day of week ────────────────────────────────
    st.markdown("### 📅 Frekuensi Entry per Hari")
    df_e = pd.DataFrame(trades)
    if "entry_date" in df_e.columns:
        df_e["entry_date"] = pd.to_datetime(df_e["entry_date"], errors="coerce")
        df_e["day_name"]   = df_e["entry_date"].dt.day_name()
        order = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
        day_counts = df_e["day_name"].value_counts().reindex(order, fill_value=0)

        fig_day = go.Figure(go.Bar(
            x=day_counts.index.tolist(),
            y=day_counts.values.tolist(),
            marker_color="#00ADB5",
            text=day_counts.values.tolist(),
            textposition="outside",
        ))
        fig_day.update_layout(
            template="plotly_dark", height=260,
            xaxis_title="Hari", yaxis_title="Jumlah Trade",
            margin=dict(t=10, b=20),
        )
        st.plotly_chart(fig_day, use_container_width=True)
