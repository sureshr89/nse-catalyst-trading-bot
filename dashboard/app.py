"""NSE Catalyst Streamlit entry point."""
from pathlib import Path
import runpy,sys
import streamlit as st
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
st.set_page_config(page_title="NSE Catalyst",page_icon="📊",layout="wide",initial_sidebar_state="collapsed")
try:
 import market.nifty500_breadth as _breadth_module
 _breadth_module.index_quote=lambda *args,**kwargs:None
except Exception: pass
_original_set_page_config=st.set_page_config
_original_download=st.download_button
# The old dashboard contains download buttons before the strategy library.
# Suppress those old buttons; the enhancements module renders downloads last.
st.download_button=lambda *args,**kwargs:None
st.set_page_config=lambda *args,**kwargs:None
try:
 runpy.run_path(str(ROOT/"dashboard"/"single_master.py"),run_name="__nse_catalyst_dashboard__")
 from dashboard.enhancements import render_enhancements
 render_enhancements()
except Exception as exc:
 st.error("The dashboard could not start.")
 st.exception(exc)
finally:
 st.download_button=_original_download
 st.set_page_config=_original_set_page_config
