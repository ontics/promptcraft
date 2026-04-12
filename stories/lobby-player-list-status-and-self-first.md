# User story: Lobby player list — status (Waiting / Ready orange vs green) and “you” first

---

**Area** (where in the app this lives — pick one or list screens):  
- [x] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [ ] Voting screen  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [x] Admin / gamemaster *(assign-groups action switches **Ready** from orange to **green** on the player-facing list; admin dashboard may stay as-is unless we align wording)*  
- [x] Other: **Player list ordering + visual emphasis for “current user” row**

**What to do** (one or two sentences in plain language):  
> Update the **lobby player list** (the list every player sees in the lobby) so each non-admin row shows a clear **status**: **Waiting** if they have **not** finished the pre-survey; **Ready** (styled in **orange**) once pre-survey is **complete** and they have **no** group yet; after the Gamemaster **assigns groups**, the label stays **Ready** but the pill is styled **green** so “survey done + grouped” reads as progression without a separate word like “Assigned.”  
> In **each player’s own view**, their alias (e.g. “Rhino”) must **always appear at the top** of the list, **regardless of join order**. Other players follow below in a consistent order (e.g. existing server order or alphabetical — implementation detail, but “you” is never buried).  
> Add or specify **additional visual cues** so it is obvious which row is “me” beyond position alone (see **Visual cues (suggestions)** below — implement a coherent subset, not every idea).

**Visual cues (suggestions)** — product/design: pick a **small set** that fits PromptCraft’s look; accessibility counts.

- **“You” / “Your seat” badge** — a compact pill next to the alias (e.g. `You` or `Your alias`) using a distinct but calm color.  
- **Row treatment** — subtle **background tint** or **left accent border** on the self row only (avoid clashing with team badges later).  
- **Icon** — small **person** or **pin** icon on the self row (with `aria-hidden` if decorative; meaningful label for screen readers).  
- **Typography** — **slightly bolder** alias for self, or a single-line **caption** under the name: “You are playing as this alias.”  
- **Focus / semantics** — `aria-label` on the row including name + status; optional `aria-current="true"` on “you” row if it matches pattern guidance.  
- **Motion** — optional **very subtle** highlight on first paint after join (once); avoid distracting animation.

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] Lobby list shows **Waiting** for any non-admin who has **not** completed the pre-survey; **Ready** in **orange** once `survey_completed` (or equivalent) is true **and** they have **no** team/group yet; after **Assign Groups** gives them a team, the pill still reads **Ready** but uses **green** styling. Admin row (Gamemaster) handling stays correct and does not break the list.  
- [ ] **Self row:** In the browser session for a logged-in player, **their** alias row is **always first** in the list; order for other players is stable and predictable. Reconnect / `lobby_players_update` does not break this rule.  
- [ ] At least **one** extra “this is you” cue beyond sort order is implemented (from suggestions or an equivalent agreed in review), with reasonable contrast and mobile layout. Smoke: two players + admin — **Waiting → Ready (orange) → Ready (green)** through pre-survey submit and assign groups.

**Do not change** (optional — what to leave alone):  
> Do not remove or weaken **pre-survey** flow, **Assign Groups**, or **Start Game / Onboarding** behavior unless this story explicitly requires a small hook. Preserve Gamemaster dashboard team controls and existing `survey_completed` / server fields; **extend** lobby list rendering and payloads only as needed for status text and ordering.

**Depends on** (optional — other stories or data that must exist first):  
> **Pre-survey** (`survey_completed` / lobby survey) and **team assignment** after “Assign Groups” must already exist so status logic can key off the same flags the server already sends (`survey_completed`, `team`, etc.). See **`stories/lobby-pre-survey-replace-how-to-play.md`** and group-assignment stories.

**Files likely involved** (optional — helps the AI and you focus):  
> `templates/index.html` (player list markup if structure changes), `static/js/game.js` (`updatePlayerList`, `lobby_players_update` / `game_joined` handlers — sort “self” first, render status + classes), `static/css/style.css` (Waiting; **Ready** orange vs **Ready** green; self-row emphasis). `app.py` only if `lobby_player_row` must add explicit `lobby_status` for the client; prefer deriving from existing `survey_completed` + `team` + `is_admin` to avoid duplicate state.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
