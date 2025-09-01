# app.py — Market Dashboard + Visuals
import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import plotly.express as px

# ---------------- Page setup ----------------
st.set_page_config(page_title="Market Dashboard", page_icon="📈", layout="wide")
st.title("Market Dashboard")

# ---------------- Google Sheets I/O ----------------
def _authorize():
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=300)  # 5 Minuten Cache
def load_range(sheet_id: str, tab: str, cell_range: str,
               header_in_first_row: bool = True,
               header_override: list[str] | None = None) -> pd.DataFrame:
    gc = _authorize()
    ws = gc.open_by_key(sheet_id).worksheet(tab)
    values = ws.get(cell_range)  # list[list]
    if not values:
        return pd.DataFrame()

    if header_in_first_row and header_override is None:
        header, rows = values[0], values[1:]
    else:
        rows = values
        header = header_override or [f"Col{i+1}" for i in range(len(rows[0]))]

    df = pd.DataFrame(rows, columns=header)

    # numerische Spalten robust konvertieren
    for c in df.columns:
        df[c] = pd.to_numeric(
            pd.Series(df[c]).astype(str)
            .str.replace("%", "", regex=False)
            .str.replace("\u00A0", "", regex=False)  # non-breaking space
            .str.replace(",", ".", regex=False),
            errors="ignore",
        )
    return df

SHEET_ID  = st.secrets["SHEET_ID"]   # z. B. "...from Sheet URL..."
SHEET_TAB = st.secrets["SHEET_TAB"]  # z. B. "Bias"

# ----------- UI: Refresh + Zeitstempel -----------
col_l, col_r = st.columns([1,1])
with col_l:
    if st.button("🔄 Aktualisieren"):
        load_range.clear()
        st.experimental_rerun()
with col_r:
    st.write(f"Zuletzt aktualisiert: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

# ----------- Daten laden -----------
df_dash = load_range(SHEET_ID, SHEET_TAB, "A1:F10", header_in_first_row=True)

gex_headers = ["Underlying", "Spot", "Gamma Flip", "Put Wall", "Call Wall",
               "Regime", "Score", "Option Bias"]
df_gex = load_range(
    SHEET_ID, SHEET_TAB, "A15:H22",  # A15, um doppelte Header zu vermeiden
    header_in_first_row=False, header_override=gex_headers
)

# ----------- Helpers -----------
color_map_bias = {
    "Extreme Bullish":"#14532d", "Bullish":"#16a34a",
    "Neutral":"#9aa0a6",
    "Bearish":"#dc2626", "Extreme Bearish":"#7f1d1d"
}
def color_bias(val: str):
    if not isinstance(val, str):
        return ""
    v = val.lower()
    if "extreme" in v and "bull" in v: return "background-color:#14532d;color:white"
    if "extreme" in v and "bear" in v: return "background-color:#7f1d1d;color:white"
    if "bull" in v:                     return "background-color:#16a34a;color:white"
    if "bear" in v:                     return "background-color:#dc2626;color:white"
    if "neutral" in v:                  return "background-color:#9aa0a6;color:white"
    return ""

# ----------- Tabellen ----------
if df_dash.empty and df_gex.empty:
    st.info("Keine Daten gefunden.")
else:
    if not df_dash.empty:
        st.subheader("Dashboard")
        cols = [c for c in df_dash.columns if c.lower() == "bias"]
        styled = df_dash.style.applymap(color_bias, subset=cols) if cols else df_dash
        st.dataframe(styled, use_container_width=True)

    st.markdown("---")

    if not df_gex.empty:
        st.subheader("Gex Data")
        cols = [c for c in df_gex.columns if "bias" in c.lower()]
        styled = df_gex.style.applymap(color_bias, subset=cols) if cols else df_gex
        st.dataframe(styled, use_container_width=True)

# ================== VISUALS ==================
if not df_gex.empty:
    st.markdown("---")
    st.header("Visuals")

    # --- 1) Option Bias Score (sorted) ---
    st.subheader("Option Bias Score (sorted)")
    df_scores = df_gex[["Underlying","Score","Option Bias"]].copy()
    df_scores = df_scores.dropna(subset=["Score"])
    df_scores = df_scores.sort_values("Score", ascending=False)
    fig1 = px.bar(
        df_scores, x="Score", y="Underlying", orientation="h",
        text="Score", color="Option Bias", color_discrete_map=color_map_bias
    )
    fig1.update_traces(texttemplate="%{x:.2f}", textposition="outside", cliponaxis=False)
    fig1.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig1, use_container_width=True)

    # --- 2) Sentiment-Heatmap (Diskrete Einschätzungen) ---
    if not df_dash.empty:
        st.subheader("Sentiment-Heatmap")
        heat_cols = ["Price Action","Option Bias Score","COT Positioning","Retail Positioning","Bias"]
        use_cols = [c for c in heat_cols if c in df_dash.columns]
        if use_cols:
            df_heat = df_dash[["Underlying"] + use_cols].copy()
            map_level = {
                "Extreme Short":-2, "Short":-1, "Bearish":-1,
                "Neutral":0, "Bullish":1, "Long":1,
                "Extreme Long":2, "Extreme Bullish":2
            }
            m = df_heat.set_index("Underlying").applymap(lambda v: map_level.get(str(v), 0))
            fig2 = px.imshow(
                m, aspect="auto",
                color_continuous_scale=["#7f1d1d","#dc2626","#e5e7eb","#16a34a","#14532d"],
                zmin=-2, zmax=2
            )
            fig2.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10), coloraxis_showscale=False)
            st.plotly_chart(fig2, use_container_width=True)

    # --- 3) Walls & Gamma Flip vs. Spot ---
    st.subheader("Walls & Gamma Flip vs. Spot")
    df_plot = df_gex[["Underlying","Spot","Put Wall","Call Wall","Gamma Flip"]].copy()
    lf = df_plot.melt(id_vars="Underlying", var_name="Level", value_name="Price").dropna()
    fig3 = px.scatter(lf, x="Price", y="Underlying", color="Level", symbol="Level")
    fig3.update_traces(marker_size=10)
    fig3.update_layout(height=520, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig3, use_container_width=True)

    # --- 4) Distance to Gamma Flip (%) ---
    st.subheader("Distance to Gamma Flip (%)")
    df_dist = df_gex[["Underlying","Spot","Gamma Flip"]].copy()
    df_dist = df_dist.dropna(subset=["Spot","Gamma Flip"])
    df_dist["Dist %"] = (df_dist["Spot"] - df_dist["Gamma Flip"]) / df_dist["Spot"] * 100
    fig4 = px.bar(
        df_dist.sort_values("Dist %"),
        x="Dist %", y="Underlying", orientation="h",
        color=np.where(df_dist["Dist %"]>=0, "Above", "Below"),
        color_discrete_map={"Above":"#16a34a","Below":"#dc2626"}
    )
    fig4.update_layout(showlegend=False, height=420, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig4, use_container_width=True)

st.caption("Live aus Google Sheets • Bereiche: Bias!A1:F10 & Bias!A15:H22 • Cache: 5 Min")
