import streamlit as st
from dashboard.nav import render_nav
from dashboard.style import load_css
st.set_page_config(page_title="NSE Catalyst | Strategy 5",page_icon="🟠",layout="wide",initial_sidebar_state="collapsed")
st.markdown(load_css(),unsafe_allow_html=True);render_nav()
st.title("🟠 Strategy 5")
st.caption("Direct PDH/PDL Breakout • Pre-API setup")
st.info("Strategy 5 rules are defined in the strategy engine. Live 500-stock data is intentionally blocked until the full NIFTY 500 feed is connected.")
for title,text in [("Before Trade","BUY: NIFTY 500 > +0.25% + full NIFTY 500 A/D > 1 + previous candle GREEN. SELL: NIFTY 500 < −0.25% + full A/D < 1 + previous candle RED."),("Entry","BUY: live LTP > PDH. SELL: live LTP < PDL."),("Risk & Exit","SL = PDH for BUY / PDL for SELL; target 1.25R; actual risk ₹1,400–₹1,500; square-off 15:00 IST."),("Live Status","Waiting for Dhan/live NIFTY 500 data. No trade is permitted on incomplete breadth.")]:
 with st.expander(title,expanded=True): st.write(text)
