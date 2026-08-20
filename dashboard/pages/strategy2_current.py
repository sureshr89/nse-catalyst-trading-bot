"""Compatibility dashboard page for Strategy 2.
The master dashboard is the runtime source; this page exposes contract metadata.
"""
import streamlit as st
from strategy.contracts import strategy_metadata

META = strategy_metadata("STRATEGY_2")
st.set_page_config(page_title="NSE Catalyst | S2", layout="wide")
st.title("Strategy 2 — Current Trading")
st.caption(f"Contract: {META['name']} • {META['version']}")
st.json(META)
