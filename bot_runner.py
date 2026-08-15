"""Persistent paper-trading worker for the Streamlit dashboard."""
import json, os, threading, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
try:
    import fcntl
except ImportError:
    fcntl = None
from config import settings as _settings
PREMARKET_PREP_TIME=str(getattr(_settings,"PREMARKET_PREP_TIME","09:25")); TRADING_START=str(getattr(_settings,"TRADING_START","09:45")); LAST_ENTRY_TIME=str(getattr(_settings,"LAST_ENTRY_TIME","14:00")); SQUARE_OFF_TIME=str(getattr(_settings,"SQUARE_OFF_TIME","15:00")); SCAN_INTERVAL_SECONDS=int(getattr(_settings,"SCAN_INTERVAL_SECONDS",30)); HEARTBEAT_MAX_AGE_SECONDS=90; INDIA_TZ=ZoneInfo("Asia/Kolkata"); PROJECT_ROOT=Path(__file__).resolve().parent; OUTPUT_DIR=PROJECT_ROOT/"outputs"; STATUS_FILE=OUTPUT_DIR/"bot_status.json"; STATUS_LOCK_FILE=OUTPUT_DIR/"bot_status.lock"; WORKER_LOCK_FILE=OUTPUT_DIR/"paper_bot.worker.lock"; SCANNER_DIAGNOSTICS_FILE=OUTPUT_DIR/"scanner_diagnostics.json"; _lock=threading.RLock(); _thread=None; _worker_lock_handle=None
_state={"status":"STARTING","message":"Paper bot is starting.","last_cycle":None,"last_scan":None,"last_scan_completed":None,"scan_started_at":None,"scan_duration_seconds":None,"last_signal_count":0,"last_scan_error":None,"scanner_status":"IDLE","error":None,"worker_alive":False,"heartbeat":None,"cycle_count":0,"scan_count":0,"worker_id":None,"trading_start":TRADING_START,"last_entry_time":LAST_ENTRY_TIME,"premarket_prep_time":PREMARKET_PREP_TIME,"square_off_time":SQUARE_OFF_TIME,"scan_interval_seconds":SCAN_INTERVAL_SECONDS}
def _now():return datetime.now(INDIA_TZ)
def _iso_now():return _now().isoformat(timespec="seconds")
def _worker_id():return f"pid-{os.getpid()}-thread-{threading.get_ident()}"
def _heartbeat_age_seconds(value):
    try:
        stamp=datetime.fromisoformat(str(value).replace("Z","+00:00")); stamp=stamp.replace(tzinfo=INDIA_TZ) if stamp.tzinfo is None else stamp; return max(0.0,(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds())
    except Exception:return float("inf")
def _disk_heartbeat_alive():return _heartbeat_age_seconds(_read_disk_status().get("heartbeat"))<=HEARTBEAT_MAX_AGE_SECONDS
def _read_disk_status():
    try:
        with open(STATUS_FILE,"r",encoding="utf-8") as file:return json.load(file)
    except Exception:return {}
def _with_file_lock(lock_path):
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True); handle=open(lock_path,"a+",encoding="utf-8")
    if fcntl is None:return handle
    try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB); return handle
    except BlockingIOError:handle.close();return None
def _release_file_lock(handle):
    if handle is None:return
    try:
        if fcntl is not None:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
    except Exception:pass
    try:handle.close()
    except Exception:pass
def _write_status(bot=None,**updates):
    global _state
    with _lock:
        _state.update(updates);_state["heartbeat"]=_iso_now();payload=dict(_state);payload["server_time_ist"]=_iso_now();payload["worker_alive"]=_thread is not None and _thread.is_alive()
        if bot is not None:
            try:
                session=bot.paper_engine.summary();payload.update({"open_positions":session.get("open_positions",0),"available_capital":session.get("available_capital",0.0),"used_capital":session.get("used_capital",0.0),"session_pnl":session.get("total_pnl",0.0)})
            except Exception:pass
            try:
                journal=bot.journal.summary();payload.update({"total_trades":journal.get("total_trades",0),"winning_trades":journal.get("winning_trades",0),"losing_trades":journal.get("losing_trades",0),"journal_pnl":journal.get("total_pnl",0.0)})
            except Exception:pass
            try:payload["daily_pnl"]=bot.daily_pnl;payload["cooldown_until"]=bot.cooldown_until.isoformat() if bot.cooldown_until else None
            except Exception:pass
        OUTPUT_DIR.mkdir(parents=True,exist_ok=True);status_lock=_with_file_lock(STATUS_LOCK_FILE)
        if status_lock is None:return
        temporary=OUTPUT_DIR/f"bot_status.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
        try:
            with open(temporary,"w",encoding="utf-8") as file:json.dump(payload,file,indent=2,default=str);file.flush();os.fsync(file.fileno())
            os.replace(temporary,STATUS_FILE)
        except Exception:
            try:temporary.unlink(missing_ok=True)
            except Exception:pass
        finally:_release_file_lock(status_lock)
def _persist_scanner_diagnostics(bot):
    try:
        diagnostics=getattr(bot.scanner,"diagnostics",None)
        if not isinstance(diagnostics,dict):return
        payload=dict(diagnostics);payload["rejections"]=dict(diagnostics.get("rejections",{}) or {});payload["timestamp"]=_iso_now();OUTPUT_DIR.mkdir(parents=True,exist_ok=True);temporary=OUTPUT_DIR/f"scanner_diagnostics.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
        with open(temporary,"w",encoding="utf-8") as file:json.dump(payload,file,indent=2,default=str);file.flush();os.fsync(file.fileno())
        os.replace(temporary,SCANNER_DIAGNOSTICS_FILE)
    except Exception as error:print("Could not persist scanner diagnostics:",error)
def _prepare_pre_entry_candidates(bot):
    try:
        _write_status(bot,status="PREPARING",message="Preparing NIFTY 500 PDH/PDL and today's Open setups.",scanner_status="PREPARING");references=bot.scanner.prepare_reference_data();candidates=bot.scanner.prepare_opening_candidates();_persist_scanner_diagnostics(bot)
        if references.empty or candidates.empty:
            _write_status(bot,status="WAITING",message="NIFTY 500 setup preparation incomplete; retrying.",scanner_status="ERROR",error="PDH/PDL or opening setup coverage unavailable");return False
        _write_status(bot,status="WAITING",message=f"NIFTY 500 setups ready: {len(candidates)} stocks. Waiting for {TRADING_START} IST.",scanner_status="IDLE",error=None);return True
    except Exception as error:
        _write_status(bot,status="WAITING",message="Pre-entry preparation failed; worker will retry.",scanner_status="ERROR",error=f"{type(error).__name__}: {error}");return False
def _refresh_master_data(bot=None, reason="End-of-day refresh"):
    """Refresh master research files only after the journal has the final EOD state."""
    try:
        from master_data import build_master_data
        result=build_master_data()
        _write_status(bot,master_data_refreshed_at=_iso_now(),master_data_refresh_reason=reason,master_data_error=None)
        return result
    except Exception as error:
        message=f"Master-data refresh failed: {type(error).__name__}: {error}"
        _write_status(bot,master_data_refresh_error=message)
        print(message);traceback.print_exc();return None
def _run_one_trading_day():
    from main import TradingBot
    session_date=_now().date().isoformat();bot=TradingBot();_write_status(bot,status="RUNNING",message="NIFTY 500 paper-trading bot is running.",error=None,scanner_status="IDLE",cycle_count=0,scan_count=0,worker_id=_worker_id(),session_date=session_date);pre_entry_ready=False
    while True:
        if _now().date().isoformat()!=session_date:return
        current=_now().strftime("%H:%M")
        if current<TRADING_START:
            if current>=PREMARKET_PREP_TIME and not pre_entry_ready:pre_entry_ready=_prepare_pre_entry_candidates(bot)
            elif current<PREMARKET_PREP_TIME:_write_status(bot,status="WAITING",message=f"Waiting for NIFTY 500 preparation at {PREMARKET_PREP_TIME} IST.",scanner_status="IDLE")
            time.sleep(10);continue
        if current<SQUARE_OFF_TIME:
            _write_status(bot,status="RUNNING",message="NIFTY 500 paper-trading bot is running.",last_cycle=_iso_now(),cycle_count=int(_state.get("cycle_count",0))+1);scan_started=time.monotonic();stamp=_iso_now();_write_status(bot,scanner_status="SCANNING",last_scan=stamp,scan_started_at=stamp,last_scan_error=None,scan_count=int(_state.get("scan_count",0))+1)
            try:
                bot.run_cycle();_persist_scanner_diagnostics(bot);_write_status(bot,last_signal_count=int(getattr(bot.scanner.diagnostics,"get",lambda *_:0)("final_signals",0)),last_scan_error=None,error=None)
            except Exception as error:
                message=f"Scanner/trading cycle error: {type(error).__name__}: {error}";_persist_scanner_diagnostics(bot);_write_status(bot,last_scan_error=message,error=message,status="ERROR",scanner_status="ERROR");print(message);traceback.print_exc()
            finally:_write_status(bot,scanner_status="IDLE",last_scan_completed=_iso_now(),scan_duration_seconds=round(time.monotonic()-scan_started,2))
            time.sleep(SCAN_INTERVAL_SECONDS);continue
        _write_status(bot,status="RUNNING",message="Running mandatory 15:00 IST square-off.",last_cycle=_iso_now(),scanner_status="IDLE")
        while bot.paper_engine.open_positions:
            try:bot.square_off_all()
            except Exception as error:_write_status(bot,status="ERROR",message="15:00 square-off retry failed; retrying.",error=f"{type(error).__name__}: {error}");print("15:00 square-off error:",error)
            if bot.paper_engine.open_positions:
                _write_status(bot,status="RUNNING",message=f"15:00 square-off pending: {len(bot.paper_engine.open_positions)} position(s) remain. Retrying market price.",scanner_status="IDLE");time.sleep(10)
        # The journal is now final for the session. Refresh master data AFTER square-off
        # so DailyPnL/ClosedTrades/Analysis/Downloads all include the final exits.
        _write_status(bot,status="RUNNING",message="Refreshing final daily research data after 15:00 square-off.",scanner_status="IDLE")
        _refresh_master_data(bot,reason="Final post-square-off refresh")
        _write_status(bot,status="WAITING",message="Trading day complete. All paper positions squared off at market price and master data refreshed.",scanner_status="IDLE",error=None,open_positions=0)
        return
def _run_bot():
    global _thread,_worker_lock_handle
    try:
        _write_status(status="STARTING",message="NIFTY 500 paper bot worker started.",error=None,worker_alive=True,worker_id=_worker_id())
        while True:
            now=_now()
            if now.weekday()>=5:_write_status(status="WAITING",message="Weekend. Waiting for the next Indian market session.",scanner_status="IDLE",error=None);time.sleep(30);continue
            try:
                if now.strftime("%H:%M")<SQUARE_OFF_TIME:_run_one_trading_day()
                else:_write_status(status="WAITING",message="Market session finished. Waiting for the next Indian market session.",scanner_status="IDLE",error=None);time.sleep(30)
            except Exception as error:
                message=f"Worker cycle error: {type(error).__name__}: {error}";_write_status(status="ERROR",message="Trading cycle failed; worker remains alive and will retry.",scanner_status="ERROR",error=message,last_scan_error=message);print(message);traceback.print_exc();time.sleep(5)
    except Exception as error:
        try:_write_status(status="ERROR",message="Worker bootstrap failed; dashboard watchdog will restart it.",scanner_status="ERROR",error=f"{type(error).__name__}: {error}")
        except Exception:pass
    finally:
        _release_file_lock(_worker_lock_handle);_worker_lock_handle=None
        with _lock:_thread=None;_state["worker_alive"]=False
def start_bot():
    global _thread,_worker_lock_handle
    with _lock:
        if _thread is not None and _thread.is_alive():return get_status()
        lock_handle=_with_file_lock(WORKER_LOCK_FILE)
        if lock_handle is None:
            alive=_disk_heartbeat_alive();_state["status"]="WAITING" if alive else "STOPPED";_state["message"]="Paper-bot worker is running in another Streamlit session." if alive else "Worker lock is unavailable but no fresh heartbeat was found.";_state["worker_alive"]=alive;_state["error"]=None if alive else "Worker heartbeat unavailable";return get_status()
        _worker_lock_handle=lock_handle;_thread=threading.Thread(target=_run_bot,name="nifty500-paper-trading-bot",daemon=True);_thread.start()
    return get_status()
def ensure_bot_running():
    with _lock:alive=_thread is not None and _thread.is_alive()
    return get_status() if alive else start_bot()
def get_status():
    disk_state=_read_disk_status()
    with _lock:local_alive=_thread is not None and _thread.is_alive();current=dict(_state)
    disk_fresh=_heartbeat_age_seconds(disk_state.get("heartbeat"))<=HEARTBEAT_MAX_AGE_SECONDS
    if local_alive:
        current.update(disk_state);current["worker_alive"]=True
        if not disk_fresh:current["status"]="STARTING";current["message"]="Paper-bot worker thread is alive; waiting for a fresh heartbeat.";current["error"]=None
    elif disk_fresh:current.update(disk_state);current["worker_alive"]=True
    else:current.update(disk_state);current["worker_alive"]=False;current["status"]="STOPPED";current["message"]="Paper bot worker is not running. Dashboard watchdog will restart it."
    return current
