```mermaid
graph TD
    subgraph BEFORE["BEFORE — show_tree branch duplicates both formulas"]
        direction TB
        B0["Bool³ = s × v × j"]
        B0 --> BA1["show_tree=True: solve? print action : 'Action?'"]
        B0 --> BA2["show_tree=False: always print action"]
        BA1 --> BT1["not just_final: TreeOut copy A"]
        BA2 --> BT2["not just_final: solve? print_tree : 'Tree?' — copy A'"]
        B0 --> BF["just_final=True block"]
        BF --> BT3["show_tree? print_tree : (solve? print_tree : 'Tree?') — copy B, re-derives A' again"]
        BT1 -.->|"provably equal only by hand-check"| BT2
        BT2 -.->|"re-derived a third time"| BT3
    end
```

```mermaid
graph TD
    subgraph AFTER["AFTER — one formula per output, cadence gates timing"]
        direction TB
        A0["ForkerConfig: basis × reveal × cadence"]
        A0 --> ActionOut["ActionOut = (basis=ACTION) ∨ (reveal=REVEAL)  — one term"]
        A0 --> TreeOut["TreeOut = (basis=TREE) ∨ (reveal=REVEAL)  — one term"]
        A0 --> Cadence["cadence : PER_STEP ⊎ FINAL_ONLY"]
        Cadence -->|"¬j"| Step["display_tree_step calls TreeOut"]
        Cadence -->|"j"| Final["emit_final calls TreeOut"]
        Step -.->|"same shared term"| TreeOut
        Final -.->|"same shared term"| TreeOut
        Step ---|"¬j ∨ j = ⊤,  ¬j ∧ j = ⊥"| Final
    end
```

**Before**: the tree-display rule is written out three separate times (`show_tree=True`, `show_tree=False`, and the trailing `just_final` block), and only hand-verification — the proof from a few messages back — establishes they're the same term; nothing in the code enforces that.

**After**: `TreeOut` is a single function `display_tree_step`/`emit_final` both call. `TelemetryCadence` doesn't add a fourth copy of the logic — it's a genuine partition ($\lnot j \lor j = \top$, disjoint) of *when* the one shared term fires, not a new instance of the term itself.