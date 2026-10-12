# Setup: turning a vague goal into a runnable loop

Read this when starting a new run, or when a user's request is a goal ("make retrieval better") rather than a loop.

## The interview

Ask in one batched exchange. Fill in whatever the user already implied and state your reading instead of asking — a setup interrogation before a single trial has run is its own kind of failure.

1. **What counts as better, as a number?** Push until you get a command and a direction. "Faster" becomes `hyperfine ... | grep mean`, lower better. "Better answers" becomes a graded eval set with a pass count, higher better. If they genuinely cannot name one, build the smallest possible scorer first and treat *that* as the deliverable — a loop without a metric is not a loop.
2. **What may change, and what may not?** The frozen set matters more than the knob set. Ask explicitly: "is the eval itself off-limits?" The answer is almost always yes, and saying it out loud prevents the drift.
3. **What does one trial cost, in time and money?** This sets everything downstream: how many repeats you can afford per trial, whether batching changes is justified, how many trials fit the budget.
4. **What is the budget and the target?** Both a stop condition ("stop at 0.95" ) and a ceiling ("stop after 40 trials / 6 hours / $20"). Either alone leaves the loop unbounded in one direction.
5. **How is a trial reverted?** Confirm git is clean and usable, or agree on a snapshot directory.

## Bootstrap

```bash
TAG=$(date +%b%d)                     # or a name the user picks
mkdir -p .experiments/$TAG/logs
git checkout -b experiment/$TAG        # when the knobs live in git
python3 ~/.claude/skills/experiment-loop/scripts/ledger.py init .experiments/$TAG
```

Keep `.experiments/` out of version control unless the user wants the run itself committed — mixing ledger churn into the trial commits makes `git reset` on discard messy.

## PLAN.md

Write once, at setup. Read on every resume. Keep it short enough that re-reading it is free.

```markdown
# Experiment: <tag>

**Goal**      <one sentence>
**Target**    <metric value that ends the run, or "explore until budget">

## Metric
Command:    <exact command>
Read with:  <exact grep/parse>
Direction:  lower better | higher better
Tiebreak:   <secondary rule, e.g. "on ties prefer fewer tokens">

## Knobs
- <file or parameter> — <allowed range / nature of change>

## Frozen — changing any of these invalidates the run
- <evaluator file / eval data / seed policy / metric definition>

## Revert
<exact command, e.g. `git reset --hard HEAD~1`>

## Budget
<N trials | H hours | $X>   ·   ~<cost> per trial

## Baseline
value: <v>   ·   noise floor: ±<s> over <k> repeats   ·   measured <when>
```

## Ledger

Tab-separated, one row per trial, append-only. Tabs because descriptions contain commas.

```
trial	ref	metric	status	knob	note
1	a1b2c3d	0.9979	baseline	-	unchanged, repeat 1 of 3
4	e5f6a7b	0.9932	keep	lr 0.02->0.04	as predicted, ~0.005 gain
5	-	0.9975	discard	activation gelu	within noise, reverted
6	-	-	crash	width 2x	OOM at 46GB, ceiling found
7	-	-	blocked	async dataloader	3 fix attempts, deadlocks, parked
```

`status` is one of `baseline` `keep` `discard` `crash` `blocked`. `ref` is the commit or snapshot id for kept trials, `-` otherwise. Log the crashes; the whole point of the ledger is that trial 70 does not repeat trial 6.

## Noise calibration

```bash
for i in 1 2 3; do
  <metric command> > .experiments/$TAG/logs/baseline-$i.log 2>&1
  <parse command>  .experiments/$TAG/logs/baseline-$i.log
done
```

Record min, max, and the spread in `PLAN.md`. Use the **full spread**, not a standard deviation, as the threshold — with three samples a stddev is a fiction and the spread is at least an honest lower bound on how much the system moves on its own.

If the spread is larger than the improvement the user is hoping for, say so immediately and fix the measurement before running the loop. This is worth interrupting for: it changes what the run can possibly deliver.

## journal.md

Free-form, appended as you go. This is where the reusable knowledge lives — the ledger holds numbers, the journal holds understanding.

```markdown
## trial 12 — batch size 32 -> 64
Predicted small gain from better gradient estimates. Got 0.4% worse.
Guess: LR is now mistuned for the larger batch. Queued: retry 64 with LR x1.4.

## standing conclusions
- LR above 0.05 diverges within 200 steps. Do not retry.
- Memory-layout knobs dominate prompt-wording knobs by ~5x. Spend budget there.

## hypothesis queue
- [ ] retry batch 64 with scaled LR
- [ ] ablate the summary block out of the memory file entirely
```

Keep a hypothesis queue. It is what you read when you feel out of ideas at trial 50, and it is what makes a resumed run continue instead of restart.
