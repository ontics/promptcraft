# User story: Remove home button from game-over page

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [x] Game over  
- [ ] Post Survey  
- [ ] Admin / gamemaster  
- [ ] Other: _______________

**What to do** (one or two sentences in plain language):  
> Remove the **Back to Home** control from the game-over (Results / Winner) screen so players no longer see a home button after final results. The rest of the game-over content (title, `final-results`, optional post-survey hint copy) should stay as it is unless a follow-up story says otherwise.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] The game-over screen (`#gameover-screen`) has no **Back to Home** button and no empty placeholder where it used to be (layout still looks acceptable).  
- [ ] Client code no longer registers a click handler for `#back-to-home-btn` or toggles its visibility for the game-over flow; any dead references tied only to that button are removed or cleaned up.  
- [ ] Other ways to leave or reset session (e.g. post-game survey **back** if present, admin restart, reconnect) still behave as before.

**Do not change** (optional — what to leave alone):  
> Do not remove or change the post-game survey screen’s own back/home control (`#post-game-survey-back-btn` and its `back_to_home` emit) unless a separate story asks for it. Do not change `app.py` `handle_back_to_home` behavior except if required because the game-over button is the only caller and cleanup is needed (survey back may still use the same event).

**Depends on** (optional — other stories or data that must exist first):  
> None.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (`#gameover-screen`, remove `#back-to-home-btn`), `static/js/game.js` (click listener for `back-to-home-btn`; `game_over` handler that shows the button; `post_survey_started` handler that hides it — remove or simplify as appropriate).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
