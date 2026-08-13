from pathlib import Path
import json
import streamlit as st
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
st.set_page_config(page_title="NSE Catalyst | Downloads", page_icon="⬇️", layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:.45rem .55rem 1.5rem!important}

/* NAVIGATION: always two columns per row, including mobile */
.st-key-nav_row_1,.st-key-nav_row_2{width:100%!important}
.st-key-nav_row_1 [data-testid="stHorizontalBlock"],
.st-key-nav_row_2 [data-testid="stHorizontalBlock"]{
    display:flex!important;
    flex-direction:row!important;
    flex-wrap:nowrap!important;
    width:100%!important;
    gap:.45rem!important;
}
.st-key-nav_row_1 [data-testid="stColumn"],
.st-key-nav_row_2 [data-testid="stColumn"]{
    min-width:0!important;
    width:50%!important;
    flex:1 1 50%!important;
}
.st-key-nav_row_1 [data-testid="stPageLink"],
.st-key-nav_row_2 [data-testid="stPageLink"]{width:100%!important}
.st-key-nav_row_1 [data-testid="stPageLink"] a,
.st-key-nav_row_2 [data-testid="stPageLink"] a{
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    width:100%!important;
    min-height:42px!important;
    padding:.4rem .2rem!important;
    box-sizing:border-box!important;
    border:1px solid #2b3b57!important;
    border-radius:11px!important;
    background:#142036!important;
    color:#e9f0f8!important;
    font-size:.64rem!important;
    font-weight:700!important;
    text-decoration:none!important;
}

[data-testid="stDownloadButton"] button{width:100%!important;min-height:48px!important;border:1px solid #2b3b57!important;border-radius:10px!important;font-weight:700!important}
.js-plotly-plot,.js-plotly-plot *{pointer-events:none!important;touch-action:none!important}
@media(max-width:768px){
    .block-container{padding:.35rem .35rem 1rem!important}
    .st-key-nav_row_1 [data-testid="stHorizontalBlock"],
    .st-key-nav_row_2 [data-testid="stHorizontalBlock"]{gap:.35rem!important}
    .st-key-nav_row_1 [data-testid="stPageLink"] a,
    .st-key-nav_row_2 [data-testid="stPageLink"] a{min-height:44px!important;font-size:.60rem!important}
}
</style>
""", unsafe_allow_html=True)

# Fixed 2 x 2 navigation. The main app is the entrypoint, so app.py is the
# correct Streamlit page-link target for BOT STATUS.
with st.container(key="nav_row_1"):
    a, b = st.columns(2, gap="small")
    a.page_link("app.py", label="🟢 BOT STATUS", width="stretch")
    b.page_link("pages/current_trading.py", label="📌 CURRENT TRADING", width="stretch")
with st.container(key="nav_row_2"):
    c, d = st.columns(2, gap="small")
    c.page_link("pages/analysis.py", label="📊 ANALYSIS", width="stretch")
    d.page_link("pages/downloads.py", label="⬇️ DOWNLOADS", width="stretch")

def existing_bytes(name):
    p = ROOT / "outputs" / name
    try:
        return p.read_bytes() if p.exists() else None
    except Exception:
        return None

def csv_bytes(name, columns):
    data = existing_bytes(name)
    if data is not None:
        return data
    return pd.DataFrame(columns=columns).to_csv(index=False).encode("utf-8")

def json_bytes(name, fallback):
    data = existing_bytes(name)
    if data is not None:
        return data
    return json.dumps(fallback, indent=2).encode("utf-8")

st.title("⬇️ Downloads")
st.caption("Trading records, scanner data and sector classification.")
st.subheader("Trading Data")

trades_data = csv_bytes("trades.csv", ["status", "symbol", "entry_time", "exit_time", "pnl", "sector"])
signals_data = csv_bytes("signals.csv", ["timestamp", "symbol", "signal", "price", "sector"])
status_data = json_bytes("bot_status.json", {"status": "WAITING", "worker_alive": False, "message": "No runtime status file yet."})
engine_data = json_bytes("paper_engine_state.json", {"open_positions": {}, "available_capital": 250000})

st.download_button("⬇️ ACTUAL / CAPITAL-MISSED TRADES CSV", data=trades_data, file_name="trades.csv", mime="text/csv", key="download_trades_csv", width="stretch")
st.download_button("⬇️ SCANNER SIGNALS CSV", data=signals_data, file_name="signals.csv", mime="text/csv", key="download_signals_csv", width="stretch")
st.download_button("⬇️ BOT STATUS JSON", data=status_data, file_name="bot_status.json", mime="application/json", key="download_bot_status_json", width="stretch")
st.download_button("⬇️ PAPER ENGINE STATE JSON", data=engine_data, file_name="paper_engine_state.json", mime="application/json", key="download_paper_engine_json", width="stretch")

st.subheader("🏭 Sector-wise Stock Classification")
try:
    from data.stock_universe import StockUniverse
    from data.sector_store import SectorStore
    universe = StockUniverse().get_dataframe(refresh=False)
    if universe.empty:
        universe = StockUniverse().get_dataframe(refresh=True)
    mapping = SectorStore(universe).load()
except Exception:
    mapping = pd.DataFrame()

if not mapping.empty:
    mapping = mapping.drop_duplicates("Symbol").sort_values(["Sector", "Symbol"])
    summary = mapping.groupby("Sector", dropna=False).agg(Stocks=("Symbol", "count")).reset_index().sort_values("Stocks", ascending=False)
    st.success(f"{len(mapping)} NIFTY 100 stocks classified across {len(summary)} sectors.")
    st.dataframe(summary, width="stretch", hide_index=True)
    st.download_button("⬇️ SECTOR-WISE STOCK LIST CSV", data=mapping.to_csv(index=False).encode("utf-8"), file_name="sector_wise_stock_list.csv", mime="text/csv", key="download_sector_stock_list", width="stretch")
    st.download_button("⬇️ SECTOR SUMMARY CSV", data=summary.to_csv(index=False).encode("utf-8"), file_name="sector_summary.csv", mime="text/csv", key="download_sector_summary", width="stretch")
    st.markdown("**Stocks classified by sector**")
    cols = [c for c in ["Sector", "Symbol", "SectorSource"] if c in mapping.columns]
    st.dataframe(mapping[cols], width="stretch", hide_index=True)
else:
    st.warning("Sector mapping is not available yet. The page will retry from the NIFTY 100 universe on the next refresh.")
