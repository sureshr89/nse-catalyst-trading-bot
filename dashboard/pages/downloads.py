from pathlib import Path
import json
import streamlit as st
import pandas as pd
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer

ROOT = Path(__file__).resolve().parents[2]
st.set_page_config(page_title="NSE Catalyst | Downloads", page_icon="⬇️", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()

def existing_bytes(name):
    path = ROOT / "outputs" / name
    try: return path.read_bytes() if path.exists() else None
    except Exception: return None

def csv_bytes(name, columns):
    data = existing_bytes(name)
    return data if data is not None else pd.DataFrame(columns=columns).to_csv(index=False).encode("utf-8")

def json_bytes(name, fallback):
    data = existing_bytes(name)
    return data if data is not None else json.dumps(fallback, indent=2).encode("utf-8")

st.title("⬇️ Downloads")
st.caption("NIFTY 500 PDH/PDL → today's Open 1-minute reversal paper-trading records and premarket gap board.")
trades_data = csv_bytes("trades.csv", ["status", "symbol", "signal", "entry_time", "exit_time", "entry", "stop_loss", "target", "quantity", "pnl", "setup_type"])
signals_data = csv_bytes("signals.csv", ["timestamp", "symbol", "signal", "entry", "stop_loss", "target", "setup_type", "approved", "reason"])
gap_data = csv_bytes("gap_analysis.csv", ["Symbol", "PreviousClose", "TodayOpen", "Gap", "GapPercent", "GapType", "PDH", "PDL", "PreparedAtIST"])
status_data = json_bytes("bot_status.json", {"status": "WAITING", "worker_alive": False})
engine_data = json_bytes("paper_engine_state.json", {"open_positions": {}, "available_capital": 250000})
diag_data = json_bytes("scanner_diagnostics.json", {"stocks_scanned": 0, "gap_up_count": 0, "gap_down_count": 0, "final_signals": 0, "strategy": "NIFTY_500_PDH_PDL_OPEN_REVERSAL"})

st.subheader("Paper Trading Files")
st.download_button("⬇️ TRADES CSV", data=trades_data, file_name="nifty500_trades.csv", mime="text/csv", key="download_trades_csv", width="stretch")
st.download_button("⬇️ SIGNALS CSV", data=signals_data, file_name="nifty500_pdh_pdl_signals.csv", mime="text/csv", key="download_signals_csv", width="stretch")
st.download_button("⬇️ BOT STATUS JSON", data=status_data, file_name="nifty500_bot_status.json", mime="application/json", key="download_bot_status_json", width="stretch")
st.download_button("⬇️ PAPER STATE JSON", data=engine_data, file_name="nifty500_paper_engine_state.json", mime="application/json", key="download_paper_engine_json", width="stretch")
st.download_button("⬇️ SCANNER DIAGNOSTICS JSON", data=diag_data, file_name="nifty500_scanner_diagnostics.json", mime="application/json", key="download_scanner_diagnostics_json", width="stretch")
st.download_button("⬇️ PREMARKET GAP BOARD CSV", data=gap_data, file_name="nifty500_premarket_gap_board.csv", mime="text/csv", key="download_gap_board_csv", width="stretch")

st.subheader("Premarket Gap Board")
try: gaps = pd.read_csv(ROOT / "outputs/gap_analysis.csv")
except Exception: gaps = pd.DataFrame()
if not gaps.empty:
    gaps["GapPercent"] = pd.to_numeric(gaps["GapPercent"], errors="coerce")
    a,b = st.columns(2)
    with a:
        st.markdown("**🟢 Gap Ups**")
        st.dataframe(gaps[gaps["GapType"].eq("GAP_UP")].sort_values("GapPercent", ascending=False).head(30), width="stretch", hide_index=True, height=350)
    with b:
        st.markdown("**🔴 Gap Downs**")
        st.dataframe(gaps[gaps["GapType"].eq("GAP_DOWN")].sort_values("GapPercent").head(30), width="stretch", hide_index=True, height=350)
else: st.info("The gap board is created automatically from the first market data after 09:15 and prepared before the 09:45 entry window.")

st.subheader("NIFTY 500 Sector Classification")
try:
    from data.stock_universe import StockUniverse
    from data.sector_store import SectorStore
    universe = StockUniverse().get_dataframe(refresh=False)
    if universe.empty: universe = StockUniverse().get_dataframe(refresh=True)
    mapping = SectorStore(universe).load()
except Exception: mapping = pd.DataFrame()
if not mapping.empty:
    mapping = mapping.drop_duplicates("Symbol").sort_values(["Sector", "Symbol"])
    summary = mapping.groupby("Sector", dropna=False).agg(Stocks=("Symbol", "count")).reset_index().sort_values("Stocks", ascending=False)
    st.success(f"{len(mapping)} NIFTY 500 stocks classified across {len(summary)} sectors.")
    st.dataframe(summary, width="stretch", hide_index=True)
    st.download_button("⬇️ NIFTY 500 STOCK LIST BY SECTOR", data=mapping.to_csv(index=False).encode("utf-8"), file_name="nifty500_sector_wise_stock_list.csv", mime="text/csv", key="download_sector_stock_list", width="stretch")
else: st.info("NIFTY 500 sector mapping is not available yet.")
render_daily_footer()
