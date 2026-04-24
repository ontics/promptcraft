# Vote 10 synthetic pool images (E1–E5)

`voting_fixtures_config/HU/round10_synthetic_pool.json` references paths under the HU static mount, e.g.:

`/static/voting_fixtures/HU/synthetic_pool/E1.png` … `E5.png`

## If the UI looks like “empty” color cards

- **The app is usually loading the right URLs.** The allocation screen uses a large square (`object-fit: cover` on `.allocation-opt-img`), so **small** test images (e.g. 64×64) look like a **flat field of one color** at full size—not a 404, just upscaling.
- Bundled defaults are **placeholders** until you replace them with your study stimuli. **Overwrite `E1.png`…`E5.png`** in this folder (keep names, or change the `image` paths in the JSON) and do a **hard refresh** in the browser (or clear cache) so the browser reloads the files.

## Optional

- Use images at **similar resolution** to your real game images (e.g. 512×512 or larger) so heuristics and layout look like production.
- After editing only PNGs (not the JSON), the server’s pool cache is still fine: URLs are unchanged. If something looks stuck, try a **hard refresh** in case the **browser** cached the old PNG.
