from pathlib import Path
import json
import streamlit as st
import pandas as pd
from dashboard.nav import render_nav
from dashboard.style import load_css

ROOT = Path(__file__).resolve().parents[2]
st.set_page_config(page_title="NSE Catalyst | Downloads", page_icon="⬇️", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav()


def existing_bytes(name):
    path = ROOT / "outputs" / name
    try:
        return path.read_bytes() if path.exists() else None
    except Exception:
        return None


def csv_bytes(name, columns):
    data = existing_bytes(name)
    return data if data is not None else pd.DataFrame(columns=columns).to_csv(index=False).encode("utf-8")


def json_bytes(name, fallback):
    data = existing_bytes(name)
    return data if data is not None else json.dumps(fallback, indent=2).encode("utf-8")


st.title("⬇️ Downloads")
st.caption("NIFTY 500 PDH/PDL → today's Open 1-minute reversal paper-trading records.")

trades_data = csv_bytes("trades.csv", ["status", "symbol", "signal", "entry_time", "exit_time", "entry", "stop_loss", "target", "quantity", "pnl", "setup_type"])
signals_data = csv_bytes("signals.csv", ["timestamp", "symbol", "signal", "entry", "stop_loss", "target", "setup_type", "approved", "reason"])
status_data = json_bytes("bot_status.json", {"status": "WAITING", "worker_alive": False})
engine_data = json_bytes("paper_engine_state.json", {"open_positions": {}, "available_capital": 250000})
diag_data = json_bytes("scanner_diagnostics.json", {"stocks_scanned": 0, "liquidity_passed": 0, "final_signals": 0})

st.subheader("Paper Trading Files")
st.download_button("⬇️ TRADES CSV", data=trades_data, file_name="trades.csv", mime="text/csv", key="download_trades_csv", width="stretch")
st.download_button("⬇️ SIGNALS CSV", data=signals_data, file_name="signals.csv", mime="text/csv", key="download_signals_csv", width="stretch")
st.download_button("⬇️ BOT STATUS JSON", data=status_data, file_name="bot_status.json", mime="application/json", key="download_bot_status_json", width="stretch")
st.download_button("⬇️ PAPER STATE JSON", data=engine_data, file_name="paper_engine_state.json", mime="application/json", key="download_paper_engine_json", width="stretch")
st.download_button("⬇️ SCANNER DIAGNOSTICS JSON", data=diag_data, file_name="scanner_diagnostics.json", mime="application/json", key="download_scanner_diagnostics_json", width="stretch")

st.subheader("NIFTY 500 Sector Classification")
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
    st.success(f"{len(mapping)} NIFTY 500 stocks classified across {len(summary)} sectors.")
    st.dataframe(summary, width="stretch", hide_index=True)
    st.download_button("⬇️ NIFTY 500 STOCK LIST BY SECTOR", data=mapping.to_csv(index=False).encode("utf-8"), file_name="nifty500_sector_wise_stock_list.csv", mime="text/csv", key="download_sector_stock_list", width="stretch")
else:
    st.info("NIFTY 500 sector mapping is not available yet.")
