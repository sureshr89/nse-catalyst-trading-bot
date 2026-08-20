"""Live paper-trading worker used by the Streamlit dashboard.

The dashboard must execute the MasterEngine; merely reading signals.csv is not
sufficient. This module keeps one engine instance per Streamlit process and
runs one complete cycle every dashboard refresh.
"""
import streamlit as st


@st.cache_resource(show_spinner=False)
def get_engine():
    from main import MasterEngine
    return MasterEngine()


def run_once():
    engine = get_engine()
    try:
        opened = engine.run_cycle()
        return {
            "ok": True,
            "opened": len(opened or []),
            "signals": int(engine.diagnostics.get("final_signals", 0) or 0),
            "diagnostics": dict(engine.diagnostics),
        }
    except Exception as exc:
        engine.diagnostics["worker_error"] = f"{type(exc).__name__}: {exc}"
        try:
            engine._write_diagnostics()
        except Exception:
            pass
        return {"ok": False, "opened": 0, "signals": 0, "diagnostics": dict(engine.diagnostics)}
