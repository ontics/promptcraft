# User story: Allocation voting (rounds 1–9 only) — decoupled column shuffles for images vs text boxes

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
- [x] Other: **Backend** (allocation voting emit / ballot construction); **Frontend** (render payload as given — no client-side shuffle)

**What to do** (one or two sentences in plain language):  
> **Scope: hardcoded fixture allocation rounds only (the nine vignette rounds — i.e. every allocation step that is not round 10).** **Do not change round 10** (the final peer-image allocation round): its emit payload, layout, pairing of image and text, ballot construction, and client rendering must remain **exactly** as today. For **rounds 1–9** only, the UI today lays out **three images** and **three heuristic text boxes** in a **locked** pairing (each text box sits under “its” image). Change the presentation **for those rounds only** so that **each player**, **each of rounds 1–9**, gets **two independent random permutations**, both computed **only at server emit time**: (1) **Image column order** — assign the three images to **left, middle, and right** using one uniform random shuffle of three positions; (2) **Text box column order** — assign the three **whole** heuristic text boxes (one per logical fixture candidate) to **left, middle, and right** using a **second** uniform random shuffle, **statistically independent** of the image shuffle. The two shuffles are **fully decoupled** by design: a text box **must not** be required to appear under the image it “belongs” to in fixture data; misalignment is **intentional**. **Inside** each text box, **bullet / heuristic lines** keep their **existing fixed order**; only the **column position of the entire text box** changes. **Do not** encode either shuffle in **JSON fixture files**; fixtures stay canonical. The server **merges** permutations into a **display-ordered** payload for rounds **1–9**; the **client** renders that layout as received (**no** client-side shuffle). **Round 10 is out of scope: leave it unchanged.** Because image and text columns are **independent**, each **on-screen column** is no longer a single logical “candidate.” **Votes (point allocations) must still be interpretable in analysis:** for **each** of the three columns, the persisted vote / ballot data must tie the player’s points for that column to **both** (a) the **canonical image identity** (`fixture_image_id` or equivalent for the image shown in that column) **and** (b) the **canonical text-box identity** (which logical fixture candidate / heuristic snapshot that box came from—e.g. stable id aligned with that candidate row in fixture data). The client submits points **per column** as today; the server (or payload) must carry enough stable ids per column so **image id and text-box identity are both recorded with the vote** for rounds **1–9**.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] For **allocation rounds 1–9 only** (fixture / hardcoded path), the server draws **two** independent uniform permutations of **{1,2,3}** (or equivalent): one for **image** columns, one for **whole text box** columns; both are **per player, per round**, at **emit** time only. **Round 10** uses **no** new shuffles and behaves **identically** to today (paired columns, same payload shape and persistence as pre-story).  
- [ ] Fixture **JSON** and static assets on disk are **unchanged** in structure and ordering; no baked-in column permutations in repo config.  
- [ ] **Within** each rendered text box (rounds **1–9**), heuristic lines appear in the **same deterministic order** as today (no shuffle of lines inside the box). The **client** does not compute permutations for this story; it renders the **column layout** described by the server payload for scoped rounds.  
- [ ] **Persistence / analysis (rounds 1–9 only)**: For **each** of the three columns, the saved vote / allocation row (or joined ballot options) records **both** the **image canonical id** for that column **and** the **text-box canonical identity** (the logical candidate / snapshot source for the heuristic block in that column), **together with** the points the player assigned to that column—so shuffles never lose which image and which text box received that allocation. **Round 10** storage and analysis paths are **unchanged** (still one paired identity per column as today).

**Do not change** (optional — what to leave alone):  
> **Round 10 (final allocation voting): no changes** — emit, UI layout, heuristics pairing, `final_allocation_plan`, ballot rows, `submit_point_allocation` handling for the final round, and any client code used **only** for round **10** must stay as today. Do not change the **ordinal schedule** for rounds **1–9** (e.g. per-player **`allocation_fixture_order`**, A/B/C group cycling, fixture choice within each group). Do not change **total points = 10**, validation, or **which** three images / three snapshots belong to a fixture round — only **column layout for rounds 1–9**. Do not shuffle lines inside heuristic boxes. Prefer **`random`** (or an existing project RNG) with **no** new external dependencies unless the team agrees.

**Depends on** (optional — other stories or data that must exist first):  
> Assumes current **allocation voting** flow (fixture JSON pack, `emit_allocation_round_for_player`, `allocation_vote_started`, `submit_point_allocation`, ballot / `point_allocations` behavior) is in place.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py`: **`emit_allocation_round_for_player`** (or equivalent) **only on the hardcoded / non-final branch** (`round_index < TOTAL_VOTING_ROUNDS`); submit / ballot paths for **fixtures only** as needed for canonical mapping. **Explicitly avoid** altering the **`is_final`** / round-**10** branch. `static/js/game.js` and `templates/index.html` only as needed to render decoupled columns **for rounds 1–9** (e.g. branch on payload shape or round index) without touching round **10** layout. `voting_fixtures_config/` — **read-only**. Optional: `db.py` / schema notes for fixture rounds only.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
