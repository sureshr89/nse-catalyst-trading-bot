from strategy.contracts import STRATEGY_VERSION
import papertrade.paper_trade_engine as mod


def test_paper_engine_uses_current_clean_strategy_version():
    assert mod.CURRENT_STRATEGY == STRATEGY_VERSION
    assert mod.STATE_VERSION >= 9


def test_legacy_strategy_state_can_never_match_current_contract():
    assert 'NIFTY_500_PDH_PDL_OPEN_RETURN' != mod.CURRENT_STRATEGY


def test_buy_and_sell_pnl_are_directionally_correct():
    assert mod.PaperTradeEngine.calculate_pnl('BUY', 100, 110, 10) == 100
    assert mod.PaperTradeEngine.calculate_pnl('SELL', 110, 100, 10) == 100
