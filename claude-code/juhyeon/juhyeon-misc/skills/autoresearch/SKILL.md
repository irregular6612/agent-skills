---
name: autoresearch
description: Run an autonomous experiment loop — change one variable, measure, keep or revert, self-debug, repeat — until a target is hit or the budget runs out. Use this whenever something needs to be tuned, optimized, swept, or ablated against a measurable outcome, in ANY domain: hyperparameter tuning, prompt and system-prompt iteration, agent harness or memory-structure changes, retrieval/RAG configs, index and cache settings, latency or cost optimization, threshold search, flaky-test hunting. Trigger it on phrases like "tune this until", "keep iterating until the metric hits X", "sweep these settings", "run an ablation", "optimize X", "밤새 돌려놔", "목표 달성할 때까지 반복해줘", "변수 하나씩 바꿔가며 실험해줘", "여러 설정 비교해줘", "이거 최적화해줘". Also use to resume, inspect, or report on a run started earlier. Reach for it any time more than two trials will be needed — ad-hoc one-off runs lose the comparison.
---

# Experiment Loop

Change one thing. Measure it. Keep it or throw it away. Repeat until the goal is met or the budget is gone.

The domain does not matter. Hyperparameters, a system prompt, an agent's memory layout, a retrieval config, a build flag — if you can name a number that says "better" and a command that produces it, this loop applies.

## The bet this skill makes

A human researcher's bottleneck is patience. Yours is the opposite: you can run a hundred trials without getting bored, but you will happily fool yourself — accept a win that was noise, change three things and credit the wrong one, or quietly rewrite the ruler when the numbers stop moving.

Nearly everything below exists to guard those three failures. The loop itself is trivial. The discipline is the skill. Where a rule below feels like overhead, it is usually buying protection against one of them; skip it knowingly, not by accident.

## Five contracts, agreed before the first trial

Settle these with the user in one batched exchange, then write them into `PLAN.md` (see `references/setup.md`). If the user already gave you enough to fill them in, fill them in and state your reading rather than interrogating them.

**Metric.** One number, one command that produces it, and an explicit direction (lower better / higher better). If reading the result takes judgment, it is not yet a metric — convert it into one (a rubric score, a pass count, a p95 latency) or the loop has no steering wheel. Multiple objectives are fine, but collapse them into a rule written down *now* — "minimize latency subject to accuracy ≥ 0.90" — not one you invent later when a trial is better on one axis and worse on another. That later invention is how motivated reasoning enters.

**Knobs.** What you are allowed to change: which files, which parameters, which sections of a prompt. "Anything in the repo" is not a knob space; it produces results nobody can attribute or reuse. A narrow space explored well beats a wide one sampled at random.

**Frozen.** What must not change: the evaluator, the eval data, the seed policy, the metric definition. This is the load-bearing contract. The moment the ruler moves along with the thing being measured, every number already in the ledger becomes a lie and the run is unsalvageable. If continuing seems to require changing the frozen set, that is a stop-and-ask, not a judgment call.

**Revert.** How one bad trial is undone in one command. Git is the usual answer: a branch for the run, a commit per trial, `git reset --hard` on discard. If the work is not in git, snapshot the knob files into the run directory before touching them. Never plan to just remember what you changed — you will be sixty trials deep and context-compacted.

**Budget.** Trials, wall-clock, or money — whichever binds first — plus a rough per-trial cost. The budget is what makes autonomy safe: the user sets the ceiling once, and inside it you spend without asking.

## Calibrate the noise floor before trusting anything

Run the baseline unchanged at least twice. Three or more times if trials are cheap, or if anything in the pipeline samples — an LLM call, a random seed, wall-clock timing, network latency. The spread you observe is the noise floor.

Any later "improvement" smaller than that spread is not an improvement. It is the same run wearing a different hat.

Spending two or three trials on this feels wasteful and is the highest-return move in the entire run. Without it you spend the night committing coin flips and produce a final report that is confidently wrong.

If the noise floor swamps the effect sizes you expect, fix that before looping: pin seeds, enlarge the eval set, or average N runs per trial (and update the per-trial cost accordingly). A loop whose signal sits under its noise cannot be rescued by running more trials.

## The loop

Repeat until a stop condition below fires.

1. **State the hypothesis in one line first** — what you will change, why you expect it to move the metric, and roughly how much. A trial with a prediction teaches you something whether it wins or loses; a trial without one only teaches you when it wins. Being surprised is the most valuable event in the run, and you cannot be surprised without a prior.

2. **Change one thing.** One knob per trial keeps attribution clean and revert cheap. Batching several changes is allowed when trials are expensive and you have a strong reason — but a batched win owes you an ablation before you believe any story about *why* it won.

3. **Run it, and keep the output out of your context.** Redirect to `logs/<trial>.log`, then grep only the lines you need. One flooded run log can cost more context than ten trials of actual thinking, and context is the scarcest resource in a long autonomous run.

4. **Read the result and compare it against the noise floor**, not against the previous number. "Better than baseline" means "better by more than noise".

5. **Keep or revert immediately**, while you still remember the state. A working tree carrying three half-evaluated changes is how runs become unrecoverable.

6. **Log it** — every trial, including crashes and especially crashes. An unlogged trial will be re-run later by a version of you that has forgotten it.

7. **Write down what you learned**, not just what you measured. "LR above 0.05 diverges" is reusable; "trial 14: 0.9981" is not.

## Judging a trial

- **Better than noise → keep.** Advance the state, commit.
- **Within noise → revert by default**, and record it as *no effect*, which is a real finding. If the change also simplifies things, keep it: equal metric with less complexity is a win.
- **Worse → revert**, and record why you thought it would work. Failed predictions map the space faster than successful ones.
- **Simplicity is a tiebreaker with teeth.** A 0.1% gain that adds twenty lines of special-casing is usually a loss; the same gain from deleting code is unambiguously a win. Complexity you add now is complexity every later trial must reason around.
- **A surprising result outranks a good one.** When something moves much more or much less than predicted, stop and ask why before moving on. That is where the actual understanding is, and it often redirects the rest of the run.

## Broken is not the same as worse

A regression is data. A crash is the *absence* of data — you learned nothing about the hypothesis.

When a trial fails to produce a metric, triage before touching anything: is this a trivial execution slip (typo, missing import, wrong path), an environment or resource limit (OOM, timeout, rate limit), or is the idea itself unworkable? Fix the first kind and re-run. Log the third kind and move on — the idea is refuted.

Bound the middle case. Two or three fix attempts, then log it as blocked and go to the next hypothesis. Debugging rabbit holes are the most common way an overnight run produces nothing: eight hours, one stubborn crash, zero trials.

Repeated crashes of the same shape are themselves a finding. Every larger width OOMing tells you where the ceiling is — record that boundary and stop probing it.

`references/debugging.md` has the triage table and the escape hatches.

## Survive your own context window

Over a long run you will be compacted. The run directory is the memory, not the conversation.

```
.experiments/<tag>/
  PLAN.md      the five contracts, the target, the noise floor   (write once, read on every resume)
  ledger.tsv   one row per trial, append-only
  journal.md   what you learned, dead ends, current hypothesis queue
  logs/        raw run output, one file per trial
```

On resume — after compaction, or in a fresh session — read `PLAN.md`, tail the ledger, read the journal, then continue. Never reconstruct the plan from memory; that is how the frozen contract silently drifts.

`scripts/ledger.py` handles init/append/report so you are not re-deriving TSV plumbing each run. Use it or a shell equivalent, whichever is less friction.

## When ideas run out

Being stuck is a signal to change altitude, not to stop.

- Combine two near-misses; effects that were individually under noise sometimes stack.
- Re-try a change you discarded early — the baseline has moved since, and interactions are real.
- Switch knob families entirely. If you have been tuning magnitudes, change a structure.
- Go read something: the code you have not opened, the library docs, the paper the method came from.
- Take one deliberately large swing. A wild trial is cheap information about the *shape* of the space, which small steps never give you.
- Ablate inward: remove something the baseline has always had. If the metric holds, you have found a simplification win.

## Stopping and reporting

Stop when the target is hit, the budget is spent, or the search is provably dry — K consecutive trials with no gain over noise *and* no untried hypothesis worth its cost. Say "dry" explicitly and stop rather than grinding out filler trials.

Stop and ask the user, mid-run, only when: a change would reach outside the agreed knobs or be hard to reverse; continuing would require moving something in the frozen set; or spend is about to break the budget. Otherwise keep going — do not interrupt an autonomous run to ask whether to continue. The user may be asleep.

The final report states: the best configuration and how to reproduce it; the delta against baseline **with the noise floor quoted next to it**; what worked; what did not and why you expected it to; what remains untried and what it would cost. A run that found nothing is reported as a run that found nothing — with the ledger as evidence that the space was actually searched.

## Anti-patterns

| Pattern | Why it ruins the run |
|---|---|
| Tuning the evaluator when numbers stall | Invalidates every earlier row in the ledger. This is the one unrecoverable mistake. |
| Accepting a delta smaller than the noise floor | You commit coin flips, then build later trials on top of them. |
| Three changes, one trial, a confident story | The story is unfalsifiable and the ledger is now fiction. |
| Piping full run output into context | Burns the resource that limits the whole run. Redirect and grep. |
| Debugging one crash for hours | The budget goes to a rabbit hole instead of the search. Bound it at 2-3 attempts. |
| Stopping to ask "should I keep going?" | The user set a budget so they would not have to answer that. |
| Keeping only the winners in the ledger | Negative results are what stop you re-running the same idea at trial 70. |

## Reference files

- `references/setup.md` — the setup interview, run-directory bootstrap, `PLAN.md` and ledger formats, noise-calibration procedure.
- `references/recipes.md` — how the five contracts instantiate per domain: hyperparameters, prompts, agent harness/memory, systems performance.
- `references/debugging.md` — failure triage table, bounded fix protocol, distinguishing infra flakiness from real regressions.
- `scripts/ledger.py` — `init` / `log` / `report` for the trial ledger. Stdlib only.
