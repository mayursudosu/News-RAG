"""Local LLM engine – wraps llama-cpp-python for brief enrichment.

Provides:
  • load_llm()          – singleton model loader
  • enrich_event_card() – generates WHAT / WHY / SIGNIFICANCE from article text
  • LLM_AVAILABLE       – boolean flag for graceful fallback

The model runs on GPU via llama.cpp CUDA backend.
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path
from typing import Dict, Optional

# ── Default model path ──────────────────────────────────────────────────────

_DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models" / "mistral-7b-instruct-v0.2.Q4_K_M.gguf"

# ── Singleton ───────────────────────────────────────────────────────────────

_llm_instance = None
LLM_AVAILABLE = False

try:
    from llama_cpp import Llama
    LLM_AVAILABLE = True
except ImportError:
    Llama = None  # type: ignore


def load_llm(
    model_path: Optional[str] = None,
    n_gpu_layers: int = 35,
    n_ctx: int = 4096,
    verbose: bool = False,
) -> "Llama":
    """Load (or return cached) Llama model.

    Parameters
    ----------
    model_path : path to .gguf file.  Defaults to models/mistral-7b-instruct-v0.2.Q4_K_M.gguf.
    n_gpu_layers : layers offloaded to GPU.  35 is safe for 4-bit 7B on 8 GB VRAM.
    n_ctx : context window.  4096 is enough for article chunks.
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    if not LLM_AVAILABLE:
        raise RuntimeError(
            "llama-cpp-python is not installed.  "
            "Run: pip install llama-cpp-python"
        )

    path = Path(model_path) if model_path else _DEFAULT_MODEL
    if not path.exists():
        raise FileNotFoundError(
            f"Model file not found: {path}\n"
            "Download a GGUF model into the models/ directory."
        )

    print(f"  ⏳ Loading LLM ({path.name}) …", file=sys.stderr, flush=True)
    _llm_instance = Llama(
        model_path=str(path),
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
        verbose=verbose,
    )
    print("  ✅ LLM ready", file=sys.stderr, flush=True)
    return _llm_instance


# ── Prompt template ─────────────────────────────────────────────────────────

_ENRICH_PROMPT = """\
You are an intelligence analyst writing a daily brief for defense and geopolitics professionals.

EVENT TITLE: {title}
VERIFICATION: {verification}
SOURCES: {sources}

ARTICLE TEXT (may be truncated):
{text}

Based ONLY on the article text above, produce exactly three sections.  Be factual, concise, and analytical.  Do NOT invent facts.

WHAT HAPPENED:
(Write 3–4 sentences summarising the key facts of this event.)

WHY IT MATTERS:
(Write 2–3 sentences explaining the immediate impact, context, or consequences.)

STRATEGIC SIGNIFICANCE:
(Write exactly 2 sentences explaining the broader geopolitical, economic, or security implications.)
"""


def _truncate_text(text: str, max_chars: int = 2800) -> str:
    """Truncate article text to fit within LLM context budget.

    ~2800 chars ≈ ~700 tokens, leaving room for the prompt + response within 4096 ctx.
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + " …"


def _parse_response(raw: str) -> Dict[str, str]:
    """Parse the three sections from LLM output.

    Returns dict with keys: what_happened, why_it_matters, strategic_significance.
    Falls back to raw text if parsing fails.
    """
    result = {
        "what_happened": "",
        "why_it_matters": "",
        "strategic_significance": "",
    }

    sections = {
        "WHAT HAPPENED:": "what_happened",
        "WHY IT MATTERS:": "why_it_matters",
        "STRATEGIC SIGNIFICANCE:": "strategic_significance",
    }

    # Find each section header and grab everything until the next header
    upper = raw
    positions = []
    for header, key in sections.items():
        idx = upper.find(header)
        if idx != -1:
            positions.append((idx, header, key))

    positions.sort(key=lambda x: x[0])

    for i, (pos, header, key) in enumerate(positions):
        start = pos + len(header)
        end = positions[i + 1][0] if i + 1 < len(positions) else len(upper)
        result[key] = upper[start:end].strip()

    # If parsing failed entirely, stuff everything into what_happened
    if not any(result.values()):
        result["what_happened"] = raw.strip()[:300]

    return result


def enrich_event_card(
    title: str,
    article_texts: list[str],
    verification_status: str,
    sources: str,
    *,
    max_tokens: int = 350,
) -> Dict[str, str]:
    """Use the local LLM to generate WHAT / WHY / SIGNIFICANCE for one event.

    Parameters
    ----------
    title : event headline
    article_texts : list of raw article texts for this event
    verification_status : e.g. "Verified", "Single-source"
    sources : comma-separated source names

    Returns
    -------
    dict with keys: what_happened, why_it_matters, strategic_significance
    """
    llm = load_llm()

    # Use the longest article text
    best_text = max(article_texts, key=len) if article_texts else ""
    if not best_text:
        return {
            "what_happened": "(full text not available)",
            "why_it_matters": "Further details emerging.",
            "strategic_significance": "Monitoring for broader implications.",
        }

    prompt = _ENRICH_PROMPT.format(
        title=title,
        verification=verification_status,
        sources=sources,
        text=_truncate_text(best_text),
    )

    response = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3,       # low creativity, factual
        top_p=0.9,
    )

    raw_output = response["choices"][0]["message"]["content"]
    return _parse_response(raw_output)
