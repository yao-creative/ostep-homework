**Intent, named precisely:** you're asking whether `check_legal` is doing **lexing/parsing** (yes) — and specifically, what **algebraic type** its output actually is, since `List[str]` with a length-based tag is very likely the wrong representation for what it's computing.

### What `check_legal` really computes

The grammar of an action string is a tiny regular language over two productions:

$$\text{Action} ::= \text{Name} \,{+}\, \text{Name} \;\mid\; \text{Name} \,{-}$$

Semantically that's a **coproduct** (disjoint union / sum type):

$$\text{Action} \;=\; \text{Fork}(\text{Name} \times \text{Name}) \;\uplus\; \text{Exit}(\text{Name})$$

and `check_legal : Σ* → Action` should be the **parsing homomorphism** that decides which summand a given string belongs to and extracts its payload.

### Why `List[str]` is the wrong encoding

Right now the coproduct's tag is smuggled in as **runtime list length** — `len(tmp) == 2` means "this is a Fork," `len(tmp) == 1` means "this is an Exit." That's a coproduct encoded as a **dependent-on-a-runtime-check container** instead of an actual discriminated union. It's the same class of anti-pattern as encoding `Option<T>` as a possibly-empty list: the type system can't tell you which case you're in, so every caller has to re-derive the tag by inspecting cardinality, and nothing stops a third, malformed shape (`len(tmp) == 3`) from silently reaching the caller if the parsing logic ever drifts.

Concretely, at the call site, `run()` has to re-decode the tag it already decoded once:
```python
if len(tmp) == 2:      # re-deriving "this was a Fork" from list length
    fork_choice, new_child = tmp[0], tmp[1]
else:                   # re-deriving "this was an Exit"
    exit_choice = tmp[0]
```
A proper sum type collapses that into one pattern match with no cardinality inspection at all — the discriminant is carried by the *type*, not recomputed from `len`.

### The honest signature

There's also a second, independent problem: the declared return type `List[str]` is a lie on the failure path. `handle_bad_action` calls `exit(1)`, which never returns — but Python doesn't know that (`exit` isn't typed `NoReturn` unless you annotate it as such), so the bare `return` at the bottom is reachable-by-the-type-checker and actually yields `None`. So the *true* codomain right now is $\text{List[str]} \uplus \{\text{None}\}$, not $\text{List[str]}$ — an unintentional third case nobody handles.

### What to check / refine

1. **Replace the list with the actual coproduct.** In Rust this is exactly an `enum`:
   ```rust
   enum Action<'a> {
       Fork { parent: &'a str, child: &'a str },
       Exit { target: &'a str },
   }
   ```
   and the parser becomes `fn parse_action(s: &str) -> Result<Action, ParseError>` — a **total function into a sum type wrapped in a Result**, rather than a partial function that terminates the process on failure. This is the same fix in Python: return `Optional[Action]` (or raise a real exception) instead of sometimes-`None`-sometimes-list.

2. **Keep syntax and semantics separated — this part of the current design is actually already correct.** `check_legal` only validates the *shape* of the string (does it parse at all). It does **not** check that `fork_choice`/`exit_choice` actually exist in `self.process_list`, or that `leaf_only` permits the exit — those are done afterward, in `run()`. Formally these are two different algebraic layers:
   - **Syntactic validity**: is $a \in \Sigma^*$ in the domain of the grammar at all? (a property of the string alone)
   - **Semantic/guard validity**: does the parsed `Action` lie in the *domain of $\delta$* for the current state $Q$? (a property of string **and** current state — this is exactly the guard-restriction on $\delta$ from the LTS answer earlier)

   Don't merge these into one function even while renaming — collapsing them would make `check_legal` implicitly depend on `self.process_list`, coupling a pure parse step to mutable state it doesn't need.

3. **One implicit invariant worth stating explicitly**: the parser's correctness depends on names never containing `'+'` or `'-'`. Since names are drawn only from `string.ascii_lowercase + string.ascii_uppercase`, this holds — but it's an **unenforced precondition** on `Name`, not something the type system guarantees. If you ever let user-supplied `-A` action-list strings name processes with arbitrary characters, `'+' in action` becomes ambiguous. Worth a comment or a `Name` newtype with a validated-alphabet invariant rather than a bare `String`/`str`.