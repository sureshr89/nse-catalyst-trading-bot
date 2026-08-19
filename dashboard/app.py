"""NSE Catalyst clean mobile-first dashboard entry point."""
from pathlib import Path
import sys
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
st.set_page_config(page_title="NSE Catalyst",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")
try:
    from dashboard.enhancements import render_enhancements
    render_enhancements()
except Exception as exc:
    st.error("The dashboard could not start.")
    st.exception(exc)
