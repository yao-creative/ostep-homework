**Intent, named:** you're checking whether "policy" and "behavior" map onto the **type/term distinction** — is `SchedulerSwitchPolicy` the *type* (a closed, statically-known set of constructors) and `process_switch_behavior` its *inhabitant* (the one term chosen for this run)? That's close, and it's the right instinct, but "static vs. runtime" isn't quite the axis — the more precise axis is **type vs. term**, and separately, **selection vs. interpretation**.

## Refining the claim

A policy type is a **coproduct** (sum type) — a closed, enumerable set of constructors known once and for all:

$$P = \{p_1, p_2, \dots, p_n\}, \qquad \text{e.g. } \text{SchedulerSwitchPolicy} = \{\text{ON\_IO}, \text{ON\_END}\}$$

That part of your intuition is exactly right and *is* static — the set $P$ never grows or shrinks, whether or not the program has even started running.

But a "behavior" isn't the type — it's a **term of that type**, i.e. an element $p \in P$. Picking which $p$ you get (from CLI args) happens at *init time*, not compile time, so calling it "runtime" isn't wrong, but it invites conflating two genuinely different runtime events:

1. **Selection** — choosing $p \in P$ once, when `options` are parsed. This value then sits still for the entire run, exactly like the Reader-environment $c \in C$ from before.
2. **Interpretation** — actually *using* $p$ to decide what happens, every single tick. This is a semantic map

$$\llbracket - \rrbracket : P \to (\Sigma \to A), \qquad \llbracket p \rrbracket = \pi_p$$

that turns the static tag into the live decision function $\pi_p$ applied against the current state $\sigma$.

So the precise statement isn't "policy is static, behavior is its runtime realization" — it's: **policy is the type $P$; behavior is a distinguished term $p \in P$ chosen once; the function $\pi_p = \llbracket p \rrbracket$ is what actually gets realized at runtime, repeatedly, once per tick.** "Behavior" names the *middle* stage (the fixed choice), not the ongoing execution itself.

## Why your naming convention is already correct under this reading

```python
class SchedulerSwitchPolicy(Enum):   # the type P — closed, static
    ON_IO = auto()
    ON_END = auto()

# field holding the chosen term, i.e. the behavior
process_switch_behavior: SchedulerSwitchPolicy
```

This is the standard "type names the category of choices, value names the instance" pattern — you don't need a third name for $\pi_p$ itself, since that function lives implicitly inside `next_proc`/`handle_process_clock_cycle`, closing over `process_switch_behavior` to decide what to do each tick. Keep the field named `_behavior` (it's the term), the class named `_Policy` (it's the type), and don't be tempted to also call the interpreting function a "behavior" — that would re-collapse the distinction you just correctly drew.