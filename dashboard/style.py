"""Shared dashboard typography and component styling."""


def load_css():
    return """
    <style>
    html, body, .stApp, .stApp * {
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    }
    .stApp { background: #0E1117; }
    .block-container { padding-top: .7rem; padding-bottom: 1rem; max-width: 98%; }
    h1, h2, h3, h4, h5, h6 {
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        color: #F4F7FB !important;
        font-weight: 700 !important;
        letter-spacing: -.01em;
    }
    h1 { font-size: 1.75rem !important; color: #00E5FF !important; }
    h2 { font-size: 1.35rem !important; }
    h3 { font-size: 1.08rem !important; }
    p, label, .stCaption, .stMarkdown, [data-testid="stMetricLabel"] {
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    }
    .stCaption { color: #9FB0C7 !important; font-size: .78rem !important; }
    button, .stButton > button, .stDownloadButton > button {
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        font-weight: 650 !important;
        border-radius: 9px !important;
        min-height: 40px !important;
    }
    div[data-testid="metric-container"] {
        background: #111B2D; border: 1px solid #26344D; border-radius: 10px; padding: 12px;
    }
    div[data-testid="metric-container"] label { color: #9FB0C7 !important; }
    div[data-testid="metric-container"] div { color: #F4F7FB !important; }
    .stDataFrame { border-radius: 10px; }
    footer, header { visibility: hidden; }
    </style>
    """
