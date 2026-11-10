# Recipes: instantiating the five contracts per domain

These are worked examples, not templates to follow literally. What transfers between them is the *shape*: a command that yields a number, a small named knob set, a frozen evaluator, a one-command revert. What differs is mostly noise and cost — and those two differences change how the loop should be run.

---

## Hyperparameter / training tuning

| Contract | Typical instantiation |
|---|---|
| Metric | `uv run train.py > logs/N.log 2>&1` then `grep '^val_loss:' logs/N.log`, lower better |
| Knobs | one training file: architecture, optimizer, LR, batch size, schedule |
| Frozen | data prep, tokenizer, eval function, time or step budget |
| Revert | commit per trial, `git reset --hard HEAD~1` |
| Budget | fixed wall-clock per trial makes trials directly comparable — prefer it to fixed epochs |

**Noise:** low with a pinned seed, but not zero (nondeterministic kernels, timing-based stopping). Two baseline repeats usually suffice.

**Watch for:** resource ceilings, which look like bugs and are really findings — log the OOM boundary and stop probing it. A fixed *time* budget rather than a fixed step count keeps trials comparable when a change makes each step cheaper or dearer; it also means "faster" and "better" stop being separate objectives.

---

## Prompt / system-prompt iteration

| Contract | Typical instantiation |
|---|---|
| Metric | eval set of N cases scored by a fixed grader → pass count or mean rubric score, higher better |
| Knobs | named sections of the prompt — role framing, output contract, few-shot examples, ordering |
| Frozen | the eval cases, the grader prompt, the grading model and its temperature |
| Revert | prompt file in git, or numbered variants kept side by side |
| Budget | dominated by eval-set size × repeats; count API calls, not trials |

**Noise is the dominant problem here.** Sampled generations plus an LLM grader means a 5-case eval will happily show ±20% between identical runs. Either grow the eval set until the noise floor is smaller than the effects you care about, or repeat each trial and average — and budget for it. A prompt loop run at n=5 produces confident nonsense; this is the single most common way these runs fail.

**Watch for:** grader drift, which is the frozen-contract violation in disguise. Tuning the grader because "it is judging unfairly" is exactly the move that invalidates the run. If the grader is genuinely wrong, stop, fix it, discard every number measured under the old grader, and re-baseline. Never patch it mid-run and keep going.

Also beware overfitting to the eval set — a prompt tuned against 30 fixed cases through 40 trials has memorized them. Hold out cases from the start and check the winner against them at the end.

---

## Agent harness / memory structure

| Contract | Typical instantiation |
|---|---|
| Metric | task-suite completion rate, or steps/tokens to completion, or both under a stated rule |
| Knobs | memory file layout, what gets summarized and when, retrieval cutoffs, tool-result truncation, context budget split |
| Frozen | the task suite, the scoring rule, the model and its settings |
| Revert | config or harness file in git |
| Budget | slowest trials of any domain — a full suite run is minutes to hours. Plan for tens, not hundreds, of trials |

**Noise:** high, and structured rather than random — agents fail in correlated ways across a suite. Report per-task outcomes, not just the aggregate; a config that fixes three tasks and breaks three others is a different finding from one that changes nothing, and the aggregate hides that completely.

**Watch for:** knobs that interact strongly (truncation limits × summary frequency × context budget). This is the domain where one-at-a-time is least sufficient. When the metric plateaus, run a small grid over the two knobs you most suspect rather than continuing to walk one at a time — and say in the ledger that you did, so the attribution stays honest.

**Because trials are expensive here**, spend more of the budget on hypothesis quality: read the failing transcripts before proposing the next change. One well-grounded trial beats five guesses when each trial costs an hour.

---

## Systems performance / cost

| Contract | Typical instantiation |
|---|---|
| Metric | p95 latency, throughput, bundle size, cloud spend per unit — with the constraint stated ("p95 down, correctness tests still green") |
| Knobs | config values, indexes, cache policy, concurrency limits, algorithm choice |
| Frozen | the benchmark workload, the correctness suite, the hardware/instance class |
| Revert | git, plus a guard command that must pass on every trial |
| Budget | trials are cheap; the risk is measuring on a noisy machine, not running out of trials |

**Noise:** whatever else the machine is doing. Pin what you can, interleave baseline re-measurements every ~10 trials to detect drift, and distrust any single run.

**Watch for:** the guard. Performance work makes correctness regressions easy and tempting. A trial that improves the metric and fails the guard is a discard, always — not a "we will fix it later". Run the guard on every trial, not at the end.
