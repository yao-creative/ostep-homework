**Intent, named precisely:** you want to hoist `Action` from an implicit, string-encoded shape into an explicit **tagged coproduct** (`Fork | Exit`), and split the pipeline into a **lexer** (`Σ* ⊎ List[Action] → List[Action]`, one uniform typed token stream regardless of source) followed by a **fold-step** (`Action × Q → Q`) that never touches strings again. This is exactly the fix from the last two messages, now made concrete.

### The ADT

```python
from dataclasses import dataclass
from typing import Union, List, Literal

@dataclass(frozen=True)
class Fork:
    parent: ProcessName
    child: ProcessName

@dataclass(frozen=True)
class Exit:
    target: ProcessName

Action = Union[Fork, Exit]   # the coproduct: Action = Fork ⊎ Exit
```

$\text{Action} = \text{Fork}(\text{Name}\times\text{Name}) \uplus \text{Exit}(\text{Name})$ — no more `len(tmp)`-based tag inspection anywhere downstream; `isinstance`/pattern-match on the constructor *is* the tag.

### Lexing: two sources, one typed sink

Both the CLI string and the generator should terminate in `List[Action]` — the generator was already building typed values internally and only serialized to string for no reason; stop it from ever doing that.

```python
def lex_raw_action(token: str) -> Action:
    """Σ* → Action.  Pure syntax check only — no access to ForkerState."""
    if '+' in token:
        parts = token.split('+')
        if len(parts) != 2:
            handle_bad_action(token)
        parent, child = parts
        return Fork(parent=ProcessName(parent), child=ProcessName(child))
    elif '-' in token:
        parts = token.split('-')
        if len(parts) != 2:
            handle_bad_action(token)
        target = parts[0]
        return Exit(target=ProcessName(target))
    else:
        handle_bad_action(token)   # NoReturn in practice; see typing note below


def lex_action_source(
    forker_config: ForkerConfig,
    forker_state: ForkerState,
) -> List[Action]:
    """
    Modular lexer: dispatches on *source*, not on string shape.
    RawCLI(Σ*)          -- action_list_arg present -> split + lex_raw_action per token
    Generated(List[Action]) -- otherwise -> new_action_list already returns Action directly
    Both branches converge on the same codomain: List[Action].
    """
    if forker_config.action_list_arg != '':
        tokens = forker_config.action_list_arg.split(',')
        return [lex_raw_action(t) for t in tokens]
    else:
        return new_action_list(forker_config, forker_state)   # see retyped version below
```

### `new_action_list` retyped — no serialize/reparse round-trip

```python
def new_action_list(forker_config: ForkerConfig, forker_state: ForkerState) -> List[Action]:
    action_list: List[Action] = []
    num_actions = 0
    fork_candidate_frontier = [forker_state.root_name]

    while num_actions < forker_config.max_actions:
        if random.random() < forker_config.fork_percentage:
            fork_choice = random_choice(fork_candidate_frontier)
            new_child, forker_state = get_name(forker_state)
            action_list.append(Fork(parent=fork_choice, child=new_child))   # typed, not '%s+%s'
            fork_candidate_frontier.append(new_child)
        else:
            exit_choice = random_choice(fork_candidate_frontier)
            if exit_choice == forker_state.root_name:
                continue
            fork_candidate_frontier.remove(exit_choice)
            action_list.append(Exit(target=exit_choice))                    # typed, not '%s-'
        num_actions += 1
    return action_list
```

### `action_step` — now a pure pattern-match, no parsing at all

This is the payoff: `action_step` takes an `Action`, not a `str`. Parsing has already happened upstream in the lexer; this function is purely `validate → apply`.

```python
def action_step(action: Action, forker_config: ForkerConfig, forker_state: ForkerState) -> ForkerState:
    match action:
        case Fork(parent=parent, child=child):
            if parent not in forker_state.process_list:
                handle_bad_action(f'{parent}+{child}')
            _, forker_state = do_fork(forker_state, parent, child)
            return forker_state

        case Exit(target=target):
            if target not in forker_state.process_list:
                handle_bad_action(f'{target}-')
            if forker_config.leaf_only and len(forker_state.children[target]) > 0:
                # guarded no-op: log-worthy, but not a state transition
                return forker_state
            return do_exit(forker_state, target, forker_config.local_reparent)
```

### The composite, updated

```python
def run(forker_config: ForkerConfig) -> None:
    forker_state = new_forker_state()
    print('                           Process Tree:')
    print_tree(forker_state, forker_config)
    print('')

    action_list = lex_action_source(forker_config, forker_state)      # G, unified
    forker_state = fold_action_list(action_list, forker_config, forker_state)  # fold_δ
    emit_tree(forker_config, forker_state)                            # O
```

### Why this satisfies both design goals at once

- **Modularity you asked for**: `lex_action_source` is the *only* place that knows two sources exist; everything past it (`fold_action_list`, `action_step`, `do_fork`/`do_exit`) is source-agnostic, operating purely on `List[Action]`.
- **Parse-don't-validate**: `lex_raw_action` is the only place doing string inspection — once it returns, a `Fork`/`Exit` value is a standing certificate that the *syntax* was legal. `action_step` still validates *semantics* (existence, `leaf_only`) because that's a separate axis (state-dependent), but it never re-derives the syntactic tag by inspecting string shape again — `match` on the constructor replaces `len(tmp)` entirely.

$$
\Sigma^*_{\text{raw}} \xrightarrow{\text{lex\_raw\_action}} \text{Action} \qquad\qquad \text{Generated} \xrightarrow{\text{id}} \text{Action}
$$
$$
\text{Action} \times Q \xrightarrow{\text{action\_step (validate + apply)}} Q
$$

Two small follow-ups still open from before, now cheap to fix while you're in here: (1) `do_fork`'s `self.process_list.append()` is missing its argument — should be `.append(child_proc)`; (2) `handle_bad_action` should be annotated `-> NoReturn` so `lex_raw_action`'s branches type-check as total.