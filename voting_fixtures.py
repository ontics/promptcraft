"""
Nine hard-coded voting rounds (same order every game). Replace image URLs and heuristic
triples with your pilot assets. fixture_image_id is stable for analytics.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Uses existing static targets as placeholders; swap for real fixture images.
_BASE = "/static/images"

FIXTURE_ROUNDS: List[Dict[str, Any]] = [
    {
        "fixture_set_key": "pilot_fix_01",
        "target_image_url": f"{_BASE}/target1.jpg",
        "candidates": [
            {
                "fixture_image_id": "fx01_a",
                "image_url": f"{_BASE}/target1.jpg",
                "heuristics": {"number_of_prompts": 4, "total_word_count": 62, "prompt_complexity": 0.41},
            },
            {
                "fixture_image_id": "fx01_b",
                "image_url": f"{_BASE}/target2.jpg",
                "heuristics": {"number_of_prompts": 7, "total_word_count": 118, "prompt_complexity": 0.58},
            },
            {
                "fixture_image_id": "fx01_c",
                "image_url": f"{_BASE}/target3.jpg",
                "heuristics": {"number_of_prompts": 11, "total_word_count": 156, "prompt_complexity": 0.72},
            },
        ],
    },
    {
        "fixture_set_key": "pilot_fix_02",
        "target_image_url": f"{_BASE}/target2.jpg",
        "candidates": [
            {"fixture_image_id": "fx02_a", "image_url": f"{_BASE}/target2.jpg", "heuristics": {"number_of_prompts": 3, "total_word_count": 44, "prompt_complexity": 0.33}},
            {"fixture_image_id": "fx02_b", "image_url": f"{_BASE}/target3.jpg", "heuristics": {"number_of_prompts": 6, "total_word_count": 95, "prompt_complexity": 0.51}},
            {"fixture_image_id": "fx02_c", "image_url": f"{_BASE}/target1.jpg", "heuristics": {"number_of_prompts": 9, "total_word_count": 132, "prompt_complexity": 0.67}},
        ],
    },
    {
        "fixture_set_key": "pilot_fix_03",
        "target_image_url": f"{_BASE}/target3.jpg",
        "candidates": [
            {"fixture_image_id": "fx03_a", "image_url": f"{_BASE}/target3.jpg", "heuristics": {"number_of_prompts": 5, "total_word_count": 71, "prompt_complexity": 0.45}},
            {"fixture_image_id": "fx03_b", "image_url": f"{_BASE}/target1.jpg", "heuristics": {"number_of_prompts": 8, "total_word_count": 104, "prompt_complexity": 0.55}},
            {"fixture_image_id": "fx03_c", "image_url": f"{_BASE}/target2.jpg", "heuristics": {"number_of_prompts": 12, "total_word_count": 168, "prompt_complexity": 0.78}},
        ],
    },
    {
        "fixture_set_key": "pilot_fix_04",
        "target_image_url": f"{_BASE}/target1.jpg",
        "candidates": [
            {"fixture_image_id": "fx04_a", "image_url": f"{_BASE}/target1.jpg", "heuristics": {"number_of_prompts": 2, "total_word_count": 28, "prompt_complexity": 0.22}},
            {"fixture_image_id": "fx04_b", "image_url": f"{_BASE}/target2.jpg", "heuristics": {"number_of_prompts": 5, "total_word_count": 81, "prompt_complexity": 0.49}},
            {"fixture_image_id": "fx04_c", "image_url": f"{_BASE}/target3.jpg", "heuristics": {"number_of_prompts": 10, "total_word_count": 141, "prompt_complexity": 0.69}},
        ],
    },
    {
        "fixture_set_key": "pilot_fix_05",
        "target_image_url": f"{_BASE}/target2.jpg",
        "candidates": [
            {"fixture_image_id": "fx05_a", "image_url": f"{_BASE}/target2.jpg", "heuristics": {"number_of_prompts": 6, "total_word_count": 88, "prompt_complexity": 0.52}},
            {"fixture_image_id": "fx05_b", "image_url": f"{_BASE}/target3.jpg", "heuristics": {"number_of_prompts": 8, "total_word_count": 121, "prompt_complexity": 0.61}},
            {"fixture_image_id": "fx05_c", "image_url": f"{_BASE}/target1.jpg", "heuristics": {"number_of_prompts": 10, "total_word_count": 149, "prompt_complexity": 0.74}},
        ],
    },
    {
        "fixture_set_key": "pilot_fix_06",
        "target_image_url": f"{_BASE}/target3.jpg",
        "candidates": [
            {"fixture_image_id": "fx06_a", "image_url": f"{_BASE}/target3.jpg", "heuristics": {"number_of_prompts": 4, "total_word_count": 55, "prompt_complexity": 0.38}},
            {"fixture_image_id": "fx06_b", "image_url": f"{_BASE}/target1.jpg", "heuristics": {"number_of_prompts": 7, "total_word_count": 99, "prompt_complexity": 0.56}},
            {"fixture_image_id": "fx06_c", "image_url": f"{_BASE}/target2.jpg", "heuristics": {"number_of_prompts": 11, "total_word_count": 159, "prompt_complexity": 0.71}},
        ],
    },
    {
        "fixture_set_key": "pilot_fix_07",
        "target_image_url": f"{_BASE}/target1.jpg",
        "candidates": [
            {"fixture_image_id": "fx07_a", "image_url": f"{_BASE}/target1.jpg", "heuristics": {"number_of_prompts": 3, "total_word_count": 39, "prompt_complexity": 0.29}},
            {"fixture_image_id": "fx07_b", "image_url": f"{_BASE}/target3.jpg", "heuristics": {"number_of_prompts": 6, "total_word_count": 92, "prompt_complexity": 0.54}},
            {"fixture_image_id": "fx07_c", "image_url": f"{_BASE}/target2.jpg", "heuristics": {"number_of_prompts": 9, "total_word_count": 127, "prompt_complexity": 0.64}},
        ],
    },
    {
        "fixture_set_key": "pilot_fix_08",
        "target_image_url": f"{_BASE}/target2.jpg",
        "candidates": [
            {"fixture_image_id": "fx08_a", "image_url": f"{_BASE}/target2.jpg", "heuristics": {"number_of_prompts": 5, "total_word_count": 68, "prompt_complexity": 0.43}},
            {"fixture_image_id": "fx08_b", "image_url": f"{_BASE}/target1.jpg", "heuristics": {"number_of_prompts": 8, "total_word_count": 111, "prompt_complexity": 0.59}},
            {"fixture_image_id": "fx08_c", "image_url": f"{_BASE}/target3.jpg", "heuristics": {"number_of_prompts": 12, "total_word_count": 174, "prompt_complexity": 0.81}},
        ],
    },
    {
        "fixture_set_key": "pilot_fix_09",
        "target_image_url": f"{_BASE}/target3.jpg",
        "candidates": [
            {"fixture_image_id": "fx09_a", "image_url": f"{_BASE}/target3.jpg", "heuristics": {"number_of_prompts": 4, "total_word_count": 51, "prompt_complexity": 0.36}},
            {"fixture_image_id": "fx09_b", "image_url": f"{_BASE}/target2.jpg", "heuristics": {"number_of_prompts": 7, "total_word_count": 97, "prompt_complexity": 0.53}},
            {"fixture_image_id": "fx09_c", "image_url": f"{_BASE}/target1.jpg", "heuristics": {"number_of_prompts": 10, "total_word_count": 138, "prompt_complexity": 0.68}},
        ],
    },
]

NUM_HARDCODED_VOTING_ROUNDS = len(FIXTURE_ROUNDS)
TOTAL_VOTING_ROUNDS = NUM_HARDCODED_VOTING_ROUNDS + 1  # + final
