"""Streamlit page entrypoint for the read-only trading analysis."""
from pathlib import Path
import runpy
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent

# Four navigation buttons, always visible on mobile in a 2x2 grid.
st.markdown("""
<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{background:#0b1220}
.block-container{max-width:1420px!important;padding:.7rem .7rem 2rem!important}
[data-testid="stPageLink"] a{display:flex!important;align-items:center!important;justify-content:center!important;min-height:42px!important;padding:.42rem .25rem!important;border:1px solid #2b3b57!important;border-radius:11px!important;background:#142036!important;color:#e9f0f8!important;font-size:.70rem!important;font-weight:700!important;text-decoration:none!important}
/* Charts are intentionally static: no pinch, zoom, pan, hover or touch interaction. */
.js-plotly-plot,.js-plotly-plot *{pointer-events:none!important;touch-action:none!important}
@media(max-width:768px){[data-testid="stPageLink"] a{min-height:42px!important;font-size:.64rem!important;padding:.35rem .12rem!important}}
</style>
""", unsafe_allow_html=True)

n1,n2=st.columns(2,gap="small")
n3,n4=st.columns(2,gap="small")
n1.page_link("app.py",label="🟢 BOT STATUS",icon="🟢")
n2.page_link("pages/current_trading.py",label="📌 CURRENT TRADING",icon="📌")
n3.page_link("pages/analysis.py",label="📊 ANALYSIS",icon="📊")
n4.page_link("pages/downloads.py",label="⬇️ DOWNLOADS",icon="⬇️")

# Render the existing read-only research page.
runpy.run_path(str(ROOT / "analysis.py"), run_name="__main__")

# Sector performance is based on CLOSED actual trades only. Capital-missed outcomes remain separate.
try:
    trades_path=ROOT/"outputs"/"trades.csv"
    trades=pd.read_csv(trades_path)
except Exception:
    trades=pd.DataFrame()

if not trades.empty and "status" in trades.columns:
    actual=trades[trades["status"].astype(str).str.upper().eq("CLOSED")].copy()
else:
    actual=pd.DataFrame()

if not actual.empty:
    try:
        from data.stock_universe import StockUniverse
        from data.sector_store import SectorStore
        universe=StockUniverse().get_dataframe(refresh=False)
        sector_map=SectorStore(universe).load()
        if not sector_map.empty and "symbol" in actual.columns:
            sector_map["Symbol"]=sector_map["Symbol"].astype(str).str.upper().str.strip()
            actual["Symbol"]=actual["symbol"].astype(str).str.upper().str.strip()
            actual=actual.merge(sector_map[["Symbol","Sector"]],on="Symbol",how="left",suffixes=("","_map"))
            actual["Sector"]=actual["Sector"].fillna(actual.get("sector", "UNKNOWN"))
        elif "sector" in actual.columns:
            actual["Sector"]=actual["sector"].fillna("UNKNOWN")
        else:
            actual["Sector"]="UNKNOWN"
    except Exception:
        actual["Sector"]=actual.get("sector", "UNKNOWN")

    actual["pnl"]=pd.to_numeric(actual.get("pnl",0),errors="coerce").fillna(0)
    sector_rows=[]
    for sector,g in actual.groupby("Sector",dropna=False):
        sector=str(sector) if pd.notna(sector) and str(sector).strip() else "UNKNOWN"
        pnl=g["pnl"]
        wins=int((pnl>0).sum()); losses=int((pnl<0).sum()); flat=int((pnl==0).sum())
        sector_rows.append({"Sector":sector,"Trades":len(g),"Wins":wins,"Losses":losses,"Flat":flat,"Win Rate %":round(wins/len(g)*100,1) if len(g) else 0.0,"P&L":round(float(pnl.sum()),2),"Avg P&L":round(float(pnl.mean()),2) if len(g) else 0.0})
    sector_stats=pd.DataFrame(sector_rows).sort_values(["P&L","Win Rate %"],ascending=[False,False]).reset_index(drop=True)

    st.markdown('<div class="section-title">🏭 Sector Performance — Which Sector Favors the Strategy?</div>',unsafe_allow_html=True)
    st.caption("Based on CLOSED actual trades. Positive P&L + higher win rate indicates sectors where this strategy has worked better. Capital-missed trades are not mixed into actual performance.")
    if not sector_stats.empty:
        winners=sector_stats[(sector_stats["P&L"]>0)&(sector_stats["Win Rate %"]>=50)].copy()
        losers=sector_stats[(sector_stats["P&L"]<0)].copy()
        c1,c2=st.columns(2)
        c1.metric("Winning Sectors",len(winners)); c2.metric("Losing Sectors",len(losers))
        st.dataframe(sector_stats,use_container_width=True,hide_index=True)
        import plotly.express as px
        fig=px.bar(sector_stats,x="Sector",y="P&L",text="Trades",title="Actual P&L by Sector")
        fig.update_layout(height=380,margin=dict(l=10,r=10,t=55,b=90),yaxis_title="₹")
        st.plotly_chart(fig,use_container_width=True)
        fig2=px.bar(sector_stats,x="Sector",y="Win Rate %",text="Trades",title="Strategy Win Rate by Sector")
        fig2.update_layout(height=380,margin=dict(l=10,r=10,t=55,b=90),yaxis_title="Win Rate %")
        st.plotly_chart(fig2,use_container_width=True)
    else:
        st.info("Sector results will populate after closed actual trades are available.")
else:
    st.markdown('<div class="section-title">🏭 Sector Performance — Which Sector Favors the Strategy?</div>',unsafe_allow_html=True)
    st.info("No closed actual trades yet. Sector win/loss charts will populate automatically after trades close.")

st.markdown("""
<style>
[data-testid="stMetric"]{background:#111b2d!important;border:1px solid #26344d!important;border-radius:12px!important;padding:.55rem .7rem!important;min-height:78px!important}
[data-testid="stMetricLabel"]{font-size:.68rem!important;color:#9fb0c7!important}
[data-testid="stMetricValue"]{font-size:1.1rem!important;color:#f4f7fb!important;font-weight:700!important}
[data-testid="stDataFrame"]{border:1px solid #26344d!important;border-radius:10px!important;overflow:hidden!important}
/* hard-disable all Plotly pointer interaction */
.js-plotly-plot,.js-plotly-plot *{pointer-events:none!important;touch-action:none!important}
</style>
""",unsafe_allow_html=True)
