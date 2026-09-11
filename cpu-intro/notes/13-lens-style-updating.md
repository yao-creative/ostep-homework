**Labeling your question precisely:** this is not "mutation vs immutability" (you've already committed to immutability) — it's a question of **function signature minimality under a state-threading discipline**, i.e. how to choose the *domain of a transition morphism* when the full state is a product type. In FP terms: narrow interfaces + explicit reconstruction, vs. wide interfaces + implicit whole-state passing.

## Causal chain to the answer (goal → constraint → decision)

$$\text{Goal: local reasoning / provability (seL4-style)} \Rightarrow \text{narrow interfaces (POLA)} \Rightarrow \text{minimal transition domain} \Rightarrow \text{explicit reconstruction (lens/product decomposition)}$$

- **seL4's actual practice**: every kernel object operation is checked against a *capability* granting access to exactly the object touched — nothing more. This isn't a security nicety, it's what makes the formal proof tractable: a proof about `move_to_running` only needs to reason about the thing `move_to_running` can see. If it can see the whole `SchedulerState`, your proof obligation (and your test surface, and your mental model) balloons to the whole state, even though the function only *uses* one field.
- **Jane Street's actual practice** ("make illegal states unrepresentable," narrow functions): a function's type signature is documentation of its true dependency set. `let f : Process_info.t -> Process_info.t` tells a reader everything; `let f : Scheduler_state.t -> Scheduler_state.t` tells them nothing except "reads/writes potentially anything," which is a strictly worse type even if the *implementation* only touches one field — the type is lying about the support.

So: **pass the minimal product of exactly the fields the transition reads or writes — never the whole `SchedulerState` — and reconstruct the whole state at the call site**, not inside the transition.

## Formalizing this without definition-lingo

Think of `SchedulerState` as a Cartesian product of its fields (this is just what a dataclass *is*, set-theoretically):

$$S \;=\; \mathrm{ProcInfo} \times \mathrm{CurrProc} \times \mathrm{IOFinish} \times \mathrm{Clock} \times \mathrm{SwitchPolicy} \times \mathrm{IODonePolicy} \times \mathrm{IOLen}$$

A product comes equipped with **projections** $\pi_A : S \to A$ for each factor $A$, and — crucially — with a **universal property**: given any element of $A$ and any way of filling in the rest, there's a unique way to rebuild an $S$. That "rebuild" operation is what you're missing right now; your code mutates fields in place instead of ever doing it.

Concretely, decompose $S \cong A \times R$ where $A$ is the minimal factor a transition needs and $R$ is "everything else." A transition should be typed:

$$t : A \to A$$

not $t : S \to S$. The reconstruction back into $S$ is a separate, generic operation — a **get/modify/set** triple $(\mathrm{get}_A, \mathrm{set}_A)$ satisfying the standard lens laws (get after set returns what you set; set after get is a no-op; set twice is set-once). This triple is exactly the data of the isomorphism $S \cong A\times R$ — nothing more mystical than "a product has projections and pairing."That's the shape: transitions are typed $A \to A$, and the surrounding `get`/`set` pair does the work of the isomorphism $S \cong A \times R$.

## Bugs your draft has that fight this goal

1. **`move_to_running` is defined twice**, the second silently shadowing the first, and both set state to `READY` instead of `RUNNING` — a copy-paste error, not a design choice.
2. **`@dataclass(frozen=True)` is a lie here**: `proc_info[pid][PROC_STATE] = ...` mutates a dict *inside* a frozen dataclass. Freezing only blocks reassigning the field `proc_info` itself; it does nothing to the mutable dict the field points to. This is the single biggest gap between your stated goal ("functional, no owned mutable state") and what the code does.
3. `new_process` mutates `scheduler_state.proc_info` in place and returns the *same* object — so `SchedulerState` isn't actually a value type yet, it's a mutable object wearing a `frozen=True` costume.

## Concrete pattern**The decision procedure, stated once so you can apply it everywhere in the port:**

For every transition $t$, compute $\mathrm{supp}(t) = \{\text{fields } t \text{ reads}\} \cup \{\text{fields } t \text{ writes}\}$, and let $t$'s domain be exactly the product of those fields — never `SchedulerState` wholesale. Reconstruction into the full state happens in exactly one place (`update_process`), never inside a transition. This gives you, for free:

- **Local reasoning** (seL4): a proof/test about `move_to_running` only needs a `ProcessInfo`, not a whole scheduler fixture.
- **Honest types** (Jane Street): the signature `ProcessInfo -> ProcessInfo` *is* the documentation; `SchedulerState -> SchedulerState` would lie about the true dependency.
- **A composable core**: `next_proc` above is pure and testable as `(Mapping[int, ProcessState], int) -> int` with zero scheduler scaffolding.

"Pass the minimal amount" isn't in tension with "sometimes a transition needs two fields" — `next_proc` needs `{proc_info, curr_proc}`, and that pair *is* its minimal domain, still strictly narrower than `S`. The rule is never "pass one field," it's "pass exactly $\mathrm{supp}(t)$, no more."