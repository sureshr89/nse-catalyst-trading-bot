"""Persistent paper-trading worker for the Streamlit dashboard."""
import json, os, threading, time, traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
try:
    import fcntl
except ImportError:
    fcntl = None
from config import settings as _settings
PREMARKET_PREP_TIME=str(getattr(_settings,"PREMARKET_PREP_TIME","09:25")); TRADING_START=str(getattr(_settings,"TRADING_START","09:45")); LAST_ENTRY_TIME=str(getattr(_settings,"LAST_ENTRY_TIME","14:00")); SQUARE_OFF_TIME=str(getattr(_settings,"SQUARE_OFF_TIME","15:00")); SCAN_INTERVAL_SECONDS=int(getattr(_settings,"SCAN_INTERVAL_SECONDS",30))
INDIA_TZ=ZoneInfo("Asia/Kolkata"); PROJECT_ROOT=Path(__file__).resolve().parent; OUTPUT_DIR=PROJECT_ROOT/"outputs"; STATUS_FILE=OUTPUT_DIR/"bot_status.json"; STATUS_LOCK_FILE=OUTPUT_DIR/"bot_status.lock"; WORKER_LOCK_FILE=OUTPUT_DIR/"paper_bot.worker.lock"
_lock=threading.RLock(); _thread=None; _worker_lock_handle=None
_state={"status":"STARTING","message":"Paper bot is starting.","last_cycle":None,"last_scan":None,"last_scan_completed":None,"scan_started_at":None,"scan_duration_seconds":None,"last_signal_count":0,"last_scan_error":None,"scanner_status":"IDLE","error":None,"worker_alive":False,"heartbeat":None,"cycle_count":0,"scan_count":0,"worker_id":None,"trading_start":TRADING_START,"last_entry_time":LAST_ENTRY_TIME,"premarket_prep_time":PREMARKET_PREP_TIME,"square_off_time":SQUARE_OFF_TIME,"scan_interval_seconds":SCAN_INTERVAL_SECONDS}

def _now(): return datetime.now(INDIA_TZ)
def _iso_now(): return _now().isoformat(timespec="seconds")
def _worker_id(): return f"pid-{os.getpid()}-thread-{threading.get_ident()}"
def _with_file_lock(lock_path):
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True); handle=open(lock_path,"a+",encoding="utf-8")
    if fcntl is None:return handle
    try: fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB); return handle
    except BlockingIOError: handle.close(); return None
def _release_file_lock(handle):
    if handle is None:return
    try:
        if fcntl is not None: fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    except Exception: pass
    try: handle.close()
    except Exception: pass

def _write_status(bot=None,**updates):
    global _state
    with _lock:
        _state.update(updates); _state["heartbeat"]=_iso_now(); payload=dict(_state); payload["server_time_ist"]=_iso_now(); payload["worker_alive"]=_thread is not None and _thread.is_alive()
        if bot is not None:
            try:
                session=bot.paper_engine.summary(); payload.update({"open_positions":session.get("open_positions",0),"available_capital":session.get("available_capital",0.0),"used_capital":session.get("used_capital",0.0),"session_pnl":session.get("total_pnl",0.0)})
            except Exception: pass
            try:
                journal=bot.journal.summary(); payload.update({"total_trades":journal.get("total_trades",0),"winning_trades":journal.get("winning_trades",0),"losing_trades":journal.get("losing_trades",0),"journal_pnl":journal.get("total_pnl",0.0)})
            except Exception: pass
            try: payload["daily_pnl"]=bot.daily_pnl; payload["cooldown_until"]=bot.cooldown_until.isoformat() if bot.cooldown_until is not None else None
            except Exception: pass
        OUTPUT_DIR.mkdir(parents=True,exist_ok=True); status_lock=_with_file_lock(STATUS_LOCK_FILE)
        if status_lock is None:return
        temporary=OUTPUT_DIR/f"bot_status.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
        try:
            with open(temporary,"w",encoding="utf-8") as file: json.dump(payload,file,indent=2,default=str); file.flush(); os.fsync(file.fileno())
            os.replace(temporary,STATUS_FILE)
        except Exception:
            try: temporary.unlink(missing_ok=True)
            except Exception: pass
        finally:_release_file_lock(status_lock)

def _ist_current_time(self): return _now().strftime("%H:%M")
def _ist_cooldown_active(self):
    if self.cooldown_until is None:return False
    now=_now().replace(tzinfo=None)
    if now>=self.cooldown_until:self.cooldown_until=None; return False
    return True
def _patch_bot_for_ist(bot):
    import types
    bot.current_time=types.MethodType(_ist_current_time,bot); bot.cooldown_active=types.MethodType(_ist_cooldown_active,bot)

def _prepare_pre_entry_candidates(bot):
    try:
        _write_status(bot,status="PREPARING",message="Preparing PDC and today's Open / gap candidates before entry time.",scanner_status="PREPARING")
        references=bot.scanner.prepare_reference_data(); candidates=bot.scanner.prepare_gap_candidates()
        if references.empty or candidates.empty:
            _write_status(bot,status="WAITING",message="Pre-entry candidate preparation incomplete; retrying before 09:45.",scanner_status="ERROR",error="PDC/today-open gap candidate coverage unavailable"); return False
        up=int((candidates["GapDirection"].astype(str).str.upper()=="GAP_UP").sum()); down=int((candidates["GapDirection"].astype(str).str.upper()=="GAP_DOWN").sum())
        _write_status(bot,status="WAITING",message=f"PDC and gap candidates ready: {len(candidates)} stocks ({up} gap-up / {down} gap-down). Waiting for {TRADING_START} IST.",scanner_status="IDLE",error=None); return True
    except Exception as error:
        _write_status(bot,status="WAITING",message="Pre-entry candidate preparation failed; worker will retry.",scanner_status="ERROR",error=f"{type(error).__name__}: {error}"); return False

def _run_one_trading_day():
    from main import TradingBot
    bot=TradingBot(); _patch_bot_for_ist(bot); _write_status(bot,status="RUNNING",message="Paper trading bot is running.",error=None,scanner_status="IDLE",cycle_count=0,scan_count=0,worker_id=_worker_id())
    while True:
        current=_now().strftime("%H:%M")
        if current<TRADING_START:
            if current>=PREMARKET_PREP_TIME:_prepare_pre_entry_candidates(bot)
            else:_write_status(bot,status="WAITING",message=f"Waiting for pre-entry preparation at {PREMARKET_PREP_TIME} IST.",scanner_status="IDLE")
            time.sleep(10); continue
        if current<SQUARE_OFF_TIME:
            _write_status(bot,status="RUNNING",message="Paper trading bot is running.",last_cycle=_iso_now(),cycle_count=int(_state.get("cycle_count",0))+1)
            original_scan=bot.scanner.scan
            try:
                def monitored_scan():
                    scan_started=time.monotonic(); stamp=_iso_now(); _write_status(bot,scanner_status="SCANNING",last_scan=stamp,scan_started_at=stamp,last_scan_error=None,scan_count=int(_state.get("scan_count",0))+1)
                    try:
                        result=original_scan(); _write_status(bot,last_signal_count=len(result) if isinstance(result,list) else 0); return result
                    except Exception as error:
                        _write_status(bot,last_scan_error=f"{type(error).__name__}: {error}",error=f"Scanner error: {type(error).__name__}: {error}"); raise
                    finally:_write_status(bot,scanner_status="IDLE",last_scan_completed=_iso_now(),scan_duration_seconds=round(time.monotonic()-scan_started,2))
                bot.scanner.scan=monitored_scan; bot.run_cycle()
            finally:
                bot.scanner.scan=original_scan
                _write_status(bot,scanner_status="IDLE")
            time.sleep(SCAN_INTERVAL_SECONDS); continue
        _write_status(bot,status="RUNNING",message="Running mandatory 15:00 IST square-off.",last_cycle=_iso_now(),scanner_status="IDLE"); bot.run_cycle()
        _write_status(bot,status="WAITING",message="Trading day complete. Waiting for the next Indian market session.",scanner_status="IDLE",error=None); return

def _run_bot():
    global _thread,_worker_lock_handle
    try:
        _write_status(status="STARTING",message="Paper bot worker started.",error=None,worker_alive=True,worker_id=_worker_id())
        while True:
            now=_now()
            if now.weekday()>=5:
                _write_status(status="WAITING",message="Weekend. Waiting for the next Indian market session.",scanner_status="IDLE",error=None); time.sleep(30); continue
            try:
                if now.strftime("%H:%M")<SQUARE_OFF_TIME:
                    _run_one_trading_day()
                else:
                    _write_status(status="WAITING",message="Market session finished. Waiting for the next Indian market session.",scanner_status="IDLE",error=None); time.sleep(30)
            except Exception as error:
                # NEVER let a single scanner/data/journal exception kill the worker.
                # Keep the worker thread alive and let the next cycle retry.
                message=f"Worker cycle error: {type(error).__name__}: {error}"
                _write_status(status="ERROR",message="Trading cycle failed; worker remains alive and will retry.",scanner_status="ERROR",error=message,last_scan_error=message)
                print(message); traceback.print_exc()
                time.sleep(5)
    except Exception as error:
        try:_write_status(status="ERROR",message="Worker bootstrap failed; dashboard watchdog will restart it.",scanner_status="ERROR",error=f"{type(error).__name__}: {error}")
        except Exception:pass
    finally:
        _release_file_lock(_worker_lock_handle); _worker_lock_handle=None
        with _lock:_thread=None; _state["worker_alive"]=False

def start_bot():
    global _thread,_worker_lock_handle
    with _lock:
        if _thread is not None and _thread.is_alive():return get_status()
        lock_handle=_with_file_lock(WORKER_LOCK_FILE)
        if lock_handle is None:
            _state["status"]="WAITING"; _state["message"]="Another paper-bot worker already owns the worker lock."; _state["worker_alive"]=False; _state["error"]=None; return get_status()
        _worker_lock_handle=lock_handle; _thread=threading.Thread(target=_run_bot,name="paper-trading-bot",daemon=True); _thread.start()
    return get_status()
def ensure_bot_running():
    with _lock:alive=_thread is not None and _thread.is_alive()
    return get_status() if alive else start_bot()
def get_status():
    try:
        with open(STATUS_FILE,"r",encoding="utf-8") as file: disk_state=json.load(file)
    except Exception:disk_state={}
    with _lock:current=dict(_state); alive=_thread is not None and _thread.is_alive()
    current.update(disk_state); current["worker_alive"]=alive
    if not alive:
        current["status"]="STOPPED"; current["message"]="Paper bot worker is not running. Dashboard watchdog will restart it."; current["error"]=current.get("error") or "Worker thread is not alive."
    return current
