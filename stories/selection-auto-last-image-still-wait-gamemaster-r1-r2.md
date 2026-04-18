# User story: No player choice (auto last image) must still use R1/R2 gamemaster wait screen

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [x] Transition screen  
- [x] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> Today, when a player **never confirms** a selection and the server **auto-selects** their **last remaining image** (so selection is "complete" without an explicit player tap), the game can **skip** the same **waiting** experience used when everyone has chosen normally: the next **prompting** round may **start automatically** instead. For **rounds 1 and 2 only**, that path is wrong. **Any** way selection ends - **including** time-up with auto last-image - must still land players on the **same** interstitial as other completions: the screen that tells them they are **waiting for the game master to move the scene along** (exact wording may match existing copy for this screen). The **next** prompting round must **not** begin until the gamemaster advances, consistent with the R1/R2 admin gate.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] In **round 1 or 2**, if one or more players **never select** and the server **fills in** their final image when time runs out (or equivalent auto-select), players still see the **gamemaster wait** transition (same message intent as **"waiting for the game master to move the scene along"**), not an immediate jump into the next prompting round.  
- [ ] **Admin** remains in the **waiting / next round soon** state until they use **Next round** (or the same control wired for that gate) - **no** automatic advance triggered only because the last image was auto-picked.  
- [ ] Paths where players **do** confirm selections continue to behave as after `selection-wait-next-round-admin-gate-r1-r2.md` (no regression). **Round 3** selection completion is **unchanged**.

**Do not change** (optional — what to leave alone):  
> Do not broaden this story to **round 3** or to voting / allocation. Do not change **90s** selection timing or **which** image is auto-chosen when idle - only **what happens after** that completion path. Preserve reconnect and admin flows outside this bug.

**Depends on** (optional — other stories or data that must exist first):  
> Assumes the R1/R2 **admin gate** and wait transition from **`selection-wait-next-round-admin-gate-r1-r2.md`** (or equivalent) already exists; this story is a **bugfix / parity** so the **auto last-image** completion uses the **same** gate and UI as "all confirmed" or other end-of-selection paths.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (selection completion, `check_all_selected`, timer / auto-select branches, any emit that advances prompting without going through `awaiting_next_prompting` / admin advance). `static/js/game.js` (transition handling if a different event or payload is used for auto-complete vs confirm). `templates/index.html` only if the wait copy lives there and must stay consistent.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
