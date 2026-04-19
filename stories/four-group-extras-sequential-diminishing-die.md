# User story: Extra players after four-way split — sequential “diminishing die” (no repeat group per remainder slot)

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
- [x] Other: **Backend** (`split_into_player_groups` / `handle_assign_teams`)

**What to do** (one or two sentences in plain language):  
> Today (after **`four-group-extras-balanced-by-random-d4.md`**), each player beyond the equal floor is assigned with an **independent** uniform random choice over **all four** groups—like rolling a **four-sided die once per extra**, so two or three extras **can** land in the **same** group. Change the remainder step so it behaves like a **shrinking die**: the **first** extra is chosen uniformly among **four** eligible groups; after that group receives one remainder slot, the **next** extra is chosen uniformly among the **three** groups that have **not** yet received a remainder assignment in this split; the **next** (if any) among **two**; and so on. Equivalently, the set of groups that receive a remainder slot is **size r = n mod 4** with **no group receiving more than one remainder slot** from this pass, and every valid choice of **which r distinct groups** (and in which order, if order matters for pairing to players) follows the implied uniform distribution.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] For **n mod 4 = 2** or **3**, after admin assign groups, **no** two remainder players are placed in the **same** group by this remainder pass (each remainder slot targets a **different** label among `PLAYER_GROUPS`).  
- [ ] The sequence of random choices is **documented in code** (e.g. “uniform among remaining labels not yet chosen for a remainder”) and is **testable**—e.g. for **n = 6**, over many runs, observed group sizes are only **(2,2,1,1)** permutations where **exactly two** groups have size **+1** over the floor, never **(3,1,1,1)** from stacking two extras in one group.  
- [ ] **n mod 4 = 1** behavior remains a **single** uniform pick among four groups (same effective outcome as today). **Admin “assign groups”** entry rules, **`PLAYER_GROUPS`** strings, **`random.shuffle`** before split, equal **floor** split, and **character / treatment mapping** are **unchanged** unless a separate story says otherwise.

**Do not change** (optional — what to leave alone):  
> Do not rename the four groups or change Bud/Spud rules. Do not alter onboarding, selection, voting, or allocation flows outside this split helper. Prefer **`random`** from the Python standard library (or an existing project RNG helper) with **no** new external dependencies unless the team agrees.

**Depends on** (optional — other stories or data that must exist first):  
> Assumes **`four-group-extras-balanced-by-random-d4.md`** (or equivalent: no fixed-label-order remainder bias) is already merged. If this story ships alone, implement the **diminishing-die** remainder policy directly and treat the prior d4-per-extra story as superseded for remainder behavior only.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (`split_into_player_groups`, comments / logging in `handle_assign_teams`). Manual playtest: **n = 5, 6, 7** (and **4, 8** as regression) after assign groups.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
