# User story: Required post-game survey (Supabase + admin tracking + start button)

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby *(Gamemaster: **Start post-game survey** lives here alongside the other lobby admin actions — see below)*  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [x] Game over  
- [x] Post Survey *(dedicated UI after the game ends — may overlay or follow the game-over screen)*  
- [x] Admin / gamemaster  
- [x] Other: **Backend / player state, Supabase persistence tied to player identity**

**What to do** (one or two sentences in plain language):  
> When the Gamemaster chooses, **non-admin players** must complete a **post-game survey** before they can move forward in the app. **Every question is required**; validation blocks progression until all answers are provided. Responses are **persisted in Supabase** and **linked to the individual player** (same identity model as the pre-game survey: stable `player_id` / session linkage used elsewhere in analytics). The **admin dashboard** uses **the same style of per-player tracking** as the pre-survey (clear pending vs completed state in the player list). Add an admin control in the **lobby**: a **“Start post-game survey”** button that appears **with the same Gamemaster controls as** **Assign Groups**, **Start Onboarding**, **Start Game**, and **Restart Game** (same screen / control group — not hidden on a separate admin-only overlay unless the product already consolidates those there). The Gamemaster can use it **at any time** in the session when appropriate so players can open the survey when ready.

**Survey copy (exact wording)**

**A. Free response** (required text fields; enforce non-empty after trim and a reasonable max length per field, consistent with pre-survey free text.)

1. **Prompt:** “What was your thought process when allocating points in voting?”

2. **Prompt:** “How did you decide when to give an image more or less points than another image in the same round of voting?”

3. **Prompt:** “During image creation, what information, if any, was displayed about your prompting?”

4. **Prompt:** “On the voting screen, what information, if any, was displayed about the images?”

**B. Self-evaluation** (single choice per row; required.)

5. **Prompt:** “The images I submitted for voting represented my best work:”  
   **Options (single select, one row):**  
   - Strongly Disagree  
   - Disagree  
   - Neutral  
   - Agree  
   - Strongly Agree  

6. **Prompt:** “The images I submitted for voting represented significant effort on my part:”  
   **Options (single select, one row):**  
   - Strongly Disagree  
   - Disagree  
   - Neutral  
   - Agree  
   - Strongly Agree  

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Players who are in the **post-survey phase** see all **six** questions with the copy above; **Submit** (or “Continue”) is disabled or server-rejected until every free-response field is filled (per validation rules) and both Likert items have a selection. After successful submit, they can **move forward** (e.g. dismiss survey, see final thank-you, or return to a neutral end state — product choice, but **no bypass** without completing all items).  
- [ ] **Supabase:** Each submission is stored with a **stable tie to the player** (e.g. `player_id` on the analytics `players` table and/or a dedicated `post_survey` table with `player_id` FK + `game_id` where applicable). Reconnection restores **completed** state so players cannot be forced to resubmit the same game’s survey.  
- [ ] **Admin:** The Gamemaster sees **per-player post-survey status** analogous to pre-survey (e.g. not started / pending / completed), updating on join and on submit. A **“Start post-game survey”** (or similarly labeled) **button** is shown in the **lobby** next to **Assign Groups**, **Start Onboarding**, **Start Game**, and **Restart Game** (one coherent admin action row / panel on the lobby). It is available **at any time** the product allows in that session; triggering it puts **connected non-admin players** into the post-survey flow (exact gating—e.g. only after DB `game_id` exists vs stricter rules—is implementation detail, but the button must be usable **before** natural game end if the product wants early collection).  
- [ ] Smoke test: finish a short game path, trigger survey (manually or via game over), complete as two players, confirm admin shows both completed and DB rows exist for both.

**Do not change** (optional — what to leave alone):  
> Preserve pre-game survey behavior, lobby join, and live round flows unless this story explicitly requires a small hook (e.g. socket event for “survey started”). Do not remove or weaken existing `survey_completed` / pre-survey admin labels; **add** parallel post-survey fields and UI. Only the area(s) listed above.

**Depends on** (optional — other stories or data that must exist first):  
> **Pre-survey / player identity in Supabase** pattern (`players` row, `player_id`) should exist so post-survey can mirror linkage. If `game_id` is required for post-survey rows, ensure the game record exists before persisting (same as other round analytics).

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` — **lobby** Gamemaster block: add **Start post-game survey** alongside **Assign Groups**, **Start Onboarding**, **Start Game**, **Restart Game**; plus player-facing post-survey panel or screen. `static/js/game.js` (validation, socket events, admin list fields), `static/css/style.css`, `app.py` (player flags e.g. `post_survey_completed`, emit on admin list, handler for admin “start post survey”, handler for player submit), `db.py` + **new SQL migration** under `sql/` for post-survey columns or table. Mirror **`stories/lobby-pre-survey-replace-how-to-play.md`** and existing `pre_survey_*` / `survey_completed` patterns where practical. Follow **`GUIDELINES.md`** and **`PLAYTEST_2_TESTING_CHECKLIST.md`** for reconnection and admin.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow `GUIDELINES.md`. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
