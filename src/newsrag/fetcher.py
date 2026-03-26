"""Fetch RSS feeds and collect article titles + links."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

import feedparser

from newsrag.config_loader import Source


@dataclass
class ArticleMeta:
    """Minimal metadata for one article (no full text yet)."""
    title: str
    url: str
    source_name: str
    country: str
    tier: int
    published_at: datetime | None = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)


def fetch_rss(source: Source, max_entries: int = 20) -> List[ArticleMeta]:
    """Parse an RSS feed and return a list of ArticleMeta items."""
    feed = feedparser.parse(source.url)
    articles: List[ArticleMeta] = []

    for entry in feed.entries[:max_entries]:
        # Try to extract a published date
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        link = getattr(entry, "link", None) or ""
        title = getattr(entry, "title", "(no title)")

        articles.append(
            ArticleMeta(
                title=title,
                url=link,
                source_name=source.name,
                country=source.country,
                tier=source.tier,
                published_at=published,
            )
        )

    return articles


def fetch_all(sources: List[Source]) -> dict[str, List[ArticleMeta]]:
    """Fetch every configured source and return articles grouped by source name.

    Sources that fail to fetch are logged and skipped (no crash).
    """
    results: dict[str, List[ArticleMeta]] = {}
    for src in sources:
        try:
            articles = fetch_rss(src)
            results[src.name] = articles
            print(f"  ✓ {src.name}: {len(articles)} articles")
        except Exception as exc:
            print(f"  ✗ {src.name}: FAILED – {exc}")
            results[src.name] = []
    return results


def fetch_and_store(sources: List[Source], extract_text: bool = False) -> int:
    """Fetch all sources, persist article metadata to SQLite, return new-row count.

    If *extract_text* is True, also download and extract article body text
    for every article that doesn't have it yet.
    """
    from newsrag.storage import (
        connect, upsert_source, insert_articles,
        articles_missing_text, update_article_text,
    )

    grouped = fetch_all(sources)

    conn = connect()
    try:
        # ensure every source has a row in the sources table
        for src in sources:
            upsert_source(conn, src.name, src.url, src.type, src.country, src.tier)
        conn.commit()

        total_new = 0
        for _name, articles in grouped.items():
            new = insert_articles(conn, articles)
            total_new += new
        conn.commit()

        # ── optional text extraction pass ───────────────────────────────
        if extract_text:
            from newsrag.parser import extract_text as _extract

            missing = articles_missing_text(conn)
            if missing:
                print(f"\n  Extracting text for {len(missing)} articles…")
            ok = 0
            for row in missing:
                text = _extract(row["url"])
                if text:
                    update_article_text(conn, row["id"], text)
                    ok += 1
                    print(f"    ✓ {row['title'][:60]}")
                else:
                    print(f"    ✗ {row['title'][:60]}")
            conn.commit()
            if missing:
                print(f"  Text extracted for {ok}/{len(missing)} articles")

    finally:
        conn.close()

    return total_new
