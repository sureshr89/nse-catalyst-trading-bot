import streamlit as st
from dashboard.nav import render_nav
from dashboard.style import load_css
st.set_page_config(page_title="NSE Catalyst | Strategy 3",page_icon="🟢",layout="wide",initial_sidebar_state="collapsed")
st.markdown(load_css(),unsafe_allow_html=True);render_nav()
st.title("🟢 Strategy 3")
st.caption("PDL/PDH Sweep + Open Reclaim • Pre-API setup")
st.info("Strategy 3 rules are defined in the strategy engine. Live 500-stock data is intentionally blocked until the full NIFTY 500 feed is connected.")
for title,text in [("Before Trade","BUY: NIFTY 500 > +0.25% + full NIFTY 500 A/D > 1 + previous candle GREEN. SELL: NIFTY 500 < −0.25% + full A/D < 1 + previous candle RED."),("Entry","BUY: Open > PDL → Low < PDL → price returns to Open. SELL: Open < PDH → High > PDH → price returns below Open."),("Risk & Exit","Strategy-specific SL from information available at/before entry; target 1.25R; actual risk ₹1,400–₹1,500; square-off 15:00 IST."),("Live Status","Waiting for Dhan/live NIFTY 500 data. No trade is permitted on incomplete breadth.")]:
 with st.expander(title,expanded=True): st.write(text)
