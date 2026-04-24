"""
Load hard-coded allocation-voting vignettes (rounds 1–9) from JSON on disk.

Colleagues edit `voting_fixtures_config/<PACK>/` and `static/voting_fixtures/<PACK>/`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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


_round10_pool_cache: Optional[List[Dict[str, Any]]] = None
_round10_pool_cache_key: Optional[Tuple[float, float]] = None  # (manifest_mtime, pool_mtime)


def load_round10_synthetic_pool_candidates(pack: str = "HU") -> List[Dict[str, Any]]:
    """
    Load the Vote 10 synthetic filler pool (exactly five candidates in JSON; at least three required to enable fillers).

    Same per-candidate shape as entries inside get_fixture_rounds()[i]['candidates']:
    fixture_image_id, image_url, heuristics.
    """
    global _round10_pool_cache, _round10_pool_cache_key
    root = _pack_dir(pack)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return []
    pool_rel = "round10_synthetic_pool.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    pool_rel = manifest.get("round10_synthetic_pool") or pool_rel
    pool_path = root / pool_rel
    if not pool_path.is_file():
        print(f"[VOTING] Round-10 synthetic pool file missing: {pool_path}")
        return []
    try:
        man_m = manifest_path.stat().st_mtime
        pool_m = pool_path.stat().st_mtime
    except OSError:
        man_m = pool_m = 0.0
    key = (man_m, pool_m)
    if _round10_pool_cache is not None and _round10_pool_cache_key == key:
        return _round10_pool_cache

    with open(pool_path, encoding="utf-8") as pf:
        raw = json.load(pf)
    mount = manifest.get("static_mount") or f"/static/voting_fixtures/{pack}/"
    cands = raw.get("candidates") or []
    if len(cands) < 3:
        print(f"[VOTING] Round-10 synthetic pool needs at least 3 candidates, got {len(cands)}")
        _round10_pool_cache = []
        _round10_pool_cache_key = key
        return []
    if len(cands) != 5:
        print(f"[VOTING] Round-10 synthetic pool: expected 5 candidates, got {len(cands)} (using first {min(len(cands), 5)})")
    out: List[Dict[str, Any]] = []
    for c in cands[:5]:
        fid = c.get("fixture_image_id")
        if not fid:
            continue
        out.append(
            {
                "fixture_image_id": fid,
                "image_url": _join_url(mount, c.get("image") or ""),
                "heuristics": dict(c.get("heuristics") or {}),
            }
        )
    if len(out) < 3:
        print("[VOTING] Round-10 synthetic pool: fewer than 3 valid candidates after parsing")
        _round10_pool_cache = []
        _round10_pool_cache_key = key
        return []
    _round10_pool_cache = out
    _round10_pool_cache_key = key
    return out


def invalidate_round10_synthetic_pool_cache() -> None:
    """Clear cached pool (e.g. after tests hot-reload)."""
    global _round10_pool_cache, _round10_pool_cache_key
    _round10_pool_cache = None
    _round10_pool_cache_key = None
