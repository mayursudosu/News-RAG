"""Daily brief generator — produces a structured defense & geopolitics intelligence brief.

Pipeline:  DB articles → filter → group → verify → rank → split → brief

Each event card includes (in order):
  1. EVENT TITLE
  2. WHEN                    – event date (DD Month YYYY)
  3. WHERE                   – primary location inferred from title/text
  4. WHAT HAPPENED           – 3-4 sentence factual summary
  5. WHY IT MATTERS          – 2-3 sentences on impact/context
  6. STRATEGIC SIGNIFICANCE  – 2 sentences on broader geopolitical implications
  7. VERIFICATION            – status from Phase 7
  8. SOURCES                 – contributing news outlets

Two sections:
  🇮🇳  INDIA CURRENT AFFAIRS   (top 6)
  🌍  GLOBAL STRATEGIC AFFAIRS (top 5)
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from newsrag.ranking import BriefSections, RankedEvent

# ── LLM availability (graceful fallback) ────────────────────────────────────

try:
    from newsrag.llm_engine import LLM_AVAILABLE, enrich_event_card
except ImportError:
    LLM_AVAILABLE = False
    enrich_event_card = None  # type: ignore

# ── Text-extraction helpers ─────────────────────────────────────────────────

_WRAP_WIDTH = 68


def _wrap(text: str, indent: str = "                    ", width: int = _WRAP_WIDTH) -> str:
    """Word-wrap text with a hanging indent."""
    lines = textwrap.wrap(text, width=width)
    if not lines:
        return ""
    first = lines[0]
    rest = [indent + line for line in lines[1:]]
    return "\n".join([first] + rest)


# ── WHEN / WHERE extraction helpers ─────────────────────────────────────────

def _extract_when(articles: List[dict]) -> str:
    """Derive the best event date from article metadata.

    Picks the earliest *published_at* among the articles in the event.
    Returns a formatted date string (DD Month YYYY) or a fallback.
    """
    dates: List[datetime] = []
    for art in articles:
        raw = art.get("published_at") or ""
        if not raw:
            continue
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                     "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
            try:
                dates.append(datetime.strptime(raw[:19], fmt[:len(raw[:19])+2]))
                break
            except (ValueError, IndexError):
                continue
    if dates:
        earliest = min(dates)
        return earliest.strftime("%d %B %Y")
    return date.today().strftime("%d %B %Y")


# Major regions / countries used for WHERE inference
_LOCATION_PATTERNS: List[Tuple[str, str]] = [
    (r"\bindia\b", "India"),
    (r"\bnew delhi\b", "New Delhi, India"),
    (r"\bmumbai\b", "Mumbai, India"),
    (r"\bkashmir\b", "Kashmir, India"),
    (r"\bleh\b|\bladakh\b", "Ladakh, India"),
    (r"\biран\b|\biran\b", "Iran"),
    (r"\btehran\b", "Tehran, Iran"),
    (r"\bisrael\b", "Israel"),
    (r"\btel aviv\b|\bjerusalem\b", "Jerusalem, Israel"),
    (r"\bgaza\b", "Gaza"),
    (r"\bpalestine\b|\bwest bank\b", "Palestine"),
    (r"\blebanon\b|\bbeirut\b", "Beirut, Lebanon"),
    (r"\bsyria\b|\bdamascus\b", "Syria"),
    (r"\biraq\b|\bbaghdad\b", "Iraq"),
    (r"\bkurd", "Kurdistan Region"),
    (r"\bchina\b|\bbeijing\b", "China"),
    (r"\btaiwan\b|\btaipei\b", "Taiwan"),
    (r"\bjapan\b|\btokyo\b", "Japan"),
    (r"\bsouth korea\b|\bseoul\b", "South Korea"),
    (r"\bnorth korea\b|\bpyongyang\b", "North Korea"),
    (r"\bpakistan\b|\bislamabad\b", "Pakistan"),
    (r"\bafghanistan\b|\bkabul\b", "Afghanistan"),
    (r"\brussia\b|\bmoscow\b", "Russia"),
    (r"\bukraine\b|\bkyiv\b", "Ukraine"),
    (r"\bturkey\b|\btürkiye\b|\bankara\b", "Türkiye"),
    (r"\bspain\b|\bmadrid\b", "Spain"),
    (r"\bfrance\b|\bparis\b", "France"),
    (r"\bgermany\b|\bberlin\b", "Germany"),
    (r"\buk\b|\blondon\b|\bbritain\b", "United Kingdom"),
    (r"\bcanada\b|\bottawa\b", "Canada"),
    (r"\baustralia\b|\bcanberra\b", "Australia"),
    (r"\bindian ocean\b", "Indian Ocean"),
    (r"\bsouth china sea\b", "South China Sea"),
    (r"\bbay of bengal\b", "Bay of Bengal"),
    (r"\bmiddle east\b", "Middle East"),
    (r"\bpentagon\b|\bwashington\b|\bwhite house\b", "Washington, United States"),
    (r"\bunited states\b|\bu\.?s\.?\b", "United States"),
    (r"\bnato\b|\bbrussels\b", "Brussels (NATO HQ)"),
    (r"\bthe hague\b", "The Hague, Netherlands"),
]


def _extract_where(title: str, text: str, country_tag: str) -> str:
    """Infer the primary location from the event title, text, or country_tag.

    Checks the title first (most reliable), then the leading paragraph of
    text, then falls back to country_tag.
    """
    # Check title first, then first 500 chars of text
    for haystack in (title, text[:500]):
        lower = haystack.lower()
        for pattern, label in _LOCATION_PATTERNS:
            if re.search(pattern, lower):
                return label

    # Fall back to country_tag from the source config
    if country_tag:
        return country_tag.title()
    return "—"


def _extract_summary(article_texts: List[str], max_chars: int = 250) -> str:
    """Pull a 3–4 line factual summary from article text.

    Strategy: take the first substantial paragraph from the longest article
    text available.  Truncate to *max_chars*.
    """
    # Filter out noise / paywall stubs
    _noise_phrases = [
        "join war on the rocks", "gain access to content",
        "subscribe", "sign up for", "create a free account",
        "log in to read", "members only", "paywall",
    ]

    def _is_usable(text: str) -> bool:
        lower = text.lower()
        return not any(phrase in lower for phrase in _noise_phrases)

    # Use the longest usable text
    usable = [t for t in article_texts if t and _is_usable(t)]
    if not usable:
        # Fall back to any text even if noisy
        usable = [t for t in article_texts if t]
    best = max(usable, key=len) if usable else ""
    if not best:
        return "(full text not available)"

    # Split into paragraphs, pick the first non-trivial one
    paragraphs = [p.strip() for p in best.split("\n") if len(p.strip()) > 60]
    # Also filter out noise paragraphs
    paragraphs = [p for p in paragraphs if _is_usable(p)]

    if not paragraphs:
        # Fall back to first N chars
        summary = best[:max_chars].strip()
    else:
        summary = paragraphs[0]

    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0] + " …"
    return summary


def _infer_strategic_significance(title: str, why: str, is_india: bool) -> str:
    """Generate a brief strategic-significance statement based on keyword heuristics.

    Returns 1–2 sentences framing the event in broader geopolitical, economic,
    or security terms.  Checks the title first for high-confidence matches,
    then broadens to include the WHY text for secondary lenses.
    """
    title_l = title.lower()
    combined = (title + " " + why).lower()

    # ── Rules-based order / international law (very specific, check first) ──
    if any(k in combined for k in ("rules-based order", "international law",
                                    "the hague", "icc", "icj", "global order")):
        return ("Challenges the legitimacy and enforcement capacity of the "
                "rules-based international order. "
                "May embolden or deter similar unilateral actions by other states.")

    # ── Military hardware / arms (title only – high confidence) ────────────
    if any(k in title_l for k in ("nuclear", "missile", "warship", "submarine",
                                   "drone", "stealth", "radar", "artillery",
                                   "torpedo", "frigate", "destroyer")):
        return ("Shifts the regional military balance and could trigger "
                "an arms-race dynamic among neighbouring states. "
                "Defence procurement and deterrence postures may be reassessed.")

    # ── Active conflict / war (title only to avoid false positives) ──────
    if any(k in title_l for k in ("war ", "conflict", "strike", "bomb",
                                   "invasion", "offensive", "attack",
                                   "ceasefire", "evacuation")):
        return ("Escalation or de-escalation at this stage reshapes alliance "
                "commitments and threat perceptions across the region. "
                "Humanitarian and diplomatic fallout will test multilateral frameworks.")

    # ── Trade & economy (combined) ─────────────────────────────────
    if any(k in combined for k in ("trade", "tariff", "sanctions", "export",
                                    "import", "oil", "crude", "supply chain",
                                    "economic", "gdp", "inflation", "currency")):
        return ("Has direct implications for global supply chains, commodity "
                "prices, and bilateral trade flows. "
                "May prompt retaliatory economic measures or new trade alignments.")

    # ── Diplomacy / alliances (combined) ───────────────────────────
    if any(k in combined for k in ("treaty", "bilateral", "multilateral",
                                    "summit", "diplomacy", "alliance", "nato",
                                    "united nations", "foreign policy",
                                    "ambassador", "parliament", "concession")):
        return ("Signals a realignment of diplomatic priorities that could "
                "redraw partnership networks. "
                "Multilateral institutions may face pressure to adapt.")

    # ── Internal security / terrorism (combined) ─────────────────
    if any(k in combined for k in ("terror", "infiltration", "cybersecurity",
                                    "espionage", "intelligence", "surveillance",
                                    "border", "rebellion", "insurgent")):
        return ("Raises the internal security threshold and may accelerate "
                "intelligence-sharing agreements. "
                "Border management and counter-terrorism protocols are likely to tighten.")

    # ── Geography / maritime / climate (combined) ────────────────
    if any(k in combined for k in ("earthquake", "cyclone", "flood", "climate",
                                    "sea lane", "south china sea",
                                    "indian ocean", "strait")):
        return ("Highlights the growing intersection of geography, climate risk, "
                "and strategic competition over critical maritime routes. "
                "Disaster preparedness and resource allocation become focal points.")

    # ── Deterrence / strategic posture (combined) ───────────────
    if any(k in combined for k in ("deterrence", "posture", "flank",
                                    "front", "dilemma", "two-front",
                                    "three-front", "encirclement")):
        return ("Complicates strategic calculus by multiplying threat vectors. "
                "Force-posture decisions and alliance burden-sharing will be reassessed.")

    # ── Fallback ────────────────────────────────────────────
    if is_india:
        return ("Holds significance for India's strategic posture and its "
                "evolving role in regional security architecture.")
    return ("Reflects shifting power dynamics in the international system "
            "with potential ripple effects across multiple regions.")


# ── Event card builder ──────────────────────────────────────────────────────

@dataclass
class EventCard:
    """A formatted event entry ready for the brief."""
    rank: int
    title: str
    when: str
    where: str
    what_happened: str
    why_it_matters: str
    strategic_significance: str
    verification_status: str
    verification_icon: str
    sources: str
    source_count: int
    score: float


def build_event_card(
    ranked_event: RankedEvent,
    article_data: Dict[int, dict],
    *,
    is_india: bool = False,
    use_llm: bool = False,
) -> EventCard:
    """Build a formatted event card from a RankedEvent.

    *article_data* maps article ID → dict with keys:
        raw_text, published_at, country_tag  (from full DB row).

    If *use_llm* is True and the LLM is available, WHAT HAPPENED /
    WHY IT MATTERS / SIGNIFICANCE are generated by the local LLM.
    Otherwise, heuristic extraction is used (Phase 9 behaviour).
    """
    # Gather available texts and metadata for articles in this event
    texts: List[str] = []
    meta_articles: List[dict] = []   # dicts with published_at, country_tag
    for art in ranked_event.articles:
        aid = art.get("id")
        if aid and aid in article_data:
            row = article_data[aid]
            txt = row.get("raw_text") or ""
            if txt:
                texts.append(txt)
            meta_articles.append(row)

    # 2. WHEN – derive from article published_at
    when = _extract_when(meta_articles)

    # 3. WHERE – infer from title, text, or country_tag
    first_text = texts[0] if texts else ""
    first_ctag = meta_articles[0].get("country_tag", "") if meta_articles else ""
    where = _extract_where(ranked_event.label, first_text, first_ctag)

    sources_str = ", ".join(sorted(set(ranked_event.source_names)))

    # ── Try LLM enrichment ──────────────────────────────────────────────
    if use_llm and LLM_AVAILABLE and enrich_event_card is not None and texts:
        try:
            llm_fields = enrich_event_card(
                title=ranked_event.label,
                article_texts=texts,
                verification_status=ranked_event.verification_status,
                sources=sources_str,
            )
            return EventCard(
                rank=ranked_event.rank,
                title=ranked_event.label,
                when=when,
                where=where,
                what_happened=llm_fields["what_happened"],
                why_it_matters=llm_fields["why_it_matters"],
                strategic_significance=llm_fields["strategic_significance"],
                verification_status=ranked_event.verification_status,
                verification_icon=ranked_event.icon,
                sources=sources_str,
                source_count=ranked_event.source_count,
                score=ranked_event.rank_score,
            )
        except Exception as e:
            import sys
            print(f"  ⚠ LLM failed for '{ranked_event.label[:50]}…': {e}",
                  file=sys.stderr)
            # Fall through to heuristic extraction

    # ── Heuristic extraction (fallback / default) ───────────────────────
    # 4. WHAT HAPPENED – 3-4 line factual summary
    what_happened = _extract_summary(texts)

    # 5. WHY IT MATTERS – 2-3 lines on strategic implications
    _noise_phrases = [
        "join war on the rocks", "gain access to content",
        "subscribe", "sign up for", "create a free account",
        "log in to read", "members only", "paywall",
    ]

    def _is_usable(text: str) -> bool:
        lower = text.lower()
        return not any(phrase in lower for phrase in _noise_phrases)

    best_text = ""
    for t in sorted(texts, key=len, reverse=True):
        if _is_usable(t):
            best_text = t
            break
    if not best_text and texts:
        best_text = max(texts, key=len)

    paragraphs = [p.strip() for p in best_text.split("\n")
                  if len(p.strip()) > 40 and _is_usable(p.strip())]

    # Pick a paragraph that is different from the WHAT HAPPENED text
    why = "Further details emerging; monitoring for updates."
    for p in paragraphs[1:]:
        if p.strip()[:50] != what_happened.strip()[:50]:
            why = p
            if len(why) > 280:
                why = why[:280].rsplit(" ", 1)[0] + " …"
            break

    significance = _infer_strategic_significance(ranked_event.label, why, is_india)

    return EventCard(
        rank=ranked_event.rank,
        title=ranked_event.label,
        when=when,
        where=where,
        what_happened=what_happened,
        why_it_matters=why,
        strategic_significance=significance,
        verification_status=ranked_event.verification_status,
        verification_icon=ranked_event.icon,
        sources=sources_str,
        source_count=ranked_event.source_count,
        score=ranked_event.rank_score,
    )


# ── Full brief formatting ──────────────────────────────────────────────────

def _format_card(card: EventCard, section_idx: int) -> str:
    """Format a single event card as a text block.

    Layout (7 fields):
      WHEN → WHERE → WHAT HAPPENED → WHY IT MATTERS →
      STRATEGIC SIGNIFICANCE → VERIFICATION → SOURCES
    """
    sep = "━" * 64
    lbl = "  "  # left label indent
    sig_indent = "                    "  # align with other wrapped fields
    return (
        f"{sep}\n"
        f"{lbl}EVENT {section_idx} │ {card.title}\n"
        f"{sep}\n"
        f"{lbl}WHEN            : {card.when}\n"
        f"{lbl}WHERE           : {card.where}\n"
        f"{lbl}WHAT HAPPENED   : {_wrap(card.what_happened)}\n"
        f"{lbl}WHY IT MATTERS  : {_wrap(card.why_it_matters)}\n"
        f"{lbl}SIGNIFICANCE    : {_wrap(card.strategic_significance, indent=sig_indent)}\n"
        f"{lbl}VERIFICATION    : {card.verification_icon}  {card.verification_status}\n"
        f"{lbl}SOURCES ({card.source_count})     : {card.sources}\n"
    )


def generate_brief(
    sections: BriefSections,
    article_data: Dict[int, dict],
    *,
    use_llm: bool = False,
) -> str:
    """Generate the complete daily brief from ranked sections.

    *article_data* – dict mapping article ID → dict with keys:
        raw_text, published_at, country_tag  (from full DB rows).
    *use_llm* – if True, use local LLM to generate event descriptions.
    """
    today = date.today().strftime("%d %B %Y")
    lines: List[str] = []

    # ── Header ──
    lines.append("╔══════════════════════════════════════════════════════════════╗")
    lines.append("║        DEFENSE & GEOPOLITICS DAILY BRIEF                   ║")
    lines.append(f"║        {today:^52} ║")
    if use_llm and LLM_AVAILABLE:
        lines.append("║              🤖  LLM-Enhanced Analysis                      ║")
    lines.append("╚══════════════════════════════════════════════════════════════╝")
    lines.append("")

    # ── Executive Summary ──
    lines.append("── Executive Summary ──────────────────────────────────────────")
    lines.append("")
    all_events: List[RankedEvent] = sections.india + sections.globe
    for ev in all_events:
        bullet = ev.label
        if len(bullet) > 72:
            bullet = bullet[:69] + "…"
        lines.append(f"  • {bullet}")
    lines.append("")

    # ── Build cards ──
    india_cards = [
        build_event_card(r, article_data, is_india=True, use_llm=use_llm)
        for r in sections.india
    ]
    globe_cards = [
        build_event_card(r, article_data, is_india=False, use_llm=use_llm)
        for r in sections.globe
    ]

    # ── Top Indian News ──
    lines.append("═" * 64)
    lines.append("  🇮🇳  TOP INDIAN NEWS")
    lines.append("═" * 64)
    lines.append("")
    for i, card in enumerate(india_cards, 1):
        lines.append(_format_card(card, i))

    # ── Top International News ──
    lines.append("═" * 64)
    lines.append("  🌍  TOP INTERNATIONAL NEWS")
    lines.append("═" * 64)
    lines.append("")
    for i, card in enumerate(globe_cards, 1):
        lines.append(_format_card(card, i))

    # ── Footer ──
    lines.append("── End of Brief ───────────────────────────────────────────────")
    total = len(india_cards) + len(globe_cards)
    lines.append(
        f"   {total} events  ·  "
        f"{len(india_cards)} India  ·  "
        f"{len(globe_cards)} Global  ·  "
        f"Generated {today}"
    )
    lines.append("")

    return "\n".join(lines)


# ── End-to-end pipeline ────────────────────────────────────────────────────

def generate_next_day_brief(
    *,
    hours: int = 72,
    india_top: int = 6,
    global_top: int = 5,
    use_llm: bool = False,
    selected_topics: Optional[List[str]] = None,
) -> str:
    """Full pipeline: DB → filter → group → verify → rank → split → brief.

    If *use_llm* is True, the local LLM enriches WHAT / WHY / SIGNIFICANCE
    for each event.  Otherwise, heuristic extraction is used.

    If *selected_topics* is provided (and does not contain "all"), events are
    filtered by topic category after ranking and before section split.

    Returns the formatted brief as a string.
    """
    from newsrag.storage import connect, recent_articles, get_articles_by_ids, init_db
    from newsrag.filtering import filter_articles
    from newsrag.verification import build_verified_events
    from newsrag.ranking import rank_events, split_ranked_events

    init_db()
    conn = connect()
    articles = recent_articles(conn, hours=hours)

    if not articles:
        conn.close()
        return "⚠ No recent articles found. Run `newsrag fetch-store` first."

    # Filter
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
            "category": r.category,
        }
        for r in kept
    ]

    # Group → verify → rank → split
    groups = build_verified_events(kept_dicts)
    ranked = rank_events(groups)

    # Topic filter is applied after ranking (as requested).
    topics = [t.lower() for t in (selected_topics or [])]
    if topics and "all" not in topics:
        ranked = [r for r in ranked if r.category in topics]

    sections = split_ranked_events(
        ranked, india_top=india_top, global_top=global_top
    )

    # Collect all article IDs from the selected events to fetch full text
    all_art_ids: List[int] = []
    for r in sections.india + sections.globe:
        for art in r.articles:
            aid = art.get("id")
            if aid:
                all_art_ids.append(aid)

    # Fetch full rows from DB (raw_text + published_at + country_tag)
    full_rows = get_articles_by_ids(conn, all_art_ids)
    conn.close()

    article_data: Dict[int, dict] = {
        row["id"]: {
            "raw_text": row["raw_text"] or "",
            "published_at": row["published_at"] or "",
            "country_tag": row["country_tag"] or "",
        }
        for row in full_rows
    }

    return generate_brief(sections, article_data, use_llm=use_llm)
