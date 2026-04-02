# User story: Replace “How to play” with a required pre-survey in the lobby

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
- [x] Other: **Backend / player state (survey responses, optional analytics persistence)**

**What to do** (one or two sentences in plain language):  
> Replace the lobby **How to play** (onboarding) section with a **three-question pre-survey** that appears **after** a player has joined the lobby. **All questions are required.** The player completes the survey and clicks **Submit**. Until then, the **Gamemaster/admin** view shows a clear **pre-survey** status for each player; after submit, that status should show that they have **completed** the survey.

**Survey copy (exact wording)**

1. **Multiple choice — AI proficiency**  
   **Prompt:** “Which best describes your current level of proficiency with AI or large language model tools (e.g., ChatGPT, Claude, Gemini)?”  
   **Options (single select):**  
   - **Novice:** I have only tried these tools once or twice.  
   - **Beginner:** I can write simple, single-turn prompts for basic tasks (e.g., answering questions, writing a simple email), but I rarely refine or iterate on the AI's responses.  
   - **Intermediate:** I regularly use these tools to assist with specific workflows. I write detailed, multi-part prompts and frequently iterate (back-and-forth prompting) to steer the AI toward a better output.  
   - **Advanced:** I understand the underlying mechanics (e.g., context windows, model differences) and use advanced techniques (e.g., few-shot prompting, structured data formatting, system instructions) to integrate AI deeply into complex tasks.  

2. **Multiple choice — frequency**  
   **Prompt:** “How frequently do you use an AI chatbot (e.g., ChatGPT, Claude, Gemini)?”  
   **Options (single select):**  
   - Never (I don’t use AI chatbots)  
   - Rarely (Less than 1 time a month)  
   - Sometimes (2-3 times per month)  
   - Often (1-2 times per week)  
   - Very often (multiple times per week or daily)  

3. **Free response**  
   **Prompt:** “What skills do you think are important for creating high-quality AI outputs?”  
   **Input:** Free text (required; implement a reasonable max length and empty/whitespace validation.)

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] The lobby no longer uses the old **How to play** / Bud onboarding carousel for this flow; after join, players see the survey (same lobby area or a dedicated panel—implementation detail) with all three questions and a **Submit** control.  
- [ ] **Validation:** Submit is disabled or blocked until Q1 and Q2 have a selection and Q3 has non-empty substantive text (per product rules); successful submit stores responses server-side (and optionally in analytics DB if the project uses Supabase for similar data).  
- [ ] **Admin panel:** Each non-admin player shows a **pre-survey** state until they submit; after submit, the admin view reflects **pre-survey completed** (or equivalent clear label). Reconnection should not lose completed survey state for the session/game.  
- [ ] Smoke test still passes: multiple players join, complete surveys, Gamemaster can start the game and run at least one round (unless a follow-up story explicitly gates **Start game** on all surveys—if not in scope here, document that Start game behavior is unchanged).

**Do not change** (optional — what to leave alone):  
> Do not change prompting, selection, voting, or results flows unless required to pass survey data to later rounds (out of scope unless specified). Preserve existing lobby join, admin login, and group-assignment behavior unless this story explicitly ties survey to them.

**Depends on** (optional — other stories or data that must exist first):  
> None, unless **Start game** must be blocked until every player has submitted—then align with product and document in a separate story or add a **Done when** bullet here.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (lobby: replace/remove onboarding UI, add survey markup), `static/js/game.js` (survey state, validation, socket events, admin list updates), `static/css/style.css` (survey layout), `app.py` (player state: `survey_completed` / response fields, Socket.IO handlers for submit, payloads to admin on join and on survey updates). If persisting to Supabase: `db.py` and schema for survey answers. Follow **`GUIDELINES.md`** and smoke / **`PLAYTEST_2_TESTING_CHECKLIST.md`** when touching reconnection or admin.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow `GUIDELINES.md`. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
