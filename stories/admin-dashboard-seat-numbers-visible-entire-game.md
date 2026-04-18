# User story: Admin dashboard shows each player’s seat number for the whole game

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
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> For the **entire duration of an active game** (from after players join through prompting, transitions, selection, voting, results, game over, and any post-game admin views that still show the live roster), the **admin dashboard** must **always** show each non-admin player’s **seat number** alongside their name (or in the same row/card), using the same seat value captured at join. Seat numbers must **not** disappear, collapse, or be replaced by placeholders when the game phase changes or when the admin scrolls or refreshes dashboard data.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] At every in-game phase the gamemaster can reach without returning to lobby, the admin player list (or equivalent roster UI) still shows **seat number** next to each non-admin player, consistent with the value stored for that session.  
- [ ] Reloading or reconnecting the admin client mid-game still shows seat numbers when the dashboard repopulates from the server.  
- [ ] Non-admin player-facing screens are unchanged: seat numbers remain **admin-only** display unless another story says otherwise.

**Do not change** (optional — what to leave alone):  
> Do not change how seat numbers are collected in the lobby, treatment assignment, scoring, or experiment logic except to ensure the value is **available in all admin dashboard payloads and render paths** for the life of the game. Do not add seat numbers to the public lobby list or player game screens as part of this story.

**Depends on** (optional — other stories or data that must exist first):  
> Requires that each non-admin player has a persisted **seat number** in server state (see `stories/lobby-seat-number-admin-dashboard-display-and-filters.md` or equivalent). If that story is not merged, implement storage first or merge with it so this story only covers **visibility and payload coverage** across phases.

**Files likely involved** (optional — helps the AI and you focus):  
> `static/js/game.js` (all admin dashboard render/update paths, reconnect sync), `templates/index.html` (admin roster markup if seat column is missing in some views), `static/css/style.css` (layout only if needed for consistent column visibility), `app.py` (ensure `seat` / seat number is included on every admin-relevant emit or poll response while `game_id` or in-game status is active).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
