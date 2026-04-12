# Voting fixture configuration (hard-coded rounds 1–9)

Round **10** is always built from real player submissions in `app.py` (not configured here).

## Layout

- **`HU/`** — Heuristic-visible conditions (`C_HU`, `T_HU`). Colleagues can edit JSON + swap images under `static/voting_fixtures/HU/` without touching Python.
- **`HU/manifest.json`** — Ordered list of round definition files.
- **`HU/rounds/round_XX.json`** — One object per voting round (see schema below).

## Web assets (served by Flask)

Place images next to JSON references under:

`promptcraft/static/voting_fixtures/HU/`

Paths in JSON are usually **relative to that folder** (e.g. `options/slot_a.svg` → `/static/voting_fixtures/HU/options/slot_a.svg`). You may also use an **absolute** URL path starting with `/static/...` (e.g. game targets `/static/images/target1.jpg` for Oski / round 1, `target2.jpg` for tree / round 2, `target3.jpg` for slug / round 3).

## Round JSON schema

```json
{
  "fixture_set_key": "hu_pilot_01",
  "target_profile": "oski",
  "target_image": "/static/images/target1.jpg",
  "candidates": [
    {
      "fixture_image_id": "hu01_a",
      "image": "options/slot_a.svg",
      "heuristics": {
        "number_of_prompts": 4,
        "total_word_count": 62,
        "time_in_round_seconds": 123
      }
    }
  ]
}
```

- **`fixture_set_key`**: Stored on `voting_rounds.fixture_set_key` for analytics.
- **`target_profile`**: Documentation only (`oski` | `tree` | `slug`); not sent to clients.
- **`target_image`**: Relative path under the HU static folder, or absolute `/static/...` for shared game assets.
- **`candidates`**: Exactly **three** options (left). Each **`image`** is relative or absolute like **`target_image`**; **`heuristics`** map to the three UI lines:
  - `number_of_prompts` → “Prompt” count  
  - `total_word_count` → “Words (this prompt)”  
  - `time_in_round_seconds` → “Time in round” as `M:SS` (0–300 typical)

To add another condition pack later (e.g. `C_NA/`), copy `HU/`, point a new loader entry at `manifest.json`, and wire `get_fixture_pack_key(condition)` in `voting_fixture_loader.py`.
