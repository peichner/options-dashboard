# Overview (farbige Table)
st.subheader("Overview")
st.plotly_chart(make_overview_table(df), use_container_width=True)

st.markdown("---")

# Detailbereich
st.subheader("Asset Detail")
left, right = st.columns([1,2])

with left:
    asset = st.selectbox("Select asset", df["Underlying"].tolist())
    row = df[df["Underlying"]==asset].iloc[0]

    # Badges
    st.markdown(
        pill(row["Regime"], REGIME_COLORS.get(row["Regime"], "#9aa0a6")) + " " +
        pill(row["Bias"],   BIAS_COLORS.get(row["Bias"], "#9aa0a6")) + " " +
        pill(row["Recommendation"], REC_COLORS.get(row["Recommendation"], "#9aa0a6")),
        unsafe_allow_html=True
    )

    st.write(
        {
            "Spot": round(row["Spot"],2),
            "Gamma Flip": row["Gamma Flip"],
            "Put Wall": row["Put Wall"],
            "Call Wall": row["Call Wall"],
        }
    )

    st.plotly_chart(score_gauge(row["Score"]), use_container_width=True)

with right:
    st.plotly_chart(levels_chart(row), use_container_width=True)

st.markdown("**Methodology:** Flip-basiertes Regime; Walls nur als Extrem-Zonen (Crash/Breakout). Score = normierte Distanz Flip→Wall (−2…+2).")
st.caption("Data source: demo; replace with Google Sheets via API for live data.")

# ======== Hinweise für produktiven Einsatz ========
with st.expander("🔧 Hinweise: Google Sheets anbinden"):
    st.write("""
    1) `pip install gspread google-auth`
    2) Service Account JSON in `.streamlit/secrets.toml` eintragen
    3) Daten laden und `df` ersetzen.
    """)
