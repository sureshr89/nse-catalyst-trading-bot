from datetime import date
import streamlit as st

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


def render_daily_footer():
    quote = QUOTES[(date.today() - date(2026, 1, 1)).days % len(QUOTES)]
    st.markdown(
        f'''<div class="daily-motivation">
            <div class="daily-motivation-label">🧠 DAILY TRADING REMINDER</div>
            <div class="daily-motivation-quote">“{quote}”</div>
            <div class="daily-motivation-note">Follow your rules. Do not force a trade.</div>
        </div>
        <div class="mobile-bottom-space"></div>''',
        unsafe_allow_html=True,
    )
