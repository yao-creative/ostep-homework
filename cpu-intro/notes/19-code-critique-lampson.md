## Level 0 fixes — doc3

Fixing strictly the crash/hang-inducing defects; same triage rule as before (execute-and-observe, not architecture).

**1. `new_process` — attribute-assignment on a dict instead of constructing the dataclass**
```python
# before
scheduler_state.proc_info[proc_id] = {}
scheduler_state.proc_info[proc_id].pc = 0
scheduler_state.proc_info[proc_id].pid = proc_id
scheduler_state.proc_info[proc_id].code = []
scheduler_state.proc_info[proc_id].state = ProcessState.READY

# after
scheduler_state.proc_info[proc_id] = ProcessInfo(
    pid=proc_id, pc=0, code=[], state=ProcessState.READY
)
```

**2. `new_scheduler_config_from_options` — wrong kwargs + enum lookup by value instead of by name**
```python
# before
def new_scheduler_config_from_options(options):
    return SchedulerConfig(
        process_switch_behavior=SchedulerSwitchPolicy(options.process_switch_behavior),
        io_done_behavior=IORunPolicy(options.io_done_behavior),
        io_length=options.io_length,
    )

# after
def new_scheduler_config_from_options(options):
    switch_name = options.process_switch_behavior.removeprefix('SWITCH_')   # 'SWITCH_ON_IO' -> 'ON_IO'
    io_done_name = options.io_done_behavior.removeprefix('IO_RUN_')          # 'IO_RUN_LATER' -> 'LATER'
    return SchedulerConfig(
        process_switch_policy=SchedulerSwitchPolicy[switch_name],
        io_done_policy=IORunPolicy[io_done_name],
        io_length=options.io_length,
    )
```

**3. `handle_io_done_process_switching` — reads config attributes that don't exist**
```python
# before
if scheduler_config.io_done_behavior == IORunPolicy.IMMEDIATE and scheduler_state.curr_proc != pid and get_current_proc_info(scheduler_state).state == ProcessState.RUNNING:
    new_proc_info = transition_to_ready(get_proc_info_by_pid(pid, scheduler_state), ProcessState.RUNNING)
    scheduler_state = set_proc_info_by_pid(pid, new_proc_info, scheduler_state)
    if scheduler_config.process_switch_behavior == SchedulerSwitchPolicy.ON_END:
        scheduler_state = next_proc(scheduler_state, pid)
    if get_num_runnable(scheduler_state) == 1:
        scheduler_state = next_proc(scheduler_state, pid)
return scheduler_state

# after
if scheduler_config.io_done_policy == IORunPolicy.IMMEDIATE and scheduler_state.curr_proc != pid and get_current_proc_info(scheduler_state).state == ProcessState.RUNNING:
    new_proc_info = transition_to_ready(get_proc_info_by_pid(pid, scheduler_state), ProcessState.RUNNING)
    scheduler_state = set_proc_info_by_pid(pid, new_proc_info, scheduler_state)
    if scheduler_config.process_switch_policy == SchedulerSwitchPolicy.ON_END:
        scheduler_state = next_proc(scheduler_state, pid)
    if get_num_runnable(scheduler_state) == 1:
        scheduler_state = next_proc(scheduler_state, pid)
return scheduler_state
```

**4. `resolve_io_done` — missing return + reversed reader arguments**
```python
# before
def resolve_io_done(scheduler_state: SchedulerState, pid: int, scheduler_config: SchedulerConfig) -> SchedulerState:
    if scheduler_state.clock_tick in scheduler_state.io_finish_times[pid]:
        new_proc_info = transition_to_ready(get_proc_info_by_pid(scheduler_state, pid), ProcessState.BLOCKED)
        scheduler_state = set_proc_info_by_pid(pid, new_proc_info, scheduler_state)
        scheduler_state = handle_io_done_process_switching(scheduler_state, pid, scheduler_config)
        resolve_instructions_done(scheduler_state)

# after
def resolve_io_done(scheduler_state: SchedulerState, pid: int, scheduler_config: SchedulerConfig) -> SchedulerState:
    if scheduler_state.clock_tick in scheduler_state.io_finish_times[pid]:
        new_proc_info = transition_to_ready(get_proc_info_by_pid(pid, scheduler_state), ProcessState.BLOCKED)
        scheduler_state = set_proc_info_by_pid(pid, new_proc_info, scheduler_state)
        scheduler_state = handle_io_done_process_switching(scheduler_state, pid, scheduler_config)
        scheduler_state = resolve_instructions_done(scheduler_state)
    return scheduler_state
```

**5. `handle_io_issue` — missing return on the non-trivial branch**
```python
# before
    if scheduler_config.process_switch_policy == SchedulerSwitchPolicy.ON_IO:
        scheduler_state = next_proc(scheduler_state)

# after
    if scheduler_config.process_switch_policy == SchedulerSwitchPolicy.ON_IO:
        scheduler_state = next_proc(scheduler_state)
    return scheduler_state
```

**6. `handle_scheduler_step` — trailing comma produces a 1-tuple**
```python
# before
    return scheduler_state,

# after
    return scheduler_state, scheduler_metrics
```

**7. `emit_scheduler_state_per_tick` — concatenating `str` with an `Instruction` enum member**
```python
# before
print('%14s' % ('RUN:'+curr_instruction), end='')

# after
print('%14s' % ('RUN:'+curr_instruction.name), end='')
```

**8. `emit_instruction` — comparing an enum member to a string literal (never true)**
```python
# before
if curr_instruction == "":
    print("%14s" % " ", end="")
elif curr_instruction == "COMPUTE":
    print("%14s" % "1", end="")

# after
if curr_instruction == '':
    print("%14s" % " ", end="")
elif curr_instruction == Instruction.COMPUTE:
    print("%14s" % "1", end="")
```

**9. `next_proc` — undefined bare `proc_info` in the wraparound branch**
```python
# before
for pid in range(0, scheduler_state.curr_proc + 1):
    if proc_info[pid].state == ProcessState.READY:

# after
for pid in range(0, scheduler_state.curr_proc + 1):
    if get_proc_info_by_pid(pid, scheduler_state).state == ProcessState.READY:
```

**10. `resolve_instructions_done` — discards the transition result instead of writing it back**
```python
# before
def resolve_instructions_done(scheduler_state: SchedulerState) -> SchedulerState:
    curr_proc_info = get_current_proc_info(scheduler_state)
    if len(curr_proc_info.code) == 0 and curr_proc_info.state == ProcessState.RUNNING:
        transition_to_done(curr_proc_info, ProcessState.RUNNING)
        scheduler_state = next_proc(scheduler_state)
    return scheduler_state

# after
def resolve_instructions_done(scheduler_state: SchedulerState) -> SchedulerState:
    curr_proc_info = get_current_proc_info(scheduler_state)
    if len(curr_proc_info.code) == 0 and curr_proc_info.state == ProcessState.RUNNING:
        new_proc_info = transition_to_done(curr_proc_info, ProcessState.RUNNING)
        scheduler_state = set_proc_info_by_pid(scheduler_state.curr_proc, new_proc_info, scheduler_state)
        scheduler_state = next_proc(scheduler_state)
    return scheduler_state
```

**11. `run` — process 0 never enters `RUNNING`, so the loop never terminates**
```python
# before
def run(scheduler_state: SchedulerState, scheduler_config: SchedulerConfig) -> Tuple[int, int, int]:
    if get_num_processes(scheduler_state) == 0:
        return (0, 0, 0)
    emit_header(scheduler_state)
    scheduler_metrics = new_scheduler_statistics()
    while get_num_active(scheduler_state) > 0:
        scheduler_state, scheduler_metrics = handle_scheduler_step(scheduler_state, scheduler_metrics, scheduler_config)
    return (scheduler_metrics.cpu_busy, scheduler_metrics.io_busy, scheduler_state.clock_tick)

# after
def run(scheduler_state: SchedulerState, scheduler_config: SchedulerConfig) -> Tuple[int, int, int]:
    if get_num_processes(scheduler_state) == 0:
        return (0, 0, 0)
    scheduler_state = next_proc(scheduler_state, pid=0)   # doc2's initial move_to_running(READY)
    emit_header(scheduler_state)
    scheduler_metrics = new_scheduler_statistics()
    while get_num_active(scheduler_state) > 0:
        scheduler_state, scheduler_metrics = handle_scheduler_step(scheduler_state, scheduler_metrics, scheduler_config)
    return (scheduler_metrics.cpu_busy, scheduler_metrics.io_busy, scheduler_state.clock_tick)
```

---

## Per-unit table — classified by *Hints for Computer System Design* §§2–3

Columns: **§ Principle** (which numbered concept the unit instantiates or violates), **Opposition** (which axis from the §5 Oppositions list it sits on), **Formal role**, **Critique**.

| Unit | § Principle | Opposition | Formal role | Critique |
|---|---|---|---|---|
| `ProcessInfo` | §2.3.1 Types | Immutable ↔ mutable | $\mathbb N\times\mathbb N\times I^{*}\times Q$ | Type says `Tuple` (immutable), runtime is `list` (mutable), and `pc` is a dead field — the type is not honest evidence of the spec (§2.2, "leaky spec"). |
| `SchedulerConfig` | §2.4 Modules and interfaces | Policy ↔ mechanism | $\mathrm{SwitchPolicy}\times\mathrm{IOPolicy}\times\mathbb N$, fixed parameter of $\delta$ | This *is* the "policy" pole of policy↔mechanism, correctly `frozen`. Its interface (field names) disagreed with three consumers — fixed above (#2,#3). The lesson per §2.4: an interface is a contract every module must cite identically, not re-derive. |
| `SchedulerState` | §2.4 Modules and interfaces | Policy ↔ mechanism | varying argument of $\delta$ | Still carries `io_length`, policy-flavored data leaking into the mechanism-state module — a residual interface leak (§2.2.1, "leaky spec"). |
| `SchedulerMetrics` | §2.3.1 Types | Immutable ↔ mutable | output monoid $\mathbb N^2$ | Mutable dataclass used with `replace` (an immutable idiom) — inconsistent stance on the opposition; should be `frozen=True` to match its own usage. |
| `random_seed` | §3.6.7 (isolated side effect, not a dependability concern here) | — | effect | Correctly the one deliberate escape from purity — fine. |
| `new_scheduler_state`, `new_scheduler_statistics` | §2.1 Abstraction | — | constructors $\varnothing\to X$ | Clean; each returns a value satisfying its type's full invariant, nothing more. |
| `new_scheduler_config_from_options` | §2.4 Modules and interfaces | Spec ↔ code | Options → $C$ | Fixed (#2): kwarg names now match the record; enum-by-name lookup replaces enum-by-value, which is what made "code" (the lookup) actually match "spec" (the intended mapping from CLI strings to policy values). |
| `new_process` | §2.3.1 Types | — | $S\to S\times P$ | Fixed (#1): now genuinely constructs the declared type instead of a duck-typed dict — restores the type-safety §2.3.1 asks for. |
| `load_program`, `load` | §3.2.1 Do one thing well | — | free-monoid homomorphism $\mathrm{str}\times S\to S$ | Both now thread `scheduler_state` correctly (no class-object mutation) — clean, single-purpose, no critique. |
| `transition_to_running/ready/wait/done` | §2.1.1 Safety and liveness | Precise ↔ approximate | guarded partial function $Q\rightharpoonup Q$ | The `assert` **is** the safety property (an illegal transition halts loudly rather than corrupting state silently) — this is the one unit already exemplifying the "prefer precise failure over silent approximate behavior" stance. Keep unmodified. |
| `get_current_proc_info`, `get_proc_info_by_pid` | §2.4 Modules and interfaces | — | pure reader | Argument-order inconsistency `(state)` vs `(pid,state)` between the two is what produced bug #4 (reversed call). Per §2.4's "get the interfaces right": unify to `(pid, state)` everywhere so the shape itself prevents the mistake. |
| readers (`get_num_*`, `get_instruction`, `get_ios_in_flight`) | §2.1 Abstraction | — | $S\to\mathbb N$ | Clean projections, no side effects, no critique. |
| `set_proc_info_by_pid` | §2.4 Modules and interfaces | Immutable ↔ mutable | lens setter $P\times\mathrm{ProcessInfo}\times S\to S$ | The right primitive; not yet used *atomically* everywhere (see `resolve_instructions_done` below) — the interface is fine, discipline in using it is not. |
| `set_curr_proc_info` | §3.2.1 Do one thing well | — | specialized setter | Redundant against `set_proc_info_by_pid(scheduler_state.curr_proc, ...)` — two names for one lens violates "do one thing well" by having two things do the same thing; delete it. |
| `next_proc` | §2.4 Modules and interfaces | — | $S\times(P\uplus\{-1\})\to S$ | Fixed (#9): wraparound branch now calls the reader instead of an undefined bare name. |
| `resolve_instructions_done` | §2.1.1 Safety and liveness | Immutable ↔ mutable | guarded transition, should be atomic | Fixed (#10): was violating safety by computing a new state and never installing it — an *invisible* liveness bug (processes never reach `DONE`, so `get_num_active` never drops). |
| `handle_io_done_process_switching` | §2.4 Modules and interfaces | Policy ↔ mechanism | $S\times P\times C\to S$ | Fixed (#3) — correct field names now let the policy branch actually dispatch on `io_done_policy`/`process_switch_policy` as intended. |
| `resolve_io_done` | §2.1.1 Safety and liveness | — | orchestrator | Fixed (#4) — was the single highest-impact defect: no return meant every call silently nulled the whole state. |
| `emit_header`, `emit_scheduler_state_per_tick`, `emit_instruction`, `emit_outstanding_ios` | §2.1 Abstraction (separating effect from mechanism) | — | $S\to()$ | Correct architectural instinct — I/O isolated from state transitions. Two of four had a stale-string-vs-enum defect (#7, #8) left over from the doc2→doc1 enum migration; fixed. |
| `handle_execute_instructions` | §2.1 Abstraction | Immutable ↔ mutable | $S\times M\to S\times M\times I$ | In-place `.code.pop(0)` breaks the immutable-record convention used by the `transition_to_*` family — not a crash, but an inconsistency on the same opposition axis; flag for later. |
| `handle_io_issue` | §2.1.1 Safety and liveness | — | guarded transition | Fixed (#5) — same missing-return defect as `resolve_io_done`, same root cause. |
| `accumulate_metrics` | §2.3.1 Types | Immutable ↔ mutable | pure fold step | Cleanest unit in the file — consistently immutable via `replace`, no critique. |
| `handle_scheduler_step` | §2.4 Modules and interfaces | — | composed $\delta$ | Fixed (#6) — the `return scheduler_state,` typo is exactly the kind of interface-arity mismatch §2.4 calls out: caller and callee must agree on the *shape* of what crosses the boundary, not just its name. |
| `run` | §2.1.1 Safety and liveness | — | driver, fold $\delta^n$ | Fixed (#11) — was a liveness bug (infinite loop), not a safety bug: nothing was ever *wrong*, the state simply never advanced toward termination. |
| `main` | §2.4 Modules and interfaces | — | top-level driver | Correctly threads both `scheduler_state` and `scheduler_config` — no critique. |

**Cross-cutting note under §2.4 "Modules and interfaces":** 8 of the 11 Level-0 defects are interface-boundary mismatches (wrong kwarg names, wrong argument order, wrong return arity) rather than logic errors *inside* any single function — consistent with Hints' framing that the hard part of decomposition is getting agreement *between* modules, not correctness *within* one.