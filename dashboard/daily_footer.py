from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

INDIA_TZ = ZoneInfo("Asia/Kolkata")
ROOT = Path(__file__).resolve().parents[1]

QUOTES = [
    "Trade the setup, not the emotion.",
    "Discipline is protecting your capital when there is no clear trade.",
    "One high-quality trade is better than many impulsive trades.",
    "Wait for confirmation. Let the market come to you.",
    "Your edge is consistency, not prediction.",
    "A missed trade costs nothing; a bad trade costs capital.",
    "Follow the plan. Accept the outcome. Review and improve.",
    "Protect capital first. Opportunities come every day.",
    "Patience is part of the strategy, not a delay in the strategy.",
    "The best traders know when not to trade.",
    "Small disciplined decisions create long-term results.",
    "Do not chase the candle. Wait for your setup.",
    "Risk is controlled before the trade is entered.",
    "Consistency beats excitement in trading.",
    "Today is another opportunity to execute the plan correctly.",
    "Let the system decide; let discipline execute.",
    "No setup, no trade. Clear setup, clear execution.",
    "A good process matters more than one winning trade.",
    "Stay calm when the market moves fast.",
    "Capital preserved today gives you opportunities tomorrow.",
]


def _read_csv(path):
    try:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _unified_csv(kind):
    """Build one CSV containing both Strategy 1 and Strategy 2 records."""
    if kind == "trades":
        paths = (ROOT / "outputs" / "trades.csv", ROOT / "outputs" / "strategy2_trades.csv")
    else:
        paths = (ROOT / "outputs" / "signals.csv", ROOT / "outputs" / "strategy2_signals.csv")

    frames = []
    for path in paths:
        frame = _read_csv(path)
        if frame.empty:
            continue
        frame = frame.copy()
        if "strategy" not in frame.columns:
            strategy = "STRATEGY_2" if "strategy2" in path.name else "STRATEGY_1"
            frame.insert(0, "strategy", strategy)
        frames.append(frame)

    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


# Both Strategy 1 and Strategy 2 pages use Streamlit's download_button.
# Intercept only trade/signal CSV downloads so the downloaded file is always
# the same combined S1 + S2 dataset instead of separate strategy CSVs.
if not getattr(st, "_nse_catalyst_unified_download_patch", False):
    _original_download_button = st.download_button

    def _unified_download_button(label, data=None, *args, **kwargs):
        text = str(label or "").upper()
        file_name = str(kwargs.get("file_name") or "").lower()
        is_trades = "TRADES CSV" in text or file_name in {"nifty500_trades.csv", "strategy2_trades.csv"}
        is_signals = "SIGNALS CSV" in text or file_name in {"nifty500_signals.csv", "strategy2_signals.csv"}
        if is_trades or is_signals:
            kind = "trades" if is_trades else "signals"
            combined = _unified_csv(kind)
            data = combined.to_csv(index=False).encode("utf-8")
            label = "⬇️ ALL STRATEGIES TRADES CSV" if kind == "trades" else "⬇️ ALL STRATEGIES SIGNALS CSV"
            kwargs["file_name"] = "NSE_CATALYST_ALL_TRADES.csv" if kind == "trades" else "NSE_CATALYST_ALL_SIGNALS.csv"
            kwargs["mime"] = "text/csv"
        return _original_download_button(label, data, *args, **kwargs)

    st.download_button = _unified_download_button
    st._nse_catalyst_unified_download_patch = True


def render_daily_footer():
    # Use India time so the quote changes at the Indian calendar day boundary,
    # not at UTC midnight on Streamlit Cloud.
    india_today = datetime.now(INDIA_TZ).date()
    quote = QUOTES[(india_today - date(2026, 1, 1)).days % len(QUOTES)]
    st.markdown(
        f'''<div class="daily-motivation">
            <div class="daily-motivation-label">🧠 DAILY TRADING REMINDER</div>
            <div class="daily-motivation-quote">“{quote}”</div>
            <div class="daily-motivation-note">Follow your rules. Do not force a trade.</div>
        </div>
        <div class="mobile-bottom-space"></div>''',
        unsafe_allow_html=True,
    )
