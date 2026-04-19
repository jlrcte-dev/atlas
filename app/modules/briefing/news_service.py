"""News Briefing service.

Fetches, classifies, scores, deduplicates, and summarizes RSS articles.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime as _parsedate

from app.core.logging import get_logger, log_action
from app.integrations.news_classifier import classify_news
from app.integrations.rss_client import RSSClient

logger = get_logger("services.news")

_PUNCT_RE = re.compile(r'[^\w\s]')
_SPACE_RE = re.compile(r'\s+')


# ── Module-level helpers ──────────────────────────────────────────────────────

def _parse_published(published: str) -> datetime:
    """Parse ISO 8601 or RFC 2822 date string into a timezone-naive datetime.

    Returns datetime.min on empty input or any parse failure so that
    undated articles sort safely to the end of the list (score DESC, date DESC).
    """
    if not published:
        return datetime.min
    try:
        return datetime.fromisoformat(published).replace(tzinfo=None)
    except (ValueError, TypeError):
        pass
    try:
        return _parsedate(published).replace(tzinfo=None)
    except Exception:
        return datetime.min


def _normalize_title(title: str) -> str:
    """Normalize title for duplicate detection: lowercase, strip punctuation, collapse spaces."""
    normalized = _PUNCT_RE.sub('', title.lower())
    return _SPACE_RE.sub(' ', normalized).strip()


def _deduplicate_items(items: list[dict]) -> list[dict]:
    """Remove duplicate articles by normalized title.

    Keeps the highest-score version per group. Ties keep the first seen.
    Losers are marked is_duplicate_candidate=True (internal only) and discarded
    from the result — their score is never modified.
    Result preserves the position of each winning title's first occurrence.
    """
    positions: dict[str, int] = {}  # normalized_title -> index in result
    result: list[dict] = []

    for item in items:
        key = _normalize_title(item["title"])

        if key not in positions:
            positions[key] = len(result)
            result.append(item)
        else:
            idx = positions[key]
            existing = result[idx]
            if item["score"] > existing["score"]:
                # Incoming wins — mark displaced item internally and replace
                existing["flags"] = {**existing["flags"], "is_duplicate_candidate": True}
                result[idx] = item
            else:
                # Existing wins (or tie → keep first) — mark discarded item internally
                item["flags"] = {**item["flags"], "is_duplicate_candidate": True}

    return result


# ── Service ───────────────────────────────────────────────────────────────────

class NewsService:
    def __init__(self) -> None:
        self.client = RSSClient()

    def fetch_rss(self) -> list[dict]:
        """Return raw article list as dicts."""
        articles = self.client.fetch_all()
        log_action(logger, "fetch_rss", total=len(articles))
        return [RSSClient.to_dict(a) for a in articles]

    def normalize_articles(self) -> list[dict]:
        """Return articles in a uniform schema with classification and score applied."""
        articles = self.client.fetch_all()
        result = []
        for a in articles:
            c = classify_news(a.title, a.summary, a.source)
            result.append({
                "title": a.title,
                "source": a.source,
                "category": c["category"],
                "published": a.published,
                "summary": a.summary,
                "link": a.link,
                "flags": c["flags"],
                "score": c["score"],
                "priority": c["priority"],
                "score_reasons": c["score_reasons"],
            })
        return result

    def summarize_news(self) -> dict:
        """Classify, score, deduplicate, and sort articles into a briefing structure.

        Contract (unchanged):
          total        — count of valid (non-noise, post-dedup) items
          categories   — {category: count} excluding ruido
          by_category  — {category: [items]} including ruido for audit
          items        — sorted valid items (score DESC, published DESC)
          summary      — human-readable summary string
        """
        articles = self.client.fetch_all()
        all_items: list[dict] = []

        # Step 1: classify + score every article
        for a in articles:
            c = classify_news(a.title, a.summary, a.source)
            item = {
                **RSSClient.to_dict(a),
                "category": c["category"],
                "flags": c["flags"],
                "score": c["score"],
                "priority": c["priority"],
                "score_reasons": c["score_reasons"],
            }
            all_items.append(item)

        # Step 2: separate noise (kept for audit) from valid items
        noise_items = [i for i in all_items if i["category"] == "ruido"]
        valid_items = [i for i in all_items if i["category"] != "ruido"]

        # Step 3: deduplicate — before sort, keeps highest score per title group
        deduped = _deduplicate_items(valid_items)
        # TODO: [V4] detect trending topics across deduplicated items using clustering

        # Step 4: single sort — score DESC, then published DESC
        # _parse_published handles ISO/RFC2822/empty safely; undated items sort last
        sorted_items = sorted(
            deduped,
            key=lambda i: (i["score"], _parse_published(i.get("published") or "")),
            reverse=True,
        )
        # TODO: [V4] group sorted items by theme for richer briefing sections

        # Step 5: recompute by_category from final items + noise for audit
        by_category: dict[str, list[dict]] = defaultdict(list)
        for item in sorted_items:
            by_category[item["category"]].append(item)
        for item in noise_items:
            by_category["ruido"].append(item)

        categories = {
            cat: len(items)
            for cat, items in by_category.items()
            if cat != "ruido"
        }

        high_count = sum(1 for i in sorted_items if i["priority"] == "high")
        high_suffix = f" Destaques: {high_count} de alta prioridade." if high_count else ""

        result = {
            "total": len(sorted_items),
            "categories": categories,
            "by_category": dict(by_category),
            "items": sorted_items,
            # TODO: [V4] replace summary string with AI-generated digest of top items
            "summary": f"{len(sorted_items)} notícia(s) em {len(categories)} categoria(s).{high_suffix}",
        }

        log_action(logger, "summarize_news", total=len(sorted_items), categories=len(categories), high=high_count)
        return result

    # Backward compatibility alias
    def get_briefing(self) -> dict:
        return self.summarize_news()
