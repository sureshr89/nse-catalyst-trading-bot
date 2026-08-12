"""Paper-trading package bootstrap with durable runtime recovery."""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from . import paper_trade_engine as _engine
from .persistent_storage import restore, sync

_STATE_FILE = "outputs/paper_engine_state.json"

_original_init = _engine.PaperTradeEngine.__init__
_original_open = _engine.PaperTradeEngine.open_trade
_original_close = _engine.PaperTradeEngine.close_position


def _persist(engine):
    try:
        path = Path(_STATE_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "open_positions": engine.open_positions,
            "closed_positions": engine.closed_positions[-100:],
            "trade_counter": engine.trade_counter,
            "available_capital": engine.available_capital,
            "used_capital": engine.used_capital,
        }
        path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )
        sync(_STATE_FILE, _STATE_FILE, "Persist paper engine state")
    except Exception as error:
        print(f"Paper state persistence skipped: {type(error).__name__}: {error}")


def _restore(engine):
    try:
        restore(_STATE_FILE, _STATE_FILE)
        path = Path(_STATE_FILE)
        if not path.exists() or path.stat().st_size == 0:
            return
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("date") != datetime.now().strftime("%Y-%m-%d"):
            return
        engine.open_positions = state.get("open_positions", {}) or {}
        engine.closed_positions = state.get("closed_positions", []) or []
        engine.trade_counter = int(state.get("trade_counter", 0) or 0)
        engine.available_capital = float(
            state.get("available_capital", engine.total_capital) or engine.total_capital
        )
        engine.used_capital = float(state.get("used_capital", 0) or 0)
    except Exception as error:
        print(f"Paper state restore skipped: {type(error).__name__}: {error}")


def _init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    _restore(self)


def _open(self, trade):
    result = _original_open(self, trade)
    if isinstance(result, dict) and result.get("opened"):
        _persist(self)
    return result


def _close(self, symbol, exit_price, exit_time, reason):
    result = _original_close(self, symbol, exit_price, exit_time, reason)
    if result is not None:
        _persist(self)
    return result


_engine.PaperTradeEngine.__init__ = _init
_engine.PaperTradeEngine.open_trade = _open
_engine.PaperTradeEngine.close_position = _close


def _patch_trading_bot():
    """Patch TradingBot once its module finishes importing."""
    for _ in range(200):
        module = sys.modules.get("main")
        bot_class = getattr(module, "TradingBot", None) if module else None
        if bot_class is not None:
            if getattr(bot_class, "_persistent_state_patched", False):
                return
            original = bot_class.__init__

            def restored_init(self, *args, **kwargs):
                original(self, *args, **kwargs)
                try:
                    df = self.journal.get_trades()
                    if not df.empty and "pnl" in df.columns and "exit_time" in df.columns:
                        today = datetime.now().strftime("%Y-%m-%d")
                        dates = df["exit_time"].astype(str).str[:10]
                        pnl = __import__("pandas").to_numeric(
                            df["pnl"], errors="coerce"
                        ).fillna(0.0)
                        self.daily_pnl = round(float(pnl[dates == today].sum()), 2)
                except Exception as error:
                    print(
                        f"Daily P&L restore skipped: {type(error).__name__}: {error}"
                    )

            bot_class.__init__ = restored_init
            bot_class._persistent_state_patched = True
            return
        time.sleep(0.025)


threading.Thread(target=_patch_trading_bot, daemon=True).start()
