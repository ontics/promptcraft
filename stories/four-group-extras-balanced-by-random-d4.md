# User story: Extra players after four-way split — random group per “remainder” (no control skew)

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster  
- [x] Other: **Backend** (`split_into_player_groups` / `assign_teams`)

**What to do** (one or two sentences in plain language):  
> Today, when the number of players is **not** divisible by four, the “extra” seats are filled by giving **larger slices to the first groups in fixed label order** (`C_NA`, then `C_HU`, then `T_NA`, then `T_HU`). That **systematically biases** overflow toward **control** (`C_*`) before treatment (`T_*`). Change the algorithm so that, after whatever **fair base** split you use (e.g. everyone gets **⌊n/4⌋** first, or an equivalent), **each remaining player** is assigned to **exactly one** of the four groups using an **independent uniform random choice** over the four labels—**as if rolling a four-sided die once per extra player**—so overflow is **not** preferentially routed to control.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] For connected player counts where **n mod 4 ≠ 0**, **no** assignment rule relies on **fixed label order** to absorb extras in a way that **predictably favors** `C_NA` / `C_HU` over `T_NA` / `T_HU`.  
- [ ] For each “extra” beyond the equal floor, the implementation uses a **uniform random pick** among **`C_NA`**, **`C_HU`**, **`T_NA`**, **`T_HU`** (documented and testable—e.g. repeated runs show extras land in all four buckets, not clustered in control by construction).  
- [ ] **Admin “assign groups”** still only runs when allowed today (same entry points, same `PLAYER_GROUPS` strings); **character / treatment mapping** from `condition` is **unchanged** unless a separate story says otherwise.

**Do not change** (optional — what to leave alone):  
> Do not rename the four groups or change Bud/Spud rules. Do not alter onboarding, selection, voting, or allocation flows. Keep **`random.shuffle`** of the player list before slicing **if** you still use an ordered pass for the base portion—only replace the **remainder / tie-break** policy. Prefer **`random`** from the Python standard library (or an existing project RNG helper) with **no** new external dependencies unless the team agrees.

**Depends on** (optional — other stories or data that must exist first):  
> Builds on **`four-group-assignment-c-na-c-hu-t-na-t-hu.md`** (four labels + admin assign). None required beyond current code paths.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (`split_into_player_groups`, `handle_assign_teams`, any unit-style comments or logging that describe group sizes). Optionally add or extend a **small deterministic test** (if the repo gains tests) or a **documented manual playtest** checklist for `n = 4k+1 … +3`.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
