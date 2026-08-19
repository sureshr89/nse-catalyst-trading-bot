"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
# single_master.py is the dashboard module itself and renders at module level.
# Execute it directly so Streamlit Cloud does not require a render_dashboard symbol.
runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")
