**Intent: process-control / OS process-tree semantics.**

If you mean **`os.fork()` in Python**, the key idea is that `fork()` does **not** create a Git-like branch that you can “checkout.” It creates a second **process**.

### 1. What `fork()` does

Suppose you start with one process:

$$
P_{\text{parent}}
$$

Calling:

```python
pid = os.fork()
```

causes the OS to create:

$$
P_{\text{parent}}
\longrightarrow
\{P_{\text{parent}}, P_{\text{child}}\}
$$

Both processes continue execution **from the same point immediately after `fork()`**.

The crucial distinction is the return value:

```python
pid = os.fork()

if pid == 0:
    # child
    print("I am the child")
else:
    # parent
    print("I am the parent")
```

The OS makes the same source-level continuation appear differently to each process:

$$
\operatorname{fork}(P)
=
\begin{cases}
0 & \text{in child}\\
\operatorname{pid}_{child} & \text{in parent}
\end{cases}
$$

So:

```text
                 fork()
                   │
          ┌────────┴────────┐
          │                 │
       parent             child
    pid = child_pid      pid = 0
```

### 2. There is no "checkout"

If you're thinking:

> fork → work on child → checkout main

that's really a **Git process analogy**, not what `fork()` does.

The parent and child are now **two independent processes**. The scheduler can run either one:

$$
\text{OS scheduler}: \{P_{\text{parent}},P_{\text{child}}\}
\rightarrow
P_i
$$

For example:

```python
import os
import time

pid = os.fork()

if pid == 0:
    # child
    print("child")
    time.sleep(2)
    print("child finished")
else:
    # parent
    print("parent")
    print("waiting for child...")
    os.waitpid(pid, 0)
    print("child finished; parent continues")
```

The parent doesn't "switch back" to itself after the child. Instead, **both processes remain runnable**, and the OS scheduler decides when each executes.

### 3. If you specifically want "run child, then return to parent"

Use `waitpid()`:

```python
import os

pid = os.fork()

if pid == 0:
    print("child running")
    # child work
    os._exit(0)

else:
    print("parent waiting")
    os.waitpid(pid, 0)
    print("parent running again")
```

Conceptually:

$$
P
\xrightarrow{\operatorname{fork}}
(P,C)
$$

then:

$$
P \xrightarrow{\operatorname{waitpid}(C)}
P_{\text{blocked}}
$$

and after the child exits:

$$
C \xrightarrow{\operatorname{exit}} \varnothing
$$

so:

$$
P_{\text{blocked}}
\xrightarrow{\text{child exit}}
P_{\text{runnable}}
$$

This is probably the closest OS equivalent to:

```text
main
  ↓
fork child
  ↓
run child
  ↓
child exits
  ↓
main continues
```

### 4. If you're thinking about `fork()` as branching state

This is a useful formalization for your OSTEP-style modeling.

Let process state be:

$$
S = (\text{pid}, \text{pc}, \text{memory}, \text{status})
$$

Then `fork` transforms one process state into two:

$$
\operatorname{fork}:S
\rightarrow
S_{\text{parent}}\times S_{\text{child}}
$$

with approximately:

$$
S_{\text{parent}} =
(\text{pid}_p,\text{pc}_{fork+1},M,\text{READY})
$$

$$
S_{\text{child}} =
(\text{pid}_c,\text{pc}_{fork+1},M',\text{READY})
$$

where initially:

$$
M' \approx M
$$

but the memory is logically separate because of **copy-on-write**.

The important invariant is:

$$
\text{parent memory} \cap \text{child memory}
$$

is initially physically shareable, but a write causes the relevant page to be copied.

So `fork()` is better understood as **process-state duplication + divergent execution**, rather than checkout/branch switching.

If you want, I can also show the exact **Linux kernel state transition for `fork → scheduler → child exec → parent wait → child exit`** in the same algebraic style as your OSTEP scheduler model.
