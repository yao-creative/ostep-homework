## Root cause of the discrepancy: two independent bugs, not a policy-logic bug

Neither `handle_io_done_process_switching` nor your Case 3 reasoning is what's producing 30/30 instead of 15/25 — those numbers come from two separate defects elsewhere in `handle_scheduler_step`. I'll fix those first since they explain the observed output exactly, then correct the De Morgan derivation, since it does have a real error worth fixing on its own.

### Bug A — `cpu_busy` incremented twice per instruction

`handle_execute_instructions` mutates the metrics object **in place**:
```python
scheduler_metrics.cpu_busy += 1
```
and then `handle_scheduler_step` calls `accumulate_metrics`, which does it **again** via `cpu_delta = 1 if instruction_executed != '' else 0`. Since `SchedulerMetrics` is a mutable dataclass, that in-place `+=` is a genuine side effect that survives independently of the `replace(...)` call downstream — every instruction executed gets counted twice. $15\times2=30$, exactly your observed CPU figure.

**Fix — delete the inline mutation, let `accumulate_metrics` be the single source of truth:**
```python
# handle_execute_instructions — before
if curr_proc_info.state == ProcessState.RUNNING and len(curr_proc_info.code) > 0:
    curr_instruction = curr_proc_info.code.pop(0)
    scheduler_state = set_curr_proc_info(curr_proc_info=curr_proc_info, scheduler_state=scheduler_state)
    scheduler_metrics.cpu_busy += 1

# after
if curr_proc_info.state == ProcessState.RUNNING and len(curr_proc_info.code) > 0:
    curr_instruction = curr_proc_info.code.pop(0)
    scheduler_state = set_curr_proc_info(curr_proc_info=curr_proc_info, scheduler_state=scheduler_state)
```

### Bug B — IO outstanding count computed *after* this tick's own IO is appended

Doc2's canonical order per tick is: execute → **print/count outstanding IOs using the *old* finish-time list** → *then* append this tick's new finish time if an IO was just issued. Your `handle_scheduler_step` does it backwards — `handle_io_issue` (which appends `finish_tick` to `io_finish_times`) runs *before* `get_ios_in_flight` is computed, so the very tick an IO is issued gets counted as "in flight" a tick early. With 5 IO issuances in this run, that's exactly $25+5=30$ — your observed IO figure.

**Fix — snapshot `num_io_outstanding` before the append happens:**
```python
# handle_scheduler_step — before
scheduler_state, scheduler_metrics, curr_instruction = handle_execute_instructions(scheduler_state, scheduler_metrics)
scheduler_state = handle_io_issue(scheduler_state, scheduler_config, curr_instruction)
scheduler_state = resolve_instructions_done(scheduler_state)
num_io_outstanding = get_ios_in_flight(scheduler_state, scheduler_state.clock_tick)

# after
scheduler_state, scheduler_metrics, curr_instruction = handle_execute_instructions(scheduler_state, scheduler_metrics)
num_io_outstanding = get_ios_in_flight(scheduler_state, scheduler_state.clock_tick)   # snapshot BEFORE this tick's IO is appended
scheduler_state = handle_io_issue(scheduler_state, scheduler_config, curr_instruction)
scheduler_state = resolve_instructions_done(scheduler_state)
```

A cosmetic third issue while we're here (doesn't affect the totals, but affects the trace's visible `1`s at ticks 12/19/26/33/40): `emit_instruction` only prints `"1"` for `Instruction.COMPUTE`, but doc2 prints it for *any* executed instruction. Change the guard to `elif curr_instruction != '':` to match.

---

## Case 3 — the derivation has a real error, and it's not the one that "==0" suggests

Let $R = \texttt{get\_num\_runnable(state)}$ at this call site. Since `pid` was just transitioned to `READY` immediately before this function runs, $R\geq 1$ always holds here — that invariant matters below.

Your two coded conditions:
$$\text{Case 1} \equiv \mathrm{ON\_END} \wedge (R>1) \qquad\qquad \text{Case 2} \equiv (R=1)$$

Case 3 is everything else:
$$\text{Case 3} \equiv \neg(\text{Case 1}\vee\text{Case 2}) = \neg\text{Case 1}\wedge\neg\text{Case 2}$$

De Morgan on $\neg\text{Case 1}$:
$$\neg(\mathrm{ON\_END}\wedge R>1) \;=\; \neg\mathrm{ON\_END}\;\vee\;\neg(R>1) \;=\; \mathrm{ON\_IO}\;\vee\;(R\le 1)$$

**This is an $\vee$, not an $\wedge$** — your comment wrote `(ON_IO x COUNT(...)<=1)` as a *product* (i.e. $\wedge$), which is exactly where the derivation goes wrong. Continuing correctly:

$$\text{Case 3} = \big(\mathrm{ON\_IO}\vee(R\le1)\big)\wedge(R\ne1)$$

Distribute over the $\vee$:

$$\text{Case 3} = \underbrace{\big(\mathrm{ON\_IO}\wedge R\ne1\big)}_{\text{term A}} \;\vee\; \underbrace{\big(R\le1 \wedge R\ne1\big)}_{\text{term B} \,=\, (R=0)}$$

Term B collapses to $R=0$, which is exactly the branch your comment's final line landed on (`COUNT(...) == 0`) — but since $R\geq1$ is invariant at this point, **term B is vacuous, dead code, never reachable**. Your comment stopped there and concluded Case 3 reduces to an unreachable state. That's the actual error: **term A was dropped**, and term A is not vacuous at all — given $R\geq1$, $R\ne1 \iff R>1$, so:

$$\text{Case 3 (reachable part)} \;=\; \mathrm{ON\_IO}\wedge R>1$$

That's a completely ordinary, frequently-hit case (round-robin, multiple runnable processes) — not an edge case. Its correct meaning: under `ON_IO`, if more than one process is runnable when this IO completes, **do nothing** — let `pid` sit `READY` and get picked up in its normal turn by the plain round-robin search, rather than force-switching to it just because its IO happened to finish now. That's the right behavior, and it's what the code (silently, by omission) already does — the bug was purely in the comment's algebra, not in the `if` statements themselves.

**Corrected comment, to replace the current derivation block:**
```python
        # Case 3 = ¬Case1 ∧ ¬Case2, expanded by De Morgan:
        #   ¬Case1 = ON_IO ∨ (R<=1)        [NOT is OR here, not AND]
        #   ¬Case2 = R != 1
        #   Case3  = (ON_IO ∧ R>1)  ∨  (R=0)
        # R=0 is unreachable (pid itself is READY here, so R>=1 always) — dead branch.
        # The only live case is (ON_IO ∧ R>1): under ON_IO with several
        # runnable processes, do nothing — pid waits its normal turn.
```

The `if` statements in your code were already correct implementations of this; only the algebra comment above them was wrong, and in a way that would mislead a future reader into thinking Case 3 never fires.