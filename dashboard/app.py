"""NSE Catalyst dashboard navigation."""
import streamlit as st

master = st.Page("master_dashboard.py", title="NSE Catalyst", icon="📊", default=True)
analysis = st.Page("analysis_center.py", title="Analysis", icon="📈")
historical = st.Page("historical_data.py", title="Closed Data", icon="📚")
pg = st.navigation([master, analysis, historical], position="hidden")
pg.run()
