# User story: Per-player randomized order for allocation voting rounds 1–9 (group-interleaved)

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [x] Voting screen *(point-allocation / “distribute 10 points” flow — rounds **1–9** only)*  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster *(if admin UI or payloads expose per-round fixture identity; otherwise minimal)*  
- [x] Other: **Server-side allocation voting state** (`allocation_voting`, `emit_allocation_round_for_player`, fixture loading from `voting_fixtures_config`)

**What to do** (one or two sentences in plain language):  
> Change how **allocation voting rounds 1–9** choose which **fixture JSON** (today `round_01.json` … `round_09.json`, grouped by target: **1–3** Oski, **4–6** Tree, **7–9** slug) each player sees and in what **order**. **Do not change voting round 10** (real player submissions — same `final_allocation_plan`, same behavior after round 9 completes).  
>  
> **Grouping (fixed by content):**  
> - **Group A** — fixture indices **1, 2, 3** (JSONs for Oski target)  
> - **Group B** — fixture indices **4, 5, 6** (Tree)  
> - **Group C** — fixture indices **7, 8, 9** (slug)  
>  
> **Per player, at the start of their allocation-voting session** (the moment the server begins that player’s round-sequence for rounds 1–9 — implementation detail: e.g. when entering `allocation_voting` or when first emitting round 1 for that voter):  
> 1. **Randomly draw one fixture index from each group** (one from A, one from B, one from C). The **order of those three draws** defines a **locked cyclic group order** for that player.  
>    - *Example:* Player A draws **5** (from B), **1** (from A), **9** (from C) → locked cycle **B → A → C** for “which group supplies the next screen.”  
>    - *Example:* Player B draws **8**, **4**, **3** → locked cycle **C → B → A**.  
> 2. Within each group, the player must eventually see **all three** JSONs from that group (each fixture index **exactly once** across rounds 1–9). **Shuffle or otherwise fix an order** within each group at session start (implementation detail) so the sequence of nine screens is fully determined and **stable** for that player for the rest of the game.  
> 3. **Build rounds 1–9** by repeatedly taking the **next unused** fixture from the current group in the locked cycle, then advancing to the next group in the cycle, until all nine fixtures are consumed.  
>  
> **Hard constraint:** A player must **never** see two fixtures from the **same group** on **consecutive** allocation rounds (1–9). The cyclic B→A→C (or whatever was locked) pattern must enforce this by construction; if an edge case (reconnect, admin skip, etc.) risks violating it, implementation must preserve the constraint.  
>  
> **Persistence:** The chosen order is **unique per player** (independent randomization), **persistent** for that player for the entire session (reconnect resumes the same sequence and same next fixture).  
>  
> **UI note:** The header may still show **“Voting Round k / 10”** where **k** is the **ordinal** step (1…9 then 10); only the **mapping** from step k to **which** `round_XX.json` / `fixture_set_key` changes. Round **10** is unchanged.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] For rounds **1–9** only, each non-admin player experiences a **permutation** of the nine fixture JSONs that respects: (a) **exactly one** use of each index 1–9 per player, (b) **no two consecutive** rounds drawn from the same **group** (A/B/C as defined above), (c) order **locked at session start** and **stable** across reconnect for that player.  
- [ ] **Round 10** is unchanged: same eligibility, same `final_allocation_plan` / real-image ballots, same submit and ranking behavior; no new randomization applied to round 10.  
- [ ] **Analytics / DB** (if applicable): stored rows still identify which vignette ran (e.g. `fixture_set_key` / target URL from the JSON actually shown); document or implement so analysis can distinguish **display order** from **fixture identity** if both matter.

**Do not change** (optional — what to leave alone):  
> Do **not** change fixture **file contents** under `voting_fixtures_config/` or `static/voting_fixtures/` unless a separate story requires it. Do **not** change **round 10** logic, `TOTAL_VOTING_ROUNDS`, `assign_final_ballots`, or onboarding / live **selection** (`voting` status) flows. Do not change the **three groups’ membership** (1–3, 4–6, 7–9) unless product explicitly redefines targets. Preserve existing **10 points** allocation rules and admin **Skip Voting / Advance** intent where it touches allocation (extend carefully so constraints still hold).

**Depends on** (optional — other stories or data that must exist first):  
> Existing **allocation voting** and **voting_fixtures_config** pack **HU** (nine JSON rounds + manifest). Reconnection and admin-advance behavior must be re-tested after this story.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (`start_allocation_voting_phase`, `emit_allocation_round_for_player`, player state for allocation sequence, reconnect replay of `allocation_last_payload`), possibly `voting_fixtures.py` / `voting_fixture_loader.py` (helpers to resolve index → fixture row only — **no** requirement to change manifest order on disk). `static/js/game.js` only if `voting_round_index` semantics or displayed labels must clarify fixture vs ordinal. `db.py` only if new columns are needed to persist per-player permutation (or persist entirely in memory if acceptable for the product).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
