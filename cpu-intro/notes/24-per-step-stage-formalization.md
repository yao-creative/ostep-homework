## Formal model: transitions tagged by *when their effect is due*, not by when they run

Fix the state space $S$ and let $n=\texttt{clock\_tick}$ during one call to `handle_scheduler_step`. Model the step as a composite of atomic transitions $f_1,\dots,f_k: S\to S$ (partial, each restricted by a guard, exactly as `transition_to_*` already are). What's been missing is a *third* attribute beyond guard/read-set/write-set: give every $f_i$ a **due-tick** $e_i\in\mathbb N$ — the tick at which $f_i$'s write is *meant* to become the visible truth — and a **cause-tick** $c_i\le n$ — the tick whose event justified firing $f_i$ at all.

$$f_i \;=\; \big(g_i,\; R_i,\; W_i,\; c_i,\; e_i\big), \qquad g_i: S\to\mathbb B,\;\; R_i, W_i \subseteq \mathrm{Fields}(S)$$

This is the whole trick: **stage membership is a function of $e_i$ compared to $n$, not of source-code position.**

$$
\text{stage}(f_i) =
\begin{cases}
\textbf{prologue} & c_i < n \;\wedge\; e_i = n \quad\text{(a past event, due now)}\\[2pt]
\textbf{dispatch} & c_i = n \;\wedge\; e_i = n \;\wedge\; W_i \ne \varnothing \;\wedge\; f_i \text{ is the tick's unique canonical action}\\[2pt]
\textbf{observation} & c_i = n \;\wedge\; e_i = n \;\wedge\; W_i = \varnothing \quad\text{(pure readout)}\\[2pt]
\textbf{epilogue} & c_i = n \;\wedge\; e_i > n \quad\text{(caused now, due later)}
\end{cases}
$$

Check this against your own functions:

| function | reads | writes | $c_i$ | $e_i$ | stage |
|---|---|---|---|---|---|
| `resolve_io_done` | `io_finish_times[pid]` (set at some past tick $k$) | `proc_info[pid].state` | $k<n$ | $n$ (fires exactly when due) | prologue |
| `handle_execute_instructions` | `proc_info[curr].state, .code` | `.code`, `cpu_busy` | $n$ | $n$ | dispatch |
| `get_ios_in_flight`, `emit_*`, `accumulate_metrics` | `proc_info`, `io_finish_times` | $\varnothing$ | $n$ | $n$ | observation |
| `handle_io_issue` | `curr_instruction` | `proc_info[curr].state`, `io_finish_times[curr] \leftarrow n+L+1` | $n$ | $n+L+1$ | epilogue |
| `resolve_instructions_done` | `proc_info[curr]` | `.state`, `curr_proc` (for tick $n{+}1$'s dispatch) | $n$ | $n+1$ | epilogue |

The table falls out mechanically — you don't have to eyeball "does this feel like cleanup." That's the payoff of tagging $e_i$ explicitly.

## The general boundary-finding rule

Given any sequence of transitions with hazards between them (RAW/WAW/WAR on shared fields — same notion used for instruction scheduling), the **only** valid total order is one consistent with the hazard-induced partial order $\prec$: $f_i \prec f_j$ whenever $R_j\cap W_i\ne\varnothing$ or $W_j\cap W_i\ne\varnothing$. Within any topological sort of $\prec$, the **observation cut** is uniquely forced by three facts:

$$
\underbrace{\{f_i : e_i \le n,\; W_i\ne\varnothing\}}_{\text{must all precede the cut}}
\quad\Big|\quad
\underbrace{\{f_i : W_i=\varnothing\}}_{\text{the cut itself}}
\quad\Big|\quad
\underbrace{\{f_i : e_i > n\}}_{\text{must all follow the cut}}
$$

**Why this is forced, not stylistic:** if a $e_i\le n$ write ran *after* the cut, observation would report a stale value for something already true — wrong. If an $e_i>n$ write ran *before* the cut, observation would report a value that isn't true until next tick — exactly the pid-0-`DONE`-one-tick-early bug you found. So the cut's position is **determined by the $e_i$ tags alone**; you don't choose it, you compute it. Prologue vs. dispatch is the one remaining freedom, and it's resolved by $c_i$: prologue transitions are triggered by an event whose cause predates this tick ($c_i<n$); dispatch is the transition whose cause **is** this tick existing at all — advancing the clock and picking the one process that gets to act.

## This is a known idea across three traditions — you're not inventing a new concept, just naming one

- **Concurrent algorithms (Herlihy–Wing):** every operation has a **linearization point** — a single instant within its execution interval at which it's deemed to take effect atomically, even though the code spans several statements. Your observation stage is exactly the linearization point of the tick; the rule above ("$e_i\le n$ before it, $e_i>n$ after") is precisely how you choose that instant correctly.
- **Sequential languages (C, and Lampson's own writing on atomicity):** a **sequence point** is a moment guaranteed to see all prior side effects completed and no later ones started. Same shape of guarantee, same reason it must be a *specific* cut rather than "roughly where the print statement lives."
- **Transaction systems / seL4:** the **commit point** is deliberately placed *before* any deferred, forward-looking bookkeeping (write-ahead log flush, seL4's `NeedsToBeRescheduled` flag) is *applied* — the bookkeeping is recorded as an *intent* but its visible effect is deferred. Your epilogue is that intent-application step, correctly placed after commit.

## Practical algorithm, stated once so it generalizes beyond this file

1. For every transition in a step, write down $(R_i, W_i)$.
2. For every field write, ask: *"at what tick does a correct implementation consider this fact true?"* — that's $e_i$. (Not "when does the assignment statement run" — that's an implementation accident; $e_i$ is a semantic property of the fact being recorded.)
3. Sort: all $e_i\le n$ writes first (respecting hazard order among themselves — that's prologue-then-dispatch), then the zero-write transitions (observation), then all $e_i>n$ writes (epilogue).
4. If a hazard edge ever crosses the cut backwards (an $e_i>n$ transition's write is read by an $e_j\le n$ transition), that's a **contradiction** — it means you mis-tagged something, because a fact due in the future cannot be a legitimate input to a fact due now. This is a free correctness check you get for having formalized $e_i$ at all, and it's exactly the check that would have caught the original bug mechanically instead of by staring at trace output.