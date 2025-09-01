# app.py — Market Dashboard (kompakt) + Price-Lanes Visual
import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import plotly.express as px
from plotly.subplots import make_subplots

# ---------------- Page setup ----------------
st.set_page_config(page_title="Market Dashboard", page_icon="📈", layout="wide")
st.title("Market Dashboard")

# ---- rerun helper (kompatibel alt/neu) ----
def _rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

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

    # numerische Spalten robust konvertieren und auf 2 Dezimal stellen
    for c in df.columns:
        s = pd.Series(df[c]).astype(str)\
             .str.replace("%", "", regex=False)\
             .str.replace("\u00A0", "", regex=False)\
             .str.replace(",", ".", regex=False)
        num = pd.to_numeric(s, errors="coerce")
        df[c] = np.where(num.notna(), num.round(2), df[c])
    return df

SHEET_ID  = st.secrets["SHEET_ID"]   # aus Sheet-URL
SHEET_TAB = st.secrets["SHEET_TAB"]  # z. B. "Bias"

# ---------------- UI: Refresh + Zeitstempel ----------------
col_l, col_r = st.columns([1,1])
with col_l:
    if st.button("🔄 Aktualisieren"):
        load_range.clear()        # nur den Funktion-Cache leeren
        _rerun()
with col_r:
    st.write(f"Zuletzt aktualisiert: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

# ---------------- Daten laden ----------------
df_dash = load_range(SHEET_ID, SHEET_TAB, "A1:F10", header_in_first_row=True)

gex_headers = ["Underlying", "Spot", "Gamma Flip", "Put Wall", "Call Wall",
               "Regime", "Score", "Option Bias"]
df_gex = load_range(
    SHEET_ID, SHEET_TAB, "A15:H22",  # A15, um doppelte Header zu vermeiden
    header_in_first_row=False, header_override=gex_headers
)

# ---------------- Helpers ----------------
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

def to_num(x):
    """Robuste Zahlkonvertierung für EU-Format/Prozent/NBSP."""
    try:
        return float(str(x).replace("%","").replace("\u00A0","").replace(",", "."))
    except Exception:
        return np.nan

# ---------------- Tabellen ----------------
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

    # --- 1) Option Bias Score (sorted, 2 Dezimal) ---
    st.subheader("Option Bias Score (sorted)")
    df_scores = df_gex[["Underlying","Score","Option Bias"]].copy()
    df_scores["Score"] = pd.to_numeric(df_scores["Score"], errors="coerce").round(2)
    df_scores = df_scores.dropna(subset=["Score"]).sort_values("Score", ascending=False)

    fig1 = px.bar(
        df_scores, x="Score", y="Underlying", orientation="h",
        text=df_scores["Score"].map(lambda x: f"{x:.2f}"}),
        color="Option Bias", color_discrete_map=color_map_bias
    )
    fig1.update_traces(textposition="outside", cliponaxis=False)
    fig1.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10), xaxis_tickformat=".2f")
    st.plotly_chart(fig1, use_container_width=True)

    # --- 2) Price-Lanes: Put/Call Walls, Gamma Flip & Spot ---
    st.subheader("Price Lanes: Put/Call Walls, Gamma Flip & Spot")

    lanes = df_gex[["Underlying","Spot","Put Wall","Call Wall","Gamma Flip"]].copy()
    for c in ["Spot","Put Wall","Call Wall","Gamma Flip"]:
        lanes[c] = lanes[c].apply(to_num)

    lanes = lanes.dropna(how="all", subset=["Spot","Put Wall","Call Wall","Gamma Flip"])
    names = lanes["Underlying"].astype(str).tolist()

    n = len(lanes)
    if n == 0:
        st.info("Keine gültigen Lanes-Daten.")
    else:
        fig = make_subplots(
            rows=n, cols=1,
            shared_xaxes=False,
            vertical_spacing=0.07,
            subplot_titles=names
        )

        # Styles
        lane_height = 0.18  # vertikale Dicke der Schiene
        color_lane  = "#0f4c5c"
        color_put   = "#2563eb"   # blau
        color_call  = "#2563eb"
        color_flip  = "#f59e0b"   # orange
        color_spot  = "#0f4c5c"   # dunkelblau

        for i, (_, row) in enumerate(lanes.iterrows(), start=1):
            spot = row["Spot"]
            pw   = row["Put Wall"]
            cw   = row["Call Wall"]
            gf   = row["Gamma Flip"]

            # x-range mit Puffer
            pts = [v for v in [spot, pw, cw, gf] if pd.notna(v)]
            if not pts:
                continue
            xmin, xmax = min(pts), max(pts)
            pad = (xmax - xmin) * 0.06 if xmax > xmin else (abs(xmax) + 1) * 0.06
            xmin -= pad; xmax += pad

            # Schiene als Rechteck (y 0..1 Dummy)
            fig.add_shape(
                type="rect", x0=xmin, x1=xmax, y0=0.5 - lane_height/2, y1=0.5 + lane_height/2,
                line=dict(color=color_lane, width=2),
                fillcolor=color_lane, opacity=0.8,
                row=i, col=1
            )

            # Vertikale Linien
            if pd.notna(pw):
                fig.add_vline(x=pw, line_color=color_put, line_width=3, row=i, col=1)
                fig.add_annotation(x=pw, y=0.92, text="Put Wall", showarrow=False,
                                   font=dict(size=10), row=i, col=1)
            if pd.notna(cw):
                fig.add_vline(x=cw, line_color=color_call, line_width=3, row=i, col=1)
                fig.add_annotation(x=cw, y=0.92, text="Call Wall", showarrow=False,
                                   font=dict(size=10), row=i, col=1)
            if pd.notna(gf):
                fig.add_vline(x=gf, line_color=color_flip, line_width=3,
                              line_dash="dash", row=i, col=1)
                fig.add_annotation(x=gf, y=0.08, text="Gamma Flip", showarrow=False,
                                   font=dict(size=10), row=i, col=1)

            # Spot als Marker
            if pd.notna(spot):
                fig.add_scatter(
                    x=[spot], y=[0.5],
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=16,
                                line=dict(width=1, color="white"),
                                color=color_spot),
                    showlegend=False, row=i, col=1
                )
                fig.add_annotation(x=spot, y=0.75, text=f"Spot {spot:.2f}",
                                   showarrow=False, font=dict(size=10), row=i, col=1)

            fig.update_xaxes(range=[xmin, xmax], tickformat=".2f", row=i, col=1)
            fig.update_yaxes(visible=False, range=[0,1], row=i, col=1)

        fig.update_layout(
            height=120*n + 120,
            margin=dict(l=20, r=20, t=40, b=10),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

st.caption("Live aus Google Sheets • Bereiche: Bias!A1:F10 & Bias!A15:H22 • Cache: 5 Min")
