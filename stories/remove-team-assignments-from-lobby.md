# User story: Remove Green/Orange team assignments from the lobby UI

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> In the lobby interface, remove any visible Green/Orange team assignment indicators and any lobby-side team controls so players cannot tell which team they’re on. Keep all team assignment logic, randomization, and team-based character selection in place within the Gamemaster/Admin view and backend (e.g. the `Assign Teams` button and admin team dropdown).

**Done when** (how we know it’s finished — 1–3 bullets):  
- [ ] The lobby “Players in lobby” list no longer displays Green/Orange badges, and shows only the player name/alias (and any non-team status like “Waiting”).
- [ ] There is no lobby UI element that lets a player set or view their team (no Green/Orange selectors/dropdowns in the lobby).
- [ ] The Admin/Gamemaster dashboard still shows team assignments for players, keeps the `Assign Teams` randomization behavior, and the game still uses those team assignments for team-based character selection as before.

**Do not change** (optional — what to leave alone):  
> Do not change the backend logic that assigns teams and drives team-based character selection. Do not change the Admin/Gamemaster flow (admin login, Assign Teams, Start Game). Only change the lobby display/control surface.

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Files likely involved** (optional — helps the AI and you focus):  
> `static/js/game.js` (lobby list rendering in `updatePlayerList`; ensure admin view `updateAdminPlayerList` remains unchanged), `templates/index.html` (if any lobby-only team elements exist).

---

*For the AI: When implementing this story, change only the lobby interface display/control elements related to team. Preserve admin view behavior and all team/randomization logic. Follow `GUIDELINES.md`. After implementing, ask the developer to test: join as 2 players, refresh admin view, click `Assign Teams`, confirm lobby hides teams while admin shows teams and game characters are still assigned correctly.*

