# User story: Admin lobby — rename “Restart Game” button to “New Game”

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
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> In the **admin controls** on the **lobby** screen, change the visible label on the red control that currently reads **“Restart Game”** (including the leading emoji if present) so it reads **“New Game”** instead. Gamemasters should still understand this is the action that ends the current session and clears everyone to rejoin; this story is **copy on the button only**, not a change to server behavior or the Socket.IO event name.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] The admin lobby button shows **“New Game”** (or **“🔄 New Game”** if the team keeps the emoji — pick one consistent string and match the design system for danger buttons).  
- [ ] Clicking the control still runs the same **`restart_game`** flow as today (confirm dialog, kick, DB end, empty lobby).  
- [ ] No other screens or player-facing strings are required to change for this story unless the same literal “Restart Game” text appears elsewhere in the admin lobby chrome for the same control (then align for consistency).

**Do not change** (optional — what to leave alone):  
> Do not rename the **`restart_game`** socket event, **`handle_restart_game`** in `app.py`, or **`game_restarted_kick`** semantics. Do not change the **confirm** dialog body or server kick messages unless a follow-up story asks for full copy alignment with “New Game.” Do not change **Back to home** or other admin controls.

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (`#restart-game-btn` label). Optionally `static/js/game.js` only if a comment or string tied to that button ID must be updated for clarity; avoid broad renames of “restart” in unrelated code paths.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
