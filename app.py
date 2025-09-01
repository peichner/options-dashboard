import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ---------------- Page setup ----------------
st.set_page_config(page_title="Market Dashboard", page_icon="📈", layout="wide")
st.title("Market Dashboard")

# ---------------- Google Sheets I/O ----------------
def _authorize():
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def load_range(sheet_id: str, tab: str, cell_range: str = "A1:F10") -> pd.DataFrame:
    gc = _authorize()
    ws = gc.open_by_key(sheet_id).worksheet(tab)
    values = ws.get(cell_range)  # Liste von Listen
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    df = pd.DataFrame(rows, columns=header)
    # Numerische Spalten (falls vorhanden) konvertieren
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="ignore")
    return df

SHEET_ID = st.secrets["SHEET_ID"]
SHEET_TAB = st.secrets["SHEET_TAB"]
df = load_range(SHEET_ID, SHEET_TAB, "A1:F10")

if df.empty:
    st.info("Keine Daten in A1:F10 gefunden.")
else:
    # Optionale einfache Farblogik für 'Bias' (Spalte F)
    def bias_color(val: str):
        if isinstance(val, str):
            v = val.lower()
            if "long" in v:   return "background-color:#16a34a;color:white"
            if "short" in v:  return "background-color:#dc2626;color:white"
            if "neutral" in v:return "background-color:#9aa0a6;color:white"
        return ""
    styled = df.style.applymap(bias_color, subset=[col for col in df.columns if col.lower()=="bias"])

    st.dataframe(styled, use_container_width=True)

st.caption("Live aus Google Sheets • Bereich: A1:F10 • Cache: 30s")
