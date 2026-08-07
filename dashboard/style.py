"""
Dashboard Style
===============

Custom CSS for the NSE Catalyst Trading Bot dashboard.
"""


def load_css():
    return """
    <style>

    .main {
        background-color: #0E1117;
    }

    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 98%;
    }

    h1 {
        color: #00E5FF;
        font-weight: 700;
    }

    h2 {
        color: white;
    }

    h3 {
        color: white;
    }

    div[data-testid="metric-container"] {
        background-color: #1C1F26;
        border: 1px solid #2E323C;
        border-radius: 12px;
        padding: 15px;
    }

    div[data-testid="metric-container"] label {
        color: #BBBBBB;
    }

    div[data-testid="metric-container"] div {
        color: white;
    }

    .stDataFrame {
        border-radius: 10px;
    }

    footer {
        visibility: hidden;
    }

    header {
        visibility: hidden;
    }

    </style>
    """