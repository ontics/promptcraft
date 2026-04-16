# User story: Post-survey update — required responses, white text, UID-linked storage, per-player start

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [x] Voting screen *(post-survey trigger changes to per-player start)*  
- [x] Results / Winner screen *(waiting state if results are not ready yet)*  
- [ ] Game over  
- [x] Post Survey  
- [x] Admin / gamemaster *(progress visibility may be needed for mixed voting/survey phases)*  
- [x] Other: _______________ *(DB persistence + per-player flow orchestration)*

**What to do** (one or two sentences in plain language):  
> Update the post-game survey so that all questions are required, all survey text is white (`#FFFFFFFF` / `#FFFFFF`) for legibility, and all survey responses are persisted in the database keyed to each player UID and linked to gameplay behavior records.  
> Change survey flow so each player starts post-survey immediately after that player finishes voting (without waiting for others); if final results are not yet available when they submit, show a waiting screen with the message **"waiting for players to finish voting"** until results are ready.

**Survey questions to implement (replace prior survey set):**

**Free Response Questions**
1. What was your thought process when allocating points in voting?  
2. How did you decide when to give an image more or less points than another image in the same round of voting?  
3. During image creation, what information, if any, was displayed about your prompting?  
4. On the voting screen, what information, if any, was displayed about the images?

**Self-Evaluation**
- The images I submitted for voting represented my best work:  
- The images I submitted for voting represented significant effort on my part:  
Scale for both: **Strongly Disagree / Disagree / Neutral / Agree / Strongly Agree**

**Evaluating Peers**
For each stem below, evaluate each row (**Creative / Precise / Skilled / Efficient**) on:  
**Far Less / Somewhat Less / The Same / Somewhat More / Far More**

Stems:
- A person who submits longer prompts is:  
- A person who submits more prompts is:  
- A person who takes more time to submit prompts is:  
- A person who uses more variable vocabulary in their prompts is:

**Voting Experience Agreement**
Prompt text:  
“Please read the following statements and evaluate how strongly you agree or disagree based on your experience voting in the game.”

Scale: **Strongly Disagree / Disagree / Neutral / Agree / Strongly Agree**

Statements:
- I voted for images based purely on their visual similarity to the target image  
- I considered prompt count when voting for images.  
- I considered total prompt word count when voting for images.  
- I considered the time spent prompting when voting for images.  
- I value AI generated images more when I believe they are not easily created.  
- A player who successfully recreated the target image in just one or two prompts better understands the AI model.  
- Requiring dozens of prompts to achieve a good result is a sign of poor skill at prompting AI models.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Every survey item above is required and submission is blocked until fully complete.  
- [ ] All survey text (titles, questions, labels, helper/error copy) renders in white (`#FFFFFFFF` / `#FFFFFF`) and remains legible.  
- [ ] Survey answers are saved per player UID and can be joined to gameplay behavior data (prompts, generated images, timestamps, voting/selection metadata).  
- [ ] A player enters post-survey immediately after finishing their own voting; if results are pending, they see a waiting screen with **"waiting for players to finish voting"** and are advanced to results when ready.

**Do not change** (optional — what to leave alone):  
> Do not change player ranking/order logic, voting assignment logic, or scoring rules. Do not change unrelated lobby/onboarding/gameplay UI outside what is needed for this survey flow and waiting state.

**Depends on** (optional — other stories or data that must exist first):  
> None. If schema updates are needed, keep them minimal and specific to required survey persistence and UID linkage.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (survey structure + waiting state UI), `static/js/game.js` (required validation, per-player transition logic, waiting screen handling), `app.py` (per-player post-survey trigger after individual voting completion + results-ready handoff), `db.py` and SQL migration(s) (UID-keyed persistence and behavior-link fields), `static/css/style.css` (white text enforcement and waiting state styling).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
