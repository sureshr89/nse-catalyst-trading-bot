from news.sentiment import news_allows_trade


def test_neutral_news_does_not_block_buy_or_sell():
    neutral = {"sentiment": "NEUTRAL"}
    assert news_allows_trade("BUY", neutral) is True
    assert news_allows_trade("SELL", neutral) is True


def test_opposite_directional_news_blocks_trade():
    assert news_allows_trade("BUY", {"sentiment": "NEGATIVE"}) is False
    assert news_allows_trade("SELL", {"sentiment": "POSITIVE"}) is False


def test_supportive_news_allows_trade():
    assert news_allows_trade("BUY", {"sentiment": "POSITIVE"}) is True
    assert news_allows_trade("SELL", {"sentiment": "NEGATIVE"}) is True
