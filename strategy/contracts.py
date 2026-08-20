"""Single source of truth for the clean Dhan-only S1-S5 strategy contract."""
STRATEGY_VERSION="2026.08.20.clean-dhan-v1"
STRATEGY_1_NAME="PDH/PDL Sweep + Open Reclaim"
STRATEGY_2_NAME="PDH/PDL Breakout + Retest"
STRATEGY_3_NAME="Opposite PDH/PDL Sweep + Open Reversal"
STRATEGY_4_NAME="Intraday High/Low Breakout"
STRATEGY_5_NAME="Direct PDH/PDL Breakout"
COMMON_RULES=(
 ("Universe","NIFTY 500"),
 ("Live source","Dhan only; no Yahoo or legacy strategy source"),
 ("BUY market filter","NIFTY 500 change > 0% AND A/D ratio > 1 AND positive sectors > negative sectors"),
 ("SELL market filter","NIFTY 500 change < 0% AND A/D ratio < 1 AND negative sectors > positive sectors"),
 ("Coverage","Exactly 500 verified NIFTY 500 quotes and 500 sector mappings"),
 ("Data","Dhan live OHLC/LTP + Dhan PDH/PDL/PDC + completed Dhan 1-minute candles"),
 ("Previous candle","Diagnostic only; never a hard entry blocker"),
 ("Indicators","Not used for S1-S5 entry"),
 ("Entry","Live LTP trigger; no current-candle close confirmation"),
 ("Capital allocation","₹2,50,000 per trade"),
 ("Max trades","Maximum 2 trades per strategy per day"),
 ("Daily loss limit","Maximum ₹3,000 loss per strategy per day"),
 ("Target","1.25R"),
 ("Position risk","Actual risk ₹1,400–₹1,500; otherwise no trade"),
 ("Exit","SL or 1.25R target; mandatory 15:00 IST paper square-off"),
 ("Execution","PAPER TRADING ONLY"),
 ("Look-ahead rule","Only completed candles and current Dhan LTP/quote data available at evaluation time"),
)
STRATEGY_RULES={
 "S1":(("BUY","Open > PDH → day Low <= PDH → live LTP > Today's Open → BUY"),("SELL","Open < PDL → day High >= PDL → live LTP < Today's Open → SELL"),("SL","BUY = PDH • SELL = PDL")),
 "S2":(("BUY","Completed candle history shows break above PDH → pullback to PDH → live LTP >= PDH → BUY"),("SELL","Completed candle history shows break below PDL → pullback to PDL → live LTP <= PDL → SELL"),("SL","BUY = pullback Low • SELL = pullback High")),
 "S3":(("BUY","Open inside PDH/PDL → day Low <= PDL → live LTP > Today's Open → BUY"),("SELL","Open inside PDH/PDL → day High >= PDH → live LTP < Today's Open → SELL"),("SL","BUY = Today's Low • SELL = Today's High")),
 "S4":(("BUY","Live LTP breaks previously completed intraday High → BUY"),("SELL","Live LTP breaks previously completed intraday Low → SELL"),("SL","BUY = previous intraday Low • SELL = previous intraday High")),
 "S5":(("BUY","Live LTP > PDH → BUY"),("SELL","Live LTP < PDL → SELL"),("SL","BUY = PDH • SELL = PDL")),
}
def strategy_metadata(strategy:str)->dict:
    key=str(strategy).upper().strip();aliases={"STRATEGY_1":"S1","OPEN_RETURN":"S1","STRATEGY_2":"S2","STRATEGY_3":"S3","STRATEGY_4":"S4","STRATEGY_5":"S5"};canonical=aliases.get(key,key)
    if canonical not in STRATEGY_RULES:raise ValueError(f"Unknown strategy: {strategy}")
    names={"S1":STRATEGY_1_NAME,"S2":STRATEGY_2_NAME,"S3":STRATEGY_3_NAME,"S4":STRATEGY_4_NAME,"S5":STRATEGY_5_NAME}
    return {"strategy":canonical,"name":names[canonical],"version":STRATEGY_VERSION,"rules":COMMON_RULES+STRATEGY_RULES[canonical]}
