# User story: HU voting fixtures — candidate images A1.1 … C3.3

---

**Area** (where in the app this lives — pick one or list screens):  
- [ ] Lobby  
- [ ] Onboarding  
- [ ] Prompting screen (game play)  
- [ ] Transition screen  
- [ ] Selection screen  
- [x] Voting screen *(allocation rounds **1–9** only — hard-coded HU fixtures)*  
- [ ] Results / Winner screen  
- [ ] Game over  
- [ ] Post Survey  
- [ ] Admin / gamemaster  
- [x] Other: **`voting_fixtures_config/HU/`** (JSON + image assets mirrored under static)

**What to do** (one or two sentences in plain language):  
> New candidate images exist under **`voting_fixtures_config/HU/images/`** with names **`A1.1` … `C3.3`** (use the real file extension on disk, e.g. `.png`). **Letter** = target group: **A = Oski**, **B = Tree**, **C = Slug**. **First number** = which voting round **within that group** (1, 2, or 3). **Second number** = **slot position** on the allocation voting page (**1**, **2**, **3** = left-to-right order of the three candidates in that round’s JSON array).  
> Update **each** of `round_01.json` … `round_09.json` so every candidate’s **`image`** field points at the correct file (relative path under the pack’s static mount — see below). Do **not** change round 10 (live peer images). Do **not** change `fixture_image_id`, heuristics, `fixture_set_key`, or target image fields unless a separate story requires it.

**Mapping (round file → candidate slots → basename):**

| Round file   | Group (letter) | Within-group index | Candidate order (JSON index 0, 1, 2) → filename |
|-------------|----------------|--------------------|---------------------------------------------------|
| `round_01.json` | A | 1 | `A1.1`, `A1.2`, `A1.3` |
| `round_02.json` | A | 2 | `A2.1`, `A2.2`, `A2.3` |
| `round_03.json` | A | 3 | `A3.1`, `A3.2`, `A3.3` |
| `round_04.json` | B | 1 | `B1.1`, `B1.2`, `B1.3` |
| `round_05.json` | B | 2 | `B2.1`, `B2.2`, `B2.3` |
| `round_06.json` | B | 3 | `B3.1`, `B3.2`, `B3.3` |
| `round_07.json` | C | 1 | `C1.1`, `C1.2`, `C1.3` |
| `round_08.json` | C | 2 | `C2.1`, `C2.2`, `C2.3` |
| `round_09.json` | C | 3 | `C3.1`, `C3.2`, `C3.3` |

**Done when** (how we know it's finished — 1–3 bullets):  
- [ ] All nine `voting_fixtures_config/HU/rounds/round_*.json` files reference the new images (paths consistent with **`manifest.json`** `static_mount`, typically `/static/voting_fixtures/HU/` — e.g. `images/A1.1.png` resolves to a URL under that mount).  
- [ ] In a local run, allocation voting rounds **1–9** show the new images in the correct slots (Oski / Tree / Slug groups match **A / B / C** as above).  
- [ ] **Round 10**, onboarding-only fixtures, and non-HU packs are unchanged.

**Do not change** (optional — what to leave alone):  
> `ballot_balancer.py`, `assign_final_ballots`, round-10 logic, `TOTAL_VOTING_ROUNDS`, fixture **group membership** (rounds 1–3 Oski, 4–6 Tree, 7–9 Slug), heuristics numbers, or `voting_fixture_loader.py` unless this story’s paths require a documented exception. Prefer **only** JSON path updates plus ensuring files exist where the browser loads them.

**Depends on** (optional — other stories or data that must exist first):  
> Image files present with the agreed names (and extension). **Note:** `voting_fixture_loader.py` joins each candidate **`image`** path to `static_mount` from `manifest.json`; files must be served from the Flask **`static/`** tree (e.g. **`static/voting_fixtures/HU/images/`** with the same relative path segment as in JSON). If assets were added only under `voting_fixtures_config/HU/images/`, copy or move them to the matching **`static/voting_fixtures/HU/images/`** location (or handle in a separate story that changes loading).

**Files likely involved** (optional — helps the AI and you focus):  
> `voting_fixtures_config/HU/rounds/round_01.json` … `round_09.json`, `static/voting_fixtures/HU/images/` *(or equivalent under `static_mount`)*, optionally `voting_fixtures_config/HU/manifest.json` only if `static_mount` / layout must change.

---

*For the AI: When implementing this story, change only the area(s) and files above. Preserve all other behavior. Follow GUIDELINES.md. After implementing, ask the developer to test whether it worked (e.g. run the app and check the "Done when" criteria).*
