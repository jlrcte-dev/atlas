"""News Briefing service.

Fetches, classifies, scores, deduplicates, and summarizes RSS articles.

Pipeline (summarize_news):
  1.  Date gate           — discard articles not published today (BRT)
  2.  Quality gate        — discard low-quality articles before scoring
  3.  Scope gate          — drop items outside portfolio/macro/geo scope (no classification)
  4.  Classification      — classify + score via deterministic engine
  5.  Noise split         — separate noise (ruido) from valid items
  6.  Exact dedup         — remove exact-title duplicates, keep highest score
  7.  Near-duplicate gate — SimHash fingerprint filter, Hamming ≤ threshold
  8.  Ranking             — sort by final_score = score + quality_score*2, then date DESC
  9.  Curation            — top-5, max 3 high + medium only, low discarded
 10.  Diversity           — cap same-category items at 2 when alternatives exist
 11.  Output              — strip internal fields and build response dict
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime as _parsedate

from app.core.logging import get_logger, log_action
from app.integrations.news_classifier import (
    classify_news,
    compute_quality_score,
    is_low_quality,
    _normalize_text,
)
from app.integrations.rss_client import RSSClient
from app.integrations.simhash_utils import hamming_distance, simhash
from app.integrations.tracked_scope import evaluate_scope

logger = get_logger("services.news")

_TZ_SP = timezone(timedelta(hours=-3))  # BRT: Brazil abolished DST in 2019, permanently UTC-3


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


def _is_today_sp(published_str: str) -> bool:
    """Return True only if the article was published today (America/Sao_Paulo).

    Fail closed: absent, invalid, or unparseable dates return False.
    Uses the ISO string produced by RSSClient._extract_published.
    """
    if not published_str:
        return False
    today = datetime.now(_TZ_SP).date()
    try:
        dt = datetime.fromisoformat(published_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_TZ_SP)
        return dt.astimezone(_TZ_SP).date() == today
    except (ValueError, TypeError):
        pass
    try:
        dt = _parsedate(published_str)
        return dt.astimezone(_TZ_SP).date() == today
    except Exception:
        return False


# ── Pipeline: internal field management ──────────────────────────────────────

def _strip_internal_fields(item: dict) -> dict:
    """Remove all _-prefixed internal fields before API serialization.

    Internal fields (e.g. _normalized_text, _internal_score) carry state
    for future AI enrichment but must never appear in API responses.
    """
    return {k: v for k, v in item.items() if not k.startswith('_')}


def _build_item(article, normalized_text: str) -> dict:
    """Classify an article and return an enriched item dict.

    normalized_text must be pre-computed by the caller (via _normalize_text)
    and is reused here to avoid redundant normalization.
    _-prefixed fields carry internal state for future AI enrichment;
    they are stripped by _strip_internal_fields before leaving summarize_news.
    """
    c = classify_news(article.title, article.summary, article.source)
    normalized = normalized_text
    return {
        **RSSClient.to_dict(article),
        "category": c["category"],
        "flags": c["flags"],
        "score": c["score"],
        "priority": c["priority"],
        "score_reasons": c["score_reasons"],
        # Internal fields — stripped before API response (see _strip_internal_fields)
        "_normalized_text": normalized,
        "_internal_score": c["score"],
        "_score_reasons_internal": c["score_reasons"],
        "_flags_internal": c["flags"],
    }


# ── Pipeline: curation helpers ────────────────────────────────────────────────

def _curate_top5(items: list[dict]) -> list[dict]:
    """Select up to 5 items: max 3 high-priority, remainder medium. Low items discarded.

    Assumes items are already sorted by score DESC so within each tier
    the highest-scoring articles are chosen first.
    """
    high = [i for i in items if i["priority"] == "high"][:3]
    medium = [i for i in items if i["priority"] == "medium"]
    return (high + medium)[:5]


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
        key = _normalize_text(item["title"])

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


# ── Near-duplicate gate (SimHash) ─────────────────────────────────────────────

# Conservative initial value — 10 differing bits in 64 ≈ ~84% similarity.
# Calibrate upward (more aggressive) or downward (more permissive) based on
# observed false-positive/negative rate in production. Do not move to global
# config until threshold behavior is validated on real data.
_SIMHASH_THRESHOLD: int = 10


def _filter_near_duplicates(items: list[dict]) -> list[dict]:
    """Remove near-duplicate articles using SimHash fingerprinting.

    Iterates items in input order. For each item:
      1. Computes a 64-bit SimHash of its _normalized_text field.
      2. Compares against hashes of all previously accepted items.
      3. If Hamming distance to any accepted hash ≤ _SIMHASH_THRESHOLD → discard.
      4. Otherwise → accept, store hash, add _simhash internal field.

    Winner selection: first-seen heuristic. Items arrive in original discovery
    order (post exact-dedup), consistent with the existing dedup contract.
    Ranking (_rank_items) runs after this layer and reorders by quality.

    Complexity: O(n²) in batch size — acceptable for current volume
    (< 200 items/day after upstream gates). LSH/banding not introduced.
    """
    accepted: list[dict] = []
    accepted_hashes: list[int] = []

    for item in items:
        h = simhash(item.get("_normalized_text", ""))
        is_near_dup = any(
            hamming_distance(h, existing) <= _SIMHASH_THRESHOLD
            for existing in accepted_hashes
        )
        if is_near_dup:
            continue
        item["_simhash"] = h
        accepted.append(item)
        accepted_hashes.append(h)

    return accepted


# ── Ranking helpers (Phase B.2) ───────────────────────────────────────────────

_CATEGORY_LABELS: dict[str, str] = {
    "macro": "Politica monetaria",
    "mercado": "Mercado de acoes",
    "politica": "Cenario politico",
    "internacional": "Economia global",
    "empresas": "Resultados corporativos",
    "tecnologia": "Tecnologia",
    "setorial": "Setorial",
}


def _rank_items(items: list[dict]) -> list[dict]:
    """Sort by final_score = score + quality_score*2, then published DESC.

    quality_score is computed inline and never stored on the item — contract unchanged.
    Score remains dominant; quality_score refines ordering within score ties.
    """
    def _key(item: dict) -> tuple[int, datetime]:
        qs = compute_quality_score(item["title"], item.get("summary", ""))
        return (item["score"] + qs * 2, _parse_published(item.get("published") or ""))

    return sorted(items, key=_key, reverse=True)


def _diversify(curated: list[dict], ranked_pool: list[dict]) -> list[dict]:
    """Soft diversity: cap same-category items at 2 when a valid alternative exists.

    Only triggers when a category appears >= 3 times. Replaces the last (lowest-ranked)
    excess item with the best alternative of equal or higher priority from ranked_pool.
    If no valid alternative exists, the original list is returned unchanged.
    """
    cat_counts = Counter(i["category"] for i in curated)
    if max(cat_counts.values(), default=0) < 3:
        return curated

    result = list(curated)
    used = {_normalize_text(i["title"]) for i in result}
    priority_rank = {"high": 2, "medium": 1, "low": 0}

    for cat, count in cat_counts.items():
        if count < 3:
            continue
        excess_idx = max(
            idx for idx, item in enumerate(result) if item["category"] == cat
        )
        excess_item = result[excess_idx]
        min_pr = priority_rank.get(excess_item["priority"], 0)

        alternative = next(
            (
                i for i in ranked_pool
                if _normalize_text(i["title"]) not in used
                and i["category"] != cat
                and priority_rank.get(i["priority"], 0) >= min_pr
            ),
            None,
        )
        if alternative:
            used.discard(_normalize_text(excess_item["title"]))
            used.add(_normalize_text(alternative["title"]))
            result[excess_idx] = alternative

    return result


def _infer_focus(curated: list[dict]) -> list[str]:
    """Return top-2 category labels from curated items for the summary 'Foco do dia'."""
    counts = Counter(i["category"] for i in curated if i["category"] != "ruido")
    return [_CATEGORY_LABELS.get(cat, cat) for cat, _ in counts.most_common(2)]


# ── Memory integration (fail-safe) ───────────────────────────────────────────

def _log_ranked_news(curated: list[dict]) -> None:
    """Log ranked news events to memory. Fail-safe — never raises.

    The reference_id is normalized via `to_callback_ref` so the same value can
    be reused inside Telegram callback_data without exceeding the 64-byte limit.
    The original link is preserved in the payload for full audit trail.
    """
    try:
        from app.db.session import SessionLocal
        from app.modules.memory.service import MemoryService
        from app.modules.memory.utils import to_callback_ref

        db = SessionLocal()
        try:
            svc = MemoryService(db)
            for item in curated:
                raw = item.get("link") or item.get("title", "")
                ref = to_callback_ref(raw)
                if not ref:
                    continue
                svc.log_event(
                    event_type="news_ranked",
                    source="news",
                    reference_id=ref,
                    payload={
                        "link": item.get("link", ""),
                        "title": item.get("title", ""),
                        "category": item.get("category", ""),
                        "reason": item.get("score_reasons", []),
                    },
                    score=float(item["score"]) if item.get("score") is not None else None,
                )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Memory: falha ao logar noticias rankeadas: %s", exc)


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
        """Classify, score, deduplicate, curate, and summarize today's articles.

        Contract (unchanged):
          total        — count of curated items returned in items[]
          categories   — {category: count} from curated set, excluding ruido
          by_category  — {category: [items]} curated + ruido audit bucket
          items        — curated top-5 (score DESC, max 3 high + medium only)
          summary      — Telegram-aware one-liner (no titles — BriefingService renders items separately)
        """
        articles = self.client.fetch_all()
        all_items: list[dict] = []
        total_fetched_today = 0
        low_quality_count = 0
        scope_dropped_count = 0

        # ── Layer 1: Date gate ────────────────────────────────────────────────
        # ── Layer 2: Quality gate ─────────────────────────────────────────────
        for a in articles:
            if not _is_today_sp(a.published):
                continue
            total_fetched_today += 1

            if is_low_quality(a.title, a.summary):
                low_quality_count += 1
                continue

            # ── Layer 3: Scope gate ───────────────────────────────────────────
            # Normalized once here; reused by scope gate and _build_item.
            normalized_text = _normalize_text(f"{a.title} {a.summary}")
            in_scope, scope_reason = evaluate_scope(normalized_text)
            if not in_scope:
                scope_dropped_count += 1
                continue

            # ── Layer 4: Classification ───────────────────────────────────────
            item = _build_item(a, normalized_text)
            item["_scope_gate_reason_internal"] = scope_reason
            all_items.append(item)

        # ── Layer 5: Noise split ──────────────────────────────────────────────
        noise_items = [i for i in all_items if i["category"] == "ruido"]
        valid_items = [i for i in all_items if i["category"] != "ruido"]

        # ── Layer 6: Exact dedup ─────────────────────────────────────────────
        deduped = _deduplicate_items(valid_items)
        # TODO: [V4] detect trending topics across deduplicated items using clustering

        # ── Layer 7: Near-duplicate gate (SimHash) ────────────────────────────
        near_deduped = _filter_near_duplicates(deduped)
        simhash_dropped_count = len(deduped) - len(near_deduped)

        # ── Layer 8: Ranking ──────────────────────────────────────────────────
        ranked = _rank_items(near_deduped)

        # ── Layer 9: Curation ─────────────────────────────────────────────────
        curated = _curate_top5(ranked)

        # ── Layer 10: Diversity ───────────────────────────────────────────────
        curated = _diversify(curated, ranked)
        _log_ranked_news(curated)

        # ── Layer 11: Output ──────────────────────────────────────────────────
        # Strip internal fields before serialization — must happen before
        # by_category is built so no internal state leaks to API responses.
        curated = [_strip_internal_fields(i) for i in curated]
        noise_items = [_strip_internal_fields(i) for i in noise_items]

        by_category: dict[str, list[dict]] = defaultdict(list)
        for item in curated:
            by_category[item["category"]].append(item)
        for item in noise_items:
            by_category["ruido"].append(item)

        categories = {
            cat: len(items)
            for cat, items in by_category.items()
            if cat != "ruido"
        }

        high_count = sum(1 for i in curated if i["priority"] == "high")
        medium_count = sum(1 for i in curated if i["priority"] == "medium")
        noise_removed = low_quality_count + len(noise_items)
        focus_topics = _infer_focus(curated)

        # Step 10: Telegram-aware summary — NO titles here; BriefingService iterates items[]
        focus_lines = "\n".join(f"• {t}" for t in focus_topics) if focus_topics else "• Geral"
        summary = (
            f"📰 Radar de Noticias\n\n"
            f"Foco do dia:\n{focus_lines}\n\n"
            f"Alta prioridade: {high_count}\n"
            f"Media prioridade: {medium_count}\n"
            f"Ruidos removidos: {noise_removed}"
        )

        result = {
            "total": len(curated),
            "categories": categories,
            "by_category": dict(by_category),
            "items": curated,
            "summary": summary,
        }

        log_action(
            logger, "summarize_news",
            fetched_today=total_fetched_today,
            low_quality=low_quality_count,
            scope_dropped=scope_dropped_count,
            simhash_dropped=simhash_dropped_count,
            curated=len(curated),
            high=high_count,
            noise=len(noise_items),
        )
        return result

    # Backward compatibility alias
    def get_briefing(self) -> dict:
        return self.summarize_news()
