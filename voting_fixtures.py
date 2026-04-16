"""
Nine hard-coded voting vignettes from `voting_fixtures_config/` + one final round of real player images = 10 voting rounds total.

Edit JSON and static images under `voting_fixtures_config/HU/` and `static/voting_fixtures/HU/` (see README there).
`time_in_round_seconds` in JSON is vignette metadata (seconds into a 5-minute round), not a live clock.

Fixture JSON is reloaded when any HU manifest or round file changes on disk (mtime), so config edits apply without
restarting the server (still restart after code changes).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from voting_fixture_loader import load_fixture_rounds

_PACK = "HU"

_fixture_rounds_cache: List[Dict[str, Any]] | None = None
_fixture_mtime_key: float = -1.0


def _pack_content_mtime(pack: str) -> float:
    root = Path(__file__).resolve().parent / "voting_fixtures_config" / pack
    m = 0.0
    paths = [root / "manifest.json"]
    rounds_dir = root / "rounds"
    if rounds_dir.is_dir():
        paths.extend(sorted(rounds_dir.glob("round_*.json")))
    for path in paths:
        try:
            m = max(m, path.stat().st_mtime)
        except OSError:
            continue
    return m


def get_fixture_rounds() -> List[Dict[str, Any]]:
    """Return HU fixture rounds, reloading from disk when JSON or manifest changes."""
    global _fixture_rounds_cache, _fixture_mtime_key
    key = _pack_content_mtime(_PACK)
    if _fixture_rounds_cache is None or key != _fixture_mtime_key:
        _fixture_rounds_cache = load_fixture_rounds(_PACK)
        _fixture_mtime_key = key
    return _fixture_rounds_cache


NUM_HARDCODED_VOTING_ROUNDS = len(load_fixture_rounds(_PACK))
TOTAL_VOTING_ROUNDS = NUM_HARDCODED_VOTING_ROUNDS + 1  # + final (real submissions)
