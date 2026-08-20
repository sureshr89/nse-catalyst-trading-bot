"""Tabbed Streamlit entrypoint for the NSE Catalyst dashboard.

The TEST tab is a presentation-only diagnostic panel. It is deliberately
kept outside the MasterEngine and outside the trade journal.
"""
import streamlit as st

from dashboard.single_master import live_dashboard
from dashboard.test_tab import render_test_tab


def render_dashboard():
    master_tab, test_tab = st.tabs(["📊 MASTER DASHBOARD", "🧪 TEST"])

    with master_tab:
        live_dashboard()

    with test_tab:
        render_test_tab()


if __name__ == "__main__":
    render_dashboard()
