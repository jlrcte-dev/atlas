"""RSS feed integration client (real).

Fetches and normalizes articles from configured RSS/Atom feeds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from html import unescape
import re

import feedparser

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
    """RSS feed reader using feedparser."""

    def __init__(self, feed_urls: list[str] | None = None) -> None:
        if feed_urls:
            self.feed_urls = feed_urls
        elif settings.rss_default_feeds:
            self.feed_urls = [u.strip() for u in settings.rss_default_feeds.split(",") if u.strip()]
        else:
            self.feed_urls = []

    def fetch_all(self) -> list[RSSArticle]:
        logger.info("fetch_all (real) feeds=%d", len(self.feed_urls))

        articles: list[RSSArticle] = []

        for feed_url in self.feed_urls:
            try:
                feed = feedparser.parse(feed_url)

                feed_title = feed.feed.get("title", "RSS Feed")
                entries = feed.entries or []

                for entry in entries[:10]:
                    title = getattr(entry, "title", "(sem titulo)")
                    link = getattr(entry, "link", "")
                    published = self._extract_published(entry)
                    summary = self._clean_html(
                        getattr(entry, "summary", "")
                        or getattr(entry, "description", "")
                    )
                    category = self._infer_category(feed_title, title, summary)

                    articles.append(
                        RSSArticle(
                            title=title,
                            link=link,
                            source=feed_title,
                            category=category,
                            published=published,
                            summary=summary,
                        )
                    )

            except Exception as exc:
                logger.warning("Falha ao ler feed %s: %s", feed_url, exc)

        return articles

    def fetch_by_category(self, category: str) -> list[RSSArticle]:
        return [a for a in self.fetch_all() if a.category == category]

    def _extract_published(self, entry: object) -> str:
        published_raw = getattr(entry, "published", "") or getattr(entry, "updated", "")
        if not published_raw:
            return ""

        try:
            return parsedate_to_datetime(published_raw).isoformat()
        except Exception:
            return published_raw

    def _clean_html(self, text: str) -> str:
        if not text:
            return ""
        text = unescape(text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _infer_category(self, source: str, title: str, summary: str) -> str:
        text = f"{source} {title} {summary}".lower()

        if any(term in text for term in ["mercado", "economia", "juros", "inflação", "inflacao", "ibovespa"]):
            return "economia"
        if any(term in text for term in ["ia", "inteligência artificial", "inteligencia artificial", "tecnologia", "software"]):
            return "tecnologia"
        if any(term in text for term in ["empresa", "negócio", "negocio", "startup", "aquisição", "aquisicao"]):
            return "negocios"

        return "geral"

    @staticmethod
    def to_dict(article: RSSArticle) -> dict:
        return asdict(article)