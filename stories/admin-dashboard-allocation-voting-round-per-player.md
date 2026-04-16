# User story: Admin dashboard — show each player’s allocation voting round (1–10)

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
- [x] Other: **`app.py`** *(admin status payload, optional notifications when allocation advances)*  

**What to do** (one or two sentences in plain language):  
> While the game is in **point allocation / voting** (the **10** asynchronous rounds after round 3 — fixture rounds **1–9** plus the **final** peer round), the **Gamemaster player list** on the admin dashboard should show, for each non-admin player, **which allocation round they are currently on** (e.g. **round 4 of 10**, or **finished / waiting** once they have submitted all 10, if that state exists today). Today the list does not surface `allocation_player_round`; implement end-to-end so admins can see progress without guessing.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] With `game_state['status'] == 'allocation_voting'`, each non-admin row in the admin dashboard shows a clear label for **current allocation voting round** out of **10** (aligned with `TOTAL_VOTING_ROUNDS` / `allocation_player_round`), or an agreed label when the player has **completed** all 10 and is waiting for others.  
- [ ] As players **submit** points and advance to the next round, the admin view **updates** without requiring a manual refresh (reuse or extend existing `player_status_update` / `notify_admin_player_list` patterns, and/or the existing `player_allocation_submitted` path if appropriate).  
- [ ] Lobby, onboarding, main-game prompting, selection, legacy voting, and post-survey admin rows behave as before when not in allocation voting.

**Do not change** (optional — what to leave alone):  
> Do not change allocation **rules**, ballot building, or round-10 assignment logic. Do not rename socket events unless necessary; prefer extending payloads the admin UI already consumes (`player_status_update` / `admin_player_status_row_with_round`).

**Depends on** (optional — other stories or data that must exist first):  
> None. Uses existing per-player `allocation_player_round` (and related fields) set during `emit_allocation_round_for_player` / `_after_allocation_submit_emit`.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (`admin_player_status_row_with_round`, `notify_admin_player_list` after allocation advances — e.g. `handle_submit_point_allocation` / `_after_allocation_submit_emit` / `start_allocation_voting_phase` if the list is stale on entry), `static/js/game.js` (`updateAdminPlayerList` — `phaseBadge` or equivalent when `gameState` reflects allocation voting; may need `gameState` or payload flags for `allocation_voting` if not already present on the client).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
