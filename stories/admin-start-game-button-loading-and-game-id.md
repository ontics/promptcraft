# User story: Admin Start Game button — loading, disable until success, show game ID

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
> For the **Start game** control on the **admin dashboard**, on the **first click** in a lobby session ready to start: update the **admin-only UI** so the button **cannot be clicked again** immediately, and show a clear **loading** state (spinner, disabled styling, and/or “Starting…” text — exact treatment up to implementer) while the existing **`start_game`** flow runs. When the server has successfully created the game and set **`game_id`** (same success path as today), the button should **show that numeric `game_id`** in its label (e.g. “Game #123” or “Started — ID 123”) and remain **non-clickable** for starting again in this run. If **`start_game` fails** or **no game row is created** in the database (same failure conditions as today), **restore** the button to its normal enabled state and default label so the admin **can** try again. **Do not** change how **`start_game`** is invoked from the client, server-side game creation order, player **`game_started`** behavior, other admin controls, or any player-facing screen beyond what is strictly required to reflect this button state.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] After the admin’s first **Start game** click (while a start is in flight), the Start game button is **disabled** (or otherwise non-actionable) and shows a **loading** experience until success or failure is known.  
- [ ] On **success**, the button reflects the **created `game_id`** (readable text on or next to the control) and the admin **still cannot** use it to fire another start for that same started session.  
- [ ] On **failure** (including “no game created” / same error paths as today), the button returns to **clickable** with the original label so the admin can retry.  
- [ ] Players and all other admin flows behave **as today** except this button’s presentation and the **admin’s** access to the new **`game_id`** on success.

**Do not change** (optional — what to leave alone):  
> Do not change **`socket.emit('start_game')`** timing or who may call it beyond guarding duplicate clicks in the UI. Do not refactor **`handle_start_game`** logic (team checks, DB `create_game` / `create_player` / `create_round`, emits to non-admin players, round timers, etc.) except **additive** changes needed to deliver **`game_id`** to the **admin client** if it is not already available on an admin-only channel (e.g. include **`game_id`** on **`admin_game_started`** when present — no change to **`game_started`** payloads for players unless already shared and required for consistency). Do not change **Restart game**, **Back to home**, onboarding start, post-survey, or roster behavior. Do not change player lobby or in-game UX for this story.

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (Start game button markup if a sibling label or ARIA live region is needed), `static/js/game.js` (click handler: optimistic disable + loading; listen for **`admin_game_started`** or the earliest reliable success signal; handle **`error`** to re-enable; update button text with **`game_id`**), `static/css/style.css` (loading/disabled visuals only if needed), `app.py` (optional: add **`game_id`** to **`admin_game_started`** payload after `create_game` succeeds, if not derivable client-side today).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
