# User story: Full selection duration (90s) + “Next round starting in…” countdown between rounds 1–2 and 2–3

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [x] Transition screen  
- [x] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [ ] Admin / gamemaster  
- [x] Other: **server round / phase orchestration between selection and next prompting**

**What to do** (one or two sentences in plain language):  
> On the **image selection** phase, players must always have the **full selection duration (90 seconds)** to choose an image. The game must **not** advance early when every player has already confirmed a selection—the timer still runs for the full 90 seconds. When that timer **ends** after **round 1** or **round 2** selection, show a **new full-screen (or full-stage) transition** modeled on the reference: white background, thick dark rounded border, heading **“Next round starting in…”**, and a **large centered countdown** from **5** down to **1** (one second per step), then **automatically start the next prompting round**. After **round 3** selection ends, **do not** show this countdown; follow the **existing** flow into **voting** (no extra 5-second screen).

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] During selection in live rounds **1–3**, if all players confirm before 90 seconds elapse, the UI and server still wait until the **full 90 seconds** complete before leaving the selection phase (no early jump to the next phase for “everyone ready”).  
- [ ] After selection ends following **round 1** and **round 2**, every client sees a new transition screen: **“Next round starting in…”** with a **large centered** countdown **5 → 1** (one second each), **white** content area, **thick dark rounded border**, black sans-serif type; then **next round prompting** starts automatically.  
- [ ] After selection ends following **round 3**, the game goes straight to **voting** as today—**no** inter-round countdown screen.

**Do not change** (optional — what to leave alone):  
> Do **not** redesign or alter **prompting** UI/UX, **selection** UI (gallery, confirm button, labels), or **voting** UI/flow beyond what is strictly required to insert the new transition and enforce the full 90-second selection window. Do not change voting rules, targets, or post-round-3 behavior except to **skip** the new countdown when entering voting. Avoid unrelated refactors.

**Depends on** (optional — other stories or data that must exist first):  
> None. Assumes selection duration is (or will remain) **90 seconds** for these rounds; if the constant lives in one place (`app.py` / client), keep a single source of truth when implementing.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (selection phase end timing; block early transition when all players selected; emit events for countdown then `game_started` or equivalent for next round; after round 3 selection, unchanged path to voting), `templates/index.html` (new transition screen markup), `static/css/style.css` (countdown screen styling to match reference), `static/js/game.js` (show/hide transition, local 5-second countdown sync with server if needed).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
