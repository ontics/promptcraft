# Proposal: Low-latency “prompt complexity” (perplexity-style) scoring

This document proposes how to replace the **deterministic placeholder** complexity score with a real metric that behaves like **normalized perplexity**, while staying compatible with **Railway** (Python server) and **Supabase** (storage only).

## What perplexity would mean here

**Perplexity** (in language modeling) measures how “surprised” a model is by a token sequence: lower perplexity ⇒ the model finds the text more predictable; higher ⇒ more surprising / less predictable given the model’s training. It is **not** inherently “good” or “bad” for creative prompts—it's a **descriptive** statistic for your experiment.

For Promptcraft, the useful object is usually **per-prompt** complexity, optionally **aggregated** across the round (mean, max, or last value).

## Recommended low-latency approach: Gemini text model on the prompt only

You already call **Gemini** for image generation (`gemini-2.5-flash-image`). The lowest-integration path is to call a **Gemini text model** on the **user prompt string only** (no image, no target caption) and derive a score from the response.

### Option A — Use log-probs if exposed (best when available)

Some APIs expose **token log-probabilities** for generated or scored text. If the Gemini API you use can return **negative log-likelihood per token** for the prompt (or for a “prompt scoring” endpoint), perplexity is:

\[
\text{PP} = \exp\left(-\frac{1}{T}\sum_{t=1}^{T} \log p(x_t \mid x_{<t})\right)
\]

**Normalized display (0–1):** map \(\log \text{PP}\) to a percentile or min–max window across your pilot corpus, e.g.

- collect \(\log \text{PP}\) for all prompts in a session or study wave;
- let \(q_{10}\), \(q_{90}\) be empirical quantiles;
- `complexity_01 = clip((log_pp - q_10) / (q_90 - q_10), 0, 1)`.

**Latency:** one batched scoring call per prompt; typically **~200–800 ms** depending on model and length (much faster than image gen).

### Option B — Surrogate “complexity” without true perplexity (always feasible)

If log-probs are not available, use a **cheap proxy** from the same Gemini text model:

- **Lexical:** word count, character count, digit count, punctuation density (you already track word count).
- **Model-based surrogate:** ask the model to output a **JSON** score 1–10 for “syntactic/lexical complexity” with a strict rubric, **or** use embedding distance to a corpus of “simple” vs “complex” exemplars.

This is **not** perplexity, but can be **stable and fast** and labeled honestly in analytics as `complexity_proxy_v1`.

**Latency:** similar to a short chat completion.

### Option C — Local small LM (extra moving parts)

Run a tiny open model on Railway for true perplexity. **Pros:** full control. **Cons:** cold start, memory, another artifact pipeline—usually **higher lift** than Option A/B for a pilot.

## Practical ranges: what players might see

True perplexity is **unbounded** in theory; in practice on short user prompts you often see **tight clusters** unless prompts are very heterogeneous.

For **pilot UI** (percentage or low/medium/high):

| Presentation | Suggestion |
|--------------|------------|
| **Percentage (20–80%)** | Only if you **calibrate** on pilot data; without calibration, most prompts may cluster (e.g. 35–55%) and look “samey.” Prefer **wider mapping** using quantiles (see above). |
| **Low / medium / high** | Often clearer for participants. Example on **within-round** quantiles: low = bottom third, medium = middle third, high = top third **of that player’s own prompts that round** (always interpretable). |
| **Across all players** | Use **session-wide** quantiles so “high” means “high relative to everyone in this run.” |

**Does it change as prompts accrue?**  
- **Per-prompt score:** each new prompt gets its **own** value; earlier prompts’ scores need not change.  
- **Aggregate “round complexity”** (mean/max of prompt scores): **yes**, it changes as new prompts arrive until the round ends.

## Recommendation for production evolution

1. **Ship placeholder** (current): deterministic, stable, zero latency.  
2. **Add Gemini text scoring** behind a feature flag: try **log-prob perplexity** first; fall back to **JSON rubric proxy**.  
3. **Store raw + normalized:** e.g. `perplexity_raw`, `perplexity_log`, `complexity_normalized_01`, `complexity_bucket`, `scoring_method`.  
4. **Refresh Supabase analytics** with batch re-scoring if you change models (version column).

## References in-repo

- Game code: `heuristics.py` (`placeholder_perplexity_normalized`, registry).
- DB: `prompts.word_count`, `prompts.perplexity_normalized` (once columns exist—see `sql/experiment_voting_schema.sql`).
