"""SQLite storage layer for article metadata."""

from __future__ import annotations

import pathlib
import sqlite3
from datetime import datetime
from typing import List

# Default DB location – project root
_DEFAULT_DB = pathlib.Path(__file__).resolve().parents[2] / "news.db"

# ── Schema ──────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    url         TEXT    NOT NULL,
    type        TEXT    NOT NULL DEFAULT 'rss',
    country     TEXT    NOT NULL DEFAULT '',
    tier        INTEGER NOT NULL CHECK (tier IN (1, 2, 3))
);

CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    INTEGER NOT NULL REFERENCES sources(id),
    source_name  TEXT    NOT NULL,
    url          TEXT    NOT NULL UNIQUE,
    title        TEXT    NOT NULL,
    raw_text     TEXT    NOT NULL DEFAULT '',
    published_at TEXT,            -- ISO-8601 or NULL
    fetched_at   TEXT    NOT NULL, -- ISO-8601
    country_tag  TEXT    NOT NULL DEFAULT '',
    tier         INTEGER NOT NULL CHECK (tier IN (1, 2, 3))
);

CREATE INDEX IF NOT EXISTS idx_articles_source   ON articles(source_name);
CREATE INDEX IF NOT EXISTS idx_articles_tier     ON articles(tier);
CREATE INDEX IF NOT EXISTS idx_articles_fetched  ON articles(fetched_at);

-- Full-text search virtual table (title + raw_text)
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title,
    raw_text,
    content='articles',
    content_rowid='id'
);

-- Triggers to keep the FTS index in sync
CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, raw_text)
    VALUES (new.id, new.title, new.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, raw_text)
    VALUES ('delete', old.id, old.title, old.raw_text);
    INSERT INTO articles_fts(rowid, title, raw_text)
    VALUES (new.id, new.title, new.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, raw_text)
    VALUES ('delete', old.id, old.title, old.raw_text);
END;
"""


# ── Database helpers ────────────────────────────────────────────────────────

def get_db_path() -> pathlib.Path:
    return _DEFAULT_DB


def connect(db_path: pathlib.Path | str | None = None) -> sqlite3.Connection:
    """Return a connection with row-factory enabled."""
    path = pathlib.Path(db_path) if db_path else _DEFAULT_DB
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: pathlib.Path | str | None = None) -> pathlib.Path:
    """Create the database file and tables. Returns the DB path."""
    path = pathlib.Path(db_path) if db_path else _DEFAULT_DB
    conn = connect(path)
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    conn.close()
    return path


# ── Source helpers ──────────────────────────────────────────────────────────

def upsert_source(conn: sqlite3.Connection, name: str, url: str,
                  src_type: str, country: str, tier: int) -> int:
    """Insert or update a source row; return its id."""
    conn.execute(
        """INSERT INTO sources (name, url, type, country, tier)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
               url     = excluded.url,
               type    = excluded.type,
               country = excluded.country,
               tier    = excluded.tier""",
        (name, url, src_type, country, tier),
    )
    row = conn.execute("SELECT id FROM sources WHERE name = ?", (name,)).fetchone()
    return row["id"]


# ── Article helpers ─────────────────────────────────────────────────────────

def _dt_to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def insert_articles(conn: sqlite3.Connection, articles) -> int:
    """Insert article metadata rows, skipping duplicates (by URL).

    *articles* should be an iterable of objects with attributes:
        title, url, source_name, country, tier, published_at, fetched_at

    Returns the number of **newly inserted** rows.
    """
    inserted = 0
    for art in articles:
        try:
            # look up source_id
            src_row = conn.execute(
                "SELECT id FROM sources WHERE name = ?", (art.source_name,)
            ).fetchone()
            source_id = src_row["id"] if src_row else 0

            conn.execute(
                """INSERT OR IGNORE INTO articles
                   (source_id, source_name, url, title, published_at,
                    fetched_at, country_tag, tier)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    source_id,
                    art.source_name,
                    art.url,
                    art.title,
                    _dt_to_iso(art.published_at),
                    _dt_to_iso(art.fetched_at),
                    art.country,
                    art.tier,
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except Exception as exc:
            # Skip problematic rows but don't crash the batch
            print(f"  ⚠ skipped '{art.title[:50]}…': {exc}")
    return inserted


def article_count(conn: sqlite3.Connection) -> int:
    """Return total number of article rows."""
    return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]


def recent_articles(conn: sqlite3.Connection, hours: int = 24,
                    limit: int = 500) -> List[sqlite3.Row]:
    """Fetch articles stored within the last *hours* hours."""
    return conn.execute(
        """SELECT * FROM articles
           WHERE fetched_at >= datetime('now', ?)
           ORDER BY fetched_at DESC
           LIMIT ?""",
        (f"-{hours} hours", limit),
    ).fetchall()


def update_article_text(conn: sqlite3.Connection, article_id: int, text: str) -> None:
    """Set the raw_text for an article (also updates FTS via trigger)."""
    conn.execute(
        "UPDATE articles SET raw_text = ? WHERE id = ?",
        (text, article_id),
    )


def articles_missing_text(conn: sqlite3.Connection, limit: int = 500) -> List[sqlite3.Row]:
    """Return articles that have no extracted text yet."""
    return conn.execute(
        """SELECT id, url, title, source_name FROM articles
           WHERE raw_text = '' OR raw_text IS NULL
           ORDER BY fetched_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()


def text_stats(conn: sqlite3.Connection) -> dict:
    """Return counts of articles with/without extracted text."""
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    with_text = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE raw_text != '' AND raw_text IS NOT NULL"
    ).fetchone()[0]
    return {"total": total, "with_text": with_text, "without_text": total - with_text}


def get_articles_by_ids(conn: sqlite3.Connection,
                        ids: List[int]) -> List[sqlite3.Row]:
    """Fetch full article rows for a list of article IDs."""
    if not ids:
        return []
    placeholders = ", ".join("?" for _ in ids)
    return conn.execute(
        f"SELECT * FROM articles WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
