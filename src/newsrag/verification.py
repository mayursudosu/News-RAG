"""Verification status logic – Independent Confirmation Rule.

Articles about the **same event** are grouped together.  The verification
status of each event group is determined by the tiers of the independent
sources that reported it:

    ┌─────────────────────────────────┬──────────────────┐
    │ Condition                       │ Status           │
    ├─────────────────────────────────┼──────────────────┤
    │ ≥1 Tier-1 source                │ ✅ Verified       │
    │ ≥2 independent Tier-2 sources   │ ✅ Verified       │
    │ exactly 1 Tier-2 (no Tier-1)    │ ⚠ Single-source  │
    │ Tier-3 only (any count)         │ ❓ Unverified     │
    └─────────────────────────────────┴──────────────────┘
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

# ── Verification statuses ───────────────────────────────────────────────────

VERIFIED = "Verified"
SINGLE_SOURCE = "Single-source"
UNVERIFIED = "Unverified"

STATUS_ICON: Dict[str, str] = {
    VERIFIED: "✅",
    SINGLE_SOURCE: "⚠️",
    UNVERIFIED: "❓",
}

# ── Data classes ────────────────────────────────────────────────────────────


@dataclass
class EventGroup:
    """A cluster of articles about the same event/story."""

    event_id: int
    label: str                                 # representative headline
    articles: List[dict] = field(default_factory=list)
    source_names: List[str] = field(default_factory=list)
    tiers: List[int] = field(default_factory=list)
    verification_status: str = UNVERIFIED
    tier1_count: int = 0
    tier2_count: int = 0
    tier3_count: int = 0
    best_score: float = 0.0                    # best filter score among members

    @property
    def source_count(self) -> int:
        return len(set(self.source_names))

    @property
    def icon(self) -> str:
        return STATUS_ICON.get(self.verification_status, "?")


# ── Title normalisation ────────────────────────────────────────────────────

_NOISE_RE = re.compile(
    r"""
      ^(breaking|update|watch|live|video|opinion|editorial|explainer|analysis)[:\s|–—-]+
    | \s*\|.*$             # trailing "| Source Name" bits
    | \s*[-–—]\s+.*$       # trailing "— Source" bits after em-dash
    | [''""\"']             # quotes
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalise_title(title: str) -> str:
    """Strip common prefixes, trailing source names, and noise."""
    title = _NOISE_RE.sub("", title).strip()
    # collapse whitespace
    title = re.sub(r"\s+", " ", title)
    return title.lower()


# ── Similarity ──────────────────────────────────────────────────────────────

def title_similarity(a: str, b: str) -> float:
    """Return 0–1 similarity score between two (normalised) titles."""
    return SequenceMatcher(None, a, b).ratio()


# ── Event grouping ──────────────────────────────────────────────────────────

_DEFAULT_SIM_THRESHOLD = 0.45   # ≥ this → same event cluster


def group_into_events(
    articles,
    *,
    sim_threshold: float = _DEFAULT_SIM_THRESHOLD,
) -> List[EventGroup]:
    """Cluster a list of articles into event groups by title similarity.

    *articles* – iterable of dict-like objects (sqlite3.Row or dict) with
    at least: id, title, source_name, tier, url.  Optionally: score (from
    filtering).

    Returns a list of EventGroup, one per cluster.
    """
    # Build a list of lightweight dicts for easier handling
    items: List[dict] = []
    for art in articles:
        d = dict(art) if not isinstance(art, dict) else art
        items.append(d)

    if not items:
        return []

    # Greedy single-link clustering
    norm_titles = [normalise_title(it["title"]) for it in items]
    assigned = [False] * len(items)
    groups: List[EventGroup] = []
    event_counter = 0

    for i, item in enumerate(items):
        if assigned[i]:
            continue
        event_counter += 1
        cluster_indices = [i]
        assigned[i] = True

        for j in range(i + 1, len(items)):
            if assigned[j]:
                continue
            # compare against every member already in the cluster
            for ci in cluster_indices:
                sim = title_similarity(norm_titles[ci], norm_titles[j])
                if sim >= sim_threshold:
                    cluster_indices.append(j)
                    assigned[j] = True
                    break

        # Build the EventGroup
        cluster_articles = [items[idx] for idx in cluster_indices]
        source_names = [a["source_name"] for a in cluster_articles]
        tiers = [a["tier"] for a in cluster_articles]

        # Pick the longest title as the representative label
        label = max(cluster_articles, key=lambda a: len(a["title"]))["title"]

        # If articles carry a score (from FilterResult), grab best
        best_score = max(
            (a.get("score", 0.0) for a in cluster_articles), default=0.0
        )

        grp = EventGroup(
            event_id=event_counter,
            label=label,
            articles=cluster_articles,
            source_names=source_names,
            tiers=tiers,
            best_score=best_score,
        )
        groups.append(grp)

    return groups


# ── Verification rule ──────────────────────────────────────────────────────

def _count_independent_tiers(group: EventGroup) -> Tuple[int, int, int]:
    """Count distinct sources at each tier inside a group."""
    src_tier: Dict[str, int] = {}
    for name, tier in zip(group.source_names, group.tiers):
        # keep the best (lowest) tier if a source appears more than once
        if name not in src_tier or tier < src_tier[name]:
            src_tier[name] = tier
    t1 = sum(1 for t in src_tier.values() if t == 1)
    t2 = sum(1 for t in src_tier.values() if t == 2)
    t3 = sum(1 for t in src_tier.values() if t == 3)
    return t1, t2, t3


def verify_events(groups: List[EventGroup]) -> List[EventGroup]:
    """Apply the Independent Confirmation Rule to each event group.

    Mutates and returns the same list of groups with verification_status,
    tier1_count, tier2_count, tier3_count filled in.
    """
    for grp in groups:
        t1, t2, t3 = _count_independent_tiers(grp)
        grp.tier1_count = t1
        grp.tier2_count = t2
        grp.tier3_count = t3

        if t1 >= 1:
            grp.verification_status = VERIFIED
        elif t2 >= 2:
            grp.verification_status = VERIFIED
        elif t2 == 1:
            grp.verification_status = SINGLE_SOURCE
        else:
            grp.verification_status = UNVERIFIED

    return groups


# ── Convenience pipeline ───────────────────────────────────────────────────

def build_verified_events(
    articles,
    *,
    sim_threshold: float = _DEFAULT_SIM_THRESHOLD,
) -> List[EventGroup]:
    """Full pipeline: group → verify → return."""
    groups = group_into_events(articles, sim_threshold=sim_threshold)
    return verify_events(groups)


# ── Pretty-print helpers ───────────────────────────────────────────────────

def format_event_summary(groups: List[EventGroup]) -> str:
    """Return a human-readable summary of all event groups."""
    lines: List[str] = []
    verified = [g for g in groups if g.verification_status == VERIFIED]
    single = [g for g in groups if g.verification_status == SINGLE_SOURCE]
    unverified = [g for g in groups if g.verification_status == UNVERIFIED]

    lines.append(
        f"Event groups: {len(groups)} total  ·  "
        f"{len(verified)} Verified  ·  "
        f"{len(single)} Single-source  ·  "
        f"{len(unverified)} Unverified"
    )
    lines.append("")

    for grp in groups:
        sources_str = ", ".join(sorted(set(grp.source_names)))
        tiers_str = (
            f"T1={grp.tier1_count} T2={grp.tier2_count} T3={grp.tier3_count}"
        )
        lines.append(
            f"  {grp.icon}  Event {grp.event_id:>3d}  "
            f"[{grp.verification_status:13s}]  "
            f"({grp.source_count} src: {tiers_str})"
        )
        lines.append(f"      {grp.label[:90]}")
        lines.append(f"      Sources: {sources_str}")
        lines.append("")

    return "\n".join(lines)
