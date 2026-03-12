# User story: Admin login via lobby footer link

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
> Add a small, visually de-emphasized “Admin” link in the lobby footer that opens an admin login prompt, so admins can enter the existing admin password to become the gamemaster without interfering with the normal join/start flow.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] The lobby footer shows a subtle “Admin” text link or icon that is visible on both desktop and mobile, positioned away from the main join/start controls.  
- [ ] Clicking the “Admin” link opens an admin login UI (e.g. modal or panel) that prompts for the existing admin password/code, and entering the correct password makes that player the admin/gamemaster for the current game.  
- [ ] Entering an incorrect password shows a clear error message, does not grant admin, and allows the player to try again or cancel, while lobby behavior for non-admin players remains unchanged.  

**Do not change** (optional — what to leave alone):  
> Only the area(s) listed above. Do not change the core join/start flow, other screens (prompting, selection, voting, results, game over), or how the admin password is configured in the environment; this story only adds the lobby footer entry point and its login handling.

**Depends on** (optional — other stories or data that must exist first):  
> None (assumes the existing admin password / `ADMIN_CODE` mechanism continues to work as-is).

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (lobby layout and footer), `static/js/game.js` (lobby UI behavior and admin login interactions), `app.py` (admin login handling, validation against `ADMIN_CODE`, and updating admin/gamemaster state).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*

