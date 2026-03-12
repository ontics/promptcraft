# User story: Remove Bud/Spud from below target image (prompting screen)

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [x] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> Remove bud/spud from below the target image in the prompting (in-round) interface so the layout roughly matches the lo-fi wireframe: the right column shows only the target image and timer/round label in the header, with no character (bud/spud) or related UI below the target image.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] No bud/spud character or related elements appear below the target image on the prompting screen.  
- [ ] Right column layout matches the wireframe (target image; no extra content beneath it until the bottom input bar).  
- [ ] Lobby, other rounds, and other screens still work as before.

**Do not change** (optional — what to leave alone):  
> Do not change lobby, transition, selection, voting, results, or game-over screens. Only the prompting (in-round) screen layout and any character UI tied to "below the target image" should be removed; do not remove character logic used elsewhere (e.g. rounds 2–3) unless it is only for this placement.

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Files likely involved** (optional — helps the AI and you focus):  
> templates/index.html (prompting/game screen section, right column), static/js/game.js (prompting UI, any bud/spud rendering below target). Optionally app.py if character data is sent specifically for this placement.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
