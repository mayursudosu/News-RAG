"""Full-text search over stored articles using SQLite FTS5."""

from __future__ import annotations

import sqlite3
from typing import List

from newsrag.storage import connect


def search_articles(query: str, limit: int = 20) -> List[sqlite3.Row]:
    """Search articles by keyword(s) using the FTS5 index.

    Returns matching rows with title, url, source_name, tier, and a
    relevance snippet.
    """
    conn = connect()
    try:
        rows = conn.execute(
            """SELECT
                   a.id, a.title, a.url, a.source_name, a.tier,
                   a.country_tag, a.published_at,
                   snippet(articles_fts, 1, '»', '«', '…', 40) AS snippet
               FROM articles_fts fts
               JOIN articles a ON a.id = fts.rowid
               WHERE articles_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()
    finally:
        conn.close()
    return rows
