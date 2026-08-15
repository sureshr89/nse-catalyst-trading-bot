"""Shared dashboard typography and component styling.

Keep this file intentionally scoped to dashboard components so Streamlit's
native widget typography/layout is not globally overridden.
"""

def load_css():
    return """
<style>
:root { --dash-font: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.stApp { background:#0E1117; }
.block-container { padding-top:.55rem; padding-bottom:1rem; max-width:98%; }

.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6,
[data-testid="stAppViewContainer"] h1,[data-testid="stAppViewContainer"] h2,
[data-testid="stAppViewContainer"] h3,[data-testid="stAppViewContainer"] h4 {
    font-family:var(--dash-font)!important;color:#F4F7FB!important;
    font-weight:700!important;letter-spacing:-.01em!important;
}
.stApp h1,[data-testid="stAppViewContainer"] h1{font-size:1.55rem!important;line-height:1.2!important;margin:.15rem 0 .35rem!important}
.stApp h2,[data-testid="stAppViewContainer"] h2{font-size:1.12rem!important;line-height:1.25!important;margin:.7rem 0 .3rem!important}
.stApp h3,[data-testid="stAppViewContainer"] h3{font-size:.98rem!important;line-height:1.3!important;margin:.55rem 0 .25rem!important}
.stApp p,.stApp li,.stApp .stMarkdown,[data-testid="stMarkdownContainer"] {font-family:var(--dash-font)!important;font-size:.82rem!important;line-height:1.4!important}
.stApp .stCaption{font-family:var(--dash-font)!important;color:#9FB0C7!important;font-size:.78rem!important}
.stButton>button,.stDownloadButton>button{font-family:var(--dash-font)!important;font-size:.80rem!important;font-weight:650!important;line-height:1.15!important;min-height:40px!important;border-radius:9px!important}

.metric-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;width:100%}
.metric-card{background:#111B2D;border:1px solid #26344D;border-radius:10px;padding:9px;min-height:52px;box-sizing:border-box}
.metric-card small{display:block;color:#9FB0C7!important;font-size:.68rem!important;line-height:1.2!important;font-weight:500!important}
.metric-card b{display:block;color:#F4F7FB!important;font-size:.84rem!important;line-height:1.25!important;font-weight:700!important;margin-top:3px}

.dashboard-info-card{background:#111B2D;border:1px solid #26344D;border-radius:10px;padding:4px 12px;margin-top:2px;box-sizing:border-box}
.info-row,.session-row{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid #26344D;font-family:var(--dash-font);font-size:.80rem;line-height:1.4}
.info-row:last-child,.session-row:last-child{border-bottom:0}
.info-row span,.session-row span{flex:0 0 58px;color:#9FB0C7;font-size:.70rem;font-weight:600;letter-spacing:.02em}
.info-row b,.session-row b{flex:1;color:#F4F7FB;font-size:.80rem;font-weight:600}

.analysis-kpi-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:8px 0 12px}
.analysis-kpi{background:linear-gradient(180deg,#142036,#101a2a);border:1px solid #2b3b57;border-radius:11px;padding:9px 10px;min-height:58px;box-sizing:border-box}
.analysis-kpi span{display:block;color:#9FB0C7;font-size:.67rem;line-height:1.15}
.analysis-kpi strong{display:block;color:#F4F7FB;font-size:.95rem;line-height:1.25;margin-top:4px}
.analysis-section-title{font-size:1.02rem;font-weight:700;color:#F4F7FB;margin:2px 0 2px}
.stTabs [data-baseweb="tab-list"]{gap:5px;overflow-x:auto;padding:3px 2px 6px;scrollbar-width:none}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar{display:none}
.stTabs [data-baseweb="tab"]{height:38px;padding:0 12px;border:1px solid #26344D;border-radius:9px;background:#111B2D;color:#B9C6D8;font-size:.76rem;font-weight:650;white-space:nowrap}
.stTabs [aria-selected="true"]{background:#1a2942!important;color:#F4F7FB!important;border-color:#3b5278!important}
.stTabs [data-baseweb="tab-highlight"]{display:none}
.stPlotlyChart{border:1px solid #1f2c42;border-radius:10px;overflow:hidden;background:#101724}
.stDataFrame{border-radius:10px}
.daily-motivation{margin-top:12px;padding:14px 13px;border:1px solid #2b3b57;border-radius:12px;background:linear-gradient(180deg,#142036,#101824);text-align:center}
.daily-motivation-label{font-size:.68rem;font-weight:700;letter-spacing:.08em;color:#8fa6c4;margin-bottom:4px}
.daily-motivation-quote{font-size:.95rem;font-weight:700;line-height:1.4;color:#f4f7fb}
.daily-motivation-note{font-size:.70rem;color:#9fb0c7;margin-top:4px}
.mobile-bottom-space{height:70px}
footer,header{visibility:hidden}

@media(max-width:768px){
    .analysis-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
    .analysis-kpi{min-height:54px}.analysis-kpi strong{font-size:.86rem}
    .stTabs [data-baseweb="tab"]{font-size:.71rem;padding:0 10px;height:36px}
    .block-container{padding-left:.65rem;padding-right:.65rem}
    .dashboard-info-card{padding:3px 10px}
    .info-row,.session-row{gap:8px;padding:9px 0;font-size:.76rem}
    .info-row span,.session-row span{flex:0 0 52px;font-size:.66rem}
    .info-row b,.session-row b{font-size:.76rem}
    .daily-motivation{margin-top:12px;padding:12px 10px}
    .daily-motivation-quote{font-size:.88rem}
    .mobile-bottom-space{height:75px}
}
</style>
"""
