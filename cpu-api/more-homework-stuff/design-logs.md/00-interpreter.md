Yes—but there are **three different notions of “single thread”** that are easy to conflate.

**Intent: interpreter-level concurrency semantics of `fork()`.**

### 1. Before `fork()`

Suppose Python is executing:

```python
x = 1
pid = os.fork()
```

At the instant before `fork`, you have one OS process:

$$
P = (\text{Python interpreter},\ \text{OS thread }T_0)
$$

If this is an ordinary single-threaded Python program, there is indeed **one Python thread of execution**.

The interpreter is essentially doing:

$$
\text{source}
\rightarrow
\text{bytecode}
\rightarrow
\text{execute bytecode}
\rightarrow
\text{next bytecode}
$$

### 2. What happens at `fork()`?

`os.fork()` ultimately asks the OS to duplicate the **process**.

From Python's perspective, execution continues at the next statement:

```python
pid = os.fork()

print("hello")
```

After `fork`, there are now two processes:

$$
P
\xrightarrow{\operatorname{fork}}
\{P_{\text{parent}},P_{\text{child}}\}
$$

Each has its own Python interpreter state.

Conceptually:

$$
\begin{aligned}
P_{\text{parent}} &: \quad \text{Python interpreter}_P + T_0\\
P_{\text{child}} &: \quad \text{Python interpreter}_C + T_0'
\end{aligned}
$$

The child isn't calling the Python interpreter from scratch. Its memory image was inherited from the parent.

So both processes resume here:

```python
print("hello")
```

but they execute it independently.

---

### 3. Is only one thread "focused" at a time?

At the **CPU-core level**, each CPU core executes one hardware thread at a time.

So with one CPU core:

$$
T_P \quad\longrightarrow\quad T_C
\quad\longrightarrow\quad T_P
\quad\longrightarrow\quad T_C
$$

The OS scheduler rapidly switches between them.

With multiple cores, however:

$$
\begin{aligned}
\text{Core 0}:&\quad T_P\\
\text{Core 1}:&\quad T_C
\end{aligned}
$$

They can literally execute simultaneously.

So **no**, there isn't necessarily one thread globally executing at a time.

---

### 4. And then there's Python's GIL

This is where Python-specific terminology matters.

For **CPython**, the traditional GIL means that, within a given interpreter, only one thread at a time executes Python bytecode.

For example:

```python
import threading

def f():
    while True:
        pass

threading.Thread(target=f).start()
threading.Thread(target=f).start()
```

You can have:

$$
T_1,T_2
$$

but ordinarily only one is executing Python bytecode at a time within that interpreter.

However, this does **not** mean the OS has only one thread running.

Threads can:

* execute native code
* perform I/O
* wait
* sleep
* run C extensions that release the GIL

And modern CPython also has **free-threaded builds** where the GIL can be disabled.

---

### 5. `fork()` is different from Python threads

This is the key conceptual distinction:

```text
threading
    ↓
same process
    ↓
same interpreter
    ↓
multiple OS threads
```

versus:

```text
fork()
    ↓
two processes
    ↓
two independent interpreter instances
    ↓
each has its own process state
```

Formally, if your process state is:

$$
P=(M,T,I)
$$

where:

* $M$ = process memory
* $T$ = OS thread set
* $I$ = interpreter state

then `fork()` approximately creates:

$$
P
\mapsto
(P_1,P_2)
$$

with:

$$
I_1 \approx I_2
$$

at the instant of the fork, but thereafter:

$$
I_1(t) \neq I_2(t)
$$

as they execute different branches.

---

### 6. Your earlier "checkout" intuition

You can therefore think of:

```python
pid = os.fork()

if pid == 0:
    # child
else:
    # parent
```

as **branching the execution state**, not switching a single interpreter between branches.

$$
\boxed{
\text{one execution state}
\overset{\text{fork}}{\longrightarrow}
\text{two execution states}
}
$$

The scheduler subsequently chooses which process/thread gets CPU time.

So if you're modeling this like your OSTEP state machine, the important abstraction is actually:

$$
\text{SystemState}
=
\{P_1,P_2,\ldots,P_n\}
+
\text{SchedulerState}
$$

rather than a single `current_process` being permanently focused. `current_process` is a **scheduler observation at a particular instant**, not the totality of the system's execution state.
