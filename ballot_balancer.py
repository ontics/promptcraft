"""
Greedy balancing: assign each voter 3 distinct owner player_ids for the final round so
appearance counts stay as even as possible. Documented imperfection when N or counts don't divide evenly.
"""
from __future__ import annotations

import random
from typing import Dict, List


def assign_final_ballots(voter_ids: List[str], owner_ids: List[str], seed: int = 0) -> Dict[str, List[str]]:
    """
    Return mapping voter_id -> [owner_a, owner_b, owner_c] (distinct owners when possible).
    Never assigns a voter their own image (eligible pool excludes self).

    Greedy: among eligible owners for that voter, pick three with lowest global appearance count;
    tie-break with random shuffle derived from `seed`.
    """
    voters = list(voter_ids)
    owners = [o for o in owner_ids if o]
    rng = random.Random(seed)
    rng.shuffle(voters)
    if len(owners) < 4:
        # Need self + 3 others so each voter has 3 distinct others
        raise ValueError("Need at least 4 players with submissions for anonymous final voting.")

    appearances = {o: 0 for o in owners}
    out: Dict[str, List[str]] = {}

    def pick_three_for(v: str) -> List[str]:
        eligible = [o for o in owners if o != v]
        if len(eligible) < 3:
            raise ValueError("Not enough peers to build a ballot without self.")
        ranked = sorted(eligible, key=lambda o: (appearances[o], rng.random()))
        triple: List[str] = []
        for o in ranked:
            if o not in triple:
                triple.append(o)
            if len(triple) == 3:
                break
        if len(triple) < 3:
            pool = list(eligible)
            rng.shuffle(pool)
            for o in pool:
                if o not in triple:
                    triple.append(o)
                if len(triple) == 3:
                    break
        for o in triple:
            appearances[o] += 1
        return triple

    for v in voters:
        out[v] = pick_three_for(v)

    return out
