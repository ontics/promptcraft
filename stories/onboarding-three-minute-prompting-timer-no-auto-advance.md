# User story: Onboarding practice prompting — real 3-minute timer (no auto phase change)

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [x] Onboarding  
- [x] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> During **onboarding practice prompting** (the phase where non-admin players use the main game prompting UI with the practice target, before practice point distribution), replace the **static “5:00”** timer with a **real 3-minute (180s) countdown** that works like scored rounds: the server defines a **start time and end time** (or start + duration), clients show a **live countdown** on the player prompting UI and on the **Gamemaster** clock, and time stays **synchronized** across reconnects the same way as `game_started` / `round_end_time`. When the countdown reaches **zero**, the timer should simply **stop at 0:00** (optionally with the same warning styling used in live rounds if that already exists). **There must be no automatic transition** when time expires: do **not** auto-advance to practice voting, selection, or lobby. The Gamemaster continues to use existing controls (e.g. end practice prompting / start practice voting) to move the session forward.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Non-admins in **onboarding → practice prompting** see the `#timer` (or equivalent) count down from **3:00** to **0:00** using server time, not a fixed label.  
- [ ] The **admin dashboard** time display during that phase counts down the same window (or shows consistent remaining time), not a hard-coded **5:00**.  
- [ ] At **0:00**, **no** server or client action **automatically** changes `onboarding_phase` or `status`; practice voting starts **only** when the Gamemaster triggers it as today. Scored rounds and all other phases behave unchanged.

**Do not change** (optional — what to leave alone):  
> Do not add an automatic transition at onboarding timer expiry. Do not shorten or timer-gate **practice voting** in this story unless explicitly extended later. Do not change the **5-minute** duration of scored **playing** rounds. Preserve onboarding prompt limits (e.g. max 3 images) and existing admin flows except what’s needed to supply timer fields and display.

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (`handle_start_onboarding`, game state for onboarding end time, any `round_timer_check`-style guard if reused; ensure reconnect payloads include timer fields). `static/js/game.js` (`onboarding_started` handler: remove static `5:00`; reuse or mirror `game_started` countdown logic; admin `admin_onboarding_started` display). `templates/index.html` only if timer markup or labels need adjustment.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
