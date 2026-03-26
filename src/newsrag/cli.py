"""newsrag CLI – all user-facing commands live here."""

from __future__ import annotations

import argparse
import sys
import textwrap
from datetime import date
from typing import List


TOPIC_OPTIONS = [
    "defense",
    "economy",
    "technology",
    "diplomacy",
    "science",
    "energy",
    "global_policy",
    "all",
]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _dummy_brief() -> str:
    """Return a hard-coded sample brief for Phase 1 testing."""
    today = date.today().strftime("%d %B %Y")
    return textwrap.dedent(f"""\
    ╔══════════════════════════════════════════════════════════════╗
    ║            DEFENSE & GEOPOLITICS DAILY BRIEF                ║
    ║            {today:^46}  ║
    ╚══════════════════════════════════════════════════════════════╝

    ── Executive Summary ──────────────────────────────────────────
    • India test-fires extended-range BrahMos cruise missile.
    • NATO announces new rapid-deployment force structure.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    EVENT 1 – India Test-Fires Extended-Range BrahMos
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    WHEN          : 01 March 2026
    WHAT          : India successfully test-fired an extended-range
                    BrahMos supersonic cruise missile from a land-
                    based mobile launcher in Odisha.
    HOW           : The missile achieved its full range of ~450 km,
                    validating the upgraded propulsion and guidance
                    systems developed with DRDO and BrahMos
                    Aerospace.
    WHY           : Strengthens India's stand-off strike capability
                    amid ongoing modernization of the missile
                    arsenal and regional deterrence posture.
    IMPACT        : Enhances Indian Navy and Army strike options;
                    may accelerate export interest from friendly
                    nations (Philippines, Vietnam).
    EXAM RELEVANCE: UPSC GS-III (Science & Tech / Defence);
                    BrahMos JV structure; missile classification.
    MCQ Points    : BrahMos is a joint India-Russia venture;
                    supersonic (Mach 2.8); can be launched from
                    land, sea, sub-sea, and air platforms.
    Verification Status : Verified
    Sources       : Reuters, The Hindu, NDTV

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    EVENT 2 – NATO Announces New Rapid-Deployment Force
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    WHEN          : 28 February 2026
    WHAT          : NATO Secretary General announced the creation
                    of a 10,000-strong rapid-deployment force to
                    reinforce the alliance's eastern flank.
    HOW           : The force will draw on rotating contributions
                    from member states and be headquartered in
                    Poland with forward logistics nodes in the
                    Baltic states.
    WHY           : Responds to continued Russian force posture
                    near NATO borders and lessons learned from
                    the Ukraine conflict.
    IMPACT        : Signals deepening NATO commitment to
                    collective defense; may raise Russia-NATO
                    tensions further.
    EXAM RELEVANCE: UPSC GS-II (International Relations); NATO
                    Article 5; European security architecture.
    MCQ Points    : NATO founded 1949; 32 members as of 2024;
                    headquarters in Brussels; Article 5 =
                    collective defense clause.
    Verification Status : Verified
    Sources       : AP, BBC, Reuters

    ── End of Brief ───────────────────────────────────────────────
    """)


# ── Command handlers ────────────────────────────────────────────────────────

def _prompt_int(question: str, default: int) -> int:
    raw = input(f"{question} [{default}]: ").strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        print(f"Invalid value '{raw}', using default {default}.")
        return default


def _parse_topics(raw: str) -> List[str]:
    if not raw.strip():
        return ["all"]

    items = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not items:
        return ["all"]

    invalid = [topic for topic in items if topic not in TOPIC_OPTIONS]
    if invalid:
        print(f"Unknown topic(s): {', '.join(invalid)}. Using 'all'.")
        return ["all"]

    # If 'all' is present, no need for others.
    if "all" in items:
        return ["all"]

    # Preserve order, remove duplicates.
    unique: List[str] = []
    for topic in items:
        if topic not in unique:
            unique.append(topic)
    return unique


def _prompt_topics(default: str = "all") -> List[str]:
    print("Available topics:")
    print("  " + ", ".join(TOPIC_OPTIONS))
    raw = input(f"Which topics should be included? [{default}]: ")
    return _parse_topics(raw if raw.strip() else default)

def cmd_next_day(args: argparse.Namespace) -> None:
    """Generate and print the daily defense & geopolitics brief."""
    from newsrag.brief_builder import generate_next_day_brief

    use_llm = getattr(args, "llm", False)

    india_count = args.india
    global_count = args.globe
    topics = _parse_topics(args.topics) if args.topics else None

    # Interactive mode for plain `newsrag next-day`
    if india_count is None:
        india_count = _prompt_int("How many Indian news events do you want?", 6)
    if global_count is None:
        global_count = _prompt_int("How many International news events do you want?", 5)
    if topics is None:
        topics = _prompt_topics(default="all")

    brief = generate_next_day_brief(
        india_top=india_count,
        global_top=global_count,
        use_llm=use_llm,
        selected_topics=topics,
    )
    print(brief)


def cmd_fetch_sample(args: argparse.Namespace) -> None:
    """Fetch RSS feeds and print article titles grouped by source."""
    from newsrag.config_loader import load_sources
    from newsrag.fetcher import fetch_all

    sources = load_sources()
    print(f"Fetching from {len(sources)} configured sources…\n")
    grouped = fetch_all(sources)

    print("\n" + "═" * 64)
    for src_name, articles in grouped.items():
        tier = articles[0].tier if articles else "?"
        print(f"\n── {src_name}  (Tier {tier}) ──")
        if not articles:
            print("   (no articles fetched)")
            continue
        for art in articles:
            print(f"   • {art.title}")
            print(f"     {art.url}")
    print("\n" + "═" * 64)


def cmd_init_db(args: argparse.Namespace) -> None:
    """Create / initialise the SQLite database."""
    from newsrag.storage import init_db

    path = init_db()
    print(f"✓ Database initialised at {path}")


def cmd_fetch_store(args: argparse.Namespace) -> None:
    """Fetch RSS feeds and persist article metadata into the database."""
    from newsrag.config_loader import load_sources
    from newsrag.fetcher import fetch_and_store
    from newsrag.storage import connect, article_count, init_db, text_stats

    # ensure DB exists
    init_db()

    sources = load_sources()
    print(f"Fetching from {len(sources)} sources and storing…\n")
    new_rows = fetch_and_store(sources, extract_text=True)

    conn = connect()
    total = article_count(conn)
    stats = text_stats(conn)
    conn.close()

    print(f"\n── Results ──")
    print(f"   New articles inserted : {new_rows}")
    print(f"   Total articles in DB  : {total}")
    print(f"   Articles with text    : {stats['with_text']}")
    print(f"   Articles without text : {stats['without_text']}")


def cmd_search_articles(args: argparse.Namespace) -> None:
    """Search stored articles by keyword using full-text search."""
    from newsrag.search import search_articles

    query = args.query
    print(f"Searching for: {query!r}\n")
    results = search_articles(query)

    if not results:
        print("  No matching articles found.")
        return

    print(f"  Found {len(results)} match(es):\n")
    for i, row in enumerate(results, 1):
        print(f"  {i:>2}. [{row['source_name']}  Tier {row['tier']}]")
        print(f"      {row['title']}")
        print(f"      {row['url']}")
        if row["snippet"]:
            print(f"      …{row['snippet']}…")
        print()


def cmd_show_sources(args: argparse.Namespace) -> None:
    """List all configured sources grouped by tier."""
    from newsrag.source_info import format_sources_table

    print(format_sources_table())


def cmd_filter_sample(args: argparse.Namespace) -> None:
    """Load recent articles from DB, apply filtering, show kept vs dropped."""
    from newsrag.storage import connect, recent_articles
    from newsrag.filtering import filter_articles

    conn = connect()
    articles = recent_articles(conn, hours=72)
    conn.close()

    if not articles:
        print("No recent articles in DB. Run fetch-store first.")
        return

    results = filter_articles(articles)
    kept = [r for r in results if r.kept]
    dropped = [r for r in results if not r.kept]

    # Sort kept by score descending
    kept.sort(key=lambda r: r.score, reverse=True)
    dropped.sort(key=lambda r: r.score, reverse=True)

    print(f"Filtered {len(results)} articles  →  {len(kept)} KEPT  ·  {len(dropped)} DROPPED\n")

    print("\n━━━ KEPT (defense / geopolitics relevant) ━━━")
    for r in kept:
        pos = ", ".join(r.positive_hits[:5]) or "—"
        neg = ", ".join(r.negative_hits[:3]) or "—"
        print(f"  [{r.tier}] {r.score:+5.1f}  {r.source_name:20s}  {r.title[:70]}")
        print(f"           +[{pos}]  -[{neg}]")

    print(f"\n━━━ DROPPED (noise / irrelevant) ━━━")
    for r in dropped:
        pos = ", ".join(r.positive_hits[:5]) or "—"
        neg = ", ".join(r.negative_hits[:3]) or "—"
        print(f"  [{r.tier}] {r.score:+5.1f}  {r.source_name:20s}  {r.title[:70]}")
        print(f"           +[{pos}]  -[{neg}]")


def cmd_verify_demo(args: argparse.Namespace) -> None:
    """Group recent kept articles into events and show verification status."""
    from newsrag.storage import connect, recent_articles
    from newsrag.filtering import filter_articles
    from newsrag.verification import build_verified_events, format_event_summary

    conn = connect()
    articles = recent_articles(conn, hours=72)
    conn.close()

    if not articles:
        print("No recent articles in DB. Run fetch-store first.")
        return

    # Step 1 – filter to kept articles only
    results = filter_articles(articles)
    kept = [r for r in results if r.kept]
    kept.sort(key=lambda r: r.score, reverse=True)

    # Convert FilterResult objects to dicts for the verification pipeline
    kept_dicts = [
        {
            "id": r.article_id,
            "title": r.title,
            "source_name": r.source_name,
            "tier": r.tier,
            "score": r.score,
            "country_tag": r.country_tag,
        }
        for r in kept
    ]

    print(f"Filtered {len(articles)} articles → {len(kept)} kept\n")

    # Step 2 – group into events & verify
    groups = build_verified_events(kept_dicts)

    # Step 3 – display
    print(format_event_summary(groups))


def cmd_rank_events(args: argparse.Namespace) -> None:
    """Rank event groups and display two UPSC sections: India + Global."""
    from newsrag.storage import connect, recent_articles
    from newsrag.filtering import filter_articles
    from newsrag.verification import build_verified_events
    from newsrag.ranking import (
        rank_events, split_ranked_events, format_brief_sections,
        format_ranked_events,
    )

    conn = connect()
    articles = recent_articles(conn, hours=72)
    conn.close()

    if not articles:
        print("No recent articles in DB. Run fetch-store first.")
        return

    # Filter → keep
    results = filter_articles(articles)
    kept = [r for r in results if r.kept]
    kept.sort(key=lambda r: r.score, reverse=True)

    kept_dicts = [
        {
            "id": r.article_id,
            "title": r.title,
            "source_name": r.source_name,
            "tier": r.tier,
            "score": r.score,
            "country_tag": r.country_tag,
        }
        for r in kept
    ]

    print(f"Filtered {len(articles)} articles → {len(kept)} kept")

    # Group → verify → rank
    groups = build_verified_events(kept_dicts)
    ranked = rank_events(groups)
    print(f"Grouped into {len(groups)} events\n")

    if args.flat:
        # Legacy single-list mode
        print(format_ranked_events(ranked, top_n=args.top))
    else:
        # UPSC two-section mode (default)
        sections = split_ranked_events(
            ranked, india_top=args.india, global_top=args.globe
        )
        print(format_brief_sections(sections))


# ── CLI wiring ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="newsrag",
        description="Defense News RAG – daily intelligence brief generator",
    )
    sub = parser.add_subparsers(dest="command")

    # next-day
    p_next = sub.add_parser("next-day", help="Generate (or display) the next-day defense brief")
    p_next.add_argument("--india", type=int, default=None,
                        help="Indian events count (interactive prompt if omitted)")
    p_next.add_argument("--globe", type=int, default=None,
                        help="International events count (interactive prompt if omitted)")
    p_next.add_argument("--topics", type=str, default=None,
                        help="Comma-separated topics: defense,economy,technology,diplomacy,science,energy,global_policy,all")
    p_next.add_argument("--llm", action="store_true", default=False,
                        help="Use local LLM to enrich event descriptions")

    # fetch-sample  (Phase 2)
    sub.add_parser("fetch-sample", help="Fetch RSS feeds and print article titles")

    # init-db  (Phase 3)
    sub.add_parser("init-db", help="Create / initialise the SQLite database")

    # fetch-store  (Phase 3)
    sub.add_parser("fetch-store", help="Fetch RSS feeds and store article metadata in DB")

    # search-articles  (Phase 4)
    p_search = sub.add_parser("search-articles", help="Full-text search over stored articles")
    p_search.add_argument("query", help="Keyword(s) to search for")

    # show-sources  (Phase 5)
    sub.add_parser("show-sources", help="List all configured sources grouped by tier")

    # filter-sample  (Phase 6)
    sub.add_parser("filter-sample", help="Show which recent articles pass relevance filtering")

    # verify-demo  (Phase 7)
    sub.add_parser("verify-demo", help="Group kept articles into events and show verification status")

    # rank-events  (Phase 8)
    p_rank = sub.add_parser("rank-events", help="Rank events by composite score (UPSC two-section)")
    p_rank.add_argument("--india", type=int, default=6,
                        help="Max India Current Affairs events (default: 6)")
    p_rank.add_argument("--globe", type=int, default=5,
                        help="Max Global Strategic Affairs events (default: 5)")
    p_rank.add_argument("--flat", action="store_true",
                        help="Show flat ranked list instead of two sections")
    p_rank.add_argument("-n", "--top", type=int, default=15,
                        help="Number of events in flat mode (default: 15)")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "next-day": cmd_next_day,
        "fetch-sample": cmd_fetch_sample,
        "init-db": cmd_init_db,
        "fetch-store": cmd_fetch_store,
        "search-articles": cmd_search_articles,
        "show-sources": cmd_show_sources,
        "filter-sample": cmd_filter_sample,
        "verify-demo": cmd_verify_demo,
        "rank-events": cmd_rank_events,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()
