# Debugging inside the loop

A crash is not a result. It tells you nothing about the hypothesis, and it costs budget that produces no data. The job here is to spend as little as possible getting back to trials — while making sure the failures that *are* informative get recorded as findings rather than thrown away.

## Triage first, fix second

Before editing anything, read the tail of the log and classify:

| Class | Signal | Response |
|---|---|---|
| **Execution slip** | typo, missing import, wrong path, bad argument | Fix and re-run. Does not count as a trial. |
| **Resource limit** | OOM, timeout, rate limit, disk full | The idea is refuted *at this size*. Log the boundary, do not fight it. |
| **Idea is unworkable** | shape mismatch, unsupported op, API rejects the config | Log `crash`, move to the next hypothesis. This is a real, useful negative result. |
| **Infra flake** | network blip, transient 5xx, another process interfering | Re-run once. If it reproduces, it is not a flake — reclassify. |
| **You broke the frozen set** | evaluator errors, eval data missing, metric parses differently | Stop the loop. Restore the frozen set, verify the baseline still reproduces, then continue. |

Classification matters because the responses are opposites: an execution slip should be fixed in thirty seconds, and an unworkable idea should not be fixed at all.

## Bound the fix attempts

Two or three attempts, then log `blocked` with a one-line reason and move on. Add it to the journal's hypothesis queue if it still seems worth returning to.

This bound is the whole point. The failure mode it prevents — eight hours of autonomous time spent on one stubborn crash, zero trials completed — is by far the most common way an overnight run delivers nothing. A parked hypothesis costs one line in the journal. A rabbit hole costs the run.

If the same class of failure blocks three different hypotheses, that is no longer a debugging problem; it is a finding about the system. Write it up, and redirect the run to a knob family that does not hit it.

## Keep the log out of your context

```bash
<run command> > logs/N.log 2>&1          # never tee, never stream into context
grep -E '^(metric|score|elapsed):' logs/N.log   # the happy path
tail -n 40 logs/N.log                     # only when the grep came back empty
```

An empty grep *is* the crash detector — you do not need to watch the run to know it failed. When you do need the trace, read the last 40 lines, not the file. Long stack traces and progress bars can eat more context than an hour of reasoning, and context exhaustion mid-run is how a loop loses its own plan.

## Distinguishing a regression from a break

Both look like "the number got worse". They are not the same:

- A **regression** produced a metric. It is data: the change was tried and it hurt. Revert, log, learn.
- A **break** produced no metric, or produced one the evaluator would not certify. Nothing was learned about the hypothesis.

Recording a break as a regression is a quiet corruption of the ledger — it makes a hypothesis look refuted when it was never actually tested, and you will not retry it.

## When results stop making sense

Sudden discontinuities, impossible values, or a metric that stops responding to knobs that used to move it: suspect the harness before the hypothesis.

Re-run the *baseline configuration* and check it still reproduces the number in `PLAN.md`. If it does not, something in the frozen set moved — an environment change, a cache, an upstream dependency, an edit you made without noticing. Find it and restore it before running another trial. Every number measured since the drift began is suspect; mark them in the ledger rather than silently keeping them.

This check is cheap and worth running unprompted every ten or twenty trials in any domain where the environment can shift under you.
