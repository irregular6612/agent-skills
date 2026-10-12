# autoresearch

> **Status: unreviewed.** This skill was drafted from the design notes below but has not been run against real test cases yet — read it critically and expect the loop's judgment calls to need tuning before you trust an overnight run to it.

## Where this came from

[karpathy/autoresearch](https://github.com/karpathy/autoresearch) gave an agent one training file, one metric (`val_bpb`), a fixed five-minute budget, and told it to loop overnight: edit, train, compare, keep or `git reset`, log to a TSV, repeat. The insight was that the researcher's job moves up a level — you stop editing the Python and start editing the `program.md` that programs the agent.

This skill is that idea with the LLM-training specifics dissolved out of it.

## What was kept

Three things turned out to be the load-bearing parts, and none of them are about training:

- **A frozen ruler.** The evaluator, the eval data, and the metric definition cannot move. The original enforced this by making `prepare.py` read-only. Here it is the "Frozen" contract, and violating it is the one unrecoverable mistake in a run.
- **One reversible change per trial.** A commit per trial, a reset on discard. Clean attribution and cheap undo are what let the loop run unattended.
- **An append-only ledger, crashes included.** `results.tsv` became `ledger.tsv`. Negative results are the point: they are what stops trial 70 from repeating trial 6.

Plus the softer ones worth carrying over: the simplicity tiebreaker (a tiny gain that adds ugly complexity is a loss; the same gain from deleting code is a win), bounded crash-debugging, and not stopping to ask permission mid-run when the user has already set a budget.

## What was generalized

The original assumes a domain where a single run is a signal — one GPU, a pinned seed, a near-deterministic result. Most tuning is not like that.

- **A noise floor, measured before the loop starts.** Baseline repeated 2-3×; anything smaller than that spread is not an improvement. Prompt and agent-harness evals routinely swing ±20% between identical runs, and without this step an overnight run just commits coin flips.
- **The five contracts** (Metric / Knobs / Frozen / Revert / Budget) replace the hardcoded `train.py` + `val_bpb` + five minutes, so the same loop covers hyperparameters, prompts, agent memory structure, and systems performance. `references/recipes.md` instantiates each.
- **A durable run directory** (`.experiments/<tag>/`). A hundred trials guarantees context compaction, so the plan, the ledger, and the journal live on disk — the loop resumes by reading them rather than by remembering.
- **Explicit failure triage.** A crash is not a result. Classifying it (execution slip / resource ceiling / unworkable idea / flake / broken harness) decides whether to fix it in thirty seconds or never fix it at all.

## Layout

```
SKILL.md                the loop and the principles behind it
references/setup.md     setup interview, run-dir bootstrap, PLAN.md and ledger formats
references/recipes.md   the five contracts per domain
references/debugging.md failure triage, bounded fix attempts
scripts/ledger.py       init / log / report for the trial ledger (stdlib only)
```
