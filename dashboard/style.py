"""Shared dashboard styling."""


def load_css():
    return """
    <style>
    :root {
        --app-font: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    html, body, [class*="css"], .stApp, .stApp * {
        font-family: var(--app-font) !important;
    }

    .stApp { background-color: #0E1117; }
    .main { background-color: #0E1117; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 98%; }

    h1, h2, h3, h4, h5, h6 {
        font-family: var(--app-font) !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em;
    }
    h1 { color: #00E5FF !important; font-size: 2rem !important; }
    h2, h3, h4, h5, h6 { color: #F4F7FB !important; }

    p, label, .stCaption, .stMarkdown, .stText, [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"], [data-testid="stDataFrame"] {
        font-family: var(--app-font) !important;
    }

    p, .stMarkdown, .stText { font-size: 0.92rem; }
    .stCaption { color: #9FB0C7 !important; font-size: 0.78rem !important; }

    button, .stButton > button, .stDownloadButton > button,
    div[data-baseweb="button"], div[role="button"] {
        font-family: var(--app-font) !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }

    .stButton > button, .stDownloadButton > button {
        min-height: 38px;
        font-size: 0.88rem !important;
    }

    div[data-testid="metric-container"] {
        background-color: #1C1F26;
        border: 1px solid #2E323C;
        border-radius: 12px;
        padding: 15px;
    }
    div[data-testid="metric-container"] label { color: #BBBBBB !important; }
    div[data-testid="metric-container"] div { color: white; }
    .stDataFrame { border-radius: 10px; }

    footer, header { visibility: hidden; }
    </style>
    """
