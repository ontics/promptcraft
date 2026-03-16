# User story: Replace username input with Join Game button and assign animal aliases

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
> Replace the lobby’s username creation (e.g. “Enter your name” input + join flow) with a single “Join Game” button. When a player clicks Join Game, the server automatically and randomly assigns them an animal alias (e.g. Wildcat, Shark, Bear); that alias **replaces the user-chosen name in the database**—i.e. the animal alias is stored as the player’s name/display name in the DB and used everywhere in the app (lobby list, in-game, etc.). Layout should align with the page mock-up: welcome title, prominent Join Game button, “Players in lobby” list showing animal names, and “Here’s how the game works” (or equivalent) content; Admin link remains in the footer.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Lobby shows “Welcome to PromptCraft!” (or equivalent), a single “Join Game” button, and no visible “Enter your name” (or similar) text input for choosing a display name.  
- [ ] Clicking “Join Game” joins the player to the lobby; the server assigns a random animal alias (from a fixed list, e.g. Wildcat, Shark, Bear, etc.) that is unique among current lobby players where feasible. That alias is **stored as the player’s name in the database** (replacing the previous user-entered username) and is used as the player’s display name everywhere (lobby list, in-game, results, etc.).  
- [ ] “Here’s how the game works” (or existing How to Play) and the Admin footer link are still present and unchanged in behavior; other screens (prompting, selection, voting, results, game over) and admin login flow are unchanged.

**Do not change** (optional — what to leave alone):  
> Only the area(s) listed above. Do not change admin login (footer Admin link and password), game flow (prompting, selection, voting, results, game over), or how the gamemaster/admin is determined; only change how players enter the lobby and how their display name is chosen (no manual name, animal alias only).

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Reference:**  
> Page mock-up: welcome title, single “Join Game” button (no name field), “Players in lobby” listing animal aliases (e.g. Wildcat, Shark, Bear), “Here’s how the game works” panel, Admin link in bottom right.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (lobby: remove name input, keep/emphasize Join Game button, “Players in lobby” and how-to section), `static/js/game.js` (lobby: join without sending a name; display assigned alias from server), `app.py` (join_game or equivalent: assign random animal alias, enforce uniqueness in lobby, store alias as player name in in-memory state and when persisting to DB; keep admin logic unchanged), `db.py` (ensure player records use the assigned animal alias as player name, not a user-supplied username).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test (e.g. run the app, click Join Game, confirm an animal alias appears in Players in lobby and is used in-game; test with multiple players to confirm aliases are assigned and unique where possible).*

# User story: Replace username input with Join Game button and assign animal aliases

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
> Replace the lobby’s username creation (e.g. “Enter your name” input + join flow) with a single “Join Game” button. When a player clicks Join Game, the server automatically and randomly assigns them an animal alias (e.g. Wildcat, Shark, Bear); that alias **replaces the user-chosen name in the database**—i.e. the animal alias is stored as the player’s name/display name in the DB and used everywhere in the app (lobby list, in-game, etc.). Layout should align with the page mock-up: welcome title, prominent Join Game button, “Players in lobby” list showing animal names, and “Here’s how the game works” (or equivalent) content; Admin link remains in the footer.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Lobby shows “Welcome to PromptCraft!” (or equivalent), a single “Join Game” button, and no visible “Enter your name” (or similar) text input for choosing a display name.  
- [ ] Clicking “Join Game” joins the player to the lobby; the server assigns a random animal alias (from a fixed list, e.g. Wildcat, Shark, Bear, etc.) that is unique among current lobby players where feasible. That alias is **stored as the player’s name in the database** (replacing the previous user-entered username) and is used as the player’s display name everywhere (lobby list, in-game, results, etc.).  
- [ ] “Here’s how the game works” (or existing How to Play) and the Admin footer link are still present and unchanged in behavior; other screens (prompting, selection, voting, results, game over) and admin login flow are unchanged.

**Do not change** (optional — what to leave alone):  
> Only the area(s) listed above. Do not change admin login (footer Admin link and password), game flow (prompting, selection, voting, results, game over), or how the gamemaster/admin is determined; only change how players enter the lobby and how their display name is chosen (no manual name, animal alias only).

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Reference:**  
> Page mock-up: welcome title, single “Join Game” button (no name field), “Players in lobby” listing animal aliases (e.g. Wildcat, Shark, Bear), “Here’s how the game works” panel, Admin link in bottom right.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (lobby: remove name input, keep/emphasize Join Game button, “Players in lobby” and how-to section), `static/js/game.js` (lobby: join without sending a name; display assigned alias from server), `app.py` (join_game or equivalent: assign random animal alias, enforce uniqueness in lobby, store alias as player name in in-memory state and when persisting to DB; keep admin logic unchanged), `db.py` (ensure player records use the assigned animal alias as player name, not a user-supplied username).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test (e.g. run the app, click Join Game, confirm an animal alias appears in Players in lobby and is used in-game; test with multiple players to confirm aliases are assigned and unique where possible).*
