"""Closed-market / previous-day data view, separate from live scanning."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import requests
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")
st.set_page_config(page_title="Closed Data | NSE Catalyst", page_icon="📚", layout="wide")
st.markdown("""
<style>
html,body,[class*="css"]{font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif}.block-container{max-width:1450px;padding:1.1rem .9rem 2rem}
.title{font-size:clamp(1.8rem,4vw,2.7rem);font-weight:900;color:#f4f7fb;margin-bottom:5px}.sub{color:#9fb1ca;font-size:.9rem;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.card{border:1px solid #2b4163;background:linear-gradient(145deg,#111b2b,#0f1928);border-radius:14px;padding:13px;min-height:82px}.card small{color:#9fb1ca;font-size:.66rem;font-weight:800;text-transform:uppercase}.card b{display:block;color:#f4f7fb;font-size:1.18rem;margin-top:7px}.ok{color:#43d17a!important}.wait{color:#ffd166!important}.bad{color:#ff6675!important}.note{border:1px solid #2b4163;background:#111b2b;border-radius:12px;padding:13px 15px;color:#dbe6f5;margin:12px 0}
@media(max-width:900px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:600px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.block-container{padding:.9rem .8rem 1.5rem}.title{font-size:1.65rem}.card{padding:11px;min-height:76px}.card b{font-size:1.02rem}}
</style>""", unsafe_allow_html=True)

def secret(name):
    try:return str(st.secrets.get(name, "")).strip()
    except Exception:return ""

def card(label,value,cls=""):
    return f"<div class='card'><small>{label}</small><b class='{cls}'>{value}</b></div>"

def load_json(name):
    try:return json.loads((ROOT/"outputs"/name).read_text(encoding="utf-8"))
    except Exception:return {}

def clean_symbols(df):
    if df is None or df.empty:return pd.DataFrame(columns=["Symbol","SecurityId"])
    symbol_col=next((c for c in df.columns if str(c).upper() in {"SEM_TRADING_SYMBOL","SEM_CUSTOM_SYMBOL","SYMBOL_NAME","SM_SYMBOL_NAME","SYMBOL"}),None)
    sec_col=next((c for c in df.columns if str(c).upper() in {"SECURITY_ID","SEM_SM_SECURITY_ID","SECURITYID"}),None)
    if not symbol_col or not sec_col:return pd.DataFrame(columns=["Symbol","SecurityId"])
    out=pd.DataFrame({"Symbol":df[symbol_col].astype(str).str.upper().str.strip().str.replace("-EQ$","",regex=True),"SecurityId":df[sec_col].astype(str).str.strip()})
    return out[out["SecurityId"].ne("")].drop_duplicates("Symbol")

@st.cache_data(ttl=3600,show_spinner=False)
def dhan_instrument_master():
    try:
        r=requests.get("https://images.dhan.co/api-data/api-scrip-master.csv",timeout=30)
        if r.ok:return pd.read_csv(__import__("io").StringIO(r.text),low_memory=False)
    except Exception:pass
    return pd.DataFrame()

def dhan_ohlc(client_id,token,instruments):
    if not instruments:return {},"No instruments"
    try:
        r=requests.post("https://api.dhan.co/v2/marketfeed/ohlc",headers={"access-token":token,"client-id":client_id,"Accept":"application/json","Content-Type":"application/json"},json=instruments,timeout=20)
        if r.ok:
            payload=r.json();return payload.get("data",{}),"OK"
        return {},f"HTTP {r.status_code}"
    except Exception as e:return {},f"ERROR {type(e).__name__}"

client_id=secret("DHAN_CLIENT_ID");token=secret("DHAN_ACCESS_TOKEN")
reference=load_json("master_data.json")

st.markdown("<div class='title'>📚 Closed / Previous-Day Data</div>",unsafe_allow_html=True)
st.markdown("<div class='sub'>Closed-market reference values • Dhan verification • PDH / PDL / PDC • never mixed with the live 15-second strategy scanner</div>",unsafe_allow_html=True)

st.markdown("### 🔐 Dhan Data Connection")
if client_id and token:
    try:
        r=requests.get("https://api.dhan.co/v2/fundlimit",headers={"access-token":token,"client-id":client_id},timeout=10)
        st.markdown(card("DHAN API","CONNECTED" if r.ok else f"HTTP {r.status_code}","ok" if r.ok else "bad"),unsafe_allow_html=True)
    except Exception:st.markdown(card("DHAN API","ERROR","bad"),unsafe_allow_html=True)
else:st.markdown(card("DHAN API","SECRETS MISSING","wait"),unsafe_allow_html=True)

st.markdown("### 📅 Dhan Closed Values")
if client_id and token:
    if st.button("🔄 Refresh Dhan Closed Values",use_container_width=True):
        master=dhan_instrument_master()
        try:
            from data.stock_universe import StockUniverse
            universe=StockUniverse().get_dataframe(refresh=False)
        except Exception:
            universe=pd.DataFrame()
        eq=master.copy()
        if not eq.empty and "SEGMENT" in eq.columns: eq=eq[eq["SEGMENT"].astype(str).str.upper().eq("E")]
        mapping=clean_symbols(eq)
        if not universe.empty and "Symbol" in universe.columns:
            symbols=universe["Symbol"].astype(str).str.upper().tolist()[:500]
            mapping=mapping[mapping["Symbol"].isin(symbols)].copy()
        mapping=mapping.drop_duplicates("Symbol")
        inst={"NSE_EQ":[int(x) if str(x).isdigit() else str(x) for x in mapping["SecurityId"].tolist()]}
        data,status=dhan_ohlc(client_id,token,inst)
        rows=[]
        block=data.get("NSE_EQ",{}) if isinstance(data,dict) else {}
        reverse={str(r.SecurityId):r.Symbol for r in mapping.itertuples()}
        for sec,q in block.items():
            o=q.get("ohlc",{}) if isinstance(q,dict) else {}
            rows.append({"Symbol":reverse.get(str(sec),str(sec)),"Previous/Close":o.get("close"),"Today Open":o.get("open"),"Today High":o.get("high"),"Today Low":o.get("low"),"LTP":q.get("last_price")})
        df=pd.DataFrame(rows)
        st.session_state["dhan_closed_df"]=df
        st.session_state["dhan_closed_status"]=status
        st.session_state["dhan_closed_count"]=len(df)
    df=st.session_state.get("dhan_closed_df",pd.DataFrame())
    status=st.session_state.get("dhan_closed_status","Not refreshed yet")
    count=int(st.session_state.get("dhan_closed_count",0))
    st.markdown("<div class='grid'>"+"".join([card("NIFTY 500 STOCKS",f"{count}/500"),card("Dhan Quote Status",status),card("CLOSED VALUES","READY" if count else "WAITING","ok" if count else "wait"),card("PDH/PDL SOURCE","Historical layer"),card("LAST CHECK",datetime.now(IST).strftime("%H:%M:%S"))])+"</div>",unsafe_allow_html=True)
    if not df.empty:
        st.dataframe(df.sort_values("Symbol"),use_container_width=True,hide_index=True,height=520)
        st.download_button("⬇️ Download Dhan Closed Values CSV",df.to_csv(index=False).encode(),"dhan_closed_values.csv","text/csv")
else:st.info("Add DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN to Streamlit Secrets first.")

st.markdown("### 📌 PDH / PDL / PDC Reference")
payload=reference.get("previous_day",{}) if isinstance(reference,dict) else {}
if not isinstance(payload,dict):payload={}
nifty_close=payload.get("nifty500_close") or payload.get("nifty_close") or reference.get("nifty500_previous_close")
pdh=payload.get("pdh");pdl=payload.get("pdl");pdc=payload.get("pdc") or payload.get("previous_close")
coverage=payload.get("coverage") or reference.get("reference_data_count")
st.markdown("<div class='grid'>"+"".join([card("NIFTY 500 PREVIOUS CLOSE",nifty_close if nifty_close is not None else "WAITING"),card("PDH",pdh if pdh is not None else "WAITING"),card("PDL",pdl if pdl is not None else "WAITING"),card("PDC",pdc if pdc is not None else "WAITING"),card("REFERENCE COVERAGE",f"{coverage}/500" if coverage is not None else "WAITING")])+"</div>",unsafe_allow_html=True)

st.markdown("<div class='note'><b>Separation rule:</b> this page is for closed/reference data. Today's live NIFTY 500, A/D, sectors, LTP and S1–S5 signals remain on the live dashboard. No artificial values are generated when Dhan data is unavailable.</div>",unsafe_allow_html=True)
st.caption(f"Checked {datetime.now(IST).strftime('%d %b %Y %H:%M:%S IST')} • Paper trading only")
