import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import streamlit as st
import os
os.environ["LLAMA_CPP_LIB"] = ""
os.environ["OMP_NUM_THREADS"] = "1"
import time

# ==========================================
# CONFIGURATION & SETUP
# ==========================================
st.set_page_config(
    page_title="Intelligence Briefing",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for cleaner spacing and card-like feel
st.markdown("""
<style>
    .event-card {
        background-color: rgba(255, 255, 255, 0.03);
        border-left: 3px solid #4a90e2;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border-radius: 0 8px 8px 0;
    }
    .meta-text {
        font-size: 0.85rem;
        color: #888;
        margin-bottom: 1rem;
    }
    .section-header {
        font-weight: 600;
        color: #e0e0e0;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .footer-text {
        font-size: 0.8rem;
        color: #777;
        margin-top: 1rem;
        border-top: 1px solid #333;
        padding-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# MOCK DATA
# ==========================================
def get_mock_data():
    """Provides mock structured data mimicking the backend."""
    india_events = [
        {
            "id": "i1",
            "title": "Hardeep Puri Assures Adequate Petroleum Reserves",
            "published_time": "2 hours ago",
            "importance": "HIGH",
            "what": "Oil Minister Hardeep Singh Puri stated that India has adequate reserves of petrol and diesel to meet domestic demand despite the ongoing crisis in the Middle East.",
            "why": [
                "Calms domestic markets and addresses panic buying concerns",
                "Demonstrates readiness of Strategic Petroleum Reserves (SPR)"
            ],
            "impact": [
                "Stabilizes the domestic economy against global supply shocks",
                "May encourage localized investment in alternative fuels"
            ],
            "confidence": "HIGH",
            "sources": ["The Hindu", "Indian Express", "NDTV"],
            "category": "energy"
        },
        {
            "id": "i2",
            "title": "DRDO Successfully Tests Extended Range Advanced Missile",
            "published_time": "5 hours ago",
            "importance": "MEDIUM",
            "what": "The Defense Research and Development Organization successfully test-fired a newly upgraded surface-to-air missile from the Odisha coast.",
            "why": [
                "Validates completely indigenous seeker technology",
                "Bolsters multi-layered air defense systems"
            ],
            "impact": [
                "Enhances border deterrence posture",
                "Potential reduction in foreign arms dependence"
            ],
            "confidence": "HIGH",
            "sources": ["Times of India"],
            "category": "defense"
        },
        {
            "id": "i3",
            "title": "RBI Signals Pause on Repo Rate Amidst Global Uncertainty",
            "published_time": "1 day ago",
            "importance": "LOW",
            "what": "The Reserve Bank of India indicated it may hold interest rates steady in the upcoming policy meeting, citing inflation risks from geopolitical tensions.",
            "why": [
                "Aims to balance growth support with inflation targeting",
                "Direct response to surging crude oil prices"
            ],
            "impact": [
                "Keeps borrowing costs stable for Indian businesses",
                "Protects currency valuation"
            ],
            "confidence": "MEDIUM",
            "sources": ["Reuters", "The Hindu"],
            "category": "economy"
        }
    ]

    world_events = [
        {
            "id": "w1",
            "title": "'Simply not ready': US Military Cannot Escort Vessels in Hormuz",
            "published_time": "3 hours ago",
            "importance": "HIGH",
            "what": "The United States military is currently unable to escort oil ships through the Strait of Hormuz due to resource allocations focusing on countering broader regional threats.",
            "why": [
                "Leaves a major geopolitical economic artery undefended",
                "Forces commercial shippers to halt operations or take massive risks"
            ],
            "impact": [
                "Approximately 20% of global oil flow is effectively stalled",
                "Severe economic shocks and skyrocketing insurance premiums"
            ],
            "confidence": "HIGH",
            "sources": ["Al Jazeera", "BBC World", "AP News"],
            "category": "geopolitics"
        },
        {
            "id": "w2",
            "title": "Global Markets Plunge as Supply Chain Fears Grow",
            "published_time": "8 hours ago",
            "importance": "HIGH",
            "what": "Major indices across Europe and Asia saw significant sell-offs today, with energy sectors being the sole gainers in a highly volatile trading session.",
            "why": [
                "Reflects investor panic over prolonged Middle East disruptions",
                "Highlights systemic fragility in just-in-time supply chains"
            ],
            "impact": [
                "Triggers potential inflationary cycles globally",
                "Forces central banks into difficult policy corners"
            ],
            "confidence": "MEDIUM",
            "sources": ["Reuters", "Bloomberg"],
            "category": "economy"
        },
        {
            "id": "w3",
            "title": "New Multi-Modal AI Research Model Released Open-Source",
            "published_time": "12 hours ago",
            "importance": "LOW",
            "what": "A leading European AI lab open-sourced a new 7B parameter multi-modal model capable of reasoning over complex visual and textual datasets.",
            "why": [
                "Democratizes access to high-tier AI capabilities",
                "Challenges proprietary model dominance"
            ],
            "impact": [
                "Accelerates global AI research",
                "Raises dual-use security concerns"
            ],
            "confidence": "HIGH",
            "sources": ["TechCrunch", "The Diplomat"],
            "category": "technology"
        }
    ]
    
    return india_events, world_events


# ==========================================
# BACKEND INTEGRATION
# ==========================================
import sys
import json
import subprocess
from pathlib import Path

# Add the src directory to Python path if running standalone
src_path = str(Path(__file__).resolve().parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

@st.cache_data(show_spinner=False, ttl=3600)
def get_real_data(india_limit: int, world_limit: int, use_llm: bool):
    """Fetches real DB data via an isolated subprocess to prevent CUDA/Streamlit thread clashing."""
    import tempfile
    
    # We write a tiny runner script to call the pipeline in complete isolation
    script = f'''
import sys
import json
from pathlib import Path
sys.path.insert(0, "{src_path}")

from newsrag.storage import connect, recent_articles, get_articles_by_ids, init_db
from newsrag.filtering import filter_articles
from newsrag.verification import build_verified_events
from newsrag.ranking import rank_events, split_ranked_events
from newsrag.brief_builder import build_event_card

def extract():
    init_db()
    conn = connect()
    articles = recent_articles(conn, hours=72)
    if not articles:
        conn.close()
        return {{"india": [], "world": []}}

    results = filter_articles(articles)
    kept = [r for r in results if r.kept]
    kept.sort(key=lambda r: r.score, reverse=True)

    kept_dicts = [
        {{
            "id": r.article_id,
            "title": r.title,
            "source_name": r.source_name,
            "tier": r.tier,
            "score": r.score,
            "country_tag": r.country_tag,
            "category": getattr(r, "category", "global_policy"),
        }}
        for r in kept
    ]

    groups = build_verified_events(kept_dicts)
    ranked = rank_events(groups)
    sections = split_ranked_events(ranked, india_top={india_limit}, global_top={world_limit})

    all_art_ids = []
    for r in sections.india + sections.globe:
        for art in r.articles:
            if art.get("id"):
                all_art_ids.append(art["id"])

    full_rows = get_articles_by_ids(conn, all_art_ids)
    conn.close()

    article_data = {{
        row["id"]: {{
            "raw_text": row["raw_text"] or "",
            "published_at": row["published_at"] or "",
            "country_tag": row["country_tag"] or "",
        }}
        for row in full_rows
    }}

    def to_dashboard_event(ranked_ev, is_india):
        card = build_event_card(ranked_ev, article_data, is_india=is_india, use_llm={use_llm})
        
        conf_map = {{"Verified": "HIGH", "Single-source": "MEDIUM", "Unverified": "LOW", "✅  Verified": "HIGH", "⚠️  Single-source": "MEDIUM"}}
        conf = conf_map.get(card.verification_status, "LOW")
        
        score = card.score
        if score > 15: importance = "HIGH"
        elif score > 8: importance = "MEDIUM"
        else: importance = "LOW"
        
        def split_sentences(text):
            if not text: return []
            sents = [s.strip() for s in text.replace("\\n", " ").split(". ") if len(s.strip()) > 5]
            if sents and not sents[-1].endswith("."): sents[-1] += "."
            return sents or [text]
            
        return {{
            "id": ranked_ev.id,
            "title": card.title,
            "published_time": card.when,
            "importance": importance,
            "what": card.what_happened,
            "why": split_sentences(card.why_it_matters),
            "impact": split_sentences(card.strategic_significance),
            "confidence": conf,
            "sources": [s.strip() for s in card.sources.split(",")],
            "category": getattr(ranked_ev, "category", "global_policy")
        }}

    india_events = [to_dashboard_event(r, True) for r in sections.india]
    world_events = [to_dashboard_event(r, False) for r in sections.globe]
    
    return {{"india": india_events, "world": world_events}}

print(json.dumps(extract()))
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tf:
        tf.write(script)
        tf_name = tf.name

    try:
        # Run process using standard python executable matching current environment
        result = subprocess.run([sys.executable, tf_name], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data["india"], data["world"]
    except subprocess.CalledProcessError as e:
        print(f"Error during backend execution: {e.stderr}", file=sys.stderr)
        raise e
    except Exception as e:
        print(f"Failed to parse backend data: {e}", file=sys.stderr)
        raise e
    finally:
        import os
        os.unlink(tf_name)

def run_backend_fetch():
    """Trigger the backend RSS fetcher via subprocess to prevent blocking."""
    script = f'''
import sys
from pathlib import Path
sys.path.insert(0, "{src_path}")
from newsrag.config_loader import load_sources
from newsrag.fetcher import fetch_and_store
sources = load_sources()
fetch_and_store(sources, extract_text=True)
'''
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tf:
        tf.write(script)
        tf_name = tf.name

    try:
        subprocess.run([sys.executable, tf_name], capture_output=True, text=True, check=True)
    finally:
        import os
        os.unlink(tf_name)

# ==========================================
# LOGIC & FILTERING
# ==========================================
def filter_events(events, topics, limit):
    """Filters events by category and limits the count."""
    filtered = events
    if topics and "All" not in topics:
        filtered = [e for e in filtered if e["category"].lower() in [t.lower() for t in topics]]
    
    return filtered[:limit]


def get_importance_icon(importance_level):
    if importance_level == "HIGH":
        return "🔥"
    elif importance_level == "MEDIUM":
        return "⚠"
    else:
        return "•"


def render_event_card(event):
    """Renders a single event card using clean Markdown."""
    imp_icon = get_importance_icon(event.get('importance', 'LOW'))
    
    # Render with Streamlit container instead of raw HTML div wrapping for better compatibility
    with st.container():
        # Title and metadata
        imp_color = "red" if event['importance'] == 'HIGH' else "orange" if event['importance'] == 'MEDIUM' else "gray"
        
        st.markdown(f"### {event['title']}")
        st.markdown(f"🕒 {event['published_time']} &nbsp; | &nbsp; {imp_icon} **Importance:** <span style='color:{imp_color}'>{event['importance']}</span>", unsafe_allow_html=True)
        
        # Body text built cleanly using Markdown
        body_md = f"**WHAT:**\n\n{event['what']}\n\n"
        
        body_md += "**💡 WHY THIS MATTERS:**\n"
        for item in event['why']:
            body_md += f"- {item}\n"
            
        body_md += "\n**⚡ IMPACT:**\n"
        for item in event['impact']:
            body_md += f"- {item}\n"
            
        st.markdown(body_md)
        
        # Footer
        st.caption(f"**Confidence:** {event['confidence']} &nbsp; | &nbsp; **Sources:** {', '.join(event['sources'])}")
        st.markdown("---")



# ==========================================
# MAIN UI APPLICATION
# ==========================================
def main():
    st.title("🛡️ Daily Intelligence Brief")
    st.markdown("A clean, fast, 5-minute global intelligence overview.")

    # Top Bar: Filters and Controls
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns([1, 1, 2, 2])
    
    with col1:
        india_limit = st.number_input("🇮🇳 India Events", min_value=1, max_value=10, value=3)
    with col2:
        world_limit = st.number_input("🌍 World Events", min_value=1, max_value=10, value=3)
    with col3:
        all_topics = ["All", "defense", "economy", "technology", "energy", "diplomacy", "science", "global_policy"]
        selected_topics = st.multiselect("📊 Topics", options=all_topics, default=["All"])
    with col4:
        st.write("") # Spacing 
        use_llm = st.checkbox("🤖 Use LLM (Mistral 7B)", value=False, help="Enable AI-generated summaries. Takes 1-2 minutes.")
        col4_a, col4_b = st.columns(2)
        with col4_a:
            do_fetch = st.button("📥 Fetch Latest News", use_container_width=True)
        with col4_b:
            refresh = st.button("🔄 Generate Brief", use_container_width=True, type="primary")

    if do_fetch:
        with st.spinner("Fetching latest articles from sources..."):
            run_backend_fetch()
            st.success("Database updated! Click 'Generate Brief' to see results.")
            get_real_data.clear() # Clear cache to force next brief to use new data

    if refresh:
        get_real_data.clear() # Clear cache to regenerate if asked directly

    # Load Data Load State Trigger
    if 'has_run' not in st.session_state:
        st.session_state.has_run = True

    try:
        with st.spinner("Compiling intelligence brief... (Using LLM may take a few minutes)"):
            raw_india, raw_world = get_real_data(10, 10, use_llm)  # Pull top 10 from backend, slice in UI
    except Exception as e:
        st.error(f"Error loading backend data: {e}")
        raw_india, raw_world = get_mock_data() # Fallback to mock gracefully
    
    # Apply Filters (Post-ranking topic filter limits)
    india_events = filter_events(raw_india, selected_topics, india_limit)
    world_events = filter_events(raw_world, selected_topics, world_limit)

    # Main View: Side-by-Side Columns
    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        st.header("🇮🇳 India")
        if not india_events:
            st.info("No significant events found for selected filters.")
        else:
            for event in india_events:
                render_event_card(event)

    with col_right:
        st.header("🌍 World")
        if not world_events:
            st.info("No significant events found for selected filters.")
        else:
            for event in world_events:
                render_event_card(event)

if __name__ == "__main__":
    main()
