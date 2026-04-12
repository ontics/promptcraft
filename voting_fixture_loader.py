"""
Load hard-coded allocation-voting vignettes (rounds 1–9) from JSON on disk.

Colleagues edit `voting_fixtures_config/<PACK>/` and `static/voting_fixtures/<PACK>/`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _pack_dir(pack: str) -> Path:
    return Path(__file__).resolve().parent / "voting_fixtures_config" / pack


def _join_url(mount: str, rel_path: str) -> str:
    """Resolve paths under `static_mount`, or use absolute `/static/...` URLs as-is."""
    rel = (rel_path or "").strip()
    if rel.startswith("/"):
        return rel
    base = (mount or "").rstrip("/")
    rel = rel.lstrip("/")
    return f"{base}/{rel}" if rel else base


def load_fixture_rounds(pack: str = "HU") -> List[Dict[str, Any]]:
    """
    Returns the same shape as the legacy FIXTURE_ROUNDS list:
    fixture_set_key, target_image_url, candidates[{fixture_image_id, image_url, heuristics}].
    """
    root = _pack_dir(pack)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Voting fixture manifest missing: {manifest_path}")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    mount = manifest.get("static_mount") or f"/static/voting_fixtures/{pack}/"
    round_files = manifest.get("round_files") or []
    if len(round_files) != 9:
        raise ValueError(f"Expected 9 round_files in manifest, got {len(round_files)}")

    out: List[Dict[str, Any]] = []
    for rel in round_files:
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(f"Round file missing: {path}")
        with open(path, encoding="utf-8") as rf:
            raw = json.load(rf)
        cands = raw.get("candidates") or []
        if len(cands) != 3:
            raise ValueError(f"{path}: expected 3 candidates, got {len(cands)}")
        row: Dict[str, Any] = {
            "fixture_set_key": raw["fixture_set_key"],
            "target_image_url": _join_url(mount, raw["target_image"]),
            "target_profile": raw.get("target_profile"),
            "candidates": [],
        }
        for c in cands:
            row["candidates"].append(
                {
                    "fixture_image_id": c["fixture_image_id"],
                    "image_url": _join_url(mount, c["image"]),
                    "heuristics": dict(c.get("heuristics") or {}),
                }
            )
        out.append(row)
    return out
