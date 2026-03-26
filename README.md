# 🛡️ Defense News RAG – Daily Global Intelligence Brief System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![LLM / AI](https://img.shields.io/badge/LLM%20/%20AI-Mistral%207B-FF6B35?style=for-the-badge&logo=meta&logoColor=white)
![CUDA / GPU Support](https://img.shields.io/badge/CUDA%20/%20GPU%20Support-12.1-76B900?style=for-the-badge&logo=nvidia&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

**A local AI-powered system that generates structured global intelligence briefs from real-time news.**

</div>

---

## 2. LIVE SAMPLE OUTPUT

```text
╔══════════════════════════════════════════════════════════════╗
║        DEFENSE & GEOPOLITICS DAILY BRIEF                    ║
║                        13 March 2026                        ║
║              🤖  LLM-Enhanced Analysis                      ║
╚══════════════════════════════════════════════════════════════╝

── Executive Summary ──────────────────────────────────────────
  • US says its military cannot escort vessels in Hormuz right now
  • Hardeep Puri clarifies: No shortage of petrol or diesel in India
  • Strait of Hormuz will stay closed to pressure enemies, says Khamenei
  • Can Iran's asymmetric warfare hold US-Israeli military power at bay?

════════════════════════════════════════════════════════════════
  🇮🇳  TOP INDIAN NEWS
════════════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EVENT 1 │ No shortage of petrol, diesel: Hardeep Puri
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHEN            : 13 March 2026
  WHERE           : India
  WHAT HAPPENED   : Oil Minister Hardeep Singh Puri stated that India has
                    adequate reserves of petrol and diesel to meet domestic
                    demand despite the ongoing crisis in the Middle East.
  WHY IT MATTERS  : Calms domestic markets and addresses panic buying
                    concerns as global supply chains face extreme pressure.
  IMPACT          : Stabilizes the domestic economy and demonstrates
                    strategic petroleum reserve readiness in a crisis.
  CONFIDENCE      : ✅  Verified
  SOURCES (3)     : The Hindu, Indian Express, NDTV

════════════════════════════════════════════════════════════════
  🌍  TOP INTERNATIONAL NEWS
════════════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EVENT 1 │ 'Simply not ready': US says its military cannot escort vessels
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHEN            : 12 March 2026
  WHERE           : United States
  WHAT HAPPENED   : The United States military is currently unable to escort
                    oil ships through the Strait of Hormuz due to the focus
                    on destroying Iran's offensive capabilities.
  WHY IT MATTERS  : The closure has caused oil prices to soar and disrupted
                    global energy markets, leaving allied nations vulnerable.
  IMPACT          : Approximately one-third of the world's seaborne oil
                    passes through the strait, creating severe economic shocks.
  CONFIDENCE      : ✅  Verified
  SOURCES (4)     : BBC World, Al Jazeera, Reuters, AP News

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EVENT 2 │ Strait of Hormuz will stay closed to pressure enemies
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHEN            : 13 March 2026
  WHERE           : Iran
  WHAT HAPPENED   : Iran’s new Supreme Leader Mojtaba Khamenei declared
                    the vital shipping lane will remain closed to maximize
                    economic pressure on adversaries.
  WHY IT MATTERS  : Shifts the conflict from pure military engagement to
                    asymmetric economic warfare affecting the entire globe.
  IMPACT          : Escalates global recession risks, alters maritime trade
                    routes, and forces strategic realignment among Gulf states.
  CONFIDENCE      : ⚠️  Single-source
  SOURCES (1)     : Al Jazeera
```

---

## 3. FEATURE TABLE

| Feature | Description |
|---|---|
| **Multi-source aggregation** | Ingests from 12+ Tier 1/2/3 RSS feeds across global and regional outlets. |
| **Event deduplication** | Uses semantic embeddings (`sentence-transformers`) to group identical stories. |
| **Verification logic** | Cross-references sources to apply confidence scoring (Verified vs Single-source). |
| **Importance ranking** | Ranks events composite formula of recency, diversity, tier trust, and keyword hits. |
| **Local LLM** | No API dependency. Runs Mistral 7B locally via `llama.cpp` for ultimate privacy. |
| **GPU acceleration** | Offloads transformer layers to CUDA backend for fast, efficient text processing. |
| **Structured intelligence** | Outputs rigorous analyst-style cards (WHAT, WHY, IMPACT, CONFIDENCE). |
| **India + global split** | Segmented reporting separating domestic strategic issues from international ones. |

---

## 4. ARCHITECTURE DIAGRAM

```text
       RSS Sources
            ↓
         Fetcher
            ↓
 Filtering + Categorization
            ↓
      SQLite Storage
            ↓
     Event Clustering
            ↓
    Verification Engine
            ↓
      Ranking Engine
            ↓
LLM (Mistral via llama.cpp)
            ↓
 Daily Intelligence Brief
```

---

## 5. PROJECT STRUCTURE

```text
news_rag/
├── src/newsrag/
│   ├── __main__.py         # Entry point: python -m newsrag
│   ├── cli.py              # Argument parser + interactive prompts
│   ├── fetcher.py          # RSS fetch + HTTP article download
│   ├── parser.py           # HTML → clean text (BeautifulSoup + lxml)
│   ├── filtering.py        # Keyword scoring + topic category assignment
│   ├── ranking.py          # Composite rank score + India/Global split
│   ├── verification.py     # Cross-source deduplication + confidence engine
│   ├── brief_builder.py    # Event card assembly + final brief output
│   ├── llm_engine.py       # Mistral 7B singleton loader + prompt engine
│   ├── storage.py          # SQLite persistence layer
│   └── search.py           # Full-text search over stored articles
├── config/
│   ├── sources.yml         # Curated RSS sources with tiers
│   └── filters.yml         # Relevance keywords + topic categories
├── models/
│   └── mistral-7b...gguf   # Quantized LLM (downloaded separately)
└── pyproject.toml          # Build and dependency definitions
```

---

## 6. QUICK START GUIDE

### Step 1: Create Virtual Environment

```bash
python3.12 -m venv rag_env
source rag_env/bin/activate
```

### Step 2: Install Core Dependencies

```bash
pip install -e .
```

### Step 3: Install PyTorch (CUDA Wheel) & llama-cpp-python

```bash
pip install torch
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

### Step 4: Fix LD_LIBRARY_PATH (if needed)

If you encounter `libcudart.so` errors, add this to `rag_env/bin/activate`:

```bash
export LD_LIBRARY_PATH="$(python -c "import site, pathlib; print(':'.join(str(p/'lib') for p in (pathlib.Path(site.getsitepackages()[0])/'nvidia').iterdir() if (p/'lib').is_dir()))"):$LD_LIBRARY_PATH"
```

### Step 5: Download GGUF Model

```bash
mkdir -p models
wget -O models/mistral-7b-instruct-v0.2.Q4_K_M.gguf https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.q4_K_M.gguf
```

### Step 6: Run Fetch

```bash
python -m newsrag fetch-store
```

### Step 7: Run Next-Day Brief

```bash
python -m newsrag next-day --llm
```

---

## 7. CLI REFERENCE

| Command | Description | Example |
|---|---|---|
| `next-day` | Generates the daily intelligence brief | `python -m newsrag next-day --llm` |
| `fetch` | Pulls the latest RSS feeds and articles | `python -m newsrag fetch` |
| `search` | Full-text search over stored database events | `python -m newsrag search "hormuz"` |
| `init-db` | Initializes a fresh SQLite database | `python -m newsrag init-db` |

**Optional Flags (for `next-day`)**

| Flag | Description | Example |
|---|---|---|
| `--india` | Exact count of Indian events to report | `--india 3` |
| `--globe` | Exact count of international events to report | `--globe 3` |
| `--topics` | Comma-separated list of topics to filter | `--topics defense,energy` |
| `--llm` | Enables LLM generation for WHAT/WHY/IMPACT | `--llm` |

---

## 8. PYTHON PACKAGE STACK

### Core

* **`requests`**: Handles fast HTTP downloads with retry logic for articles.
* **`feedparser`**: Robust parsing for various RSS and Atom feed formats.
* **`beautifulsoup4`**: HTML tree traversal to extract pure text from news pages.

### AI

* **`sentence-transformers`**: Generates local context embeddings to cluster similar articles.
* **`llama-cpp-python`**: C++ bindings to run quantized GGUF LLMs with GPU offloading.
* **`torch`**: PyTorch backend required for running the local sentence transformers.

### Storage

* **`sqlite3`**: Built-in, lightweight relational database to store articles and vectors.

---

## 9. LLM ENGINE DEEP-DIVE

* **Model Used**: Mistral 7B Instruct v0.2 (GGUF format).
* **Why Quantized?**: Using 4-bit quantization (Q4_K_M) allows a large, coherent model to run in under 8GB of VRAM.
* **Why Local Inference?**: For defense and intelligence work, sending article data over an API to third-party providers severely compromises OPSEC.
* **Temperature Setting**: Kept extremely low (`0.3`) to prevent hallucination and strictly enforce factual representation.
* **Prompt Structure**: Enforces a rigid JSON-like output mimicking a professional analyst: WHAT HAPPENED, WHY IT MATTERS, IMPACT.

**Fallback Logic:**
The system is built resiliently. If the GPU fails or the `llama-cpp-python` bindings are uninstalled, `LLM_AVAILABLE` catches the `ImportError` gracefully. The pipeline will automatically fall back to fast Regex & Keyword heuristic extraction and generate the brief without crashing.

---

## 10. RANKING ALGORITHM

The system calculates an urgency score to prioritize what bubbles up to the brief.

$$ \text{Score} = (\text{Relevance} + \text{Verification} + \text{Diversity} + \text{Recency}) \times \text{Tier Multiplier} $$

* **Relevance**: Best keyword match score derived from the article title and body.
* **Verification**: +5 points if covered by multiple distinct sources, +2 if single source.
* **Diversity**: Rewards stories covered across multiple different regions or domains.
* **Recency**: Exponential decay applied to older stories.
* **Tier Multiplier**: 1.2x weight for Tier-1 trusted wires, 0.8x for niche blogs.

---

## 11. NEWS SOURCES

**Tier 1** (Highest trust wire services)
* Reuters, BBC World, AP News, AFP, Al Jazeera

**Tier 2** (National/Regional coverage)
* The Hindu, Indian Express, NDTV, Times of India, South China Morning Post

**Tier 3** (Niche/Opinion/Analysis)
* War on the Rocks, The Diplomat, Defense One

---

## 12. TOPIC CATEGORIES

The system categorizes events for granular filtering:

* **defense**: *missile, drone, airstrike, warship, artillery*
* **geopolitics**: *treaty, sovereignty, alliance, summit*
* **economy**: *inflation, GDP, sanctions, supply chain*
* **energy**: *oil price, Strait of Hormuz, pipeline, LNG*
* **technology**: *cybersecurity, AI, semiconductor, ISRO*
* **science**: *nuclear, climate, pandemic, space*
* **global policy**: *NATO, BRICS, UN, Middle East*

---

## 13. KNOWN LIMITATIONS

* **GPU Compatibility (sm_120)**: Newer Blackwell architectures may face minor warnings loading standard PyTorch `cu121` wheels.
* **Context Token Limits**: To fit on an 8GB GPU, the model uses a 4096 context window. Extremely long articles are truncated.
* **RSS Inconsistencies**: Some sites deploy scraping countermeasures or serve partial RSS strings rather than full text.
* **Temporal Tracking**: Currently operates day-by-day. It does not yet automatically track week-over-week strategic shifts.

---

## 14. CONTRIBUTING

Contributions are welcome to make this system more robust.

**Areas for Improvement:**
* Integrations with broader global feeds (e.g., non-English sources translated locally).
* Better Named Entity Recognition (NER) for exact geographic tracking.
* Implementing a long-term rolling memory for multi-day crises.

**How to Submit PRs:**
1. Fork the repo and create a `feature/` branch.
2. Ensure you haven't broken the `LLM_AVAILABLE` fallback logic.
3. Submit a PR outlining exactly what you improved.

---

## 15. LICENSE

This project is licensed under the MIT License - see the LICENSE file for details.
# News-RAG
