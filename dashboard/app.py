"""NSE Catalyst dashboard navigation."""
import streamlit as st

st.set_page_config(page_title="NSE Catalyst", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

master = st.Page("master_dashboard.py", title="NSE Catalyst", icon="📊", default=True)
analysis = st.Page("analysis_center.py", title="Analysis", icon="📈")
historical = st.Page("historical_data.py", title="Closed Data", icon="📚")

# Keep navigation visible on mobile and desktop.
pg = st.navigation([master, analysis, historical], position="top")
pg.run()
