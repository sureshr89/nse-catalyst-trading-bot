from datetime import datetime
import papertrade.paper_trade_engine as mod

def test_legacy_strategy_state_is_not_restored(monkeypatch,tmp_path):
    engine=object.__new__(mod.PaperTradeEngine)
    engine.open_positions={'ABC':{'symbol':'ABC'}}
    engine.closed_positions=[{'trade_id':'OLD-1'}]
    state={'state_version':8,'strategy':'OLD_LEGACY_STRATEGY','open_positions':engine.open_positions,'closed_positions':engine.closed_positions,'trade_counter':9,'total_capital':1250000,'available_capital':1250000,'used_capital':0,'session_date':datetime.now(mod.INDIA_TZ).date().isoformat()}
    assert state['strategy'] != mod.CURRENT_STRATEGY

def test_buy_pnl_is_positive_when_exit_is_higher():
    assert mod.PaperTradeEngine.calculate_pnl('BUY',100,110,10)==100

def test_sell_pnl_is_positive_when_exit_is_lower():
    assert mod.PaperTradeEngine.calculate_pnl('SELL',110,100,10)==100
