import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

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

@st.cache_data(ttl=300)  # 5 Minuten
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

    # numerische Spalten sauber konvertieren ("," → ".", "%" entfernen)
    for c in df.columns:
        df[c] = pd.to_numeric(
            pd.Series(df[c]).astype(str).str.replace("%", "").str.replace(",", "."),
            errors="ignore"
        )
    return df

SHEET_ID  = st.secrets["SHEET_ID"]      # z. B. "1AbC..."
SHEET_TAB = st.secrets["SHEET_TAB"]     # z. B. "Bias"

# ----------- Load both blocks -----------
df_dash = load_range(SHEET_ID, SHEET_TAB, "A1:F10", header_in_first_row=True)

gex_headers = ["Underlying", "Spot", "Gamma Flip", "Put Wall", "Call Wall",
               "Regime", "Score", "Option Bias"]
# Start bei Zeile 15, damit die Tabellen-Header aus dem Sheet NICHT doppelt erscheinen
df_gex = load_range(
    SHEET_ID, SHEET_TAB, "A15:H22",
    header_in_first_row=False, header_override=gex_headers
)

# ----------- Styling helpers -----------
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

# ----------- UI: Refresh + Zeitstempel -----------
col_l, col_r = st.columns([1,1])
with col_l:
    if st.button("🔄 Aktualisieren"):
        load_range.clear()  # Cache invalidieren
        st.experimental_rerun()
with col_r:
    st.write(f"Zuletzt aktualisiert: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

# ----------- Render -----------
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

st.caption("Live aus Google Sheets • Bereiche: Bias!A1:F10 & Bias!A15:H22 • Cache: 5 Min")
