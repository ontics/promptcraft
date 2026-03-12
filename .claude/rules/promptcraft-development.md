---
description: PromptCraft v2 development — follow GUIDELINES.md for branch strategy, testing, and merges
---

# PromptCraft v2 Development

When working in this codebase:

1. **Read GUIDELINES.md** (at repo root) for branch strategy, codebase structure, testing, and how to use the AI for merges and conflicts. Follow it unless the user explicitly asks otherwise.

2. **Codebase structure**: One HTML file (`templates/index.html`), one main JS file (`static/js/game.js`), and one backend file (`app.py`) cover all screens and logic. Changes in one "screen" (e.g. lobby) often live in the same files as another (e.g. prompting). Prefer minimal, targeted edits and preserve existing behavior outside the user story scope.

3. **Branches**: All new work happens on feature branches from `v2`. Do not merge `v2` into `main` until the team agrees v2 is ready.

4. **Conflicts**: When resolving merge conflicts, combine both sides' behavior where they affect different features; use the guidelines in GUIDELINES.md for AI-assisted conflict resolution.

5. **Testing**: No automated suite yet. Run the app and the smoke test (create game, 2 players, one full round) and use `PLAYTEST_2_TESTING_CHECKLIST.md` when touching reconnection, admin, or voting.
