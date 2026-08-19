"""NSE Catalyst: one combined paper-trading master dashboard."""
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
st.set_page_config(
    page_title="NSE Catalyst | Master Dashboard",
    page_icon=str(ROOT / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Single UI only. S1-S5 are shown together in master_dashboard.py.
master = st.Page("master_dashboard.py", title="NSE Catalyst", icon="📊", default=True)
pg = st.navigation([master], position="hidden")
pg.run()
