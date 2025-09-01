import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# -------- Page setup --------
st.set_page_config(page_title="Options Market Dashboard", page_icon="📊", layout="wide")
st.title("📊 Options Market Dashboard")
st.caption("Educational research only — no financial advice.")

# -------- Colors / badges --------
BIAS_COLORS = {"Long":"#16a34a", "Neutral":"#9aa0a6", "Short":"#dc2626"}
REC_COLORS  = {
    "Long":"#16a34a","Long+":"#0ea5e9","Long++":"#2563eb",
    "Short":"#dc2626","Short+":"#f59e0b","Short++":"#b45309",
    "Neutral":"#9aa0a6"
}
REGIME_COLORS = {
    "Short-Gamma (neg)":"#ef4444",
    "Long-Gamma (pos)":"#10b981",
    "Neutral (Flip)":"#9aa0a6",
    "Crash Risk":"#fb7185",
    "Breakout Risk":"#60a5fa"
}
def pill(text, color):
    return f"<span style='background:{color};color:white;padding:4px 8px;border-radius:9999px;font-size:12px;'>{text}</span>"

# -------- Google Sheets I/O --------
def _authorize():
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def load_sheet():
    gc = _authorize()
    ws = gc.open_by_key(st.secrets["SHEET_ID"]).worksheet(st.secrets.get("SHEET_TAB","Dashboard"))
    df = pd.DataFrame(ws.get_all_records())
    # cast numerics if present
    for c in ["Spot","Gamma Flip","Put Wall","Call Wall","Score"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# -------- Charts / tables --------
def make_overview_table(df: pd.DataFrame):
    header = ["Underlying","Price Action","Option Bias Score","COT Positioning","Retail Positioning",
              "Regime","Bias","Recommendation","Spot","Gamma Flip","Put Wall","Call Wall","Score"]
    cells = [df[h] if h in df.columns else [""]*len(df) for h in header]
    bias_colors = [BIAS_COLORS.get(x,"#ffffff") for x in df.get("Bias", [""]*len(df))]
    rec_colors  = [REC_COLORS.get(x,"#ffffff") for x in df.get("Recommendation", [""]*len(df))]
    reg_colors  = [REGIME_COLORS.get(x,"#ffffff") for x in df.get("Regime", [""]*len(df))]
    fills = [
        ["#ffffff"]*len(df),["#ffffff"]*len(df),["#ffffff"]*len(df),["#ffffff"]*len(df),["#ffffff"]*len(df),
        reg_colors, bias_colors, rec_colors,
        ["#ffffff"]*len(df),["#ffffff"]*len(df),["#ffffff"]*len(df),["#ffffff"]*len(df),["#ffffff"]*len(df),
    ]
    fig = go.Figure(data=[go.Table(
        header=dict(values=header, fill_color="#111827", font=dict(color="white", size=12), align="left"),
        cells=dict(values=cells, fill_color=fills, align="left", height=28)
    )])
    fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=36+28*(len(df)+1))
    return fig

def levels_chart(row: pd.Series):
    fig = go.Figure()
    if pd.notna(row.get("Gamma Flip")):
        fig.add_hline(y=row["Gamma Flip"], line_dash="dot", line_width=2, annotation_text=f"Gamma Flip {row['Gamma Flip']}")
    if pd.notna(row.get("Put Wall")):
        fig.add_hline(y=row["Put Wall"], line_dash="dot", line_width=2, annotation_text=f"Put {row['Put Wall']}")
    if pd.notna(row.get("Call Wall")):
        fig.add_hline(y=row["Call Wall"], line_dash="dot", line_width=2, annotation_text=f"Call {row['Call Wall']}")
    if pd.notna(row.get("Spot")):
        fig.add_scatter(x=[row["Underlying"]], y=[row["Spot"]], mode="markers", marker=dict(size=14), name="Spot")
    fig.update_layout(yaxis_title="Level", showlegend=False, height=320, margin=dict(l=10,r=10,t=10,b=10))
    return fig

def score_gauge(value: float):
    v = 0.0 if pd.isna(value) else float(value)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=v,
        gauge={
            "axis":{"range":[-2,2]},
            "bar":{"thickness":0.2},
            "steps":[
                {"range":[-2,-1],"color":"#fecaca"},
                {"range":[-1,-0.3],"color":"#fee2e2"},
                {"range":[-0.3,0.3],"color":"#e5e7eb"},
                {"range":[0.3,1],"color":"#dcfce7"},
                {"range":[1,2],"color":"#bbf7d0"},
            ],
            "threshold":{"line":{"color":"#111827","width":2},"value":v},
        },
        number={"valueformat":".2f"}
    ))
    fig.update_layout(height=260, margin=dict(l=10,r=10,t=10,b=10))
    return fig

# -------- Load & show data --------
try:
    df = load_sheet()
except Exception as e:
    st.error(f"Fehler beim Laden des Sheets: {e}")
    st.stop()

# KPIs
c1,c2,c3,c4 = st.columns(4)
c1.metric("Assets", len(df))
c2.metric("Long", int((df.get("Bias","")== "Long").sum()) if "Bias" in df else 0)
c3.metric("Neutral", int((df.get("Bias","")== "Neutral").sum()) if "Bias" in df else 0)
c4.metric("Short", int((df.get("Bias","")== "Short").sum()) if "Bias" in df else 0)

st.markdown("---")

st.subheader("Overview")
st.plotly_chart(make_overview_table(df.copy()), use_container_width=True)

st.markdown("---")

# Detail
if "Underlying" in df.columns:
    st.subheader("Asset Detail")
    left, right = st.columns([1,2])
    asset = left.selectbox("Select asset", df["Underlying"].unique().tolist())
    row = df[df["Underlying"]==asset].iloc[0]

    # badges
    left.markdown(
        pill(row.get("Regime",""), REGIME_COLORS.get(row.get("Regime",""), "#9aa0a6")) + " " +
        pill(row.get("Bias",""),   BIAS_COLORS.get(row.get("Bias",""), "#9aa0a6")) + " " +
        pill(row.get("Recommendation",""), REC_COLORS.get(row.get("Recommendation",""), "#9aa0a6")),
        unsafe_allow_html=True
    )
    left.write({
        "Spot": row.get("Spot"),
        "Gamma Flip": row.get("Gamma Flip"),
        "Put Wall": row.get("Put Wall"),
        "Call Wall": row.get("Call Wall"),
        "Score": row.get("Score")
    })
    left.plotly_chart(score_gauge(row.get("Score")), use_container_width=True)
    right.plotly_chart(levels_chart(row), use_container_width=True)

st.caption("Live from Google Sheets (read-only). Cache TTL 30s – Seite neu laden für Sofort-Refresh.")
