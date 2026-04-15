# User story: Post-game survey — white text, two Likert matrices, and “AI images are more impressive if”

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby *(remove or retire the Gamemaster **Start post-game survey** entry point; see flow change below)*  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [x] Voting screen *(flow handoff: **voting completes** → post-survey starts automatically for players)*  
- [x] Results / Winner screen *(shown **after** post-survey completion for non-admins — see flow below)*  
- [ ] Game over  
- [x] Post Survey  
- [x] Admin / gamemaster *(no longer starts post-survey from lobby; admin list may still show completion status)*  
- [x] Other: **`static/css/style.css`** *(post-survey section — ensure all survey copy uses white text)*  

**What to do** (one or two sentences in plain language):  
> **Change the post-game survey entry point.** Do **not** require the Gamemaster to start the survey from the **lobby** (remove or disable the **Start post-game survey** control and any equivalent admin-only trigger for opening the survey). Instead, for **non-admin** players, the post-game survey **starts automatically** as soon as **voting for the game has completed** (the same moment in the server/client flow where voting is done and players would otherwise move on — implementation should hook the automatic transition there). After a player **successfully completes and submits** the post-survey, they then see the **Results / Winner** screen (and the usual results experience for that phase). **Admins** are out of scope for taking the player survey unless product says otherwise; preserve a sensible admin view (e.g. they may already see results / dashboard without the player survey).  
> Update the **post-game survey** UI and content. **All text** shown in the post-game survey (labels, prompts, scale headers, row text, errors, buttons as needed for consistency) must use **white** as the foreground color: **`#ffffff`** (valid CSS hex; six `f` characters).  
> Add the following instruments in the order below: **Likert Matrix 1** (three separate matrix blocks sharing the same column scale), **Likert Matrix 2** (one matrix), and a **single-choice** question **“AI images are more impressive if:”** with the five mutually exclusive options listed. Extend validation, persistence, and admin “completed” tracking to include every new required item; **reconnect** must resume the survey if voting is already complete and the player has not yet submitted.

**Likert Matrix 1 — column scale (all three blocks)**  
Each block is a matrix: **one rating per row** (required). Rows and stems differ per block; columns are identical.

**Columns (left → right):**  
Far Less · Somewhat Less · The Same · Somewhat More · Far More  

**Block A — stem:**  
“A person who submits **longer** prompts is:”  

**Rows (each row vs the column scale):**  
- Creative  
- Precise  
- Skilled  
- Efficient  

**Block B — stem:**  
“A person who submits **more** prompts is:”  

**Rows:**  
- Creative  
- Precise  
- Skilled  
- Efficient  

**Block C — stem:**  
“A person who submits prompts with **more variable vocabulary** is…”  

**Rows:**  
- Creative  
- Precise  
- Skilled  
- Efficient  

---

**Likert Matrix 2 — column scale**  
**Columns (left → right):**  
Strongly Disagree · Disagree · **Neutral** *(not “Neural”; use correct spelling)* · Agree · Strongly Agree  

**Rows (each row vs the column scale; one selection per row, required):**  
- I voted for images based purely on their visual similarity to the target image  
- I considered prompt count when voting for images.  
- I considered total prompt word count when voting for images.  
- I considered prompt vocabulary variability when voting for images.  
- I value AI generated images more when I believe they are not easily created.  
- A player who successfully recreated the target image in just one or two prompts better understands the AI model.  
- Requiring dozens of prompts to achieve a good result is a sign of poor prompt engineering skills.  

---

**Single choice — “AI images are more impressive if:”**  
One required selection (radio group or equivalent). Options **exact** wording:

1. …I could make it without AI  
2. …I could make it without AI with some difficulty  
3. …I could easily make it with AI  
4. …I could make it with AI with some difficulty  
5. …I don’t know how to make it at all  

*(Leading ellipsis “…” is part of the option text as specified.)*

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] **Flow:** When **voting completes**, each **non-admin** player is taken to the **post-game survey automatically** without an admin lobby action. The lobby **no longer** exposes a **Start post-game survey** (or equivalent) as the way to open the survey. After **successful post-survey submit**, the same player is shown the **Results / Winner** screen (not before). Non-admins **cannot** reach Results/Winner for that game session **until** post-survey is completed (except any explicit admin-only paths).  
- [ ] Every piece of **post-game survey** copy (including matrix headers, row labels, scale labels, validation messages, and primary actions in that flow) renders in **`#ffffff`** on the survey surfaces; contrast remains readable (adjust survey panel background or borders if needed — **do not** ship gray-on-white body text in this flow).  
- [ ] **Likert Matrix 1** appears as three blocks with the stems, rows, and **Far Less → Far More** scale above; **Likert Matrix 2** appears with the **Strongly Disagree → Strongly Agree** scale and all seven rows; the **“AI images are more impressive if:”** question appears with all five options. Submit (or equivalent) stays disabled / server rejects until **all** new required cells and the single-choice item are answered, in addition to any **existing** required post-game items this story keeps.  
- [ ] **Persistence:** New answers are stored (Supabase and/or existing post-survey storage pattern) with stable player/game linkage; reconnection restores **in-progress** post-survey or **completed** state appropriately. **Admin** roster still reflects post-survey completion when applicable.  

**Do not change** (optional — what to leave alone):  
> Do not change **pre-game** survey copy or styling except where a shared component must be split to avoid unintended side effects. Do not change **round 10** allocation or the **rules** of voting mechanics except the **transition targets** required here (post-survey → results). Do not alter fixture JSON under `voting_fixtures_config/` for this story. If legacy free-text post-game questions remain, keep them unless product explicitly removes them in the same change — this story **adds** matrices and the new single-choice item and **requires** white text for the post-game survey region. **Exception:** This story **does** change the post-survey **entry point** (remove lobby admin start; auto-start after voting; results after submit).  

**Depends on** (optional — other stories or data that must exist first):  
> Prior **post-game survey** implementation (`post_survey_completed`, Supabase from `stories/post-game-survey-required-supabase-admin.md`). This story **replaces** the lobby-admin **Start post-game survey** trigger with **automatic** start after voting completes; reconcile server events (`post_survey_active`, etc.) and any `back_to_home` / gating logic so they match the new order (**survey → Results/Winner**). Extend schema if new columns are needed for matrix keys and the single-choice value.  

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (post-game survey markup; **remove** lobby **Start post-game survey** button or hide it permanently; ensure Results/Winner screen wiring after survey). `static/css/style.css` (scoped rules — **#ffffff** text). `static/js/game.js` (automatic navigation to post-survey when server signals voting complete; after `post_game_survey_saved` or equivalent, **show Results/Winner**; validation / emit payload). `app.py` (emit post-survey phase when voting completes for non-admins; stop relying on admin socket to open survey; adjust `post_survey_active` / transitions); `db.py` + `sql/` migration if new fields. Re-test **`PLAYTEST_2_TESTING_CHECKLIST.md`** for reconnection mid post-survey and after voting.  

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
