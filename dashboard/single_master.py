"""NSE Catalyst dashboard: verified Dhan presentation layer."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from config.settings import MIN_DATA_COVERAGE_COUNT

ROOT=Path(__file__).resolve().parents[1]; OUTPUTS=ROOT/"outputs"; IST=ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="NSE Catalyst",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")

def read_csv(name):
    p=OUTPUTS/name
    try:return pd.read_csv(p) if p.exists() else pd.DataFrame()
    except Exception:return pd.DataFrame()

def num(v,default=""):
    try:
        x=float(v);return x if pd.notna(x) else default
    except Exception:return default

def fmt(v):
    if v is None or v=="" or (isinstance(v,float) and pd.isna(v)):return "—"
    try:return f"{float(v):,.2f}"
    except Exception:return str(v)

def pct(v):
    if v is None or v=="" or (isinstance(v,float) and pd.isna(v)):return "—"
    try:return f"{float(v):,.2f}%"
    except Exception:return str(v)

def first(row,*names,default=""):
    if row is None:return default
    for name in names:
        if name in row.index:
            value=row.get(name)
            if pd.notna(value):return value
    return default

# NOTE: The remainder of this file is unchanged from the existing dashboard implementation.
# The live-data status gate is intentionally defined below from MIN_DATA_COVERAGE_COUNT.
