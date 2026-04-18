# User story: After R3 selection — waiting screen + admin must start voting

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [x] Transition screen  
- [x] Selection screen  
- [x] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> After **round 3** image **selection** completes (90 seconds elapsed, including any server auto-select, **or** all active players have confirmed), do **not** automatically start the next phase. Instead, show all non-admin players a **waiting transition screen** that clearly says they are **waiting for the game master to start voting** (exact copy can match this intent). The **Gamemaster dashboard** must show a distinct status indicating the game is **ready to start voting**, and voting begins **only** when the Gamemaster clicks an explicit **Start voting** button (or a clearly labeled admin control wired to that outcome).

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] After **round 3 selection** completes, players see a **waiting-for-gamemaster** transition screen and **do not** enter the voting UI until the Gamemaster starts it.  
- [ ] The Gamemaster dashboard shows a **dedicated status** (e.g. “Waiting — ready to start voting”) and offers a **Start voting** control that transitions everyone into the correct round-3 voting flow.  
- [ ] Rounds **1–2** behavior is unchanged (still uses the existing R1/R2 gate and **Next round** behavior; no new voting-start gate there unless another story says so).

**Do not change** (optional — what to leave alone):  
> Do not change selection timing (**90s**) or auto-select rules. Do not change how votes are counted, scoring, or which images appear in voting. Only add the **admin-gated waiting step** between the end of R3 selection and the start of the existing voting flow.

**Depends on** (optional — other stories or data that must exist first):  
> None, but this should compose cleanly with `selection-wait-next-round-admin-gate-r1-r2.md` (R1/R2 gate) by using a separate round-3-only waiting status + admin action.

**Files likely involved** (optional — helps the AI and you focus):  
> `app.py` (round 3 selection completion path; introduce a new status like `awaiting_voting_start` or reuse an existing transition state; emit `show_transition_screen` with `wait_for_admin`; add an admin socket event like `start_voting` or reuse existing handlers safely).  
> `static/js/game.js` (render/handle the new waiting transition; admin dashboard: show “Start voting” button in this state and hide irrelevant controls; keep other admin states unchanged).  
> `templates/index.html` (ensure transition and admin controls exist; add a button if needed).  
> `static/css/style.css` if new UI elements need styling consistent with other admin controls/transitions.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*

