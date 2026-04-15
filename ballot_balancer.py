"""
Round-10 assignment:
- Shuffle players once.
- Assign each voter the next k players in a circular shift.

This guarantees:
- no self-views
- no duplicate submitters per voter
- equal exposure for every submitter
"""
from __future__ import annotations

import random
from typing import Dict, List


def assign_final_ballots(voter_ids: List[str], owner_ids: List[str], seed: int = 0) -> Dict[str, List[str]]:
    """
    Return mapping voter_id -> [owner_a, owner_b, owner_c].

    Uses a randomized circular assignment:
    voter i receives owners at (i+1), (i+2), ... (i+k) modulo N
    over one shuffled player list.
    """
    voters = [v for v in voter_ids if v]
    owners = [o for o in owner_ids if o]
    rng = random.Random(seed)
    if len(owners) < 2:
        raise ValueError("Need at least 2 players with round-3 selections for final voting.")

    # Use common eligible set (intersection), preserving owner identity.
    player_ids = [p for p in owners if p in set(voters)]
    if len(player_ids) < 2:
        raise ValueError("Need at least 2 overlapping voters/owners for final voting.")

    rng.shuffle(player_ids)
    n = len(player_ids)
    k = 3 if n >= 4 else max(1, n - 1)

    out: Dict[str, List[str]] = {}
    for i, voter in enumerate(player_ids):
        out[voter] = [player_ids[(i + shift) % n] for shift in range(1, k + 1)]

    return out
