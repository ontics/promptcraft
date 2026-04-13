# User story: Show animal alias in voting screen headers

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [x] Onboarding *(onboarding **practice** point-distribution screen — same header pattern as live allocation voting)*  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [x] Voting screen *(point-allocation UI on `#voting-screen` — all allocation “rounds” 1–10)*  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [ ] Admin / gamemaster  
- [x] Other: **`static/css/style.css`** *(header layout / typography if the alias line needs to match `#game-screen`)*  

**What to do** (one or two sentences in plain language):  
> On every **voting** experience that uses the allocation-style header (live **point allocation** after round 3, and **onboarding practice voting**), show the player’s **animal alias** (the same display name used elsewhere, e.g. under the round title on `#game-screen` via `#player-display-name`) **in the header** so it is always obvious **who** is voting. Today those headers use a spacer (`allocation-voting-header-spacer` / non-breaking space); replace or augment that area with visible text, consistent with the main game header pattern.  
> If a **legacy** single-image vote UI on the same `#voting-screen` is ever shown again, the alias should appear there too for consistency (implementation may reuse one element id or shared update helper).

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] While a non-admin is on **allocation voting** (`#voting-screen`), each step (rounds **1–10**) shows their **animal alias** in the header (readable on desktop and narrow viewports).  
- [ ] While a non-admin is on **onboarding practice voting** (`#onboarding-practice-voting-screen`), the header shows the same **animal alias** in the equivalent position.  
- [ ] **Gamemaster / admin** flows are unchanged; no alias required on admin-only views. Lobby, prompting, selection, and post-survey screens behave as before except where this story explicitly adds the alias to voting headers.

**Do not change** (optional — what to leave alone):  
> Do not change how aliases are **assigned** (server / join flow) or the **wording** of allocation instructions, point rules, or fixture content. Do not remove the round counter (“Voting Round x/10”) or points-to-allocate line unless product asks for a layout tweak in review. Only the area(s) listed above.

**Depends on** (optional — other stories or data that must exist first):  
> **Animal aliases** and `gameState.playerName` (or equivalent) already populated on join, as today. No backend change required unless the client cannot read the name without a new socket payload (prefer reusing existing client state).

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (`#voting-screen` and `#onboarding-practice-voting-screen` header blocks — replace spacer with a visible element, e.g. mirroring `player-display-name` pattern), `static/js/game.js` (set text when showing allocation / practice voting — e.g. `allocation_vote_started`, `onboarding_practice_voting_started`, and any path that shows `#voting-screen`), `static/css/style.css` (spacing/typography for `allocation-game-header` + `player-info` if needed). **`app.py`:** only if server must send the name explicitly (unlikely).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
