from pathlib import Path
import runpy
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
SIGNALS = ROOT / "outputs" / "signals.csv"

# Clean legacy duplicate scanner rows before the page reads the journal.
try:
    df = pd.read_csv(SIGNALS)
    if not df.empty:
        dates = pd.to_datetime(df.get("timestamp", pd.Series(index=df.index)), errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        for col in ["symbol", "signal", "setup_type"]:
            if col not in df.columns:
                df[col] = ""
        key = dates + "|" + df["symbol"].astype(str).str.upper().str.strip() + "|" + df["signal"].astype(str).str.upper().str.strip() + "|" + df["setup_type"].astype(str).str.upper().str.strip()
        cleaned = df.loc[~key.duplicated(keep="first")].copy()
        if len(cleaned) != len(df):
            cleaned.to_csv(SIGNALS, index=False)
except Exception:
    pass

# Reserve the first screen position for navigation, then render the page content.
_top_nav = st.empty()
runpy.run_path(str(ROOT / "pages" / "current.py"), run_name="__main__")

with _top_nav.container(horizontal=True, gap="small"):
    st.page_link("app.py", label="🟢 BOT", icon="🟢")
    st.page_link("pages/current_trading.py", label="📌 TRADING", icon="📌")
    st.page_link("pages/analysis.py", label="📊 ANALYSIS", icon="📊")
    st.page_link("pages/downloads.py", label="⬇️ FILES", icon="⬇️")

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:1rem 1.1rem 2rem!important}
h1{font-size:1.45rem!important;line-height:1.2!important;color:#f5f8fc!important}
h2{font-size:1rem!important;color:#dce6f3!important;margin-top:1rem!important}
h3{font-size:.9rem!important;color:#dce6f3!important}
[data-testid="stMetric"]{background:#111b2d!important;border:1px solid #26344d!important;border-radius:12px!important;padding:.55rem .7rem!important;min-height:76px!important}
[data-testid="stMetricLabel"]{font-size:.68rem!important;color:#9fb0c7!important}
[data-testid="stMetricValue"]{font-size:1.1rem!important;color:#f4f7fb!important;font-weight:700!important}
[data-testid="stDataFrame"]{border:1px solid #26344d!important;border-radius:10px!important;overflow:hidden!important}
.stAlert{border-radius:10px!important}
[data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:40px!important;padding:.42rem .65rem!important;border:1px solid #2b3b57!important;border-radius:11px!important;background:#142036!important;color:#e9f0f8!important;font-size:.76rem!important;font-weight:700!important;text-decoration:none!important}
@media(max-width:768px){.block-container{padding:.6rem .5rem 1.5rem!important}h1{font-size:1.2rem!important}h2{font-size:.86rem!important}[data-testid="stMetric"]{min-height:64px!important;padding:.42rem .48rem!important}[data-testid="stMetricValue"]{font-size:.95rem!important}[data-testid="stMetricLabel"]{font-size:.61rem!important}}
</style>
""", unsafe_allow_html=True)
