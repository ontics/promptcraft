"""
Nine hard-coded voting vignettes from `voting_fixtures_config/` + one final round of real player images = 10 voting rounds total.

Edit JSON and static images under `voting_fixtures_config/HU/` and `static/voting_fixtures/HU/` (see README there).
`time_in_round_seconds` in JSON is vignette metadata (seconds into a 5-minute round), not a live clock.
"""
from __future__ import annotations

from typing import Any, Dict, List

from voting_fixture_loader import load_fixture_rounds

FIXTURE_ROUNDS: List[Dict[str, Any]] = load_fixture_rounds("HU")

NUM_HARDCODED_VOTING_ROUNDS = len(FIXTURE_ROUNDS)
TOTAL_VOTING_ROUNDS = NUM_HARDCODED_VOTING_ROUNDS + 1  # + final (real submissions)
