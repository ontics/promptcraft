# User story: Admin dashboard — show each player’s round-10 earned points (persistent)

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster  
- [x] Other: **allocation voting (round 10) point attribution**

**What to do** (one or two sentences in plain language):  
> During allocation voting round 10 (peer images), the Gamemaster dashboard should show how many **incentive points / earned points** each player has accumulated from round 10 so far. This value should remain visible on the admin dashboard after round 10 completes and persist across later phases (post-survey, results, etc.) for the remainder of the session.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] While `allocation_voting` is in progress, the admin player list shows each player’s **round-10 earned points** and updates live as point allocations are submitted.  
- [ ] After round 10 completion, the same round-10 points remain visible for each player on the admin dashboard across later phases (post-survey, results/game over) until the game is restarted/cleared.  
- [ ] Values match server-side scoring logic for round-10 allocations (no double counting; reconnect/admin refresh shows consistent values).

**Do not change** (optional — what to leave alone):  
> Do not change the allocation voting rules, totals, ballot assignment, or the ranking logic. Only add display/persistence of the existing round-10 points values.

**Depends on** (optional — other stories or data that must exist first):  
> None. Assumes round-10 allocations already award points to players (e.g. via `incentive_points` updates) and that the admin dashboard receives player status payloads.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (where round-10 points are added to player state; include the per-player round-10 total in admin status payloads), `static/js/game.js` (render the new value in `updateAdminPlayerList` and keep it visible outside allocation voting), optionally `db.py` (only if round-10 points must be persisted to Supabase and restored on reconnect for long sessions).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
