"""Background paper worker for Strategy 2.

Runs independently from Strategy 1 with its own ₹2.5 lakh paper capital pool.
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scanner.scanner_engine import ScannerEngine
from strategy2_runtime import Strategy2Runtime
from config.settings import PREMARKET_PREP_TIME, TRADING_START, SQUARE_OFF_TIME, SCAN_INTERVAL_SECONDS

INDIA_TZ = ZoneInfo("Asia/Kolkata")
STATUS = Path("outputs/strategy2_status.json")
S2_GAP_FILE = Path("outputs/strategy2_gap_analysis.csv")
_lock = threading.RLock(); _thread = None; _runtime = None


def _now(): return datetime.now(INDIA_TZ)


def _write(**updates):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        current = {}
        try: current = json.loads(STATUS.read_text(encoding="utf-8"))
        except Exception: pass
        current.update(updates); current["timestamp"] = _now().isoformat(timespec="seconds")
        STATUS.write_text(json.dumps(current, indent=2, default=str), encoding="utf-8")


def _prepare(scanner):
    """Prepare and validate daily NIFTY 500 reference/opening-gap data."""
    references = scanner.prepare_reference_data(force=True)
    if references is None or references.empty:
        raise RuntimeError("NIFTY 500 reference data is unavailable or below the required coverage.")
    candidates = scanner.prepare_opening_candidates(force=True)
    if candidates is None or candidates.empty:
        raise RuntimeError("NIFTY 500 opening-gap data is unavailable; no valid Open > PDH or Open < PDL candidates were prepared.")
    gap_board = scanner.gap_analysis.copy() if scanner.gap_analysis is not None else None
    if gap_board is None or gap_board.empty:
        raise RuntimeError("Strategy 2 gap board could not be created from the prepared market data.")
    S2_GAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    gap_board.to_csv(S2_GAP_FILE, index=False)
    scanner._nifty_snapshot()
    return len(references), len(candidates)


def _run():
    global _runtime
    try:
        scanner = ScannerEngine(); _runtime = Strategy2Runtime(scanner)
        _write(status="PREPARING", message="Strategy 2 worker started; preparing NIFTY 500 reference and opening-gap data.", worker_alive=True, total_capital=250000, available_capital=_runtime.paper_engine.available_capital, open_positions=len(_runtime.paper_engine.open_positions), daily_pnl=_runtime.daily_pnl)
        prepared = False; session_date = _now().date()
        while _now().date() == session_date:
            hhmm = _now().strftime("%H:%M")
            if hhmm < PREMARKET_PREP_TIME:
                _write(status="WAITING", message=f"Waiting for preparation at {PREMARKET_PREP_TIME} IST.", worker_alive=True); time.sleep(10); continue
            if not prepared:
                try:
                    _write(status="PREPARING", message="Preparing and validating Strategy 2 opening-gap candidates.", worker_alive=True)
                    ref_count, candidate_count = _prepare(scanner); prepared = True
                    _write(status="READY", message=f"Strategy 2 data ready: {ref_count} references, {candidate_count} opening-gap candidates.", worker_alive=True, reference_count=ref_count, opening_candidate_count=candidate_count, last_error="")
                except Exception as error:
                    _write(status="DATA_ERROR", message=f"Preparation failed: {type(error).__name__}: {error}", worker_alive=True, last_error=f"{type(error).__name__}: {error}", reference_count=0, opening_candidate_count=0)
                    time.sleep(30); continue
            if hhmm < TRADING_START:
                time.sleep(10); continue
            if hhmm < SQUARE_OFF_TIME:
                started = _now()
                try:
                    _write(status="SCANNING", message="Strategy 2 is scanning every 30 seconds.", worker_alive=True)
                    scanner._nifty_snapshot(); signals = _runtime.run_cycle()
                    _write(status="RUNNING", message="Strategy 2 paper worker is running.", worker_alive=True, last_scan=started.isoformat(timespec="seconds"), last_signal_count=len(signals or []), diagnostics=_runtime.diagnostics, available_capital=_runtime.paper_engine.available_capital, open_positions=len(_runtime.paper_engine.open_positions), daily_pnl=_runtime.daily_pnl, nifty500_change_pct=scanner._nifty_change, last_error="")
                except Exception as error:
                    _write(status="ERROR", message=f"Strategy 2 scan error: {type(error).__name__}: {error}", worker_alive=True, last_error=f"{type(error).__name__}: {error}")
                time.sleep(SCAN_INTERVAL_SECONDS); continue
            try: _runtime.square_off_all()
            except Exception as error:
                _write(status="ERROR", message=f"Strategy 2 square-off error: {type(error).__name__}: {error}", worker_alive=True, last_error=f"{type(error).__name__}: {error}"); time.sleep(10); continue
            _write(status="WAITING", message="Strategy 2 session complete; positions squared off.", worker_alive=True, available_capital=_runtime.paper_engine.available_capital, open_positions=len(_runtime.paper_engine.open_positions), daily_pnl=_runtime.daily_pnl); return
    except Exception as error:
        _write(status="ERROR", message=f"Strategy 2 worker stopped: {type(error).__name__}: {error}", worker_alive=False, last_error=f"{type(error).__name__}: {error}")
    finally:
        with _lock:
            global _thread
            _thread = None


def ensure_strategy2_running():
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive(): return
        _thread = threading.Thread(target=_run, name="strategy2-paper-worker", daemon=True); _thread.start()


def get_strategy2_status():
    try: return json.loads(STATUS.read_text(encoding="utf-8"))
    except Exception: return {"status":"STARTING","message":"Strategy 2 worker is starting.","worker_alive":False,"total_capital":250000,"available_capital":250000,"open_positions":0,"daily_pnl":0}
