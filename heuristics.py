"""
Modular prompting/voting heuristics for the Promptcraft experiment.

Swap implementations by changing registry entries or replacing placeholder_perplexity_normalized.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


def word_count(text: str) -> int:
    if not text or not str(text).strip():
        return 0
    return len(re.findall(r"\S+", str(text).strip()))


def placeholder_perplexity_normalized(text: str, prompt_index: int = 1) -> float:
    """
    Deterministic pseudo-complexity in ~[0.12, 0.95] from prompt content + index.
    Replace with real perplexity / Gemini scoring later (see proposal.md).
    """
    raw = f"{prompt_index}|{text or ''}".encode("utf-8", errors="ignore")
    h = hashlib.sha256(raw).digest()
    x = int.from_bytes(h[:4], "big") / 0xFFFFFFFF
    return round(0.12 + 0.83 * x, 4)


@dataclass(frozen=True)
class HeuristicDef:
    id: str
    label: str
    description: str


# IDs stable for analytics columns / JSON keys
HEURISTIC_NUMBER_OF_PROMPTS = HeuristicDef(
    id="number_of_prompts",
    label="Number of prompts",
    description="Prompt index for this generated image (1-based).",
)
HEURISTIC_TOTAL_WORD_COUNT = HeuristicDef(
    id="total_word_count",
    label="Total word count",
    description="Words written across prompts up to and including this image.",
)
HEURISTIC_PROMPT_COMPLEXITY = HeuristicDef(
    id="prompt_complexity",
    label="Prompt complexity",
    description="Normalized complexity score (placeholder until real perplexity).",
)

HEURISTIC_REGISTRY: Dict[str, HeuristicDef] = {
    HEURISTIC_NUMBER_OF_PROMPTS.id: HEURISTIC_NUMBER_OF_PROMPTS,
    HEURISTIC_TOTAL_WORD_COUNT.id: HEURISTIC_TOTAL_WORD_COUNT,
    HEURISTIC_PROMPT_COMPLEXITY.id: HEURISTIC_PROMPT_COMPLEXITY,
}


def cumulative_word_count_for_round(images: List[dict], up_to_index_inclusive: int) -> int:
    """images: server image_entry list in order; up_to_index_inclusive is 1-based prompt_index."""
    total = 0
    for img in images:
        idx = img.get("prompt_index") or 0
        if idx <= 0:
            continue
        if idx > up_to_index_inclusive:
            break
        p = img.get("prompt") or ""
        total += word_count(p)
    return total


def snapshot_for_image_entry(
    *,
    prompt_index: int,
    prompt_text: str,
    images_before_and_including: List[dict],
) -> Dict[str, Any]:
    cum_words = cumulative_word_count_for_round(images_before_and_including, prompt_index)
    ppn = placeholder_perplexity_normalized(prompt_text, prompt_index)
    return {
        HEURISTIC_NUMBER_OF_PROMPTS.id: prompt_index,
        HEURISTIC_TOTAL_WORD_COUNT.id: cum_words,
        HEURISTIC_PROMPT_COMPLEXITY.id: ppn,
    }


def format_snapshot_for_ui(snapshot: Dict[str, Any]) -> List[Dict[str, str]]:
    """Label + formatted value for client display."""
    out: List[Dict[str, str]] = []
    order = [
        HEURISTIC_NUMBER_OF_PROMPTS,
        HEURISTIC_TOTAL_WORD_COUNT,
        HEURISTIC_PROMPT_COMPLEXITY,
    ]
    for h in order:
        v = snapshot.get(h.id)
        if v is None:
            continue
        if h.id == HEURISTIC_PROMPT_COMPLEXITY.id:
            pct = max(0.0, min(1.0, float(v))) * 100.0
            text = f"{pct:.0f}%"
        else:
            text = str(int(v)) if isinstance(v, (int, float)) and h.id != HEURISTIC_PROMPT_COMPLEXITY.id else str(v)
        out.append({"id": h.id, "label": h.label, "value": text})
    return out


def aggregate_snapshot_for_round(*, total_prompts: int, total_words: int, complexities: List[float]) -> Dict[str, Any]:
    """Aggregate under target (T_NA / T_HU prompting)."""
    avg_c = sum(complexities) / len(complexities) if complexities else 0.0
    return {
        HEURISTIC_NUMBER_OF_PROMPTS.id: total_prompts,
        HEURISTIC_TOTAL_WORD_COUNT.id: total_words,
        HEURISTIC_PROMPT_COMPLEXITY.id: round(avg_c, 4),
    }


def show_prompting_heuristics(team: Optional[str]) -> bool:
    return team in ("T_NA", "T_HU")


def show_voting_heuristics(team: Optional[str]) -> bool:
    return team in ("C_HU", "T_HU")
