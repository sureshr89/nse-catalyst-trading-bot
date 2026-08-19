import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
IST=ZoneInfo('Asia/Kolkata')
REFRESH=15
STRATEGIES={'S1':'PDH/PDL Sweep + Open Reclaim','S2':'PDH/PDL Breakout + Retest','S3':'PDL/PDH Sweep + Open Reclaim','S4':'Intraday High/Low Breakout','S5':'Direct PDH/PDL Breakout'}
st.set_page_config(page_title='NSE Catalyst',page_icon='📊',layout='wide',initial_sidebar_state='collapsed')
st_autorefresh(interval=REFRESH*1000,key='refresh')

try:
    from market.nifty500_breadth import BREADTH
    d=BREADTH.snapshot(force=True)
except Exception as e:
    d={'complete':False,'reason':f'{type(e).__name__}: {e}','evaluated':0,'total':500,'market_data_source':'DHAN'}

n=d.get('nifty500_change_pct'); sec=d.get('sector_alignment_pct'); ad=d.get('ad_ratio')
evaln=int(d.get('evaluated',0) or 0); sm=int(d.get('sector_mapped',0) or 0); sp=int(d.get('sector_priced',0) or 0)
complete=bool(d.get('complete')); scomplete=bool(d.get('sector_complete'))
buy=complete and scomplete and n is not None and sec is not None and ad is not None and n>0 and sec>0 and ad>1
sell=complete and scomplete and n is not None and sec is not None and ad is not None and n<0 and sec<0 and ad<1
bias='🟢 BUY' if buy else '🔴 SELL' if sell else '⚪ NO TRADE'

def v(x):
    try:return f'{float(x):+.2f}%'
    except:return '—'
def box(label,value):return f"<div class='box'><small>{label}</small><b>{value}</b></div>"

st.markdown('''<style>
html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}.block-container{padding:.9rem .8rem 2rem;max-width:1450px}
.h{font-size:clamp(1.7rem,4vw,2.7rem);font-weight:900;margin-bottom:5px}.sub{color:#9fb1ca;font-size:.82rem;margin-bottom:16px}.sec{font-size:1.25rem;font-weight:850;margin:20px 0 9px}
.grid6{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.box{border:1px solid #2b4163;background:#111b2b;border-radius:12px;padding:10px;min-height:70px}.box small{display:block;color:#9fb1ca;font-size:.58rem;font-weight:800}.box b{display:block;font-size:1rem;margin-top:6px}.status{border:1px solid #2b4163;background:#111b2b;border-radius:12px;padding:11px;margin-top:8px}.muted{color:#9fb1ca;font-size:.78rem}.green{color:#43d17a}.yellow{color:#ffd166}.red{color:#ff6675}.strategy{border:1px solid #2b4163;background:#111b2b;border-radius:12px;padding:12px;min-height:105px}.strategy h4{margin:0 0 6px;font-size:1rem}.strategy p{font-size:.8rem}
@media(max-width:900px){.grid6{grid-template-columns:repeat(3,1fr)}.grid4{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.grid6,.grid4{grid-template-columns:repeat(2,1fr);gap:7px}.grid2{grid-template-columns:1fr}.box{min-height:66px;padding:8px}.box b{font-size:.9rem}.h{font-size:1.6rem}}
</style>''',unsafe_allow_html=True)

now=datetime.now(IST)
st.markdown("<div class='h'>📊 NSE Catalyst — Master Dashboard</div>",unsafe_allow_html=True)
st.markdown(f"<div class='sub'>NIFTY 500 • S1–S5 • PAPER ONLY • DHAN LIVE DATA • REFRESH {REFRESH}s • {now.strftime('%d %b %Y %H:%M:%S')} IST</div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>🎯 Master Market Alignment</div>",unsafe_allow_html=True)
st.markdown('<div class="grid6">'+''.join([box('NIFTY 500',v(n)),box('SECTORS',v(sec)),box('A/D RATIO',f'{float(ad):.2f}' if ad is not None else 'WAITING'),box('BREADTH',f'{evaln}/500'),box('SECTOR DATA',f'{sp}/500'),box('MASTER BIAS',bias)])+'</div>',unsafe_allow_html=True)

if complete and scomplete:
    st.markdown(f"<div class='status'><span class='green'><b>● DHAN LIVE DATA READY</b></span> — 500/500 stocks • Advances {d.get('advances','—')} • Declines {d.get('declines','—')} • A/D {float(ad):.2f} • updated {d.get('updated_at','—')}</div>",unsafe_allow_html=True)
else:
    st.markdown(f"<div class='status'><span class='yellow'><b>● DHAN DATA WAITING</b></span> — {d.get('reason','Waiting for Dhan market data')} • stocks {evaln}/500 • sectors mapped {sm}/500 • priced {sp}/500</div>",unsafe_allow_html=True)

st.markdown(f"<div class='grid4'><div class='box'><b>🟢 BUY GATE</b><br>{'PASS ✓' if buy else 'WAIT'}</div><div class='box'><b>🔴 SELL GATE</b><br>{'PASS ✓' if sell else 'WAIT'}</div><div class='box'><b>📡 DATA</b><br>Dhan {evaln}/500</div><div class='box'><b>🔄 REFRESH</b><br>15 sec</div></div>",unsafe_allow_html=True)

st.markdown("<div class='sec'>📚 Previous Close / Reference</div>",unsafe_allow_html=True)
pc=d.get('nifty500_previous_close')
st.markdown('<div class="grid4">'+''.join([box('NIFTY 500 PREVIOUS CLOSE',f'{float(pc):,.2f}' if pc is not None else '—'),box('ADVANCES TODAY',d.get('advances','—')),box('DECLINES TODAY',d.get('declines','—')),box('A/D TODAY',f'{float(ad):.2f}' if ad is not None else '—'),box('POSITIVE SECTORS',d.get('positive_sectors','—')),box('NEGATIVE SECTORS',d.get('negative_sectors','—')),box('SECTOR MAPPING',f'{sm}/500'),box('SOURCE','DHAN')])+'</div>',unsafe_allow_html=True)

st.markdown("<div class='sec'>🔒 Fixed Paper-Trading Rules</div>",unsafe_allow_html=True)
st.markdown('<div class="grid6">'+''.join([box('CAPITAL / TRADE','₹250,000'),box('RISK / TRADE','₹1,400–₹1,500'),box('TARGET / TRADE','1.25R'),box('MAX TRADES / STRATEGY','1 / day'),box('DAILY LOSS / TRADE','₹1,500'),box('REFRESH','15 sec')])+'</div>',unsafe_allow_html=True)

st.markdown("<div class='sec'>🔥 All 5 Strategies</div>",unsafe_allow_html=True)
st.markdown('<div class="grid2">'+''.join([f"<div class='strategy'><h4>{s} • {'🟢 ELIGIBLE' if (buy or sell) else '⚪ WAITING'}</h4><div class='muted'>{name}</div><p>1 trade/day • Risk ₹1,400–₹1,500 • Target 1.25R</p></div>" for s,name in STRATEGIES.items()])+'</div>',unsafe_allow_html=True)

st.markdown("<div class='sec'>💼 Current Paper Trades</div>",unsafe_allow_html=True)
st.info('No open paper trades — waiting for complete alignment and exact OHLC/PDH/PDL setup.')
