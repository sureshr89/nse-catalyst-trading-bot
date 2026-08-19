"""NSE Catalyst: combined paper-trading dashboard with historical data page."""
import streamlit as st

master = st.Page("master_dashboard.py", title="NSE Catalyst", icon="📊", default=True)
historical = st.Page("historical_data.py", title="Historical / Previous Day", icon="📚")
pg = st.navigation([master, historical], position="hidden")
pg.run()
