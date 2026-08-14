"""Single shared dashboard typography and component styling."""

def load_css():
    return """
<style>
:root { --dash-font: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
html, body, .stApp, .stApp * { font-family:var(--dash-font) !important; }
.stApp { background:#0E1117; }
.block-container { padding-top:.7rem; padding-bottom:1rem; max-width:98%; }

.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6,
[data-testid="stAppViewContainer"] h1,[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3,[data-testid="stAppViewContainer"] h4 {
 font-family:var(--dash-font)!important;color:#F4F7FB!important;font-weight:700!important;letter-spacing:-.01em!important;
}
.stApp h1,[data-testid="stAppViewContainer"] h1{font-size:1.55rem!important;line-height:1.2!important;margin:.15rem 0 .35rem!important}
.stApp h2,[data-testid="stAppViewContainer"] h2{font-size:1.12rem!important;line-height:1.25!important;margin:.75rem 0 .3rem!important}
.stApp h3,[data-testid="stAppViewContainer"] h3{font-size:.98rem!important;line-height:1.3!important;margin:.6rem 0 .28rem!important}
.stApp p,.stApp li,.stApp label,.stApp .stMarkdown,.stApp .stCaption,[data-testid="stMarkdownContainer"],[data-testid="stMetricLabel"],[data-testid="stMetricValue"]{font-family:var(--dash-font)!important}
.stApp p,.stApp li,.stApp .stMarkdown{font-size:.82rem!important;line-height:1.4!important}
.stApp .stCaption{color:#9FB0C7!important;font-size:.78rem!important}

.stButton>button,.stDownloadButton>button,button,[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-primary"]{font-family:var(--dash-font)!important;font-size:.80rem!important;font-weight:650!important;line-height:1.15!important;min-height:40px!important;border-radius:9px!important}

.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;width:100%}
.metric-card{background:#111B2D;border:1px solid #26344D;border-radius:10px;padding:9px;min-height:52px;box-sizing:border-box}
.metric-card small{display:block;color:#9FB0C7!important;font-family:var(--dash-font)!important;font-size:.68rem!important;line-height:1.2!important;font-weight:500!important}
.metric-card b{display:block;color:#F4F7FB!important;font-family:var(--dash-font)!important;font-size:.84rem!important;line-height:1.25!important;font-weight:700!important;margin-top:3px}

div[data-testid="metric-container"]{background:#111B2D;border:1px solid #26344D;border-radius:10px;padding:10px}
div[data-testid="metric-container"] label{color:#9FB0C7!important;font-size:.68rem!important}
div[data-testid="metric-container"] [data-testid="stMetricValue"]{color:#F4F7FB!important;font-size:1rem!important;font-weight:700!important}
.stDataFrame{border-radius:10px} footer,header{visibility:hidden}
</style>
"""
