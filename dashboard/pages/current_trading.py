"""Compatibility dashboard page for Strategy 1.
The master dashboard is the runtime source; this page exposes contract metadata.
"""
import streamlit as st
from strategy.contracts import strategy_metadata

META = strategy_metadata("STRATEGY_1")
st.set_page_config(page_title="NSE Catalyst | S1", layout="wide")
st.title("Strategy 1 — Current Trading")
st.caption(f"Contract: {META['name']} • {META['version']}")
st.json(META)
