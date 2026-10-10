import pytest
from app.providers.demo_news import DemoNewsProvider

@pytest.mark.asyncio
async def test_news_simulation_labeling_and_attribution():
    """
    Verifies that all simulated news articles are explicitly labelled simulated,
    attributed strictly to the demo engine (never real publications), and contain disclaimers.
    """
    provider = DemoNewsProvider()
    articles = await provider.get_market_news(limit=5)

    assert len(articles) > 0
    for article in articles:
        assert article.is_simulated is True
        assert article.source == "Simulated Demo Financial News Engine"
        assert "Simulated financial news" in article.disclaimer
        assert article.published_at is not None
        assert article.title is not None
        assert article.summary is not None

@pytest.mark.asyncio
async def test_news_filter_by_symbols():
    """Verifies that news querying filters articles by related symbol tags."""
    provider = DemoNewsProvider()

    # Query for RELIANCE
    reliance_articles = await provider.get_news_for_symbols(["RELIANCE"])
    assert len(reliance_articles) >= 1
    assert any("RELIANCE" in a.related_symbols for a in reliance_articles)

    # Query for IT companies
    it_articles = await provider.get_news_for_symbols(["TCS", "INFY"])
    assert len(it_articles) >= 1
    assert any("TCS" in a.related_symbols or "INFY" in a.related_symbols for a in it_articles)

@pytest.mark.asyncio
async def test_news_unknown_symbol_empty_result():
    """Verifies that querying symbols with no matching news returns an empty list cleanly."""
    provider = DemoNewsProvider()
    articles = await provider.get_news_for_symbols(["UNKNOWN_SYMBOL_999"])
    assert articles == []

@pytest.mark.asyncio
async def test_news_limit_parameter():
    """Verifies that the limit parameter restricts returned article counts."""
    provider = DemoNewsProvider()
    articles_2 = await provider.get_market_news(limit=2)
    assert len(articles_2) <= 2
