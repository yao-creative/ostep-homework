## Direct answer: yes, there's a real emergent rule — but it isn't fully honored yet

Your instinct is correct and it's worth stating **as a formal rule** rather than a vibe, because right now it holds for *most* units but is silently broken by one:

$$\texttt{handle\_}f \;\iff\; f: S \times C \times (\ldots) \to S \quad\text{(mechanism parameterized by policy)}$$
$$\texttt{resolve\_}f \;\iff\; f: S \times (\ldots) \to S \quad\text{(mechanism alone — pattern-triggered, policy-free)}$$

This is a genuine categorical distinction, not just a naming convention: `SchedulerConfig` is a **fixed index object**, and every `handle_*` function is really a *curried family* of endomorphisms on $S$ indexed by $C$:

$$\delta : C \to S^{S}, \qquad \delta(c) = \delta_c : S \to S$$

($S^S$ here is the usual exponential-object notation for "the set of functions $S\to S$" — read it as "Hom-set of endomorphisms," nothing more exotic). `handle_io_issue` and `handle_io_done_process_switching` are legitimately elements of this family — their behavior *branches on* $c\in C$. A `resolve_*` function, by contrast, is a **single fixed element of $S^S$** with no dependence on $C$ at all — it's triggered purely by matching a pattern in $S$ (code-empty, tick-in-finish-times), so it rightly takes no config argument. `resolve_instructions_done` and `resolve_io_done`'s *outer* clock-match guard both respect this.

**Where it breaks:** `handle_execute_instructions(scheduler_state, scheduler_metrics)` takes no `scheduler_config` — under your own rule it should be named `resolve_execute_instructions` or `execute_current_instruction`, since it currently *is* a $C$-independent mechanism wearing a `handle_` label that promises policy-dependence it doesn't have. This isn't cosmetic: if a future change makes instruction execution policy-sensitive (e.g. priority-based preemption), the naming would already be "ready" for that only if you fix it now — otherwise the rename later is a breaking-change smell that could've been avoided.

## Table: prefix → category role → verdict

| Prefix / unit class | Formal role | Signature shape | Verdict |
|---|---|---|---|
| `new_*` | Constructor $\varnothing \to X$ | `() -> X` | Consistent. `new_scheduler_config_from_options` is the one constructor that takes an argument (`Options -> C`) — correctly so, since it's compiling *external* input into the policy object, still a "birth" of the value, not a transition on it. |
| `get_*` | Pure reader (projection) | `S -> X` or `P × S -> X` | Consistent, all side-effect-free. |
| `set_*` | Lens setter | `P × X × S -> S` | Consistent but **duplicated** (`set_curr_proc_info` is a redundant special case of `set_proc_info_by_pid`) — flagged previously, still present. |
| `transition_to_*` | Guarded partial function, the primitive morphism | $Q \rightharpoonup Q$ (lifted to `ProcessInfo -> ProcessInfo`) | Consistent — these are the atomic building blocks every `resolve_*`/`handle_*` composes. |
| `resolve_*` | Policy-free mechanism, pattern-triggered | $S \to S$ | Consistent for `resolve_instructions_done`; consistent for `resolve_io_done`'s **own** guard (clock match), even though it internally *calls* a `handle_*` (fine — a resolve can delegate part of its body to a handle, since delegation isn't the same as *resolve itself* branching on `C`). |
| `handle_*` | Policy-parameterized mechanism, the curried family $\delta(c)$ | $S \times C \times(\ldots) \to S$ | **Inconsistent at one site**: `handle_execute_instructions` has no `C` parameter. Everywhere else (`handle_io_issue`, `handle_io_done_process_switching`, `handle_scheduler_step`) it holds. |
| `emit_*` | Effect (Kleisli arrow into the IO "monad," informally) | $S \to ()$ | Consistent — none of them touch `S` or return it, which is exactly right: effects should be dead ends in the data-flow graph, not points anything is threaded back through. |
| `accumulate_*` | Pure fold step on the metrics monoid | $M \times I \to M$ | Consistent, and the cleanest unit in the file (already noted). |

So: **interfaces and effects are well-separated already** (nothing effectful returns `S`, nothing pure calls `print`). The **one gap** is that "mechanism vs policy-parameterized mechanism" — your `handle_`/`resolve_` split — has exactly one violator, and it's worth a one-line rename rather than leaving the convention with an exception.

## Two remaining defects in "the code fixed" — not naming, but they undermine the claim

**1. `new_scheduler_config_from_options` computes the right values and then ignores them** — this is a half-applied fix:

```python
# current (still broken)
switch_name = options.process_switch_behavior.removeprefix('SWITCH_')
io_done_name = options.io_done_behavior.removeprefix('IO_RUN_')
return SchedulerConfig(
    process_switch_behavior=SchedulerSwitchPolicy(options.process_switch_behavior),  # wrong kwarg + wrong lookup
    io_done_behavior=IORunPolicy(options.io_done_behavior),                          # wrong kwarg + wrong lookup
    io_length=options.io_length,
)

# fix
def new_scheduler_config_from_options(options):
    switch_name = options.process_switch_behavior.removeprefix('SWITCH_')
    io_done_name = options.io_done_behavior.removeprefix('IO_RUN_')
    return SchedulerConfig(
        process_switch_policy=SchedulerSwitchPolicy[switch_name],
        io_done_policy=IORunPolicy[io_done_name],
        io_length=options.io_length,
    )
```

**2. `next_proc`'s wraparound branch never updates `curr_proc` before reading/transitioning** — the first loop does `scheduler_state.curr_proc = pid` before `get_current_proc_info`; the second loop dropped that line, so it reads and transitions the *old* current process instead of `pid`, then writes the result into slot `pid` — silently duplicating/corrupting a `ProcessInfo` into the wrong dict key:

```python
# current (still broken)
for pid in range(0, scheduler_state.curr_proc + 1):
    if get_proc_info_by_pid(pid, scheduler_state).state == ProcessState.READY:
        proc_info = get_current_proc_info(scheduler_state)          # reads OLD curr_proc, not pid
        new_proc_info = transition_to_running(proc_info, ProcessState.READY)
        return set_proc_info_by_pid(pid, new_proc_info, scheduler_state)   # writes to pid anyway

# fix
for pid in range(0, scheduler_state.curr_proc + 1):
    if get_proc_info_by_pid(pid, scheduler_state).state == ProcessState.READY:
        scheduler_state.curr_proc = pid
        proc_info = get_current_proc_info(scheduler_state)
        new_proc_info = transition_to_running(proc_info, ProcessState.READY)
        return set_proc_info_by_pid(pid, new_proc_info, scheduler_state)
```

Both are Level-0-class (wrong-value / wrong-key, not stylistic), so worth closing before the naming-convention question is fully moot — a correct taxonomy doesn't help if two of the cells in it still execute the wrong branch.