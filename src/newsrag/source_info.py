"""Utility helpers for inspecting and grouping news sources by tier."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from newsrag.config_loader import Source, load_sources

# Human-readable tier labels
TIER_LABELS: Dict[int, str] = {
    1: "Tier 1 – Major international wire services & broadcasters",
    2: "Tier 2 – National newspapers & credible regional outlets",
    3: "Tier 3 – Niche blogs, opinion sites & specialist outlets",
}


def sources_by_tier(sources: List[Source] | None = None) -> Dict[int, List[Source]]:
    """Return sources grouped by tier (1, 2, 3).

    If *sources* is None, loads from the default config file.
    """
    if sources is None:
        sources = load_sources()

    grouped: Dict[int, List[Source]] = defaultdict(list)
    for src in sources:
        grouped[src.tier].append(src)

    return dict(sorted(grouped.items()))


def tier_summary(sources: List[Source] | None = None) -> Dict[int, int]:
    """Return a {tier: count} mapping."""
    grouped = sources_by_tier(sources)
    return {tier: len(srcs) for tier, srcs in grouped.items()}


def format_sources_table(sources: List[Source] | None = None) -> str:
    """Return a formatted string listing all sources grouped by tier."""
    grouped = sources_by_tier(sources)
    lines: list[str] = []

    for tier in sorted(grouped):
        label = TIER_LABELS.get(tier, f"Tier {tier}")
        lines.append(f"\n{'━' * 64}")
        lines.append(f"  {label}")
        lines.append(f"{'━' * 64}")
        for src in sorted(grouped[tier], key=lambda s: s.name):
            lines.append(f"    • {src.name:30s}  {src.country:15s}  {src.url[:50]}")

    summary = tier_summary(sources)
    lines.append(f"\n{'─' * 64}")
    lines.append("  Summary:")
    for tier, count in sorted(summary.items()):
        lines.append(f"    Tier {tier}: {count} source(s)")
    lines.append(f"    Total : {sum(summary.values())} source(s)")
    lines.append(f"{'─' * 64}")

    return "\n".join(lines)
