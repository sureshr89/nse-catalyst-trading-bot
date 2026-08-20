"""Persistent paper-trade execution engine for the clean NIFTY 500 S1-S5 strategy."""
import json, os, re
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from config.settings import PAPER_TRADING,LIVE_TRADING,TRADING_START,LAST_ENTRY_TIME,SQUARE_OFF_TIME,MARKET_CLOSE,TOTAL_CAPITAL,MAX_OPEN_POSITIONS,MIN_REQUIRED_RISK,MAX_RISK_PER_TRADE,MIN_RR_RATIO,TRADE_LOG_FILE
from papertrade.persistent_storage import restore_json,sync_json
from strategy.contracts import STRATEGY_VERSION
INDIA_TZ=ZoneInfo("Asia/Kolkata");STATE_VERSION=9;CURRENT_STRATEGY=STRATEGY_VERSION
class PaperTradeEngine:
    """Simulated execution engine. Live trading is deliberately prohibited."""
    def __init__(self):
        self.paper_trading=bool(PAPER_TRADING);self.live_trading=bool(LIVE_TRADING);self.trading_start=TRADING_START;self.last_entry_time=LAST_ENTRY_TIME;self.square_off_time=SQUARE_OFF_TIME;self.market_close=MARKET_CLOSE;self.open_positions={};self.closed_positions=[];self.trade_counter=0;self.total_capital=float(TOTAL_CAPITAL);self.available_capital=float(TOTAL_CAPITAL);self.used_capital=0.0
        from market.price_data import PriceData
        self.price_data=PriceData();self._restore_state()
    def _state_path(self):return os.path.join("outputs","paper_engine_state.json")
    @staticmethod
    def _number(v):
        try:n=float(v);return n if n==n else None
        except (TypeError,ValueError):return None
    @staticmethod
    def _candle_key(v):
        if v is None:return ""
        try:
            p=pd.to_datetime(v,errors="coerce")
            if pd.isna(p):return str(v)
            p=p.tz_localize(INDIA_TZ) if getattr(p,"tzinfo",None) is None else p.tz_convert(INDIA_TZ);return p.isoformat()
        except Exception:return str(v)
    @staticmethod
    def _session_date(v):
        try:
            p=pd.to_datetime(v,errors="coerce")
            if pd.isna(p):return None
            p=p.tz_localize(INDIA_TZ) if getattr(p,"tzinfo",None) is None else p.tz_convert(INDIA_TZ);return p.date()
        except Exception:return None
    @staticmethod
    def _time_string(v):
        if v is None:return None
        try:return v.strftime("%H:%M")
        except Exception:pass
        s=str(v).strip()
        try:return datetime.fromisoformat(s).strftime("%H:%M")
        except ValueError:
            m=re.search(r"(?:^|T|\s)(\d{2}):(\d{2})",s);return f"{m.group(1)}:{m.group(2)}" if m else None
    @staticmethod
    def _trade_number(t):
        m=re.search(r"PAPER-(\d+)$",str(t).strip().upper());return int(m.group(1)) if m else 0
    def _valid_open_position(self,k,p):
        if not isinstance(p,dict):return False
        symbol=str(p.get("symbol",k)).strip().upper();sig=str(p.get("signal","")).strip().upper();e=self._number(p.get("entry"));sl=self._number(p.get("stop_loss"));tg=self._number(p.get("target"));q=self._number(p.get("quantity"))
        return bool(symbol==str(k).strip().upper() and sig in {"BUY","SELL"} and e and e>0 and sl and sl>0 and tg and tg>0 and q and q>0 and int(q)==q and p.get("trade_id"))
    def _migrate_state(self,state,version):
        s=dict(state);s.setdefault("open_positions",{});s.setdefault("closed_positions",[]);s.setdefault("trade_counter",0);s.setdefault("total_capital",TOTAL_CAPITAL);s.setdefault("available_capital",s.get("total_capital",TOTAL_CAPITAL));s.setdefault("used_capital",0.0);s.setdefault("session_date",s.get("saved_at"))
        if not isinstance(s["open_positions"],dict) or not isinstance(s["closed_positions"],list):raise ValueError(f"Unsupported paper state collections in legacy version {version}")
        s["state_version"]=STATE_VERSION;return s
    def _restore_state(self):
        path=self._state_path()
        try:
            restore_json(path,path.replace(os.sep,"/"))
            if not os.path.exists(path):return
            with open(path,"r",encoding="utf-8") as f:state=json.load(f)
            version=int(state.get("state_version",0) or 0)
            if version>STATE_VERSION:return
            if version<STATE_VERSION:state=self._migrate_state(state,version)
            if str(state.get("strategy","")).strip()!=CURRENT_STRATEGY:
                state={"state_version":STATE_VERSION,"strategy":CURRENT_STRATEGY,"open_positions":{},"closed_positions":[],"trade_counter":0,"total_capital":TOTAL_CAPITAL,"available_capital":TOTAL_CAPITAL,"used_capital":0.0,"session_date":datetime.now(INDIA_TZ).date().isoformat()}
            self.open_positions={str(k).strip().upper():v for k,v in state.get("open_positions",{}).items() if self._valid_open_position(k,v)};self.closed_positions=[v for v in state.get("closed_positions",[]) if isinstance(v,dict)]
            d=self._session_date(state.get("session_date") or state.get("saved_at"))
            if d is not None and d!=datetime.now(INDIA_TZ).date():self.open_positions={};self.closed_positions=[]
            for p in self.open_positions.values():p.setdefault("mae",0.0);p.setdefault("mfe",0.0);p.setdefault("last_processed_candle",self._candle_key(p.get("entry_time")));p.setdefault("last_live_price",None)
            self.total_capital=float(state.get("total_capital",TOTAL_CAPITAL) or TOTAL_CAPITAL)
            counters=[self._trade_number(p.get("trade_id")) for p in self.open_positions.values()]+[self._trade_number(p.get("trade_id")) for p in self.closed_positions]
            try:
                j=pd.read_csv(TRADE_LOG_FILE)
                if "trade_id" in j.columns:counters.extend(j["trade_id"].map(self._trade_number).tolist())
            except Exception:pass
            self.trade_counter=max([int(state.get("trade_counter",0) or 0),*counters],default=0);self.used_capital=round(sum(float(p.get("entry",0) or 0)*int(float(p.get("quantity",0) or 0)) for p in self.open_positions.values()),2);self.available_capital=round(self.total_capital-self.used_capital,2)
            if self.available_capital<0:raise ValueError("Persisted open positions exceed total capital")
            self._save_state()
        except Exception as e:print(f"Paper state restore skipped: {type(e).__name__}: {e}")
    def _save_state(self):
        path=self._state_path();os.makedirs(os.path.dirname(path),exist_ok=True);state={"state_version":STATE_VERSION,"strategy":CURRENT_STRATEGY,"session_date":datetime.now(INDIA_TZ).date().isoformat(),"open_positions":self.open_positions,"closed_positions":self.closed_positions,"trade_counter":self.trade_counter,"total_capital":self.total_capital,"available_capital":self.available_capital,"used_capital":self.used_capital,"saved_at":datetime.now(INDIA_TZ).isoformat()}
        try:
            with open(path,"w",encoding="utf-8") as f:json.dump(state,f,ensure_ascii=False,indent=2,default=str);f.flush()
            sync_json(path,path.replace(os.sep,"/"),"Save clean S1-S5 paper-trading state")
        except Exception as e:print(f"Paper state sync skipped: {type(e).__name__}: {e}")
    def has_open_position(self,symbol):return str(symbol).strip().upper() in self.open_positions
    def _validate_trade(self,t):
        if not isinstance(t,dict):return None,"Trade must be a dictionary"
        if not self.paper_trading:return None,"Paper trading is disabled"
        if self.live_trading:return None,"Live trading must remain disabled"
        if not t.get("approved",False):return None,"Trade has not been approved"
        symbol=str(t.get("symbol","")).strip().upper();sig=str(t.get("signal","")).strip().upper();e=self._number(t.get("entry"));sl=self._number(t.get("stop_loss"));tg=self._number(t.get("target"));qv=self._number(t.get("quantity"));ar=self._number(t.get("actual_risk"))
        if not symbol:return None,"Missing symbol"
        if sig not in {"BUY","SELL"}:return None,"Invalid signal"
        if any(v is None or v<=0 for v in (e,sl,tg,qv)):return None,"Invalid trade values"
        if int(qv)!=qv:return None,"Quantity must be a positive whole number"
        q=int(qv)
        if sig=="BUY" and (sl>=e or tg<=e):return None,"Invalid BUY stop/target"
        if sig=="SELL" and (sl<=e or tg>=e):return None,"Invalid SELL stop/target"
        risk=round(abs(e-sl)*q,2);reward=round(abs(tg-e)*q,2);rr=reward/risk if risk>0 else 0
        if risk<float(MIN_REQUIRED_RISK):return None,f"Actual risk Rs {risk:.2f} is below minimum {float(MIN_REQUIRED_RISK):.2f}"
        if risk>float(MAX_RISK_PER_TRADE):return None,f"Actual risk Rs {risk:.2f} exceeds maximum {float(MAX_RISK_PER_TRADE):.2f}"
        if rr<float(MIN_RR_RATIO):return None,f"Risk:Reward {rr:.2f} is below minimum 1:{float(MIN_RR_RATIO):.1f}"
        if ar is not None and abs(ar-risk)>1:return None,"Approved risk does not match calculated risk"
        hh=self._time_string(t.get("entry_time") or datetime.now(INDIA_TZ))
        if hh is None or hh<self.trading_start or hh>self.last_entry_time:return None,"Entry time is outside the allowed window"
        value=round(e*q,2)
        if value>self.available_capital:return None,"Insufficient available capital"
        if self.has_open_position(symbol):return None,f"{symbol} already has an open position"
        if len(self.open_positions)>=MAX_OPEN_POSITIONS:return None,"Maximum open positions reached"
        return {"symbol":symbol,"signal":sig,"entry_time":t.get("entry_time"),"entry":round(e,4),"stop_loss":round(sl,4),"target":round(tg,4),"quantity":q,"risk":risk,"reward":reward,"rr":round(rr,4),"position_value":value},None
    def open_trade(self,t):
        v,reason=self._validate_trade(t)
        if v is None:return {"opened":False,"reason":reason}
        self.trade_counter+=1;tid=f"PAPER-{self.trade_counter:04d}";p={"trade_id":tid,"symbol":v["symbol"],"stock":v["symbol"],"signal":v["signal"],"buy_sell":v["signal"],"entry_time":v["entry_time"],"entry":v["entry"],"stop_loss":v["stop_loss"],"target":v["target"],"quantity":v["quantity"],"risk":v["risk"],"reward":v["reward"],"rr":v["rr"],"mae":0.0,"mfe":0.0,"last_processed_candle":self._candle_key(v["entry_time"]),"last_live_price":v["entry"],"status":"OPEN","exit_time":None,"exit_price":None,"exit_reason":None,"pnl":None}
        ignored={"approved","reasons","min_rr_ratio","min_required_risk","max_risk","capital","trade_count"}
        for k,val in t.items():
            if k not in ignored and k not in p and val is not None:p[k]=val
        p["risk_per_share"]=round(abs(v["entry"]-v["stop_loss"]),4);p["actual_risk"]=v["risk"];p["position_value"]=v["position_value"];self.open_positions[v["symbol"]]=p;self.used_capital=round(self.used_capital+v["position_value"],2);self.available_capital=round(self.total_capital-self.used_capital,2);self._save_state();return {"opened":True,"trade_id":tid,"position":p.copy()}
    @staticmethod
    def calculate_pnl(signal,entry,exit_price,quantity):
        if signal=="BUY":return round((exit_price-entry)*quantity,2)
        if signal=="SELL":return round((entry-exit_price)*quantity,2)
        return 0.0
    def _update_excursions(self,p,h,l):
        e=float(p.get("entry",0) or 0);q=int(float(p.get("quantity",0) or 0));sig=str(p.get("signal","")).upper()
        if e<=0 or q<=0:return
        fav=max(0,(h-e)*q) if sig=="BUY" else max(0,(e-l)*q);adv=max(0,(e-l)*q) if sig=="BUY" else max(0,(h-e)*q);p["mfe"]=round(max(float(p.get("mfe",0) or 0),fav),2);p["mae"]=round(max(float(p.get("mae",0) or 0),adv),2)
    def close_position(self,symbol,exit_price,exit_time,reason):
        symbol=str(symbol).strip().upper()
        if not self.has_open_position(symbol):return None
        x=self._number(exit_price)
        if x is None or x<=0:return None
        p=self.open_positions[symbol];p.update({"status":"CLOSED","exit_time":exit_time,"exit_price":round(x,4),"exit_reason":reason,"pnl":self.calculate_pnl(p["signal"],p["entry"],x,p["quantity"])})
        c=p.copy();self.closed_positions.append(c);value=round(float(p["entry"])*int(p["quantity"]),2);self.used_capital=round(max(0,self.used_capital-value),2);self.available_capital=round(self.total_capital-self.used_capital,2);del self.open_positions[symbol];self._save_state();return c
    def process_live_price(self,symbol,price,timestamp=None,high=None,low=None):
        symbol=str(symbol).strip().upper()
        if not self.has_open_position(symbol):return None
        value=self._number(price)
        if value is None or value<=0:return None
        now=datetime.now(INDIA_TZ)
        if not(time(9,15)<=now.time()<=time(15,30)):return None
        if high is None or low is None:
            try:
                live=self.price_data.get_latest_live_price(symbol,max_age_seconds=2)
                if live is not None:high=live.get("High");low=live.get("Low");value=self._number(live.get("Close")) or value;timestamp=live.get("Datetime") or timestamp
            except Exception:pass
        p=self.open_positions[symbol];sig=str(p.get("signal")).upper();sl=float(p["stop_loss"]);tg=float(p["target"]);oh=max(value,self._number(high) or value);ol=min(value,self._number(low) or value);p["last_live_price"]=value;self._update_excursions(p,oh,ol);stamp=timestamp or now
        if sig=="BUY":a,b=ol<=sl,oh>=tg
        elif sig=="SELL":a,b=oh>=sl,ol<=tg
        else:return None
        if a and b:return self.close_position(symbol,sl,stamp,"AMBIGUOUS_LIVE_BAR_STOP_FIRST")
        if a:return self.close_position(symbol,sl,stamp,"STOP_LOSS_LIVE")
        if b:return self.close_position(symbol,tg,stamp,"TARGET_LIVE")
        self._save_state();return None
    def process_candle(self,symbol,candle):
        symbol=str(symbol).strip().upper()
        if not self.has_open_position(symbol):return None
        items=[]
        try:
            h=self.price_data.get_1m(symbol)
            if h is not None and not h.empty:items=h.to_dict("records")
        except Exception:pass
        if not items:
            if not isinstance(candle,dict):
                try:candle=candle.to_dict()
                except Exception:return None
            items=[candle]
        last=self._candle_key(self.open_positions[symbol].get("last_processed_candle"));now=datetime.now(INDIA_TZ);minute=now.replace(second=0,microsecond=0);selected=[]
        for it in items:
            hi=self._number(it.get("High"));lo=self._number(it.get("Low"));cl=self._number(it.get("Close"));ct=it.get("Datetime")
            if hi is None or lo is None or cl is None:continue
            p=pd.to_datetime(ct,errors="coerce")
            if pd.isna(p):continue
            p=p.tz_localize(INDIA_TZ) if getattr(p,"tzinfo",None) is None else p.tz_convert(INDIA_TZ)
            if p.date()!=now.date() or not(time(9,15)<=p.time()<=time(15,30)) or p.to_pydatetime()>=minute:continue
            key=self._candle_key(p)
            if key and last and key<=last:continue
            selected.append((p,key,hi,lo))
        for p,key,hi,lo in sorted(selected,key=lambda x:x[0]):
            if not self.has_open_position(symbol):return None
            pos=self.open_positions[symbol];self._update_excursions(pos,hi,lo);sig=str(pos["signal"]).upper();sl=float(pos["stop_loss"]);tg=float(pos["target"]);a,b=((lo<=sl,hi>=tg) if sig=="BUY" else (hi>=sl,lo<=tg));pos["last_processed_candle"]=key or last
            if a and b:return self.close_position(symbol,sl,key,"AMBIGUOUS_CANDLE_STOP_FIRST")
            if a:return self.close_position(symbol,sl,key,"STOP_LOSS")
            if b:return self.close_position(symbol,tg,key,"TARGET")
        self._save_state();return None
    def summary(self):
        vals=[self._number(t.get("pnl")) or 0 for t in self.closed_positions];return {"open_positions":len(self.open_positions),"closed_positions":len(self.closed_positions),"winning_trades":sum(1 for x in vals if x>0),"losing_trades":sum(1 for x in vals if x<0),"total_pnl":round(sum(vals),2),"total_capital":self.total_capital,"available_capital":round(self.available_capital,2),"used_capital":round(self.used_capital,2)}
