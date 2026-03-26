"""Basic relevance filtering for defense / geopolitics articles.

Scoring formula per article:
    score = (positive keyword hits) - (negative keyword hits) + tier_bonus

    tier_bonus:  Tier 1 → +1,  Tier 2 → +0.5,  Tier 3 → 0

Articles with score < min_score are dropped.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import yaml

_DEFAULT_FILTERS = pathlib.Path(__file__).resolve().parents[2] / "config" / "filters.yml"

# Small bonus for higher-tier sources
TIER_BONUS: Dict[int, float] = {1: 1.0, 2: 0.5, 3: 0.0}


@dataclass
class FilterResult:
    """Result of filtering a single article."""
    article_id: int
    title: str
    source_name: str
    tier: int
    score: float
    positive_hits: List[str]
    negative_hits: List[str]
    kept: bool
    country_tag: str = ""
    category: str = "global_policy"


def load_filter_config(path: pathlib.Path | str | None = None) -> dict:
    """Load filters.yml and return the parsed dict."""
    path = pathlib.Path(path) if path else _DEFAULT_FILTERS
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _count_keyword_hits(text: str, keywords: List[str]) -> List[str]:
    """Return the list of keywords that appear in *text* (case-insensitive)."""
    text_lower = text.lower()
    hits: List[str] = []
    for kw in keywords:
        # Use word-boundary regex so "war" doesn't match "warning" etc.
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, text_lower):
            hits.append(kw)
    return hits


def _infer_category(
    title: str,
    raw_text: str,
    topic_keywords: Dict[str, List[str]],
) -> str:
    """Assign one category based on strongest keyword-hit count."""
    if not topic_keywords:
        return "global_policy"

    combined = f"{title} {raw_text}".strip()
    if not combined:
        return "global_policy"

    counts: Dict[str, int] = {}
    for category, keywords in topic_keywords.items():
        counts[category] = len(_count_keyword_hits(combined, keywords or []))

    best_count = max(counts.values()) if counts else 0
    if best_count <= 0:
        return "global_policy"

    # Deterministic tie-breaker: keep config order.
    for category in topic_keywords.keys():
        if counts.get(category, 0) == best_count:
            return category

    return "global_policy"


def score_article(title: str, raw_text: str, tier: int,
                  positive_kws: List[str], negative_kws: List[str]) -> Tuple[float, List[str], List[str]]:
    """Score a single article. Returns (score, positive_hits, negative_hits)."""
    combined = f"{title} {raw_text}"

    pos_hits = _count_keyword_hits(combined, positive_kws)
    neg_hits = _count_keyword_hits(combined, negative_kws)

    score = len(pos_hits) - len(neg_hits) + TIER_BONUS.get(tier, 0.0)
    return score, pos_hits, neg_hits


def filter_articles(articles, config: dict | None = None) -> List[FilterResult]:
    """Score and filter a batch of articles.

    *articles* should be an iterable of sqlite3.Row or dict-like objects with
    keys: id, title, raw_text (or empty string), source_name, tier.

    Returns a list of FilterResult for every article (kept and dropped).
    """
    if config is None:
        config = load_filter_config()

    positive_kws: List[str] = config.get("positive", [])
    negative_kws: List[str] = config.get("negative", [])
    min_score: float = config.get("min_score", 1)
    topic_keywords: Dict[str, List[str]] = config.get("topic_keywords", {})

    results: List[FilterResult] = []
    for art in articles:
        title = art["title"] if isinstance(art, dict) else art["title"]
        raw_text = (art.get("raw_text", "") if isinstance(art, dict)
                    else (art["raw_text"] if "raw_text" in art.keys() else ""))
        tier = art["tier"]
        source_name = art["source_name"]
        article_id = art["id"]
        country_tag = (art.get("country_tag", "") if isinstance(art, dict)
                       else (art["country_tag"] if "country_tag" in art.keys() else ""))

        score, pos_hits, neg_hits = score_article(
            title, raw_text or "", tier, positive_kws, negative_kws
        )
        category = _infer_category(title, raw_text or "", topic_keywords)

        results.append(FilterResult(
            article_id=article_id,
            title=title,
            source_name=source_name,
            tier=tier,
            score=score,
            positive_hits=pos_hits,
            negative_hits=neg_hits,
            kept=score >= min_score,
            country_tag=country_tag,
            category=category,
        ))

    return results
