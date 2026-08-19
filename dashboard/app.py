"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import sys

# Streamlit runs dashboard/app.py with the dashboard directory as the
# script location. Add the repository root so both `dashboard.*` and the
# root-level application packages (`engine`, `market`, `strategy`, etc.)
# resolve reliably in Streamlit Cloud.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.single_master import render_dashboard

render_dashboard()
