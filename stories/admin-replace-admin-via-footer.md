# User story: Allow new admin to replace existing admin via lobby footer login

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [x] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> When a user enters the correct admin password through the lobby footer Admin link, they should become the new Gamemaster even if there is already an existing admin. The previous Gamemaster is **disconnected** (removed from the game), not demoted to a player, to avoid unwanted data or state.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Entering the correct admin password via the lobby footer Admin link always results in that user becoming the sole active Gamemaster, regardless of whether a previous admin exists or is connected.  
- [ ] Any previous Gamemaster is **disconnected** (removed from the game): they are no longer in the lobby or in game state; their client is notified and must rejoin (e.g. click Join Game again) to re-enter. They are not demoted to a regular player.  
- [ ] If the previous admin had already disconnected (no active socket), the new admin can still successfully take over via the footer login; the old admin’s stale entry is removed from game state.

**Do not change** (optional — what to leave alone):  
> Only the area(s) listed above. Do not change how non-admin players join the lobby or how the main game flow (prompting, selection, voting, results, game over) works; only change how admin status is reassigned when logging in via the lobby footer.

**Depends on** (optional — other stories or data that must exist first):  
> `admin-login-footer-link` story (lobby footer Admin link and password prompt) must exist and be implemented.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (admin login handling and admin state transfer logic for `admin_login`), `static/js/game.js` (client-side handling of admin login events, ensuring UI updates reflect the new admin), `templates/index.html` (lobby footer layout, if any tweaks to the Admin entry point are needed).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app with two different browsers/sessions, log in as admin from each in turn via the footer, and verify that admin status cleanly transfers each time).*
