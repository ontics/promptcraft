"""
Modular prompting/voting heuristics for the Promptcraft experiment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def word_count(text: str) -> int:
    if not text or not str(text).strip():
        return 0
    return len(re.findall(r"\S+", str(text).strip()))


def format_seconds_mm_ss(total_seconds: int) -> str:
    """Format elapsed seconds (e.g. 0–300) as M:SS for UI."""
    s = max(0, int(total_seconds))
    m, sec = divmod(s, 60)
    return f"{m}:{sec:02d}"


@dataclass(frozen=True)
class HeuristicDef:
    id: str
    label: str
    description: str


# Stable IDs for analytics / JSON snapshots
HEURISTIC_PROMPT_INDEX = HeuristicDef(
    id="prompt_index",
    label="Prompt #",
    description="1-based prompt index in this round.",
)
HEURISTIC_WORD_COUNT_PROMPT = HeuristicDef(
    id="word_count_prompt",
    label="Word count",
    description="Word count for this prompt only.",
)
HEURISTIC_TIME_IN_ROUND = HeuristicDef(
    id="time_in_round_seconds",
    label="Timestamp",
    description="Seconds after round start when the prompt was sent (0–300 for a 5-minute round); shown as M:SS.",
)
# Aggregate under target (two metrics only)
HEURISTIC_TOTAL_PROMPTS = HeuristicDef(
    id="total_prompts",
    label="Prompts sent",
    description="Number of successful prompts in this round so far.",
)
HEURISTIC_TOTAL_WORDS_ROUND = HeuristicDef(
    id="total_word_count_round",
    label="Total words",
    description="Sum of word counts across all prompts so far in this round.",
)

HEURISTIC_REGISTRY: Dict[str, HeuristicDef] = {
    HEURISTIC_PROMPT_INDEX.id: HEURISTIC_PROMPT_INDEX,
    HEURISTIC_WORD_COUNT_PROMPT.id: HEURISTIC_WORD_COUNT_PROMPT,
    HEURISTIC_TIME_IN_ROUND.id: HEURISTIC_TIME_IN_ROUND,
    HEURISTIC_TOTAL_PROMPTS.id: HEURISTIC_TOTAL_PROMPTS,
    HEURISTIC_TOTAL_WORDS_ROUND.id: HEURISTIC_TOTAL_WORDS_ROUND,
}


def cumulative_word_count_for_round(images: List[dict], up_to_index_inclusive: int) -> int:
    """Words across prompts with prompt_index <= up_to_index_inclusive (1-based). Order-independent."""
    total = 0
    for img in images:
        idx = img.get("prompt_index") or 0
        if idx <= 0 or idx > up_to_index_inclusive:
            continue
        p = img.get("prompt", "")
        total += word_count(p)
    return total


def snapshot_for_image_entry(
    *,
    prompt_index: int,
    prompt_text: str,
    images_before_and_including: List[dict],
    prompt_elapsed_seconds: int,
    cumulative_word_count_for_prompt_line: bool = False,
) -> Dict[str, Any]:
    """If True, per-image word line is total words in the round up to and including this prompt."""
    if cumulative_word_count_for_prompt_line:
        wc = cumulative_word_count_for_round(images_before_and_including, prompt_index)
        wc_label = "Total words"
    else:
        wc = word_count(prompt_text)
        wc_label = HEURISTIC_WORD_COUNT_PROMPT.label
    elapsed = max(0, min(int(prompt_elapsed_seconds), 3600))
    return {
        HEURISTIC_PROMPT_INDEX.id: prompt_index,
        HEURISTIC_WORD_COUNT_PROMPT.id: wc,
        HEURISTIC_TIME_IN_ROUND.id: elapsed,
        "_word_count_label": wc_label,
    }


def aggregate_snapshot_for_round(*, total_prompts: int, total_words: int) -> Dict[str, Any]:
    """Totals under target (T_NA / T_HU prompting)."""
    return {
        HEURISTIC_TOTAL_PROMPTS.id: total_prompts,
        HEURISTIC_TOTAL_WORDS_ROUND.id: total_words,
    }


def format_snapshot_for_ui(snapshot: Dict[str, Any]) -> List[Dict[str, str]]:
    """Label + formatted value for prompting, selection, or voting fixture snapshots."""
    out: List[Dict[str, str]] = []
    idx = snapshot.get(HEURISTIC_PROMPT_INDEX.id)
    if idx is None:
        idx = snapshot.get("number_of_prompts")
    if idx is not None:
        out.append(
            {
                "id": HEURISTIC_PROMPT_INDEX.id,
                "label": HEURISTIC_PROMPT_INDEX.label,
                "value": str(int(idx)),
            }
        )
    wc = snapshot.get(HEURISTIC_WORD_COUNT_PROMPT.id)
    if wc is None:
        wc = snapshot.get("total_word_count")
    if wc is not None:
        wc_lbl = snapshot.get("_word_count_label") or HEURISTIC_WORD_COUNT_PROMPT.label
        out.append(
            {
                "id": HEURISTIC_WORD_COUNT_PROMPT.id,
                "label": wc_lbl,
                "value": str(int(wc)),
            }
        )
    t = snapshot.get(HEURISTIC_TIME_IN_ROUND.id)
    if t is not None:
        out.append(
            {
                "id": HEURISTIC_TIME_IN_ROUND.id,
                "label": HEURISTIC_TIME_IN_ROUND.label,
                "value": format_seconds_mm_ss(int(t)),
            }
        )
    return out


def format_aggregate_for_ui(snapshot: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for h in (HEURISTIC_TOTAL_PROMPTS, HEURISTIC_TOTAL_WORDS_ROUND):
        v = snapshot.get(h.id)
        if v is None:
            continue
        text = str(int(v)) if isinstance(v, (int, float)) else str(v)
        out.append({"id": h.id, "label": h.label, "value": text})
    return out


def show_prompting_heuristics(condition: Optional[str]) -> bool:
    c = (condition or "").strip().upper()
    return c in ("T_NA", "T_HU")


def show_voting_heuristics(condition: Optional[str]) -> bool:
    c = (condition or "").strip().upper()
    return c in ("C_HU", "T_HU")
