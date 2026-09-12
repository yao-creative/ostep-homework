**Intent, named precisely:** you're not asking "where do I put three fields" — you're asking whether `(process_switch_behavior, io_done_behavior, io_length)` belong in the **carrier set of a state machine** or in its **parameter/index set**. That's the Reader-environment vs. State-monad-carrier distinction, and it's exactly the kind of thing that gets caught by type discipline in seL4's Isabelle/HOL model and by Jane Street's "config vs. state" convention. Below I derive the answer instead of asserting it.

## 1. Goal decomposition (top-down)

- **Terminal goal:** a scheduler whose types make illegal mutation impossible and whose invariants are cheap to state/prove.
- **Sub-goal A:** partition all data touched by `run()` into *varies-per-tick* vs. *fixed-per-run*.
- **Sub-goal B:** express the transition step as a typed function over exactly those two partitions.
- **Sub-goal C:** let the Rust/Python architecture fall out of that typing, not the reverse.

Applying sub-goal A to your fields: `proc_info`, `curr_proc`, `io_finish_times`, `clock_tick`, `io_done` change every tick. `process_switch_behavior`, `io_done_behavior`, `io_length` are set once from CLI args and never reassigned anywhere in `run()`. They fail the "varies" test — so by construction they don't belong in `SchedulerState`.

## 2. Set-theoretic formalization

Let $\Sigma$ be the set of runtime states (all values a `SchedulerState` record can take), and $C$ the set of configurations (all triples of the three fixed fields). The version you're tempted toward is:

$$\Sigma' = \Sigma \times C, \qquad \text{step}': \Sigma' \to \Sigma'$$

This is a **product-type conflation**: it forces every transition to carry $C$ through, even though $\text{step}'$ never actually changes the $C$-component. The honest signature is:

$$\text{step} : C \times \Sigma \to \Sigma$$

## 3. Category-theoretic lens: currying reveals *why* they're different roles

In a Cartesian closed category (which `Set`, and your type system, both are), there's an adjunction giving you:

$$\mathrm{Hom}(C \times \Sigma,\ \Sigma) \;\cong\; \mathrm{Hom}(C,\ \Sigma^{\Sigma})$$

Curry $\text{step}$ along this isomorphism:

$$\widehat{\text{step}} : C \to \operatorname{End}(\Sigma)$$

Read this plainly: **each configuration $c \in C$ selects one fixed endomorphism** $f_c = \widehat{\text{step}}(c)$ of the state space, and then running the scheduler for $n$ ticks is just iterating that one arrow:

$$\sigma_n = f_c^{\,n}(\sigma_0)$$

That's a **monoid action** of $(\mathbb{N}, +, 0)$ on $\Sigma$, with $c$ picking which action you get. Since $c$ never varies mid-action, it plays exactly the role of a **Reader environment** ($\text{Reader}\ C\ A = C \to A$), while $\Sigma$ plays the role of the **State monad's carrier** ($\text{State}\ \Sigma\ A = \Sigma \to \Sigma \times A$). The combined computation is the standard transformer stack:

$$\text{ReaderT}\ C\ (\text{State}\ \Sigma)\ A \;\cong\; C \to \Sigma \to (\Sigma \times A)$$

— which is literally $\widehat{\text{step}}$ curried one step further. Nothing here is invented; it's the same currying isomorphism that tells you a two-argument function and a function-returning-a-function are the same fact viewed two ways. The *design decision* is which of those two views you commit to in your types — and the type-theoretic cost of getting it wrong is that every invariant you later prove about $\Sigma$ has to needlessly quantify over an unchanging $C$-slot sitting inside it.## 4. What seL4 and Jane Street actually do with this fact

**seL4** models the kernel step relation in Isabelle/HOL as a state monad `s → (a × s) set` over the abstract kernel state record. Boot-time configuration (memory layout, capability limits) is *not* stored as a mutable field inside that record — it's fixed as a `locale` parameter or a constant threaded in as a read-only argument. The reason is invariant hygiene: every invariant they prove is a predicate over $\Sigma$, universally quantified across the whole proof; if $C$ lived inside $\Sigma$, every single invariant would carry a spurious, unprovable-looking obligation "and this never changes" that has nothing to do with kernel correctness.

**Jane Street** does the same thing at the module level: parse CLI args into an immutable `Config.t` once, then either close over it via a functor (`module Make (C : Config_intf) : Scheduler_intf`) or pass `config : Config.t` as an explicit first argument to every function, strictly separate from the mutable `State.t` (often a `ref` or explicit `State.t -> State.t`). "Make illegal states unrepresentable" specifically means: a field that's write-once should not share a record with fields that mutate every tick, because the type then claims a mutability it doesn't have.

## 5. Concrete fix

**Python** (fixing doc 2's actual conflation):

```python
@dataclass(frozen=True)
class SchedulerConfig:
    process_switch_behavior: str
    io_done_behavior: str
    io_length: int

@dataclass
class SchedulerState:
    proc_info: Dict[int, ProcessInfo]
    curr_proc: int
    io_finish_times: Dict[int, List[int]]
    clock_tick: int
    io_done: bool

def step(config: SchedulerConfig, state: SchedulerState) -> SchedulerState: ...
```

`new_scheduler_state()` should stop taking the three behavior args entirely — they go into a separate `SchedulerConfig` constructed once in `main()`.

**Rust**, matching your stated preference exactly — functional components borrow or mutate, never own:

```rust
struct SchedulerConfig { switch: SwitchBehavior, io_done: IoDoneBehavior, io_length: u32 }
struct SchedulerState { proc_info: Vec<ProcessInfo>, curr_proc: usize, io_finish_times: Vec<Vec<u64>>, clock_tick: u64 }

fn step(config: &SchedulerConfig, state: &mut SchedulerState) {
    // reads config by shared borrow, mutates state by exclusive borrow
    // never constructs or owns either — the driver loop owns both
}
```

The driver (`main`, or a `run` loop) owns `config: SchedulerConfig` and `state: SchedulerState`; `step` never initializes either, only borrows — which is your "never init with state for functional components" rule applied at the type level, not just by convention.