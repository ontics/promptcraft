# User story: Round 10 allocation — synthetic image pool when peers or R3 selections are missing

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [x] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [ ] Admin / gamemaster  
- [x] Other: **Allocation voting (Vote 10 / final round)** — server + fixture assets

**What to do** (one or two sentences in plain language):  
> Today, **Vote 10** (final allocation round) can **fail with an error** when there are **fewer than four eligible players** in the peer pool, or when **a player in a larger session has no Round 3 image selection**, because the ballot cannot always be built from three real peer submissions. Replace that failure mode with a **fallback pool of exactly five synthetic vignettes**: each entry is an **image plus heuristics** (same conceptual shape as a row in existing **round JSON** files). When the server needs one or more **stand-in slots** to complete a Vote 10 ballot, it should **randomly sample** (without replacement where possible) from this pool so every voter still receives a valid **three-option** allocation UI when the product rules require it. Add a **new JSON file** in the voting-fixture config tree whose structure **mirrors the round files** (e.g. `fixture_set_key`, `target_profile` / `target_image` as needed for consistency with the loader, and a **`candidates` array** of objects with `fixture_image_id`, **`image`** path relative to a dedicated upload folder, and **`heuristics`** as an object the author can fill or leave sparse). Add a **companion folder** under static assets for the **five image files** the author uploads. **Do not** rely on showing an error to the player for these two scenarios once the pool is configured; if the pool is empty or invalid at runtime, the implementation may still error or block—define that edge case explicitly in implementation notes.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] **Repo layout:** A **JSON file** exists (e.g. under `voting_fixtures_config/` for the HU pack or a clearly named sibling) listing **five** synthetic candidates in the **same general schema as** `voting_fixtures_config/HU/rounds/round_*.json` (per-candidate `fixture_image_id`, `image`, `heuristics` keys; author can populate heuristics fields to match real rounds or leave placeholders documented in a short comment block or README next to the file—**no** requirement to duplicate every optional key from every round if the loader tolerates minimal objects).  
- [ ] **Static files:** A **folder** exists for authors to drop **five** images (paths in JSON point into that folder via the pack’s `static_mount` convention or an equivalent documented pattern).  
- [ ] **Runtime:** When Vote 10 would previously fail because **eligible real peers &lt; 4** or because **one or more voters lack an R3 selection** in an otherwise large game, the server **fills missing ballot slots** by **random draws** from the five-pool (document seeding / no-replacement rules so QA can reproduce). Players who only need “filler” slots get synthetic options; **real peer slots** stay real when available. **Rounds 1–9** allocation behavior stays unchanged unless a shared loader change is unavoidable.  
- [ ] **UX:** Players no longer see the current **“Could not build the final voting ballot (missing peer targets)…”** (or equivalent) for the covered scenarios when the pool is valid; normal allocation submit and incentive flows still apply to **real** submissions, with **clear rules** documented for whether synthetic targets earn incentive points (implementation choice—spell out in PR).

**Do not change** (optional — what to leave alone):  
> Do not redesign **rounds 1–9** fixture JSON on disk except to share types/helpers if needed. Do not change **Socket.IO event names** for allocation. Preserve **admin skip / timeout** behavior except where it must account for synthetic ballots. Do not remove **`assign_final_ballots`** circular-fairness logic for the **real** subset; extend, don’t replace, unless the story’s QA plan requires a single unified slot builder.

**Depends on** (optional — other stories or data that must exist first):  
> None, but implementers should read **`ballot_balancer.py`** and **`emit_allocation_round_for_player`** (Vote 10 branch) to align filler injection with existing `options` / `slot_owners` / DB ballot creation.

**Files likely involved** (optional — helps the AI and you focus):  
> New: `voting_fixtures_config/HU/` (or chosen pack) **synthetic pool JSON** + **`static/voting_fixtures/HU/`** (or parallel) **image folder**; `voting_fixture_loader.py` / `voting_fixtures.py` if the pool must be loaded with mtime reload like other rounds; **`app.py`** (`start_allocation_voting_phase`, **`emit_allocation_round_for_player`** final-round branch, **`assign_final_ballots`** call sites or post-process plan); **`ballot_balancer.py`** only if the assignment model changes; **`static/js/game.js`** only if the client assumes exactly three “real” peers (e.g. labels, analytics); **`db.py`** if ballot rows must distinguish synthetic `owner_player_id` from real sessions.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
