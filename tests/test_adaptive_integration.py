"""Integration tests for Adaptive Score Engine v1 → Inbox + News pipelines.

These tests validate that:
  1. Positive / important feedback promotes an item in the ranking.
  2. Negative feedback penalizes an item in the ranking.
  3. Without feedback, the ranking equals the baseline.
  4. Engine failures are absorbed — pipeline continues with neutral adjustment.
  5. Public contracts of summarize_emails() and summarize_news() are preserved.

The tests share the in-memory pytest DB via a SessionLocal proxy so that
both the test setup (seeding memory_events) and the production code under
test (which opens its own SessionLocal()) operate on the same database.
"""
from __future__ import annotations

from typing import Iterable

import pytest

from app.integrations.email_models import EmailMessage
from app.modules.briefing.news_service import (
    NewsService,
    _apply_memory_adjustments,
    _curate_top5,
    _rank_items,
)
from app.modules.inbox.service import InboxService
from app.modules.memory.service import MemoryService
from app.modules.memory.utils import to_callback_ref


# ── Helpers ───────────────────────────────────────────────────────────────────

class _SessionProxy:
    """Wrap a session and make .close() a no-op so fixtures stay alive."""

    def __init__(self, real) -> None:
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def close(self) -> None:  # no-op — fixture handles teardown
        pass


@pytest.fixture()
def use_test_db(db_session, monkeypatch):
    """Make SessionLocal() return the test session (with no-op close).

    Both inbox.service and news_service import SessionLocal lazily inside
    helpers, so patching the source module is sufficient.
    """
    monkeypatch.setattr(
        "app.db.session.SessionLocal",
        lambda: _SessionProxy(db_session),
    )
    return db_session


def _seed_news_feedback(db_session, link_or_title: str, feedback: str) -> None:
    svc = MemoryService(db_session)
    ref = to_callback_ref(link_or_title)
    svc.log_event(
        event_type="news_ranked",
        source="news",
        reference_id=ref,
        payload={"link": link_or_title, "title": link_or_title},
        score=0.0,
    )
    svc.add_feedback(ref, feedback, source="news", event_type="news_ranked")


def _seed_email_feedback(db_session, email_id: str, feedback: str) -> None:
    svc = MemoryService(db_session)
    ref = to_callback_ref(email_id)
    svc.log_event(
        event_type="email_classified",
        source="email",
        reference_id=ref,
        payload={"email_id": email_id},
        score=0.0,
    )
    svc.add_feedback(ref, feedback, source="email", event_type="email_classified")


def _build_news_items(specs: Iterable[tuple[str, str, int]]) -> list[dict]:
    """Build minimal news items for ranking tests.

    Each spec is (link, title, base_score). Items receive the canonical fields
    consumed by _apply_memory_adjustments + _rank_items + _curate_top5.
    Priority is derived from base_score using the same thresholds as the
    classifier (>=8 high, >=4 medium, else low) so curation reflects the score.
    """
    out: list[dict] = []
    for link, title, score in specs:
        if score >= 8:
            priority = "high"
        elif score >= 4:
            priority = "medium"
        else:
            priority = "low"
        out.append({
            "link": link,
            "title": title,
            "summary": "",
            "category": "macro",
            "score": score,
            "priority": priority,
            "published": "",
        })
    return out


# ── Fake email client ─────────────────────────────────────────────────────────

class _FakeEmailClient:
    """Provider-agnostic fake — returns a fixed list of EmailMessage."""

    def __init__(self, emails: list[EmailMessage]) -> None:
        self._emails = emails

    def list_recent_emails(self, max_results: int = 10) -> list[EmailMessage]:
        return list(self._emails)[:max_results]


def _build_emails() -> list[EmailMessage]:
    """Three actionable emails with deliberately identical text so the only
    discriminator under test is the memory adjustment. Same sender format
    (human), same subject, same snippet → same base score.
    """
    common_subject = "Pode confirmar antes do prazo"
    common_snippet = "Pode confirmar antes do prazo? Aguardo retorno hoje."
    return [
        EmailMessage(
            id="msg_001",
            sender="Pessoa A <a@empresa.com>",
            subject=common_subject,
            snippet=common_snippet,
            priority="media",
            timestamp="2026-04-26T09:00:00",
            is_read=False,
        ),
        EmailMessage(
            id="msg_002",
            sender="Pessoa B <b@empresa.com>",
            subject=common_subject,
            snippet=common_snippet,
            priority="media",
            timestamp="2026-04-26T09:05:00",
            is_read=False,
        ),
        EmailMessage(
            id="msg_003",
            sender="Pessoa C <c@empresa.com>",
            subject=common_subject,
            snippet=common_snippet,
            priority="media",
            timestamp="2026-04-26T09:10:00",
            is_read=False,
        ),
    ]


# ═════════════════════════════════════════════════════════════════════════════
#  News — helper-level integration
# ═════════════════════════════════════════════════════════════════════════════

def test_news_positive_feedback_promotes_item(use_test_db):
    """`important` feedback on item C should bring it above its baseline peer."""
    items = _build_news_items([
        ("https://x/a", "Titulo A com varias palavras relevantes", 5),
        ("https://x/b", "Titulo B com varias palavras relevantes", 5),
        ("https://x/c", "Titulo C com varias palavras relevantes", 5),
    ])
    _seed_news_feedback(use_test_db, "https://x/c", "important")

    _apply_memory_adjustments(items)
    ranked = _rank_items(items)

    assert ranked[0]["link"] == "https://x/c"
    item_c = next(i for i in items if i["link"] == "https://x/c")
    assert item_c["_base_score"] == 5.0
    assert item_c["_memory_adjustment"] == 2.0
    assert item_c["_memory_reason"] == "important"
    assert item_c["score"] == 7.0


def test_news_positive_one_promotes_above_neutral(use_test_db):
    """`positive` (+1) is enough to break a tie among same-score peers."""
    items = _build_news_items([
        ("https://x/a", "Titulo A com varias palavras relevantes", 5),
        ("https://x/b", "Titulo B com varias palavras relevantes", 5),
    ])
    _seed_news_feedback(use_test_db, "https://x/b", "positive")

    _apply_memory_adjustments(items)
    ranked = _rank_items(items)

    assert ranked[0]["link"] == "https://x/b"
    assert ranked[0]["_memory_adjustment"] == 1.0


def test_news_negative_feedback_demotes_item(use_test_db):
    """`negative` feedback on the originally top-ranked item must drop it."""
    items = _build_news_items([
        ("https://x/top", "Titulo top com varias palavras relevantes", 8),
        ("https://x/mid", "Titulo mid com varias palavras relevantes", 7),
    ])
    _seed_news_feedback(use_test_db, "https://x/top", "negative")

    _apply_memory_adjustments(items)
    ranked = _rank_items(items)

    # 8 - 2 = 6  <  7 (no quality bonus on these synthetic titles) → mid wins
    assert ranked[0]["link"] == "https://x/mid"
    top = next(i for i in items if i["link"] == "https://x/top")
    assert top["_memory_adjustment"] == -2.0
    assert top["_memory_reason"] == "negative"
    assert top["score"] == 6.0


def test_news_no_feedback_keeps_baseline_order(use_test_db):
    """Without any feedback the ranking must equal the unadjusted baseline."""
    items = _build_news_items([
        ("https://x/a", "Titulo A com varias palavras relevantes", 9),
        ("https://x/b", "Titulo B com varias palavras relevantes", 6),
        ("https://x/c", "Titulo C com varias palavras relevantes", 3),
    ])

    baseline = _rank_items([dict(i) for i in items])
    _apply_memory_adjustments(items)
    after = _rank_items(items)

    assert [i["link"] for i in after] == [i["link"] for i in baseline]
    for item in items:
        assert item["_base_score"] == float(item["score"])
        assert item["_memory_adjustment"] == 0.0
        assert item["_memory_reason"] is None


def test_news_engine_failure_keeps_pipeline_neutral(use_test_db, monkeypatch):
    """If compute_memory_adjustment raises, items stay neutral and ranking continues."""
    items = _build_news_items([
        ("https://x/a", "Titulo A com varias palavras relevantes", 9),
        ("https://x/b", "Titulo B com varias palavras relevantes", 6),
    ])

    # Force the engine to raise on every call — fail-safe must absorb it.
    monkeypatch.setattr(
        "app.modules.memory.scoring.compute_memory_adjustment",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("engine down")),
    )

    # Must not raise.
    _apply_memory_adjustments(items)
    ranked = _rank_items(items)

    assert [i["link"] for i in ranked] == ["https://x/a", "https://x/b"]
    for item in items:
        assert item["_memory_adjustment"] == 0.0
        assert item["_memory_reason"] is None


def test_news_curate_top5_after_promotion(use_test_db):
    """End-to-end at helper level: feedback promotion influences top-5 curation."""
    items = _build_news_items([
        ("https://x/lo1", "Titulo LO1 com varias palavras relevantes", 2),
        ("https://x/lo2", "Titulo LO2 com varias palavras relevantes", 2),
        ("https://x/lo3", "Titulo LO3 com varias palavras relevantes", 2),
    ])
    _seed_news_feedback(use_test_db, "https://x/lo3", "important")

    _apply_memory_adjustments(items)
    ranked = _rank_items(items)
    curated = _curate_top5(ranked)

    # All three LOW survive in the top-5 (curation V3.1 fallback), and the
    # boosted item ranks first.
    assert curated[0]["link"] == "https://x/lo3"
    assert {i["link"] for i in curated} == {"https://x/lo1", "https://x/lo2", "https://x/lo3"}


# ═════════════════════════════════════════════════════════════════════════════
#  Inbox — full summarize_emails() integration
# ═════════════════════════════════════════════════════════════════════════════

def test_inbox_positive_feedback_promotes_email(use_test_db):
    """`important` feedback should put msg_003 at the top of action_items."""
    client = _FakeEmailClient(_build_emails())
    inbox = InboxService(client=client)

    _seed_email_feedback(use_test_db, "msg_003", "important")

    result = inbox.summarize_emails()

    action_ids = [a["id"] for a in result["action_items"]]
    assert "msg_003" in action_ids
    assert action_ids[0] == "msg_003"

    top5_ids = [t["id"] for t in result["top5"]]
    assert top5_ids[0] == "msg_003"


def test_inbox_negative_feedback_demotes_email(use_test_db):
    """`negative` feedback drops the targeted email below its peers."""
    client = _FakeEmailClient(_build_emails())
    inbox = InboxService(client=client)

    # Penalize msg_001 — the 3 emails are otherwise comparable, so msg_001
    # must end up last among action_items after the −2 adjustment.
    _seed_email_feedback(use_test_db, "msg_001", "negative")

    result = inbox.summarize_emails()
    action_ids = [a["id"] for a in result["action_items"]]

    assert "msg_001" in action_ids
    assert action_ids[-1] == "msg_001"


def test_inbox_no_feedback_keeps_baseline(use_test_db):
    """Without feedback the baseline ranking must be preserved."""
    client = _FakeEmailClient(_build_emails())
    baseline = InboxService(client=client).summarize_emails()
    after = InboxService(client=_FakeEmailClient(_build_emails())).summarize_emails()

    assert [a["id"] for a in baseline["action_items"]] == [
        a["id"] for a in after["action_items"]
    ]
    assert [t["id"] for t in baseline["top5"]] == [t["id"] for t in after["top5"]]


def test_inbox_engine_failure_keeps_pipeline(use_test_db, monkeypatch):
    """Engine raising must not break summarize_emails — neutral ranking applies."""
    client = _FakeEmailClient(_build_emails())
    inbox = InboxService(client=client)

    monkeypatch.setattr(
        "app.modules.memory.scoring.compute_memory_adjustment",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("engine down")),
    )

    # Must not raise; result shape unchanged.
    result = inbox.summarize_emails()
    assert result["total"] == 3
    assert isinstance(result["action_items"], list)
    assert isinstance(result["top5"], list)


# ═════════════════════════════════════════════════════════════════════════════
#  Public contracts (Inbox + News + Briefing payload shape)
# ═════════════════════════════════════════════════════════════════════════════

_INBOX_KEYS = {
    "total", "high_priority", "medium_priority", "low_priority", "unread",
    "newsletter_count", "items", "action_items", "top5", "summary",
}

_NEWS_KEYS = {"total", "categories", "by_category", "items", "summary"}


def test_inbox_contract_preserved(use_test_db):
    client = _FakeEmailClient(_build_emails())
    result = InboxService(client=client).summarize_emails()

    assert set(result.keys()) >= _INBOX_KEYS
    assert isinstance(result["total"], int)
    assert isinstance(result["items"], list)
    assert isinstance(result["action_items"], list)
    assert isinstance(result["top5"], list)
    # No internal fields leaked into top-5 dicts
    for item in result["top5"]:
        assert not any(k.startswith("_") for k in item.keys())


def test_news_contract_preserved(use_test_db):
    """summarize_news must keep its public shape after adaptive scoring runs."""
    result = NewsService().summarize_news()

    assert set(result.keys()) >= _NEWS_KEYS
    assert isinstance(result["total"], int)
    assert isinstance(result["categories"], dict)
    assert isinstance(result["items"], list)
    assert isinstance(result["summary"], str)

    # No internal `_`-prefixed fields in serialized items
    for item in result["items"]:
        assert not any(k.startswith("_") for k in item.keys())
        # score serialization must remain numeric (int OR float — both pass JSON)
        if "score" in item:
            assert isinstance(item["score"], (int, float))


def test_briefing_payload_news_keys_intact(use_test_db):
    """Briefing's news section must keep the same shape as summarize_news."""
    result = NewsService().summarize_news()

    # Internal sanity: items[i] from news_service.summarize_news still has
    # `score` and `priority` (the keys consumed by BriefingService._compose
    # and TelegramBot.format_briefing_blocks).
    for item in result["items"]:
        assert "title" in item
        assert "category" in item
        assert "priority" in item


# ═════════════════════════════════════════════════════════════════════════════
#  Priority recalculation after score adjustment (Correção pós-audit)
# ═════════════════════════════════════════════════════════════════════════════

def test_news_priority_promoted_when_score_crosses_high_threshold(use_test_db):
    """Item with base=6 (medium) + important(+2) = 8 must be re-labelled 'high'."""
    items = _build_news_items([
        ("https://x/borderline", "Titulo borderline com varias palavras", 6),
    ])
    # base=6 → medium by classifier (SCORE_THRESHOLD_HIGH=8, MEDIUM=4)
    assert items[0]["priority"] == "medium"

    _seed_news_feedback(use_test_db, "https://x/borderline", "important")
    _apply_memory_adjustments(items)

    # 6 + 2 = 8.0 → exactly at HIGH threshold
    assert items[0]["score"] == 8.0
    assert items[0]["priority"] == "high"
    assert items[0]["_base_score"] == 6.0
    assert items[0]["_memory_adjustment"] == 2.0


def test_news_priority_demoted_when_score_crosses_low_threshold(use_test_db):
    """Item with base=4 (medium) + negative(-2) = 2 must be re-labelled 'low'."""
    items = _build_news_items([
        ("https://x/borderdown", "Titulo borderdown com varias palavras", 4),
    ])
    # base=4 → medium by classifier
    assert items[0]["priority"] == "medium"

    _seed_news_feedback(use_test_db, "https://x/borderdown", "negative")
    _apply_memory_adjustments(items)

    # 4 - 2 = 2.0 → below MEDIUM threshold (4), re-labelled low
    assert items[0]["score"] == 2.0
    assert items[0]["priority"] == "low"
    assert items[0]["_base_score"] == 4.0
    assert items[0]["_memory_adjustment"] == -2.0


def test_news_priority_unchanged_when_no_feedback(use_test_db):
    """Without feedback, priority must not be altered."""
    items = _build_news_items([
        ("https://x/stable", "Titulo stable com varias palavras", 6),
    ])
    original_priority = items[0]["priority"]

    _apply_memory_adjustments(items)

    assert items[0]["priority"] == original_priority
    assert items[0]["_memory_adjustment"] == 0.0


# ═════════════════════════════════════════════════════════════════════════════
#  _log_ranked_news preserves base_score in payload (Correção pós-audit)
# ═════════════════════════════════════════════════════════════════════════════

def test_log_ranked_news_preserves_base_score_in_payload(use_test_db):
    """When an item carries _base_score, _log_ranked_news must include it in payload."""
    import json
    from app.modules.briefing.news_service import _log_ranked_news
    from app.modules.memory.repository import MemoryRepository
    from app.modules.memory.utils import to_callback_ref

    link = "https://x/log-test"
    item = {
        "link": link,
        "title": "Titulo para log test",
        "category": "macro",
        "score": 8.0,          # adjusted (6 + 2)
        "priority": "high",
        "score_reasons": ["+2 important"],
        "_base_score": 6.0,    # original classifier score
        "_memory_adjustment": 2.0,
        "_memory_reason": "important",
    }

    _log_ranked_news([item])

    repo = MemoryRepository(use_test_db)
    ref = to_callback_ref(link)
    event = repo.get_by_type_and_ref("news_ranked", ref)

    assert event is not None
    payload = json.loads(event.payload)
    assert "base_score" in payload
    assert payload["base_score"] == 6.0
    # Top-level score reflects the adjusted value the user saw
    assert event.score == 8.0
