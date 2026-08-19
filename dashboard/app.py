"""Primary NSE Catalyst Streamlit entrypoint."""
from pathlib import Path
import runpy
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
# single_master.py is the dashboard module itself and renders at module level.
# Execute it directly so Streamlit Cloud does not require a render_dashboard symbol.
runpy.run_path(str(ROOT / "dashboard" / "single_master.py"), run_name="__main__")

# Small readability adjustment only — no layout, colours, strategy, data or refresh changes.
st.markdown("""
<style>
.label{font-size:.62rem!important}
.value{font-size:1.02rem!important}
.sec{font-size:1.16rem!important}
.strategy-title{font-size:.92rem!important}
.state{font-size:.72rem!important}
.trade-label{font-size:.55rem!important}
.trade-value{font-size:.76rem!important}
.sub{font-size:.78rem!important}
.status{font-size:.79rem!important}
</style>
""", unsafe_allow_html=True)
