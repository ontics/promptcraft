# PromptCraft v2 — Development Guidelines

This document is for **developers and AI assistants** (Cursor, Claude Code, etc.). When making changes, follow these principles so we keep behavior consistent and avoid breaking other parts of the game.

---

## 1. Codebase structure (important for avoiding conflicts)

- **Single HTML file**: `templates/index.html` contains **all** screens in one file: lobby, game (prompting), transition, selection, voting, results, game over. Editing "the lobby" and "the prompting screen" often means editing the same file in different sections.
- **Single JS file**: `static/js/game.js` handles all client logic for every screen. Lobby, prompting, selection, and voting logic live in this one file.
- **Single backend file**: `app.py` has all Flask routes and Socket.IO handlers (join, teams, prompts, character/Bud/Spud, selection, voting, etc.).
- **Shared CSS**: `static/css/style.css` styles the whole app.

**Implication**: When two people work in parallel (e.g. one on lobby, one on prompting screen), they will often touch the same files. Merge conflicts are normal. Resolve them by **keeping both sets of changes** where they affect different screens or features; use the AI to help combine conflict blocks.

---

## 2. Branch strategy

- **`main`**: Treated as the stable / v1 baseline. Do **not** merge `v2` into `main` until the whole team is satisfied with v2 and ready to release.
- **`v2`**: The integration branch for all v2 work. All feature branches are created from `v2` and merged back into `v2` via Pull Requests.
- **Feature branches**: One branch per user story (or per logical chunk), e.g. `feature/remove-bud-spud`, `feature/lobby-auto-alias`, `feature/selection-heuristics`. Always branch from an up-to-date `v2`.

---

## 3. Collaborative development

- **One feature branch per person per story** — don’t all work on the same branch.
- **Pull before you start**: `git checkout v2 && git pull origin v2` before creating a new feature branch.
- **Merge order**: Respect dependencies between user stories. If Story B depends on Story A (e.g. backend change before frontend), merge A’s PR first, then pull `v2` and create B’s branch from the updated `v2`.
- **After merging a PR**: Whoever merges (or the next person to work) should run the app and do the smoke test (see below) to catch integration issues.

---

## 4. Testing and breaking changes

- **No automated test suite yet.** Rely on:
  - **Smoke test**: Start app → create game → 2 players → one full round (prompt → generate → selection → vote).
  - **Playtest 2 Testing Checklist** (`PLAYTEST_2_TESTING_CHECKLIST.md`) for reconnection, admin, voting, and error-image scenarios when your change touches those areas.
- **Before merging a PR**: Author runs the app and smoke test (and relevant checklist scenarios) on their branch.
- **After merging to v2**: Run the same checks on `v2` to ensure the combined code still works.

---

## 5. Using the AI for merges and PRs

- **Before pushing**: You can paste `git diff` (or the changed files) into the AI and ask: “Review this diff for the [feature name] branch — does it look correct and did I miss any call sites or related logic?” This helps catch obvious mistakes before the PR.
- **When you have merge conflicts**: Open the conflicted file(s). You’ll see `<<<<<<<`, `=======`, `>>>>>>>`. Paste the conflicted section(s) into the AI and say: “Resolve this merge conflict. Our branch did [X], the other branch did [Y]. We need both behaviors.” Then apply the suggested resolution and remove the conflict markers.
- **Don’t merge v2 into main** until the team has agreed that v2 is ready; say so in PRs and in the demo so everyone remembers.

---

## 6. Code and UX consistency

- **Preserve existing behavior** unless the user story explicitly changes it. When removing a feature (e.g. Bud/Spud), remove or stub the related logic in both frontend and backend so the app doesn’t reference undefined state.
- **Game flow**: Lobby → Game (prompting) → Transition → Selection → Voting → Results (between rounds) → Game Over (after round 3). User stories may add or remove screens (e.g. pre-survey, “shuffling into new group” screen); keep the flow documented in this file or in the user-story list.
- **Naming**: Prefer clear names (e.g. `player-display-name`, `selection-gallery`). If you add new IDs or classes, make them consistent with existing patterns in `index.html` and `game.js`.

---

## 7. User stories and owners

User stories are organized by interface area (Lobby, Prompting, Selection, Voting, Winner/Results, Post-game). See the project’s user-story list or DEMO_GUIDE for the full list and dependencies. When implementing:

- Implement only what the user story asks for; avoid scope creep.
- If a story depends on another (e.g. “game data structure must include heuristic data”), implement or merge the dependency first.

---

**Summary for the AI**: When editing PromptCraft, prefer minimal changes that match the user story; preserve behavior elsewhere; and assume multiple developers may be editing the same few files (index.html, game.js, app.py) — resolve conflicts by combining both sides’ intent where possible. Always refer to this file when unsure about branch strategy, testing, or merge process.
