"""Composite ranking for verified event groups.

Each EventGroup receives a **rank_score** combining:

    ┌──────────────────────┬────────────────────────────────────────┐
    │ Component            │ Formula                                │
    ├──────────────────────┼────────────────────────────────────────┤
    │ Relevance            │ best keyword score among articles      │
    │ Verification bonus   │ Verified +5 · Single-source +2 · else 0│
    │ Source diversity      │ ln(unique_sources + 1) × 3            │
    │ Recency bonus        │ e^(-hours_old / 24) × 4               │
    │ Tier multiplier      │ best tier: T1 → 1.2 · T2 → 1.0 · 0.8│
    └──────────────────────┴────────────────────────────────────────┘

    rank_score = (relevance + verification + diversity + recency) × tier_mult

Events are sorted by rank_score descending; top-N selected for the brief.

The final selection splits events into two UPSC-focused sections:
  A) INDIA CURRENT AFFAIRS   – Top 6 India-related events
  B) GLOBAL STRATEGIC AFFAIRS – Top 5 remaining events
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import Counter

from newsrag.verification import (
    VERIFIED,
    SINGLE_SOURCE,
    UNVERIFIED,
    EventGroup,
)

# ── Tuneable weights ────────────────────────────────────────────────────────

VERIFICATION_BONUS: Dict[str, float] = {
    VERIFIED: 5.0,
    SINGLE_SOURCE: 2.0,
    UNVERIFIED: 0.0,
}

TIER_MULTIPLIER: Dict[int, float] = {
    1: 1.20,
    2: 1.00,
    3: 0.85,
}

DIVERSITY_COEFF = 3.0        # multiplied by ln(source_count + 1)
RECENCY_SCALE = 4.0          # max recency bonus (when age → 0)
RECENCY_HALFLIFE_H = 24.0    # hours until recency bonus halves


# ── India-detection keywords ────────────────────────────────────────────────

_INDIA_KEYWORDS: List[str] = [
    # Country / demonyms
    "india", "indian", "india's",
    # Leadership & institutions
    "modi", "rajnath", "jaishankar", "doval",
    "parliament", "lok sabha", "rajya sabha", "supreme court",
    "election commission", "niti aayog",
    # Defense
    "drdo", "isro", "brahmos", "tejas", "arjun",
    "indian army", "indian navy", "indian air force", "bsf", "crpf", "cisf",
    "loc", "line of control", "lac", "line of actual control",
    # States & cities (major)
    "delhi", "mumbai", "chennai", "kolkata", "hyderabad", "bengaluru",
    "bangalore", "pune", "ahmedabad", "jaipur", "lucknow",
    "kashmir", "ladakh", "arunachal", "sikkim", "assam", "manipur",
    "nagaland", "mizoram", "tripura", "meghalaya",
    "rajasthan", "gujarat", "maharashtra", "karnataka", "kerala",
    "tamil nadu", "andhra pradesh", "telangana", "odisha", "bihar",
    "uttar pradesh", "madhya pradesh", "chhattisgarh", "jharkhand",
    "west bengal", "punjab", "haryana", "uttarakhand", "himachal",
    "goa",
    # Neighbours (India-centric angle)
    "pakistan", "pok", "china border", "galwan",
    "sri lanka", "bangladesh", "nepal", "bhutan", "myanmar",
    # Organisations
    "rbi", "sebi", "upsc", "ias", "ips",
    # Common phrases
    "new delhi", "south block", "north block", "race course road",
]

# Pre-compiled pattern for fast matching
_INDIA_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(kw) for kw in _INDIA_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _is_india_event(event: "RankedEvent") -> bool:
    """Return True if the event is India-related.

    Checks:
      1. Any article's country_tag == "India"
      2. India keyword match in the event label (representative title)
      3. India keyword match in any member article's title
    """
    # Check country_tag on member articles
    for art in event.group.articles:
        if art.get("country_tag", "").lower() == "india":
            return True

    # Check event label
    if _INDIA_PATTERN.search(event.label):
        return True

    # Check individual article titles
    for art in event.group.articles:
        if _INDIA_PATTERN.search(art.get("title", "")):
            return True

    return False


# ── Ranked event wrapper ───────────────────────────────────────────────────

@dataclass
class RankedEvent:
    """An EventGroup decorated with ranking components."""

    group: EventGroup
    rank: int = 0                              # 1-based after sorting

    # Component scores
    relevance: float = 0.0
    verification_bonus: float = 0.0
    diversity_bonus: float = 0.0
    recency_bonus: float = 0.0
    tier_multiplier: float = 1.0

    # Final composite
    rank_score: float = 0.0

    # Pass-through convenience properties
    @property
    def label(self) -> str:
        return self.group.label

    @property
    def verification_status(self) -> str:
        return self.group.verification_status

    @property
    def icon(self) -> str:
        return self.group.icon

    @property
    def source_count(self) -> int:
        return self.group.source_count

    @property
    def articles(self) -> list:
        return self.group.articles

    @property
    def source_names(self) -> list:
        return self.group.source_names

    @property
    def category(self) -> str:
        """Dominant event topic category from member articles."""
        categories = [
            art.get("category", "")
            for art in self.group.articles
            if art.get("category")
        ]
        if not categories:
            return "global_policy"

        counts = Counter(categories)
        max_count = max(counts.values())
        preferred_order = [
            "defense",
            "economy",
            "technology",
            "diplomacy",
            "science",
            "energy",
            "global_policy",
        ]
        for category in preferred_order:
            if counts.get(category, 0) == max_count:
                return category

        return counts.most_common(1)[0][0]


# ── Scoring helpers ─────────────────────────────────────────────────────────

def _best_tier(group: EventGroup) -> int:
    """Return the best (lowest) tier number in the group."""
    if not group.tiers:
        return 3
    return min(group.tiers)


def _newest_article_age_hours(group: EventGroup,
                               now: Optional[datetime] = None) -> float:
    """Return the age (in hours) of the freshest article in the group.

    Falls back to 48h if no parseable timestamp is found.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    min_age: float = 48.0  # fallback
    for art in group.articles:
        ts_str = art.get("published_at") or art.get("fetched_at")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_str))
            # make tz-aware if naive
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_h = (now - ts).total_seconds() / 3600.0
            if age_h < min_age:
                min_age = max(age_h, 0.0)
        except (ValueError, TypeError):
            continue
    return min_age


def _recency_score(age_hours: float) -> float:
    """Exponential-decay recency bonus.  Freshest → RECENCY_SCALE, decays."""
    decay = math.exp(-age_hours * math.log(2) / RECENCY_HALFLIFE_H)
    return RECENCY_SCALE * decay


# ── Main ranking function ──────────────────────────────────────────────────

def rank_events(
    groups: List[EventGroup],
    *,
    now: Optional[datetime] = None,
) -> List[RankedEvent]:
    """Score, sort, and rank a list of EventGroups.

    Returns a list of RankedEvent sorted by rank_score descending.
    """
    ranked: List[RankedEvent] = []

    for grp in groups:
        relevance = grp.best_score
        verif = VERIFICATION_BONUS.get(grp.verification_status, 0.0)
        diversity = DIVERSITY_COEFF * math.log(grp.source_count + 1)
        age_h = _newest_article_age_hours(grp, now=now)
        recency = _recency_score(age_h)
        tier_mult = TIER_MULTIPLIER.get(_best_tier(grp), 0.85)

        raw = relevance + verif + diversity + recency
        composite = raw * tier_mult

        ranked.append(RankedEvent(
            group=grp,
            relevance=relevance,
            verification_bonus=verif,
            diversity_bonus=diversity,
            recency_bonus=recency,
            tier_multiplier=tier_mult,
            rank_score=composite,
        ))

    # Sort descending
    ranked.sort(key=lambda r: r.rank_score, reverse=True)

    # Assign 1-based ranks
    for i, r in enumerate(ranked, 1):
        r.rank = i

    return ranked


# ── Convenience: full pipeline from filtered articles ──────────────────────

def rank_from_articles(
    articles,
    *,
    top_n: int = 6,
    now: Optional[datetime] = None,
) -> List[RankedEvent]:
    """End-to-end: filter-kept articles → group → verify → rank → top N.

    *articles* – sqlite3.Row or dicts from recent_articles().
    Returns the top *top_n* RankedEvents.
    """
    from newsrag.filtering import filter_articles
    from newsrag.verification import build_verified_events

    results = filter_articles(articles)
    kept = [r for r in results if r.kept]

    # Convert FilterResult → dicts with score + country_tag
    kept_dicts = [
        {
            "id": r.article_id,
            "title": r.title,
            "source_name": r.source_name,
            "tier": r.tier,
            "score": r.score,
            "country_tag": r.country_tag,
            "category": r.category,
            "url": "",  # not needed for ranking
        }
        for r in kept
    ]

    groups = build_verified_events(kept_dicts)
    ranked = rank_events(groups, now=now)
    return ranked[:top_n]


# ── Two-section UPSC split ─────────────────────────────────────────────────

@dataclass
class BriefSections:
    """Two ranked sections for the UPSC daily brief."""
    india: List[RankedEvent]
    globe: List[RankedEvent]

    @property
    def total(self) -> int:
        return len(self.india) + len(self.globe)


def split_ranked_events(
    ranked: List[RankedEvent],
    *,
    india_top: int = 6,
    global_top: int = 5,
) -> BriefSections:
    """Partition ranked events into India and Global sections.

    India events are identified by country_tag or keyword matching.
    No event appears in both sections.  Each section is independently
    re-ranked (1-based) after partitioning.
    """
    india: List[RankedEvent] = []
    globe: List[RankedEvent] = []

    for r in ranked:
        if _is_india_event(r) and len(india) < india_top:
            india.append(r)
        elif not _is_india_event(r) and len(globe) < global_top:
            globe.append(r)
        elif _is_india_event(r) and len(india) >= india_top:
            continue  # skip excess India events
        elif not _is_india_event(r) and len(globe) >= global_top:
            continue  # skip excess global events

    # Re-assign 1-based ranks within each section
    for i, r in enumerate(india, 1):
        r.rank = i
    for i, r in enumerate(globe, 1):
        r.rank = i

    return BriefSections(india=india, globe=globe)


# ── Pretty-print ───────────────────────────────────────────────────────────

def _format_event_block(r: RankedEvent) -> List[str]:
    """Format a single ranked event entry."""
    sources = ", ".join(sorted(set(r.source_names)))
    return [
        f"  #{r.rank:>3d}  {r.icon}  "
        f"score {r.rank_score:6.1f}  "
        f"[{r.verification_status:13s}]  "
        f"({r.source_count} src)",
        f"        {r.label[:90]}",
        f"        Sources: {sources}",
        f"        Breakdown: relevance={r.relevance:.1f}  "
        f"verif={r.verification_bonus:.1f}  "
        f"diversity={r.diversity_bonus:.1f}  "
        f"recency={r.recency_bonus:.1f}  "
        f"×tier={r.tier_multiplier:.2f}",
        "",
    ]


def format_ranked_events(ranked: List[RankedEvent], *, top_n: int = 0) -> str:
    """Return a human-readable ranking table (flat, single-section)."""
    items = ranked[:top_n] if top_n else ranked
    lines: List[str] = []

    total = len(ranked)
    shown = len(items)
    lines.append(f"Ranked {total} events – showing top {shown}\n")

    for r in items:
        lines.extend(_format_event_block(r))

    return "\n".join(lines)


def format_brief_sections(sections: BriefSections) -> str:
    """Return the two-section UPSC brief ranking output."""
    lines: List[str] = []

    lines.append(
        f"Total {sections.total} events selected  "
        f"({len(sections.india)} India + {len(sections.globe)} Global)\n"
    )

    # ── India Current Affairs ──
    lines.append("━" * 60)
    lines.append("  🇮🇳  INDIA CURRENT AFFAIRS")
    lines.append("━" * 60)
    lines.append("")
    if sections.india:
        for r in sections.india:
            lines.extend(_format_event_block(r))
    else:
        lines.append("  (no India-related events found)")
        lines.append("")

    # ── Global Strategic Affairs ──
    lines.append("━" * 60)
    lines.append("  🌍  GLOBAL STRATEGIC AFFAIRS")
    lines.append("━" * 60)
    lines.append("")
    if sections.globe:
        for r in sections.globe:
            lines.extend(_format_event_block(r))
    else:
        lines.append("  (no global events found)")
        lines.append("")

    return "\n".join(lines)
