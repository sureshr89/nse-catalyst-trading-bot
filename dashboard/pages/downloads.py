from pathlib import Path
import sys
import json
from io import BytesIO
from copy import copy
from datetime import datetime
from dateutil.relativedelta import relativedelta

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
from dashboard.nav import render_nav
from dashboard.style import load_css
from dashboard.daily_footer import render_daily_footer
from bot_runner import ensure_bot_running
from master_data import build_master_data

st.set_page_config(page_title="NSE Catalyst | Downloads", page_icon="⬇️", layout="wide")
st.markdown(load_css(), unsafe_allow_html=True)
render_nav(24)
try:
    ensure_bot_running()
except Exception as error:
    st.warning(f"Worker launcher: {type(error).__name__}: {error}")


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


def read_csv(name):
    try:
        path = ROOT / "outputs" / name
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _month_series(frame, columns):
    for column in columns:
        if column in frame.columns:
            values = pd.to_datetime(frame[column], errors="coerce")
            if values.notna().any():
                return values.dt.strftime("%Y-%m")
    return pd.Series([None] * len(frame), index=frame.index, dtype="object")


def filter_month(frame, month, date_columns):
    if frame.empty:
        return frame
    return frame.loc[_month_series(frame, date_columns).eq(month)].copy()


def last_six_calendar_months():
    now = datetime.now()
    first = now.replace(day=1)
    return [(first - relativedelta(months=i)).strftime("%Y-%m") for i in range(6)]


def signal_quality(row):
    """Research-only score. Never used by the trading engine."""
    score = 0
    reasons = []
    side = str(row.get("signal", row.get("buy_sell", ""))).upper()
    required = "BULLISH" if side == "BUY" else "BEARISH" if side == "SELL" else ""
    for field, points, label in [("market_direction", 30, "NIFTY 500 aligned"), ("sector_direction", 30, "Sector aligned"), ("stock_direction", 20, "Stock aligned")]:
        if required and str(row.get(field, "")).upper() == required:
            score += points
            reasons.append(label)
    try:
        gap = abs(float(row.get("gap_percent", 0) or 0))
        if gap > 0:
            score += 10
            reasons.append(f"Gap {gap:.2f}%")
    except Exception:
        pass
    try:
        entry = pd.to_datetime(row.get("entry_time"), errors="coerce")
        if not pd.isna(entry):
            minute = entry.hour * 60 + entry.minute
            if 585 <= minute <= 615:
                score += 10
                reasons.append("Early-window entry")
            elif 615 < minute <= 660:
                score += 5
                reasons.append("Mid-morning entry")
    except Exception:
        pass
    return score, " • ".join(reasons)


def enrich_trade_data(frame):
    if frame.empty:
        return frame
    out = frame.copy()
    scores = out.apply(signal_quality, axis=1)
    out["Signal Quality Score"] = [x[0] for x in scores]
    out["Why This Trade"] = [x[1] or "Recorded setup context only" for x in scores]
    # Preserve any real execution values already recorded; never manufacture MAE/MFE.
    if "mae" not in out.columns:
        out["mae"] = pd.NA
    if "mfe" not in out.columns:
        out["mfe"] = pd.NA
    return out


def monthly_record_counts():
    counts = {m: 0 for m in last_six_calendar_months()}
    for filename, date_columns in [("MASTER_DAILY_STOCK_DATA.csv", ["TradeDate"]), ("MASTER_TRADES.csv", ["TradeDate", "entry_time", "exit_time"]), ("MASTER_DAILY_SUMMARY.csv", ["TradeDate"])]:
        frame = read_csv(filename)
        if frame.empty:
            continue
        keys = _month_series(frame, date_columns)
        for month in counts:
            counts[month] += int(keys.eq(month).sum())
    return counts


def build_monthly_master_excel(month):
    daily_stock = read_csv("MASTER_DAILY_STOCK_DATA.csv")
    trades = enrich_trade_data(read_csv("MASTER_TRADES.csv"))
    if trades.empty:
        trades = enrich_trade_data(read_csv("trades.csv"))
    signals = read_csv("signals.csv")
    sheets = {
        "Daily Stock Inputs": (daily_stock, ["TradeDate"]),
        "All Trades": (trades, ["TradeDate", "entry_time", "exit_time"]),
        "Daily Summary": (read_csv("MASTER_DAILY_SUMMARY.csv"), ["TradeDate"]),
        "Gap Board": (daily_stock, ["TradeDate"]),
        "Signals": (signals, ["timestamp"]),
    }
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, (frame, date_columns) in sheets.items():
            monthly = filter_month(frame, month, date_columns)
            if sheet_name == "Gap Board" and not monthly.empty:
                gap_columns = [c for c in ["TradeDate", "Symbol", "PreviousClose", "TodayOpen", "Gap", "GapPercent", "GapType", "PDH", "PDL", "GapFromPreviousClose", "GapPercentFromPreviousClose", "PreviousDayTurnover", "LiquidityQualified", "DataSnapshotIST"] if c in monthly.columns]
                monthly = monthly[gap_columns]
            if monthly.empty:
                monthly = pd.DataFrame({"Status": [f"No records for {month}"]})
            monthly.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.book[sheet_name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for column_cells in ws.columns:
                values = [str(cell.value) if cell.value is not None else "" for cell in list(column_cells)[:300]]
                width = min(max(max((len(v) for v in values), default=10) + 2, 10), 32)
                ws.column_dimensions[column_cells[0].column_letter].width = width
            for cell in ws[1]:
                new_font = copy(cell.font)
                new_font.bold = True
                cell.font = new_font
        pd.DataFrame([["Month", month], ["Purpose", "NIFTY 500 paper-trading research master data"], ["Strategy Gap Definition", "GAP_UP_PDH = Today's Open > PDH; GAP_DOWN_PDL = Today's Open < PDL"], ["Sheets", "Daily Stock Inputs, All Trades, Daily Summary, Gap Board, Signals"], ["Research Fields", "Signal Quality Score, Why This Trade, MAE, MFE (when actually recorded)"], ["Generated", pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d %H:%M:%S IST")]], columns=["Field", "Value"]).to_excel(writer, sheet_name="README", index=False)
        writer.book["README"].freeze_panes = "A2"
    output.seek(0)
    return output.getvalue()

try:
    build_master_data()
except Exception as error:
    st.warning(f"Master data refresh warning: {type(error).__name__}: {error}")

st.title("⬇️ Downloads")
st.caption("NIFTY 500 PDH/PDL → today's Open 1-minute reversal paper-trading records, premarket PDH/PDL gap board and master research data.")

trades_frame = enrich_trade_data(read_csv("trades.csv"))
signals_frame = read_csv("signals.csv")
trades_data = trades_frame.to_csv(index=False).encode("utf-8") if not trades_frame.empty else csv_bytes("trades.csv", ["status", "symbol", "signal", "entry_time", "exit_time", "entry", "stop_loss", "target", "quantity", "pnl", "setup_type", "Signal Quality Score", "Why This Trade", "mae", "mfe"])
signals_data = signals_frame.to_csv(index=False).encode("utf-8") if not signals_frame.empty else csv_bytes("signals.csv", ["timestamp", "symbol", "signal", "entry", "stop_loss", "target", "setup_type", "approved", "reason"])
gap_data = csv_bytes("gap_analysis.csv", ["Symbol", "PreviousClose", "TodayOpen", "Gap", "GapPercent", "GapType", "PDH", "PDL", "GapFromPreviousClose", "GapPercentFromPreviousClose", "PreparedAtIST"])
status_data = json_bytes("bot_status.json", {"status": "WAITING", "worker_alive": False})
engine_data = json_bytes("paper_engine_state.json", {"open_positions": {}, "available_capital": 250000})
diag_data = json_bytes("scanner_diagnostics.json", {"stocks_scanned": 0, "gap_up_count": 0, "gap_down_count": 0, "final_signals": 0, "strategy": "NIFTY_500_PDH_PDL_OPEN_REVERSAL"})

st.subheader("⭐ Master Trading Data — Last 6 Months")
st.caption("Each selected monthly workbook contains the current research fields used by Strategy Insights. Existing MAE/MFE values are preserved; missing historical values remain blank.")
six_months = last_six_calendar_months()
counts = monthly_record_counts()
month_rows = pd.DataFrame([{"Month": pd.Timestamp(month + "-01").strftime("%B %Y"), "File": f"NSE_CATALYST_MASTER_TRADING_DATA_{month}.xlsx", "Records": counts.get(month, 0), "Status": "Available" if counts.get(month, 0) else "No data yet"} for month in six_months])
st.dataframe(month_rows, use_container_width=True, hide_index=True, height=255)
selected_month = st.selectbox("📅 Select a month to download", six_months, format_func=lambda x: pd.Timestamp(x + "-01").strftime("%B %Y"), index=0, key="master_month_select")
monthly_excel = build_monthly_master_excel(selected_month)
st.download_button(f"⬇️ DOWNLOAD MASTER — {pd.Timestamp(selected_month + '-01').strftime('%B %Y')}", data=monthly_excel, file_name=f"NSE_CATALYST_MASTER_TRADING_DATA_{selected_month}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_master_monthly_excel", width="stretch")
st.caption("Monthly workbook: Daily Stock Inputs • All Trades + research fields • Daily Summary • Gap Board • Signals • README")

st.subheader("Paper Trading Files")
st.download_button("⬇️ TRADES CSV", data=trades_data, file_name="nifty500_trades.csv", mime="text/csv", key="download_trades_csv", width="stretch")
st.download_button("⬇️ SIGNALS CSV", data=signals_data, file_name="nifty500_pdh_pdl_signals.csv", mime="text/csv", key="download_signals_csv", width="stretch")
st.download_button("⬇️ BOT STATUS JSON", data=status_data, file_name="nifty500_bot_status.json", mime="application/json", key="download_bot_status_json", width="stretch")
st.download_button("⬇️ PAPER STATE JSON", data=engine_data, file_name="nifty500_paper_engine_state.json", mime="application/json", key="download_paper_engine_json", width="stretch")
st.download_button("⬇️ SCANNER DIAGNOSTICS JSON", data=diag_data, file_name="nifty500_scanner_diagnostics.json", mime="application/json", key="download_scanner_diagnostics_json", width="stretch")
st.download_button("⬇️ PREMARKET GAP BOARD CSV", data=gap_data, file_name="nifty500_premarket_gap_board.csv", mime="text/csv", key="download_gap_board_csv", width="stretch")

st.subheader("Premarket Gap Board — PDH/PDL based")
gaps = read_csv("gap_analysis.csv")
if not gaps.empty and "GapType" in gaps.columns:
    gaps["GapPercent"] = pd.to_numeric(gaps["GapPercent"], errors="coerce")
    a, b = st.columns(2)
    with a:
        st.markdown("**🟢 Gap Ups — Open > PDH**")
        st.dataframe(gaps[gaps["GapType"].eq("GAP_UP_PDH")].sort_values("GapPercent", ascending=False).head(30), width="stretch", hide_index=True, height=350)
    with b:
        st.markdown("**🔴 Gap Downs — Open < PDL**")
        st.dataframe(gaps[gaps["GapType"].eq("GAP_DOWN_PDL")].sort_values("GapPercent").head(30), width="stretch", hide_index=True, height=350)
else:
    st.info("The PDH/PDL gap board is created automatically from the first market data after 09:15 and prepared before the 09:45 entry window.")

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

render_daily_footer()
