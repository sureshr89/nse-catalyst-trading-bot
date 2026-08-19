"""Single-page NSE Catalyst dashboard entrypoint."""
from pathlib import Path
import json
import streamlit as st

st.set_page_config(page_title="NSE Catalyst", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
ROOT = Path(__file__).resolve().parents[1]

def load_reference():
    for name in ("master_data.json", "previous_day_data.json", "reference_data.json"):
        p = ROOT / "outputs" / name
        try:
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def pick(d, *keys):
    if not isinstance(d, dict): return None
    for k in keys:
        v = d.get(k)
        if v is not None and v != "": return v
    return None

def val(v): return "—" if v is None else str(v)

# One page only. Analysis and closed/reference information stay inside this dashboard.
ref = load_reference()
prev = ref.get("previous_day", {}) if isinstance(ref, dict) else {}
if not isinstance(prev, dict): prev = {}
nifty_close = pick(prev, "nifty500_close", "nifty_close", "previous_close") or pick(ref, "nifty500_previous_close")
ad_ratio = pick(prev, "ad_ratio", "previous_ad_ratio") or pick(ref, "previous_ad_ratio")
adv = pick(prev, "advances", "advance_count", "adv")
dec = pick(prev, "declines", "decline_count", "dec")
sector_alignment = pick(prev, "sector_alignment", "sector_bias", "sector_change") or pick(ref, "previous_sector_alignment")
positive_sectors = pick(prev, "positive_sectors", "sectors_positive")
negative_sectors = pick(prev, "negative_sectors", "sectors_negative")
coverage = pick(prev, "coverage", "ad_coverage", "market_data_coverage") or pick(ref, "reference_data_count")
data_date = pick(prev, "date", "data_date", "session_date") or pick(ref, "previous_day_date")

st.markdown("""
<style>
.pc-title{font-size:1.05rem;font-weight:850;margin:0 0 8px}.pc-grid{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:7px;margin-bottom:12px}.pc-card{border:1px solid #2b4163;background:linear-gradient(145deg,#111b2b,#0f1928);border-radius:10px;padding:8px 9px;min-height:58px}.pc-card small{display:block;color:#9fb1ca;font-size:.57rem;font-weight:800;text-transform:uppercase;line-height:1.15}.pc-card b{display:block;color:#f4f7fb;font-size:.88rem;margin-top:4px;line-height:1.15}@media(max-width:900px){.pc-grid{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:600px){.pc-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.pc-card{min-height:54px;padding:7px 8px}.pc-card b{font-size:.84rem}}
</style>""", unsafe_allow_html=True)

st.markdown("<div class='pc-title'>📚 Previous Close — Reference Data</div>", unsafe_allow_html=True)
st.markdown("<div class='pc-grid'>" + "".join([
    f"<div class='pc-card'><small>NIFTY 500 CLOSE</small><b>{val(nifty_close)}</b></div>",
    f"<div class='pc-card'><small>A/D RATIO</small><b>{val(ad_ratio)}</b></div>",
    f"<div class='pc-card'><small>ADVANCES</small><b>{val(adv)}</b></div>",
    f"<div class='pc-card'><small>DECLINES</small><b>{val(dec)}</b></div>",
    f"<div class='pc-card'><small>SECTOR ALIGNMENT</small><b>{val(sector_alignment)}</b></div>",
    f"<div class='pc-card'><small>POSITIVE SECTORS</small><b>{val(positive_sectors)}</b></div>",
    f"<div class='pc-card'><small>NEGATIVE SECTORS</small><b>{val(negative_sectors)}</b></div>",
    f"<div class='pc-card'><small>COVERAGE / DATE</small><b>{val(coverage)} • {val(data_date)}</b></div>
]) + "</div>", unsafe_allow_html=True)

master = st.Page("master_dashboard.py", title="NSE Catalyst", icon="📊", default=True)
pg = st.navigation([master], position="hidden")
pg.run()
