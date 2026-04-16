# User story: Replace post-survey question set + enforce white text

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [x] Post Survey  
- [ ] Admin / gamemaster  
- [x] Other: **`static/css/style.css`** *(all post-survey text legibility rules)*

**What to do** (one or two sentences in plain language):  
> Replace the existing post-survey questions with the exact question set below (same survey screen/flow unless another story changes flow). Keep all new questions required where the current survey is required.  
> Ensure **all text in the post-survey UI is white** for legibility: **`#FFFFFF`** (titles, prompts, labels, matrix headers, row labels, helper/error text, and button text if rendered on the survey card).
> Persist each player’s responses by their unique player/session identifier (UID) in the database, and ensure those responses remain linked to that player’s gameplay records (prompts, generated images, selections/voting behavior, and related game rows) for downstream analysis.

**Question set to implement (replace existing content):**

**Section 1 — Free Response Questions (required):**
- What was your thought process when allocating points in voting?
- How did you decide when to give an image more or less points than another image in the same round of voting?
- During image creation, what information, if any, was displayed about your prompting?
- On the voting screen, what information, if any, was displayed about the images?

**Section 2 — Self-Evaluation (required):**  
Use 5-point agreement scale for each row:  
Strongly Disagree · Disagree · Neutral · Agree · Strongly Agree
- The images I submitted for voting represented my best work:
- The images I submitted for voting represented significant effort on my part:

**Section 3 — Evaluating Peers (required):**  
For each stem below, use the same 5-point comparative columns:  
Far Less · Somewhat Less · The Same · Somewhat More · Far More  
Rows for each stem: Creative · Precise · Skilled · Efficient

Stems:
- A person who submits longer prompts is:
- A person who submits more prompts is:
- A person who takes more time to submit prompts is:
- A person who uses more variable vocabulary in their prompts is:

**Section 4 — Voting Experience Agreement (required):**  
Prompt: “Please read the following statements and evaluate how strongly you agree or disagree based on your experience voting in the game.”  
Scale columns: Strongly Disagree · Disagree · Neutral · Agree · Strongly Agree
- I voted for images based purely on their visual similarity to the target image
- I considered prompt count when voting for images.
- I considered total prompt word count when voting for images.
- I considered the time spent prompting when voting for images.
- I value AI generated images more when I believe they are not easily created.
- A player who successfully recreated the target image in just one or two prompts better understands the AI model.
- Requiring dozens of prompts to achieve a good result is a sign of poor skill at prompting AI models.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] The post-survey displays exactly the four sections and prompts above, replacing the previous question set on that screen.  
- [ ] Validation requires responses for all required items (free-response fields + each Likert/matrix row) before submit succeeds.  
- [ ] All post-survey text is rendered in **`#FFFFFF`** and remains legible across desktop/mobile layouts.
- [ ] Survey responses are stored per player UID in DB and can be joined back to that player’s gameplay behavior records (prompts/images/voting-related data) without ambiguity.

**Do not change** (optional — what to leave alone):  
> Do not change player ordering/results logic, voting assignment logic, or unrelated onboarding/lobby/gameplay flows. Keep survey entry/exit flow unchanged unless a separate story requests flow changes.

**Depends on** (optional — other stories or data that must exist first):  
> None. If DB schema/keys change for persistence, include only minimal survey-related updates and preserve UID linkage to existing gameplay tables/rows.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (post-survey markup), `static/js/game.js` (survey validation + payload construction), `app.py` (server-side validation/parsing), `db.py` (extended survey persistence), `static/css/style.css` (force post-survey text color to `#FFFFFF`).

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
