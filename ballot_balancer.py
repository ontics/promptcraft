"""
Greedy balancing: assign each voter 3 owner player_ids for the final round so
appearance counts stay as even as possible. With fewer than 4 players in the
session, the same peer may appear multiple times on a ballot (required so each
voter still allocates 10 points across 3 slots).
"""
from __future__ import annotations

import random
from typing import Dict, List


def assign_final_ballots(voter_ids: List[str], owner_ids: List[str], seed: int = 0) -> Dict[str, List[str]]:
    """
    Return mapping voter_id -> [owner_a, owner_b, owner_c].

    Never assigns a voter their own image when other players exist. If there are
    not enough distinct peers to fill 3 slots, repeats peers (lowest appearance
    count first) so the UI always has 3 targets.
    """
    voters = list(voter_ids)
    owners = [o for o in owner_ids if o]
    rng = random.Random(seed)
    rng.shuffle(voters)
    if len(owners) < 2:
        raise ValueError("Need at least 2 players with round-3 selections for final voting.")

    appearances = {o: 0 for o in owners}
    out: Dict[str, List[str]] = {}

    def pick_three_for(v: str) -> List[str]:
        eligible = [o for o in owners if o != v]
        if not eligible:
            # Only one player in owners list (shouldn't happen if len(owners) >= 2)
            pool = list(owners)
            rng.shuffle(pool)
            return [pool[0], pool[0], pool[0]]

        triple: List[str] = []
        while len(triple) < 3:
            ranked = sorted(eligible, key=lambda o: (appearances[o], rng.random()))
            o = ranked[0]
            triple.append(o)
            appearances[o] += 1
        return triple

    for v in voters:
        out[v] = pick_three_for(v)

    return out
