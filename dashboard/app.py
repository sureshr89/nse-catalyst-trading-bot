"""NSE Catalyst: one combined master paper-trading dashboard."""
import streamlit as st

# The master dashboard owns page configuration and contains S1-S5 together.
master = st.Page("master_dashboard.py", title="NSE Catalyst", icon="📊", default=True)
pg = st.navigation([master], position="hidden")
pg.run()
