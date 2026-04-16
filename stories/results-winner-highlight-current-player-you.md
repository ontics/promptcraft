# User story: Results/Winner screen — highlight current player as “You” (keep order)

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [x] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [ ] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> On the Results / Winner screen, add UI so each player can clearly identify their own row/card by showing a "You" label next to their username and visually highlighting that row/card. This should be based on the current client player identity and must work for both normal and experiment result variants.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] When viewing Results / Winner as a non-admin player, that player’s own entry includes a visible "You" indicator next to the username.  
- [ ] The same entry has a clear visual highlight (e.g., border/background/accent) that is distinct but consistent with the existing design system.  
- [ ] **Player order on the results page is unchanged** from current behavior (ranking/sorting logic stays exactly the same).

**Do not change** (optional — what to leave alone):  
> Do not change ranking calculations, sorting order, tie behavior, score values, or result data payload structure except what is minimally needed to identify the current player on the client. Do not alter admin-only result behavior unless the same UI pattern is intentionally supported there without changing order.

**Depends on** (optional — other stories or data that must exist first):  
> None. Relies on existing per-client identity (`gameState.playerName` / equivalent) and current result rendering path.

**Files likely involved** (optional — helps the AI and you focus):  
> `static/js/game.js` (results rendering function, e.g. game-over/result cards where `result.player_name` is rendered), `static/css/style.css` (highlight + "You" badge styling), optional `templates/index.html` only if a wrapper/class hook is needed.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
