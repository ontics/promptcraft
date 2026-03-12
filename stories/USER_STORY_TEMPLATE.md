# User story: [Short title, e.g. "Remove Bud/Spud from prompting screen"]

Copy this template when adding a new user story. Save it in this folder (Stories/) with a descriptive filename (e.g. `remove-bud-spud-prompting.md`). Fill in the sections below. The AI uses this to make focused edits without breaking other parts of the game.

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> [e.g. "Remove the Bud/Spud character and all related messages from the prompting screen. The right column should no longer show the character avatar or speech bubbles."]

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] [e.g. "Prompting screen has no character avatar or character messages."]  
- [ ] [e.g. "Backend no longer sends character data for the prompting phase."]  
- [ ] [e.g. "Lobby and other screens still work as before."]

**Do not change** (optional — what to leave alone):  
> [e.g. "Do not change lobby, selection, or voting screens. Do not remove character logic from rounds 2–3 if it's used elsewhere."]  
> If nothing specific, write: "Only the area(s) listed above."

**Depends on** (optional — other stories or data that must exist first):  
> [e.g. "None" or "Requires heuristic data in game structure (story X). Merge after story X."]

**Files likely involved** (optional — helps the AI and you focus):  
> [e.g. "templates/index.html (game screen section), static/js/game.js (character/prompting), app.py (send_prompt, character helpers)"]

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
