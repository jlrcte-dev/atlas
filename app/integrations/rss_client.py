"""RSS feed integration client (stub).

Returns mock data. Replace with feedparser or real RSS parsing
when connecting to production feeds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("integrations.rss")


@dataclass
class RSSArticle:
    title: str
    link: str
    source: str
    category: str
    published: str
    summary: str


class RSSClient:
    """RSS feed reader. Returns mock data until real parser is wired."""

    def __init__(self, feed_urls: list[str] | None = None) -> None:
        if feed_urls:
            self.feed_urls = feed_urls
        elif settings.rss_default_feeds:
            self.feed_urls = [u.strip() for u in settings.rss_default_feeds.split(",") if u.strip()]
        else:
            self.feed_urls = []

    def fetch_all(self) -> list[RSSArticle]:
        logger.info("fetch_all (stub) feeds=%d", len(self.feed_urls))
        return [
            RSSArticle(
                title="Mercado abre em alta com otimismo global",
                link="https://example.com/mercado-alta",
                source="Reuters Business",
                category="economia",
                published="2026-04-10T07:00:00",
                summary="Ibovespa sobe 1.2% na abertura, puxado por commodities.",
            ),
            RSSArticle(
                title="Nova regulamentacao de IA entra em vigor na UE",
                link="https://example.com/regulamentacao-ia",
                source="Reuters Technology",
                category="tecnologia",
                published="2026-04-10T06:30:00",
                summary="AI Act europeu comeca a ser aplicado com foco em sistemas de alto risco.",
            ),
            RSSArticle(
                title="Startup brasileira capta US$ 50M em serie B",
                link="https://example.com/startup-serie-b",
                source="Reuters Business",
                category="negocios",
                published="2026-04-10T05:45:00",
                summary="Fintech de pagamentos recebe aporte liderado por fundo americano.",
            ),
        ]

    def fetch_by_category(self, category: str) -> list[RSSArticle]:
        return [a for a in self.fetch_all() if a.category == category]

    @staticmethod
    def to_dict(article: RSSArticle) -> dict:
        return asdict(article)
