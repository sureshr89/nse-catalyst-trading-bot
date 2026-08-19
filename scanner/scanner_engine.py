"""Stateful NIFTY 500 scanner for PDH/PDL + Today's Open return strategy."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import pandas as pd
from config.settings import TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO, NIFTY500_MIN_CHANGE_PCT
from data.reference_store import ReferenceStore
from data.stock_universe import StockUniverse
from market.price_data import PriceData
from market.live_price import get_current_market_price
from strategy.open_reversal_engine import OpenReversalEngine
from strategy.candidate_metrics import metrics, sort_key

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class ScannerEngine:
    """Maintain BUY/SELL waiting states across short control cycles."""
    def __init__(self):
        self.universe_engine = StockUniverse()
        self.universe = self.universe_engine.get_dataframe(refresh=False)
        self.price_data = PriceData()
        self.strategy = OpenReversalEngine(TRADING_START, LAST_ENTRY_TIME, RISK_REWARD_RATIO)
        self.references = pd.DataFrame()
        self.opening_candidates = pd.DataFrame()
        self.gap_analysis = pd.DataFrame()
        self.universe_market_data = {}
        self.nifty500_market_data = pd.DataFrame()
        self._prepared_date = None
        self._data_cache_at = None
        self._daily_cache_at = None
        self._nifty_cache_at = None
        self._nifty_change = 0.0
        self.daily_open_data = {}
        self._activated = {"BUY": False, "SELL": False}
        self._activated_at = {"BUY": None, "SELL": None}
        self.waiting = {"BUY": {}, "SELL": {}}
        self.qualified = {"BUY": {}, "SELL": {}}
        self.metrics_cache = {}
        self._load_waiting()
        self.diagnostics = self._empty_diagnostics()

    def _empty_diagnostics(self):
        return {
            "timestamp": None,
            "strategy": self.strategy.strategy_id,
            "strategy_name": self.strategy.strategy_name,
            "strategy_version": self.strategy.strategy_version,
            "stocks_scanned": 0,
            "reference_data_count": 0,
            "opening_setup_passed": 0,
            "market_alignment_passed": 0,
            "strategy_setup_passed": 0,
            "final_signals": 0,
            "gap_up_count": 0,
            "gap_down_count": 0,
            "gap_data_count": 0,
            "nifty500_direction": "UNKNOWN",
            "nifty500_change_pct": 0.0,
            "nifty500_bullish": 0,
            "nifty500_bearish": 0,
            "nifty500_neutral": 0,
            "nifty500_coverage": 0,
            "market_data_coverage": 0.0,
            "data_quality": "UNKNOWN",
            "data_age_seconds": None,
            "buy_waiting": 0,
            "sell_waiting": 0,
            "buy_qualified": 0,
            "sell_qualified": 0,
            "ranking": [],
            "rejections": {},
        }

    @staticmethod
    def _today():
        return pd.Timestamp.now(tz=INDIA_TZ).strftime("%Y-%m-%d")

    @staticmethod
    def _candidate_id(symbol, side, today_open, pdh, pdl):
        return "|".join([pd.Timestamp.now(tz=INDIA_TZ).strftime("%Y-%m-%d"), str(symbol).upper(), str(side).upper(), f"{float(today_open):.4f}", f"{float(pdh):.4f}", f"{float(pdl):.4f}"])

    def _waiting_path(self):
        return Path(__file__).resolve().parents[1] / "outputs" / "waiting_candidates.json"

    def _load_waiting(self):
        try:
            payload = json.loads(self._waiting_path().read_text(encoding="utf-8"))
            if payload.get("date") != self._today() or payload.get("strategy_version") not in (None, self.strategy.strategy_version): return
            self.waiting = payload.get("waiting", {"BUY": {}, "SELL": {}}); self.qualified = payload.get("qualified", {"BUY": {}, "SELL": {}}); self._activated = payload.get("activated", {"BUY": False, "SELL": False}); self._activated_at = payload.get("activated_at", {"BUY": None, "SELL": None})
        except Exception: pass

    def _save_waiting(self):
        path = self._waiting_path(); path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps({"date": self._today(), "updated_at": datetime.now(INDIA_TZ).isoformat(timespec="seconds"), "strategy": self.strategy.strategy_id, "strategy_version": self.strategy.strategy_version, "activated": self._activated, "activated_at": self._activated_at, "waiting": self.waiting, "qualified": self.qualified}, indent=2, default=str), encoding="utf-8"); tmp.replace(path)
        except Exception as error: print("Could not persist waiting candidates:", error)

    def _write_diagnostics(self):
        self.diagnostics.update({"buy_waiting": len(self.waiting["BUY"]), "sell_waiting": len(self.waiting["SELL"]), "buy_qualified": len(self.qualified["BUY"]), "sell_qualified": len(self.qualified["SELL"])})
        payload = dict(self.diagnostics); payload["rejections"] = dict(self.diagnostics.get("rejections", {})); payload["timestamp"] = datetime.now(INDIA_TZ).isoformat(timespec="seconds")
        path = Path(__file__).resolve().parents[1] / "outputs" / "scanner_diagnostics.json"; path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_name("scanner_diagnostics.tmp")
        try: tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8"); tmp.replace(path)
        except Exception as error: print("Could not write diagnostics:", error)

    def _write_gap_analysis(self, rows):
        path = Path(__file__).resolve().parents[1] / "outputs" / "gap_analysis.csv"; path.parent.mkdir(parents=True, exist_ok=True)
        try: pd.DataFrame(rows).to_csv(path, index=False)
        except Exception as error: print("Could not write gap analysis:", error)

    def prepare_reference_data(self, force=False):
        today = self._today()
        if not force and self._prepared_date == today and not self.references.empty: return self.references
        self.universe = self.universe_engine.get_dataframe(refresh=True)
        refs = ReferenceStore(self.universe).prepare()
        if refs is None or refs.empty:
            self.references = pd.DataFrame(); self._prepared_date = None
            self.diagnostics["rejections"]["reference_data"] = "REFERENCE_DATA_UNAVAILABLE"
            return self.references
        self.references = refs; self._prepared_date = today; self.diagnostics["reference_data_count"] = len(refs); self.diagnostics["nifty500_coverage"] = round(len(refs) / max(len(self.universe), 1), 4); return refs

    def _industry_for_symbol(self, symbol):
        try:
            row = self.universe[self.universe["Symbol"].astype(str).str.upper().eq(str(symbol).upper())] if "Symbol" in self.universe.columns else pd.DataFrame()
            if not row.empty and "Industry" in row.columns: return str(row.iloc[0]["Industry"] or "UNKNOWN").strip() or "UNKNOWN"
        except Exception: pass
        return "UNKNOWN"

    def _market_snapshot(self, symbols):
        now = datetime.now(INDIA_TZ)
        if self._data_cache_at is not None and (now - self._data_cache_at).total_seconds() < 55 and self.universe_market_data: return self.universe_market_data
        data = self.price_data.get_multi_1m(symbols); self.universe_market_data = data; self._data_cache_at = now; return data

    def _daily_open_snapshot(self, symbols):
        now = datetime.now(INDIA_TZ)
        if self._daily_cache_at is not None and (now - self._daily_cache_at).total_seconds() < 55 and self.daily_open_data: return self.daily_open_data
        self.daily_open_data = self.price_data.get_multi_daily(symbols, period="5d"); self._daily_cache_at = now; return self.daily_open_data

    def _nifty_snapshot(self):
        now = datetime.now(INDIA_TZ)
        if self._nifty_cache_at is not None and (now - self._nifty_cache_at).total_seconds() < 25: return self._nifty_change
        self.nifty500_market_data = self.price_data.get_index_1m("^CRSLDX")
        change = self.price_data.get_index_change_pct("^CRSLDX")
        if change is None: return None
        self._nifty_change = float(change); self._nifty_cache_at = now; return self._nifty_change

    def _build_gap_board(self, references, market_data, daily_open_data=None):
        rows, gaps = [], []; daily_open_data = daily_open_data or {}; today_date = datetime.now(INDIA_TZ).date()
        for _, ref in references.iterrows():
            symbol = str(ref["Symbol"]).upper(); op = None
            try:
                value = ref.get("TodayOpen")
                if pd.notna(value): op = float(value)
            except (TypeError, ValueError): pass
            if op is None:
                daily = daily_open_data.get(symbol)
                if isinstance(daily, pd.DataFrame) and not daily.empty:
                    try:
                        frame = daily.copy(); dates = pd.to_datetime(frame["Datetime"], errors="coerce") if "Datetime" in frame.columns else None
                        if dates is not None:
                            if getattr(dates.dt, "tz", None) is not None: dates = dates.dt.tz_convert(INDIA_TZ)
                            current = frame.loc[dates.dt.date.eq(today_date)]
                        else: current = frame.iloc[[-1]]
                        if not current.empty: op = float(current.iloc[0]["Open"])
                    except (TypeError, ValueError, KeyError): pass
            if op is None:
                data = market_data.get(symbol) if isinstance(market_data, dict) else None
                if data is not None and not data.empty:
                    today = self.price_data.today_only(data)
                    if not today.empty:
                        try: op = float(today.iloc[0]["Open"])
                        except (TypeError, ValueError, KeyError): pass
            if op is None: continue
            try: pdc, pdh, pdl = float(ref["PreviousDayClose"]), float(ref["PDH"]), float(ref["PDL"])
            except (TypeError, ValueError, KeyError): continue
            industry = self._industry_for_symbol(symbol)
            if op > pdh: gap_type, setup, level = "GAP_UP", "OPEN_ABOVE_PDH", pdh
            elif op < pdl: gap_type, setup, level = "GAP_DOWN", "OPEN_BELOW_PDL", pdl
            else: gap_type, setup, level = "INSIDE_PDH_PDL", "NO_GAP_SETUP", None
            gap_from_close = op - pdc; gap_pct_from_close = gap_from_close / pdc * 100 if pdc else 0.0; setup_gap = op - level if level is not None else 0.0; setup_gap_pct = setup_gap / level * 100 if level else 0.0
            gaps.append({"Symbol": symbol, "Industry": industry, "PreviousClose": round(pdc, 4), "TodayOpen": round(op, 4), "Gap": round(gap_from_close, 4), "GapPercent": round(gap_pct_from_close, 3), "GapFromPDH_PDL": round(setup_gap, 4), "GapPercentFromPDH_PDL": round(setup_gap_pct, 3), "GapFromPreviousClose": round(gap_from_close, 4), "GapPercentFromPreviousClose": round(gap_pct_from_close, 3), "GapType": gap_type, "PDH": round(pdh, 4), "PDL": round(pdl, 4), "PreparedAtIST": datetime.now(INDIA_TZ).isoformat(timespec="seconds")})
            if setup != "NO_GAP_SETUP": rows.append({"Symbol": symbol, "Industry": industry, "PDH": pdh, "PDL": pdl, "TodayOpen": op, "PreviousDayClose": pdc, "Gap": gap_from_close, "GapPercent": gap_pct_from_close, "GapFromPDH_PDL": setup_gap, "GapPercentFromPDH_PDL": setup_gap_pct, "GapFromPreviousClose": gap_from_close, "GapPercentFromPreviousClose": gap_pct_from_close, "GapType": gap_type, "OpeningSetup": setup})
        self.gap_analysis = pd.DataFrame(gaps).drop_duplicates("Symbol") if gaps else pd.DataFrame(); self.opening_candidates = pd.DataFrame(rows).drop_duplicates("Symbol") if rows else pd.DataFrame(); self._write_gap_analysis(gaps)
        self.diagnostics["gap_data_count"] = len(self.gap_analysis); self.diagnostics["gap_up_count"] = int((self.gap_analysis.get("GapType", pd.Series(dtype=str)) == "GAP_UP").sum()); self.diagnostics["gap_down_count"] = int((self.gap_analysis.get("GapType", pd.Series(dtype=str)) == "GAP_DOWN").sum()); self.diagnostics["opening_setup_passed"] = len(self.opening_candidates)
        if len(self.gap_analysis) == 0: self.diagnostics["rejections"]["opening_setup"] = "NO_CURRENT_OPEN_DATA"
        return self.opening_candidates

    def prepare_opening_candidates(self, force=False):
        refs = self.prepare_reference_data(force=force)
        if refs.empty: return pd.DataFrame()
        symbols = refs["Symbol"].astype(str).str.upper().drop_duplicates().tolist(); market = self._market_snapshot(symbols); daily = self._daily_open_snapshot(symbols)
        return self._build_gap_board(refs, market, daily)

    def _activate_side(self, side, change):
        active = self.strategy.market_aligned(side, change)
        if active and not self._activated[side]: self._activated[side] = True; self._activated_at[side] = datetime.now(INDIA_TZ).isoformat()
        return active

    def _seed_and_update(self, side, change, market_data):
        active = self._activate_side(side, change)
        if not active and not self._activated[side]: return
        for _, row in self.opening_candidates.iterrows():
            initial_side = self.strategy.initial_side(row["TodayOpen"], row["PDH"], row["PDL"])
            if initial_side != side: continue
            symbol = str(row["Symbol"]).upper(); candidate_id = self._candidate_id(symbol, side, row["TodayOpen"], row["PDH"], row["PDL"])
            if symbol not in self.waiting[side] and symbol not in self.qualified[side]:
                self.waiting[side][symbol] = {"candidate_id": candidate_id, "symbol": symbol, "side": side, "strategy": self.strategy.strategy_id, "strategy_version": self.strategy.strategy_version, "today_open": float(row["TodayOpen"]), "pdh": float(row["PDH"]), "pdl": float(row["PDL"]), "previous_day_close": float(row["PreviousDayClose"]), "gap": float(row.get("Gap", 0)), "gap_percent": float(row.get("GapPercent", 0)), "industry": row.get("Industry", "UNKNOWN"), "state": "WAITING_FOR_BREACH", "created_at": datetime.now(INDIA_TZ).isoformat(timespec="seconds")}
            state = self.waiting[side].get(symbol)
            if not state: continue
            state.setdefault("candidate_id", candidate_id); data = market_data.get(symbol); today = self.price_data.today_only(data) if data is not None else pd.DataFrame()
            if today.empty: continue
            for _, candle in today.iterrows():
                before = dict(state); state = self.strategy.update_state(state, row["TodayOpen"], row["PDH"], row["PDL"], candle["Close"], candle["Datetime"].isoformat())
                if state.get("pdh_breached") and not before.get("pdh_breached") and side == "BUY": state["state"] = "WAITING_FOR_OPEN"
                if state.get("pdl_breached") and not before.get("pdl_breached") and side == "SELL": state["state"] = "WAITING_FOR_OPEN"
                if state.get("open_returned"): state["state"] = "QUALIFIED"; state["qualified_close"] = float(candle["Close"]); state["qualified_at"] = candle["Datetime"].isoformat(); break
            if state.get("open_returned"): self.qualified[side][symbol] = state; self.waiting[side].pop(symbol, None)
            else: self.waiting[side][symbol] = state

    def _rank_qualified(self, side, market_data):
        rows = []
        for symbol, state in list(self.qualified[side].items()):
            data = market_data.get(symbol); today = self.price_data.today_only(data) if data is not None else pd.DataFrame()
            if today.empty: continue
            if symbol not in self.metrics_cache: self.metrics_cache[symbol] = metrics(self.price_data, symbol, today)
            item = dict(state); item.update(self.metrics_cache[symbol]); rows.append(item)
        rows.sort(key=sort_key, reverse=True); return rows

    def _final_signals(self, change, market_data):
        signals, ranking = [], []
        for side in ("BUY", "SELL"):
            if not self.strategy.market_aligned(side, change): continue
            for item in self._rank_qualified(side, market_data):
                symbol = item["symbol"]; current = get_current_market_price(symbol)
                if not current: continue
                entry = float(current["Close"]); open_price = float(item["today_open"])
                if side == "BUY" and entry < open_price: continue
                if side == "SELL" and entry > open_price: continue
                signal = self.strategy.build_signal(symbol, side, entry, open_price, item["pdh"], item["pdl"], change, {"metrics_calculated_at": item.get("metrics_calculated_at", "")})
                if signal:
                    signal.update({"candidate_id": item.get("candidate_id"), "industry": item.get("industry", "UNKNOWN"), "gap": item.get("gap", 0), "gap_percent": item.get("gap_percent", 0), "gap_type": "GAP_UP" if side == "BUY" else "GAP_DOWN", "nifty500_universe": True, "candidate_state": "QUALIFIED", "priority_rank": len(ranking) + 1})
                    ranking.append({"priority": len(ranking) + 1, "candidate_id": item.get("candidate_id"), "symbol": symbol, "side": side, "gap_percent": item.get("gap_percent", 0), "strategy_version": self.strategy.strategy_version}); signals.append(signal)
        self.diagnostics["ranking"] = ranking; return signals

    def scan(self):
        self.diagnostics = self._empty_diagnostics(); refs = self.prepare_reference_data()
        if refs.empty: self.diagnostics["rejections"]["missing_data"] = "REFERENCE_DATA_UNAVAILABLE"; return self._finish([])
        symbols = refs["Symbol"].astype(str).str.upper().drop_duplicates().tolist(); self.diagnostics["stocks_scanned"] = len(symbols); self.diagnostics["reference_data_count"] = len(refs)
        data = self._market_snapshot(symbols); self.universe_market_data = data; available = sum(1 for s in symbols if s in data and not data[s].empty); self.diagnostics["market_data_coverage"] = round(available / len(symbols), 4) if symbols else 0.0; self.diagnostics["data_quality"] = "GOOD" if available / len(symbols) >= 0.60 else "DEGRADED" if symbols else "NO_DATA"
        daily = self._daily_open_snapshot(symbols); self._build_gap_board(refs, data, daily)
        if available == 0: self.diagnostics["rejections"]["missing_data"] = "NO_INTRADAY_STOCK_DATA"; return self._finish([])
        change = self._nifty_snapshot()
        if change is None: self.diagnostics["rejections"]["missing_data"] = "NIFTY500_INDEX_UNAVAILABLE"; return self._finish([])
        self.diagnostics["nifty500_change_pct"] = round(change, 4); self.diagnostics["nifty500_direction"] = "BULLISH" if change >= NIFTY500_MIN_CHANGE_PCT else "BEARISH" if change <= -NIFTY500_MIN_CHANGE_PCT else "NEUTRAL"; self.diagnostics["nifty500_bullish"] = int(change >= NIFTY500_MIN_CHANGE_PCT); self.diagnostics["nifty500_bearish"] = int(change <= -NIFTY500_MIN_CHANGE_PCT); self.diagnostics["nifty500_neutral"] = int(abs(change) < NIFTY500_MIN_CHANGE_PCT)
        self._seed_and_update("BUY", change, data); self._seed_and_update("SELL", change, data)
        self.diagnostics["market_alignment_passed"] = sum(1 for side in ("BUY", "SELL") if self.strategy.market_aligned(side, change)); self.diagnostics["strategy_setup_passed"] = len(self.qualified["BUY"]) + len(self.qualified["SELL"])
        signals = self._final_signals(change, data); self.diagnostics["final_signals"] = len(signals); self._save_waiting(); return self._finish(signals)

    def _finish(self, signals): self._write_diagnostics(); return signals
