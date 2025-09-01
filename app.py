import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Options Dashboard", page_icon="📊", layout="wide")

st.title("📊 Options Market Dashboard")
st.caption("Educational research only — no financial advice.")

# Demo-Daten (später Sheet)
data = [
    {"Underlying":"ES/SPY","Bias":"Neutral","Recommendation":"Neutral","Gamma Flip":648,"Put Wall":640,"Call Wall":650,"Spot":645.05,"Score":-0.74,"Regime":"Short-Gamma (neg)"},
    {"Underlying":"NQ/QQQ","Bias":"Neutral","Recommendation":"Neutral","Gamma Flip":573,"Put Wall":565,"Call Wall":580,"Spot":570.40,"Score":-0.65,"Regime":"Short-Gamma (neg)"},
    {"Underlying":"GC/GLD","Bias":"Long","Recommendation":"Long","Gamma Flip":304,"Put Wall":305,"Call Wall":315,"Spot":318.07,"Score":2.00,"Regime":"Breakout Risk"},
]
df = pd.DataFrame(data)

st.subheader("Overview")
st.dataframe(df)

st.subheader("Asset Detail")
asset = st.selectbox("Select asset", df["Underlying"])
row = df[df["Underlying"] == asset].iloc[0]

st.write({
    "Spot": row["Spot"],
    "Gamma Flip": row["Gamma Flip"],
    "Put Wall": row["Put Wall"],
    "Call Wall": row["Call Wall"],
    "Score": row["Score"],
    "Regime": row["Regime"],
})
