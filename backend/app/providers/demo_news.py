from datetime import datetime, timezone
from typing import List
from app.providers.base import BaseNewsProvider
from app.schemas.market_data import NewsArticle

DEMO_ARTICLES = [
    {
        "id": "demo-news-001",
        "title": "Simulation: Energy Sector Capital Expenditure Review Indicates Green Energy Pivot",
        "summary": "In this simulated scenario, key energy conglomerates model accelerated allocations toward green hydrogen and solar infrastructure for FY26.",
        "related_symbols": ["RELIANCE"],
        "sentiment": "POSITIVE",
    },
    {
        "id": "demo-news-002",
        "title": "Demonstration Feed: Indian IT Majors Expand Generative AI Delivery Frameworks",
        "summary": "Simulated analysis highlights sustained client deal wins in cloud migration and enterprise AI transformation across tier-1 software exporters.",
        "related_symbols": ["TCS", "INFY"],
        "sentiment": "POSITIVE",
    },
    {
        "id": "demo-news-003",
        "title": "Synthetic Analysis: Banking Sector Net Interest Margins Stabilize Near Multi-Year Averages",
        "summary": "Simulated credit growth models project resilient asset quality and steady retail deposit mobilization among leading private lenders.",
        "related_symbols": ["HDFCBANK", "ICICIBANK"],
        "sentiment": "NEUTRAL",
    },
    {
        "id": "demo-news-004",
        "title": "Educational Feed: FMCG Demand Trends Reflect Rural Consumption Uptick in Test Models",
        "summary": "Simulated consumer goods quarterly review indicates volume recovery in rural distribution hubs amid stable raw material inputs.",
        "related_symbols": ["ITC"],
        "sentiment": "POSITIVE",
    },
    {
        "id": "demo-news-005",
        "title": "Simulation Scenario: Telecom Average Revenue Per User Expands in 5G Monetization Test",
        "summary": "Simulated wireless industry metrics point toward premium plan transitions and digital service adoption driving modest ARPU expansion.",
        "related_symbols": ["BHARTIARTL"],
        "sentiment": "POSITIVE",
    },
    {
        "id": "demo-news-006",
        "title": "Simulation Report: Infrastructure Order Books Reach New Highs in Public Capex Demonstration",
        "summary": "Simulated heavy civil engineering tenders demonstrate strong execution pipelines in domestic transit, ports, and renewable transmission projects.",
        "related_symbols": ["LT"],
        "sentiment": "POSITIVE",
    },
    {
        "id": "demo-news-007",
        "title": "Synthetic Market Overview: Auto Sector Commercial Vehicle Volumes Match Seasonal Patterns",
        "summary": "Simulated vehicle registration data tracks steady fleet replacement cycles and passenger SUV order backlog fulfillment.",
        "related_symbols": ["M&M", "BAJAJ-AUTO"],
        "sentiment": "NEUTRAL",
    },
]

class DemoNewsProvider(BaseNewsProvider):
    """
    Simulated financial news provider for platform demonstration.
    - Explicitly labelled simulated.
    - Attributed solely to 'Simulated Demo Financial News Engine' (no real publications).
    - Contains educational/synthetic scenarios.
    """

    PROVIDER_NAME = "Simulated Demo Financial News Engine"
    DISCLAIMER = "Simulated financial news generated for testing and demonstration only. Not verified or real news."

    async def get_news_for_symbols(self, symbols: List[str], limit: int = 10) -> List[NewsArticle]:
        normalized_symbols = {s.strip().upper() for s in symbols if s.strip()}
        now = datetime.now(timezone.utc)

        matched_articles = []
        for item in DEMO_ARTICLES:
            item_symbols = set(item["related_symbols"])
            if normalized_symbols.intersection(item_symbols):
                matched_articles.append(
                    NewsArticle(
                        id=item["id"],
                        title=item["title"],
                        summary=item["summary"],
                        source=self.PROVIDER_NAME,
                        published_at=now,
                        url=None,
                        related_symbols=item["related_symbols"],
                        sentiment=item["sentiment"],
                        is_simulated=True,
                        disclaimer=self.DISCLAIMER,
                    )
                )
                if len(matched_articles) >= limit:
                    break

        return matched_articles

    async def get_market_news(self, limit: int = 10) -> List[NewsArticle]:
        now = datetime.now(timezone.utc)
        articles = []
        for item in DEMO_ARTICLES[:limit]:
            articles.append(
                NewsArticle(
                    id=item["id"],
                    title=item["title"],
                    summary=item["summary"],
                    source=self.PROVIDER_NAME,
                    published_at=now,
                    url=None,
                    related_symbols=item["related_symbols"],
                    sentiment=item["sentiment"],
                    is_simulated=True,
                    disclaimer=self.DISCLAIMER,
                )
            )
        return articles
