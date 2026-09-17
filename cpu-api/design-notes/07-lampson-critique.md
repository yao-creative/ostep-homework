**Intent:** systematically work through Lampson's remaining named design abstractions — not just policy/mechanism/hint/naming, which we've covered — and formalize each one algebraically against this specific codebase, the same way as before: a formal statement, then the concrete artifact in the code that either satisfies or violates it.

---

### 1. Interface minimality — "do one thing, and let it be a generating set"

Lampson: an interface should be **irreducible** — no element derivable from the others — and **complete** — everything reachable is reachable through it. This is literally the algebraic notion of a **generating set** for a free structure.

Formally, $\text{Action} = \{\text{Fork}, \text{Exit}\}$ should be checked as a generating set for $\Sigma^*$'s free monoid over the transition system: every reachable $Q_n$ must be expressible as $\delta^*(\sigma)$ for some $\sigma \in \{\text{Fork},\text{Exit}\}^*$, and neither constructor should be derivable from the other (they aren't — $\text{Fork}$ and $\text{Exit}$ act on disjoint aspects of $\pi$: extend the domain vs. remove from it). **This holds cleanly in your current design** — this is the one abstraction that's already correctly satisfied, worth noting explicitly rather than only flagging violations.

### 2. Indirection — "one more level of indirection solves everything except too many levels of indirection"

$\pi : \text{Name} \rightharpoonup \text{Name}$ (the `parents` map) is precisely an indirection layer: names are stable identifiers, and the *structural* fact (who's whose parent) is stored as a separate mutable relation rather than baked into positional array structure. Formally, this is what makes $\text{do\_exit}$'s reparenting an $O(k)$ pointer-rewrite ($k$ = number of orphans) instead of an $O(n)$ tree-rebuild: indirection is precisely what decouples **identity** (the name, invariant) from **position** (the parent-edge, mutable). This is correctly present in your design too — `children` as the inverse fiber $\pi^{-1}$ is the second half of the same indirection, letting lookups go either direction without rebuilding anything.

### 3. Amortization / batching — "do it in big chunks, checked against the total"

$\text{get\_name}/\text{grow\_names}$ is exactly Lampson's batching hint: pay a large cost ($O(|\Sigma|^2)$ to regenerate the name pool) infrequently rather than a small cost every call. Formalized: let $c(n)$ be the cost of the $n$-th call to `get_name`. Growth triggers when $n = |\Sigma|^k$ for successive $k$, so

$$\sum_{i=1}^{n} c(i) \;=\; O(n) + \sum_{k} |\Sigma|^{2k} \;=\; O(n)$$

by the standard geometric-series argument (each doubling-like growth phase costs proportional to the phase size, and phases shrink geometrically as a fraction of total work) — so **amortized cost per name is $O(1)$** even though individual calls spike. This is correctly implemented; the only defect (flagged earlier) is that `curr_names` changes *type* mid-life (`str` → `List[str]`), which is an implementation bug in an otherwise correctly-chosen algorithmic strategy.

### 4. Atomicity — "make composite actions indivisible, or make partial failure safe"

This is the one **genuinely violated** in the current code. `do_exit` is a sequence of five independent mutations to `process_list`, `children` (multiple keys), and `parents`. Formally, it should behave as a single atomic morphism:

$$\text{do\_exit} : Q \to Q \quad \text{with no observable intermediate state } Q_{\text{partial}}$$

But if any step raises (e.g., a `KeyError` from an inconsistent `children` dict under a bug elsewhere), the state is left in a **torn, half-mutated configuration** — some children reparented, others not, `process_list` and `children` now disagreeing about membership. Lampson's fix here is either (a) construct the new state as an immutable value and swap it in only on full success, or (b) log the inverse operations and roll back on failure:

```python
def do_exit(state: ForkerState, cfg: ForkerConfig, p: ProcessName) -> str:
    # Build the full mutation as a batch of (target, mutation) pairs first,
    # validate all preconditions, THEN apply -- no observable partial state.
    exit_parent = state.parents[p]
    orphans = list(state.children[p])
    ...
    # apply only after every precondition above has succeeded
```
The atomicity property here is exactly the algebraic requirement that $\text{do\_exit}$ factor through a **total, precondition-checked staging step** before any mutation occurs — i.e., re-deriving the same `validate → apply` split from the `parse/don't validate` discussion, but applied to *state mutation* rather than *parsing*.

### 5. End-to-end argument — "the only check that matters is the one at the endpoint that actually needs the guarantee"

Lampson (via Saltzer/Reed/Clark, which he cites): don't duplicate a correctness check at every layer if only the top layer's check is load-bearing. Your `action_step` checking `action.parent not in state.process_list` **before** calling `do_fork` is the *correct* placement — it's the one check that actually determines legality, and `do_fork` itself doesn't re-verify. Formally: if $g: A \to B$ and $f: B \to C$ compose, and $f$'s precondition is already guaranteed by $g$'s postcondition, $f$ should **not** re-derive it — this is precisely the payoff of the `Cert⟨Action⟩` refinement from earlier: the check happens once, at the layer that can make the definitive determination, and every layer below trusts the type rather than re-verifying. Your current `action_step` already does this correctly for existence-checking; it does **not** yet do it for the `Cert` type itself (flagged before — `validate` and `apply` are still fused), so this principle is *directionally* honored but not *structurally* enforced by the type system yet.

### 6. Safety net — "handle the exceptional case once, generically, at a boundary — not ad hoc, scattered"

`handle_bad_action`'s `exit(1)` is called from four+ independent sites (`lex_raw_action` twice, `action_step` twice). Lampson's safety-net principle wants **one boundary** that catches all failure and decides the fallback uniformly — e.g., `main()` catching a raised exception once, rather than each call site independently deciding to terminate the process. Formally this is again the `Result`-propagation point from Tier-1 critique: replace scattered `exit(1)` calls with a single `raise ActionParseError(...)`, caught exactly once at the top of `main()`. This is the same defect noted twice already (parse-don't-validate critique, and Tier-1 blocking issues) — worth stating that it's *also* a direct violation of this specific Lampson principle, not just generically "bad error handling."

---

### Consolidated map

| Lampson abstraction | Formal statement | Status in current code |
|---|---|---|
| Interface minimality | `Action` is an irreducible, complete generating set | ✅ satisfied |
| Indirection | $\pi$ decouples identity from structural position | ✅ satisfied |
| Amortization | $\sum c(i) = O(n)$ via batched name growth | ✅ satisfied (impl bug aside) |
| Atomicity | $\text{do\_exit}$ has no observable partial state | ❌ violated — needs stage-then-apply |
| End-to-end argument | check once, at the layer that can decide | ⚠️ partially honored, not type-enforced |
| Safety net | one boundary catches all failure | ❌ violated — `exit(1)` scattered at 4+ sites |

The two real action items are **atomicity** (`do_exit`) and **safety net** (centralize error propagation) — both are independent of, and additive to, the `Cert⟨Action⟩` refinement already on the table.