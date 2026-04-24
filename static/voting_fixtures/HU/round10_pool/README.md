# Round 10 synthetic pool images

Place up to **five** PNG (or other static) files here for **Vote 10** filler slots when there are fewer than four eligible peer submissions or a player is missing a Round 3 selection.

1. Add your files in this folder (for example `synth_01.png`, …).
2. Edit `voting_fixtures_config/HU/round10_synthetic_pool.json` so each `candidates[].image` is a path **relative to** the HU pack `static_mount` (`/static/voting_fixtures/HU/`), e.g. `round10_pool/synth_01.png`.
3. Fill `heuristics` on each candidate like the `rounds/round_*.json` files (optional keys are fine).

Until you add custom assets, the bundled JSON may reference existing `options/*.svg` placeholders.
