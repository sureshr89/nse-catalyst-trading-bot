"""Streamlit page entrypoint for the read-only trading analysis."""
from pathlib import Path
import runpy

# Keep the actual analysis implementation in dashboard/analysis.py so this
# page is only a navigation entrypoint and does not duplicate trading code.
ANALYSIS_FILE = Path(__file__).resolve().parent.parent / "analysis.py"
runpy.run_path(str(ANALYSIS_FILE), run_name="__main__")
