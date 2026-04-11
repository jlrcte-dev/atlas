"""News Briefing service.

Fetches, normalizes, categorizes, and summarizes RSS articles.
"""

from __future__ import annotations

from collections import defaultdict

from app.core.logging import get_logger, log_action
from app.integrations.rss_client import RSSClient

logger = get_logger("services.news")


class NewsService:
    def __init__(self) -> None:
        self.client = RSSClient()

    def fetch_rss(self) -> list[dict]:
        """Return raw article list as dicts."""
        articles = self.client.fetch_all()
        log_action(logger, "fetch_rss", total=len(articles))
        return [RSSClient.to_dict(a) for a in articles]

    def normalize_articles(self) -> list[dict]:
        """Return articles in a uniform schema."""
        articles = self.client.fetch_all()
        return [
            {
                "title": a.title,
                "source": a.source,
                "category": a.category,
                "published": a.published,
                "summary": a.summary,
                "link": a.link,
            }
            for a in articles
        ]

    def summarize_news(self) -> dict:
        """Categorize and summarize news into a briefing structure."""
        articles = self.client.fetch_all()
        by_category: dict[str, list[dict]] = defaultdict(list)
        for a in articles:
            by_category[a.category].append(RSSClient.to_dict(a))

        categories = {cat: len(items) for cat, items in by_category.items()}

        result = {
            "total": len(articles),
            "categories": categories,
            "by_category": dict(by_category),
            "items": [RSSClient.to_dict(a) for a in articles],
            "summary": (
                f"{len(articles)} noticia(s) em {len(categories)} categoria(s): "
                + ", ".join(f"{cat} ({n})" for cat, n in categories.items())
                + "."
            ),
        }
        log_action(logger, "summarize_news", total=len(articles), categories=len(categories))
        return result

    # Backward compatibility alias
    def get_briefing(self) -> dict:
        return self.summarize_news()
