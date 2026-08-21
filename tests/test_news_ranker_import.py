def test_news_ranker_imports_without_optional_dependencies():
    import market.news_ranker as news_ranker
    assert callable(news_ranker.rank)
    assert callable(news_ranker.refresh_async)
