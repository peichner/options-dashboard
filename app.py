import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# ------------ Page setup ------------
st.set_page_config(page_title="Options Market Dashboard", page_icon="📊", layout="wide")
st.title("📊 Options Market Dashboard")
st.caption("Educational research only — no financial advice.")

# ------------ Colors / badges ------------
BIAS_COLORS = {"Long":"#16a34a", "Neutral":"#9aa0a6", "Short":"#dc2626"}
REC_COLORS  = {"Long":"#16a34a","Long+":"#0ea5e9","Long++":"#2563eb",
               "Short":"#dc2626","Short+":"#f59e0b","Short++":"#b45309","Neutral":"#9aa0a6"}
REGIME_COLORS = {"Short-Gamma (neg)":"#ef4444","Long-Gamma (pos)":"#10b981",
                 "Neutral (Flip)":"#9aa0a6","Crash Risk":"#fb7185","Breakout Risk":"#60a5fa"}

def pill(text, color):
    return f"<span style='background:{color};color:white;padding:4px 8px;border-radius:9999px;font-size:12px;'>{text}</span>"

# ------------ Google Sheets I/O ------------
def _authorize():
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def load_sheet():
    """Liest nur die Blöcke 'Overview' (oben) und 'GEX Data' ein, mergen via Underlying.
       COT DATA / Retail Positioning werden ignoriert."""
    gc = _authorize()
    ws = gc.open_by_key(st.secrets["SHEET_ID"]).worksheet(st.secrets.get("SHEET_TAB","Dashboard"))

    vals = ws.get_all_values()
    raw = pd.DataFrame(vals)

    def find_row(df, label):
        m = (df == label).any(axis=1)
        return int(m.idxmax()) if m.any() else None

    # ----- Overview-Block finden -----
    if not ((raw == "Underlying").any(axis=1)).any():
        raise ValueError("Header 'Underlying' im Overview-Block nicht gefunden.")
    hdr_over_idx = int(((raw == "Underlying").any(axis=1)).idxmax())

    gex_tag_idx = find_row(raw, "GEX Data")
    end_over_idx = (gex_tag_idx - 1) if gex_tag_idx is not None else len(raw) - 1

    over_hdr = raw.iloc[hdr_over_idx].tolist()
    over_df = raw.iloc[hdr_over_idx+1:end_over_idx+1].copy()
    over_df.columns = over_hdr
    over_df = over_df.dropna(how="all")

    # ----- GEX Data-Block -----
    if gex_tag_idx is not None:
        gex_hdr = raw.iloc[gex_tag_idx+1].tolist()
        cot_tag_idx = find_row(raw, "COT DATA")
        end_gex_idx = (cot_tag_idx - 1) if cot_tag_idx is not None else len(raw) - 1
        gex_df = raw.iloc[gex_tag_idx+2:end_gex_idx+1].copy()
        gex_df.columns = gex_hdr
        gex_df = gex_df.dropna(how="all")
    else:
        gex_df = pd.DataFrame(columns=["Underlying","Spot","Gamma Flip","Put Wall","Call Wall"])

    # trim + types
    for df_ in (over_df, gex_df):
        df_.columns = [str(c).strip() for c in df_.columns]
        if "Underlying" in df_.columns:
            df_["Underlying"] = df_["Underlying"].astype(str).str.strip()

    for c in ["Spot","Gamma Flip","Put Wall","Call Wall","Score"]:
        if c in gex_df.columns: gex_df[c] = pd.to_numeric(gex_df[c], errors="coerce")
        if c in over_df.columns: over_df[c] = pd.to_numeric(over_df[c], errors="coerce")

    # nur relevante Overview-Spalten (ohne COT/Retail)
    keep_over = [c for c in ["Underlying","Price Action","Option Bias Score","Regime","Bias","Recommendation","Score"] if c in over_df.columns]
    over_df = over_df[keep_over]

    # nur relevante GEX-Spalten
    keep_gex = [c for c in ["Underlying","Spot","Gamma Flip","Put Wall","Call Wall"] if c in gex_df.columns]
    gex_df = gex_df[keep_gex]

    # Merge
    df = pd.merge(over_df, gex_df, on="Underlying", how="left")

    # Abschnitts-/Leerzeilen entfernen
    bad_labels = {"GEX Data","COT DATA","Retail Positioning","","None","nan"}
    df = df[~df["Underlying"].isin(bad_labels)]

    return df.reset_index(drop=True)

# ------------ Plot helpers ------------
def make_overview_table(df: pd.DataFrame):
    cols = ["Underlying","Price Action","Option Bias Score","Bias","Recommendation",
            "Spot","Gamma Flip","Put Wall","Call Wall","Score","Regime"]
    cols = [c for c in cols if c in df.columns]
    dfv = df[cols].copy()

    bias_colors = [BIAS_COLORS.get(x,"#ffffff") for x in dfv.get("Bias", [""]*len(dfv))]
    rec_colors  = [REC_COLORS.get(x,"#ffffff") for x in dfv.get("Recommendation", [""]*len(dfv))]
    reg_colors  = [REGIME_COLORS.get(x,"#ffffff") for x in dfv.get("Regime", [""]*len(dfv))]

    fills = []
    for c in dfv.columns:
        if c == "Bias": fills.append(bias_colors)
        elif c == "Recommendation": fills.append(rec_colors)
        elif c == "Regime": fills.append(reg_colors)
        else: fills.append(["#ffffff"]*len(dfv))

    fig = go.Figure(data=[go.Table(
        header=dict(values=dfv.columns, fill_color="#111827", font=dict(color="white", size=12), align="left"),
        cells=dict(values=[dfv[c] for c in dfv.columns], fill_color=fills, align="left", height=28)
    )])
    fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=36+28*(len(dfv)+1))
    return fig, dfv

def levels_chart(row: pd.Series):
    fig = go.Figure()
    if pd.notna(row.get("Gamma Flip")):
        fig.add_hline(y=row["Gamma Flip"], line_dash="dot", annotation_text=f"Gamma Flip {row['Gamma Flip']}")
    if pd.notna(row.get("Put Wall")):
        fig.add_hline(y=row["Put Wall"],  line_dash="dot", annotation_text=f"Put {row['Put Wall']}")
    if pd.notna(row.get("Call Wall")):
        fig.add_hline(y=row["Call Wall"], line_dash="dot", annotation_text=f"Call {row['Call Wall']}")
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

# ------------ Load data ------------
try:
    df = load_sheet()
except Exception as e:
    st.error(f"Fehler beim Laden des Sheets: {e}")
    st.stop()

# KPIs
c1,c2,c3,c4 = st.columns(4)
c1.metric("Assets", len(df))
c2.metric("Long",    int((df["Bias"]=="Long").sum()) if "Bias" in df else 0)
c3.metric("Neutral", int((df["Bias"]=="Neutral").sum()) if "Bias" in df else 0)
c4.metric("Short",   int((df["Bias"]=="Short").sum()) if "Bias" in df else 0)

st.markdown("---")

# ------------ Overview (ohne COT/Retail) ------------
st.subheader("Overview")
table_fig, overview_df = make_overview_table(df.copy())
st.plotly_chart(table_fig, use_container_width=True)

st.markdown("---")

# ------------ Detail ------------
if "Underlying" in overview_df.columns and not overview_df.empty:
    st.subheader("Asset Detail")
    left, right = st.columns([1,2])
    asset = left.selectbox("Select asset", overview_df["Underlying"].unique().tolist())
    row = overview_df[overview_df["Underlying"]==asset].iloc[0]

    left.markdown(
        pill(str(row.get("Regime","")), REGIME_COLORS.get(row.get("Regime",""), "#9aa0a6")) + " " +
        pill(str(row.get("Bias","")),   BIAS_COLORS.get(row.get("Bias",""), "#9aa0a6")) + " " +
        pill(str(row.get("Recommendation","")), REC_COLORS.get(row.get("Recommendation",""), "#9aa0a6")),
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

st.caption("Live from Google Sheets (read-only). Cache TTL 30s – reload for instant refresh.")
