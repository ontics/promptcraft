# User story: Four-way random group assignment (C_NA, C_HU, T_NA, T_HU)

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [x] Admin / gamemaster  
- [x] Other: **Backend / database (Supabase `players.team`, in-memory player state)**

**What to do** (one or two sentences in plain language):  
> Replace the two-team model (Green and Orange) with **four** randomly assigned groups, labeled **`C_NA`**, **`C_HU`**, **`T_NA`**, and **`T_HU`**. Those labels must appear in the database and in the Gamemaster/admin UI (including manual team changes). **Assign players randomly to any of the four groups** (e.g. shuffle the player list, then split into four segments mapped to those labels). When the count does not divide evenly by four, **spread the extras across groups** by segment order—**no** fixed rule that sends all remainder players to **`T_HU`**.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Admin “assign groups” (or equivalent) **randomly** places connected non-admin players into four buckets **`C_NA`**, **`C_HU`**, **`T_NA`**, **`T_HU`** (not Green/Orange); sizes are as even as the split allows (at most one extra in some groups when `n` is not divisible by four), without reserving all overflow for **`T_HU`**.  
- [ ] Supabase and in-memory player records store **`team`** (or the chosen field) using **only** these four string values (no `Green` / `Orange` for new assignments); admin lists and dropdowns show these labels.  
- [ ] **Start game** still requires everyone to have a group assigned first; reconnection / DB restore paths that read `team` work with the new labels.  
- [ ] Any gameplay that previously depended on **Green vs Orange** (e.g. Bud/Spud or treatment in later rounds) is updated to use a **clear, documented mapping** from the four groups to that behavior (or explicitly stubbed with a follow-up story if out of scope).

**Do not change** (optional — what to leave alone):  
> Only the area(s) listed above. Do not change unrelated game flow (lobby → play → voting → results). Preserve smoke-test behavior: create game, multiple players, full round completes. If another open story only references Green/Orange in the lobby UI, reconcile naming when merging (see **Depends on**).

**Depends on** (optional — other stories or data that must exist first):  
> **Supabase**: Confirm the `players.team` column (or equivalent) accepts these four string values; add migration or enum update if the DB currently constrains values to Green/Orange. If **`remove-team-assignments-from-lobby.md`** is in flight, coordinate so lobby still hides group badges while admin shows **`C_NA`** / **`C_HU`** / **`T_NA`** / **`T_HU`**.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (`assign_teams`, `set_player_team`, `start_game`, `get_character` / `get_character_for_round`, join/reconnect paths, any validation that checks `Green`/`Orange`); `db.py` (`create_player`, lookups); `static/js/game.js` (admin player list, team dropdown options, emits); `templates/index.html` if any team labels are hardcoded; `stress_test.py` if it assumes two teams. Run **`GUIDELINES.md`** smoke test and **`PLAYTEST_2_TESTING_CHECKLIST.md`** scenarios if reconnection or admin flows change.

---

*For the AI: When implementing this story, change only the group-assignment model, labels, admin/DB surfaces, and dependent character/treatment logic. Follow `GUIDELINES.md` (feature branch from `v2`, minimal unrelated edits). After implementing, ask the developer to verify the “Done when” criteria and run a multi-player assign + start + one full round.*
