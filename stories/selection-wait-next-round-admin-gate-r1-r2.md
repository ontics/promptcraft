# User story: After R1/R2 selection — “Next round will start soon” + admin must start next round

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
> For **rounds 1 and 2 only**, when the **image selection** phase ends—meaning the **90-second** window has elapsed (including server auto-select for stragglers) **or** every active player has **confirmed** a selection—the game must **not** automatically start the next **prompting** round. Instead, all non-admin players should see a **new transition screen** whose message is clearly **that the next round will start soon** (exact copy can match this intent). While players are on that screen, the **Gamemaster dashboard** must show a **distinct status** indicating they are in this waiting state. The **next prompting round begins only** when the Gamemaster uses the existing **Next round** control (or an equivalent clearly labeled admin action wired to the same outcome)—i.e. **manual advance**, not automatic.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] After **round 1 or 2** selection completes (time up or all confirmed), **no** `game_started` / next-round prompting fires until the admin triggers it; players see the **“next round will start soon”** transition until then.  
- [ ] The **admin panel** shows a **dedicated status** (not the same as generic “Playing” or “Voting (Selection)”) while players are on that interstitial.  
- [ ] **Round 3** behavior after selection is **unchanged** (still proceeds to the existing post–round-3 path, e.g. voting prep / allocation flow—**no** new admin gate there unless a separate story says so).

**Do not change** (optional — what to leave alone):  
> Do not alter **round 3** selection completion logic except to avoid accidentally coupling it to the new R1/R2 gate. Do not remove **90s** selection duration or **auto-select** rules unless a separate story requires it. Preserve **allocation voting**, **post-survey**, and **reconnect** behavior outside this interstitial. Prefer reusing or extending **`handle_next_round`** / existing admin controls rather than inventing parallel “start game” paths.

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (`check_all_selected`, `advance_to_next_prompting_round_after_selection`, new server `status` or phase flag, emits to players + admin; ensure `round_timer_check` / skip paths respect the gate). `templates/index.html` (transition or dedicated screen markup/message). `static/js/game.js` (handle new socket event or transition payload; show screen; admin status label). `static/css/style.css` if the new screen needs layout consistent with other transitions.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
