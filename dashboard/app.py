from pathlib import Path
import sys
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Streamlit Cloud can execute dashboard/app.py with the dashboard directory as
# the import root. Add the repository root explicitly so package imports such
# as dashboard.nav and bot_runner resolve consistently in Cloud and locally.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running

INDIA_TZ = ZoneInfo("Asia/Kolkata")
ENTRY_START = "09:45"
ENTRY_END = "14:00"
NIFTY_THRESHOLD = 0.25

st.set_page_config(page_title="NSE Catalyst | NIFTY 500 Bot", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
st_autorefresh(interval=5000, key="live")
