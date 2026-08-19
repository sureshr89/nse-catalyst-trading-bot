"""Historical / Previous-Day data view. Kept separate from the live master dashboard."""
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import requests
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="Historical Data | NSE Catalyst", page_icon="📚", layout="wide")

st.markdown("""
<style>
html,body,[class*="css"]{font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
.block-container{max-width:1450px;padding-top:1.2rem;padding-bottom:2rem}
.title{font-size:clamp(1.8rem,4vw,2.7rem);font-weight:900;color:#f4f7fb;margin-bottom:5px}
.sub{color:#9fb1ca;font-size:.9rem;margin-bottom:18px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.card{border:1px solid #2b4163;background:linear-gradient(145deg,#111b2b,#0f1928);border-radius:14px;padding:14px;min-height:86px}
.card small{color:#9fb1ca;font-size:.68rem;font-weight:800;text-transform:uppercase}
.card b{display:block;color:#f4f7fb;font-size:1.25rem;margin-top:7px}
.ok{color:#43d17a!important}.wait{color:#ffd166!important}.bad{color:#ff6675!important}
.note{border:1px solid #2b4163;background:#111b2b;border-radius:12px;padding:13px 15px;color:#dbe6f5;margin:12px 0}
@media(max-width:800px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.block-container{padding:.9rem .8rem 1.5rem}}
@media(max-width:430px){.grid{grid-template-columns:1fr 1fr}.card{padding:11px;min-height:78px}.card b{font-size:1.02rem}}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>📚 Historical / Previous-Day Data</div>", unsafe_allow_html=True)
st.markdown("<div class='sub'>Closed-market data only • PDH / PDL / PDC / previous-day OHLC • kept separate from the live 15-second scanner</div>", unsafe_allow_html=True)


def secret(name):
    try:
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def card(label, value, cls=""):
    return f"<div class='card'><small>{label}</small><b class='{cls}'>{value}</b></div>"

client_id = secret("DHAN_CLIENT_ID")
token = secret("DHAN_ACCESS_TOKEN")

# Use the repository's existing cached/reference outputs when present.
def load_json(name):
    try:
        return json.loads((ROOT / "outputs" / name).read_text(encoding="utf-8"))
    except Exception:
        return {}

reference = load_json("master_data.json")

st.markdown("### 🔐 Dhan connection")
if client_id and token:
    try:
        r = requests.get(
            "https://api.dhan.co/v2/fundlimit",
            headers={"access-token": token, "client-id": client_id},
            timeout=10,
        )
        if r.ok:
            st.markdown(card("DHAN API", "CONNECTED", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(card("DHAN API", f"HTTP {r.status_code}", "bad"), unsafe_allow_html=True)
    except Exception as e:
        st.markdown(card("DHAN API", "ERROR", "bad"), unsafe_allow_html=True)
        st.caption(str(e)[:180])
else:
    st.markdown(card("DHAN API", "SECRETS MISSING", "wait"), unsafe_allow_html=True)

st.markdown("### 📅 Closed / Reference Values")

# Pull whatever the existing reference layer has already stored. Never fabricate values.
payload = reference.get("previous_day", {}) if isinstance(reference, dict) else {}
if not isinstance(payload, dict):
    payload = {}

nifty_close = payload.get("nifty500_close") or payload.get("nifty_close") or reference.get("nifty500_previous_close")
pdh = payload.get("pdh")
pdl = payload.get("pdl")
pdc = payload.get("pdc") or payload.get("previous_close")
coverage = payload.get("coverage") or reference.get("reference_data_count")

vals = [
    card("NIFTY 500 PREVIOUS CLOSE", nifty_close if nifty_close is not None else "WAITING"),
    card("PDH", pdh if pdh is not None else "WAITING"),
    card("PDL", pdl if pdl is not None else "WAITING"),
    card("PDC", pdc if pdc is not None else "WAITING"),
]
st.markdown("<div class='grid'>" + "".join(vals) + "</div>", unsafe_allow_html=True)

st.markdown("### 📦 Previous-Day Stock Coverage")
if coverage is not None:
    st.markdown(card("REFERENCE STOCK DATA", f"{coverage}/500"), unsafe_allow_html=True)
else:
    st.markdown(card("REFERENCE STOCK DATA", "WAITING", "wait"), unsafe_allow_html=True)

st.markdown("<div class='note'><b>Why this page exists:</b> previous-day values are fixed reference data. They are not mixed with today's live LTP, A/D, sector alignment or strategy signals. S1–S5 can use these values for PDH/PDL/PDC without confusing them with today's intraday OHLC.</div>", unsafe_allow_html=True)

st.markdown("### 🕒 Data timestamp")
st.write(datetime.now(IST).strftime("%d %b %Y %H:%M:%S IST"))

st.markdown("### 📋 Reference details")
if isinstance(payload, dict) and payload:
    clean = {k: v for k, v in payload.items() if k.lower() not in {"token", "access_token", "api_key", "api_secret"}}
    st.json(clean)
else:
    st.info("No cached previous-day payload is available yet. The page will remain separate and will populate when the Dhan historical/reference layer writes closed-market data.")
