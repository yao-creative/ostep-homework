# Python Memory Management — ASCII Virtual Memory States

Here's a walkthrough of what CPython actually puts in memory, with diagrams for each stage.

---

## 0. The one-sentence model

> **Names live on the stack. Objects live on the heap. Every object carries a counter telling you how many names point at it.**

---

## 1. The process address space

```
+---------------------------------------------------------------+
|  VIRTUAL ADDRESS SPACE OF A RUNNING python3 PROCESS           |
+---------------------------------------------------------------+
|  LOW ADDRESSES                                                |
|  +--------------------+                                       |
|  |  TEXT / CODE       |  the interpreter's machine code       |
|  +--------------------+                                       |
|  |  RODATA            |  type objects, "immortal" singletons  |
|  |                    |  (Py_None, Py_True, small ints, ...)  |
|  +--------------------+                                       |
|  |  DATA / BSS        |  global state: obmalloc arena lists,  |
|  |                    |  free lists, GC generation headers    |
|  +--------------------+                                       |
|  |                    |                                       |
|  |  HEAP  (brk/mmap)  |  <-- EVERY Python object lives here   |
|  |                    |      including the 256 KiB pymalloc   |
|  |                    |      arenas                           |
|  |                    |                                       |
|  +--------------------+                                       |
|  |  STACK  (~8 MiB)   |  C stack: PyEval frames, and the      |
|  |                    |  PyObject* pointers we call "names"   |
|  +--------------------+                                       |
|  HIGH ADDRESSES                                               |
+---------------------------------------------------------------+
```

Key point: **a variable name is not a box containing a value.** It is a pointer (a `PyObject*`) sitting either on the C stack or inside a dict/array on the heap.

---

## 2. Names → objects, and the refcount

```python
x = [1000, 2000, 3000]
y = x
z = x[0]
```

```
  MODULE GLOBALS (a dict, itself on the heap)   PYTHON HEAP (objects)
  +-------------------+                    +-----------------------------+
  | 'x'  -> 0x9A10    |--+                 | PyListObject  @ 0x9A10      |
  | 'y'  -> 0x9A10    |--+---------------->|   ob_refcnt = 2   <---------+
  | 'z'  -> 0xC1      |--+                 |   ob_type   = <class 'list'>|
  +-------------------+  |                 |   ob_size   = 3             |
                         |                 |   ob_item   = 0xB000  --+   |
                         |                 +-------------------------|---+
                         |                                           |
                         |      C array ob_item[0..2]                |
                         |      +------+------+------+  <------------+
                         |      | 0xC1 | 0xC2 | 0xC3 |
                         |      +--+---+--+---+--+---+
                         |         |      |      |
                         |         v      v      v
                         |   +--------+ +--------+ +--------+
                         +-->| 1000   | | 2000   | | 3000   |
                             | rc = 1 | | rc = 1 | | rc = 1 |
                             +--------+ +--------+ +--------+
```

| Object | Why that refcount |
|---|---|
| the list | `x` and `y` → **2** |
| `1000` | only the list slot → **1** |
| `2000` | only the list slot → **1** |
| `3000` | only the list slot → **1** |

Note `z` was assigned *before* the diagram, so its pointer is `0xC1` — it points at the int, **not** at the list slot.

### Refcount transitions

```
  ACTION                          list rc   what happens
  ------------------------------  -------   ---------------------------
  x = [1000,2000,3000]               1      list + 3 ints allocated
  y = x                              2      INCREF
  z = x[0]                           2      INCREF on int 1000
  del y                              1      DECREF
  del x                              0      DECREF -> 0 -> deallocated!
                                             list memory returns to pool
                                             each int DECREF'd -> 0 -> freed
  z still alive                      -      int 1000 survives, rc = 1
```

**The rule:** the moment `ob_refcnt` hits zero, `tp_dealloc` runs *synchronously*, right there, on that line.

---

## 3. The allocator hierarchy — arenas, pools, blocks

`pymalloc` handles every object **≤ 512 bytes**. Bigger objects go straight to `malloc`/`mmap`.

```
  ARENA  (256 KiB, mmap'd, 256 KiB-aligned)     <-- obtained from the OS
  +---------+---------+---------+---------+----- - - - ----+
  | pool 0  | pool 1  | pool 2  | pool 3  |  ... x64       |
  | 4 KiB   | 4 KiB   | 4 KiB   | 4 KiB   |                |
  +---------+---------+---------+---------+----- - - - ----+
       |          |
       |          +-----------------------+
       v                                  v
  POOL for 32-byte class           POOL for 64-byte class
  (4096 / 32 = 128 blocks)         (4096 / 64 = 64 blocks)

  +------+------+------+------+------+------+------+------+ - -
  |  U   |  U   |  F   |  U   |  F   |  F   |  U   |  F   |
  +------+------+------+------+------+------+------+------+ - -
    blk0   blk1   blk2   blk3   blk4   blk5   blk6   blk7

   U = allocated to a live PyObject
   F = free. The first 8 bytes of a free block store a pointer to
       the NEXT free block. So the free list costs ZERO extra bytes.
```

Size classes (64-bit CPython, 16-byte alignment):

```
  class:  0    1    2    3    4   ...   30    31
  bytes:  16   32   48   64   80  ...  496   512
  blocks
  /pool:  256  128  85   64   51  ...   8     8
```

So a `list` header, an `int`, a short `str`, a small `dict` — all come from these pools.

```
  FREE  -->  returns the block to its pool's free list
             (memory is NOT returned to the OS)
  ALLOC -->  reuses a block from that same free list
             (usually no syscall at all)
```

This is why creating and destroying a million small objects in a loop is fast and why RSS stays flat.

---

## 4. What `del` actually does

```
  BEFORE                              AFTER  del x
  +----------------+                  +----------------+
  | 'x' -> 0x9A10  |--+               | (key removed)  |
  +----------------+  |               +----------------+
                      |  refcnt 2 -> 1
                      v
                 +----------+
                 | list     |               still reachable via y
                 | rc = 1   |
                 +----------+

  BEFORE                              AFTER  del x, del y
  +----------------+                  +----------------+
  | 'x' -> 0x9A10  |--+               | (both removed) |
  | 'y' -> 0x9A10  |--+               +----------------+
  +----------------+  |  refcnt 2 -> 0
                      v
                 +----------+   tp_dealloc   +--------------------+
                 | list     |  ==========>  | blocks returned to |
                 | rc = 0   |               | their pools; ints  |
                 +----------+               | DECREF'd -> freed  |
                                            +--------------------+
```

---

## 5. Reference cycles and the generational GC

Refcounting alone cannot free this:

```python
a = Obj("A")
a.peer = Obj("B")
a.peer.peer = a        # A -> B -> A
del a
```

```
  BEFORE del a                        AFTER del a
  +------------------+                +------------------+
  | global 'a'       |                | (gone)           |
  +--------+---------+                +------------------+
           v
     +-----------+  peer   +-----------+
     |  Obj A    |-------->|  Obj B    |
     |  rc = 2   |         |  rc = 1   |
     |           |<--------|           |
     +-----------+  peer   +-----------+
                                     ^
     rc(A)=2, rc(B)=1                |
     but NEITHER is reachable from the roots.
     Refcounting will never free them.  This is a leak.

  The cyclic GC finds them by:
    1. suspend refcounting
    2. subtract internal references:  A: 2-1 = 1,  B: 1-1 = 0
    3. anything still > 0 is externally reachable  ->  keep
    4. the rest are garbage  ->  break the cycle and free
```

Generations:

```
  THRESHOLDS  (gc.get_threshold() == (700, 10, 10))

   new objects
        |
        v
   +----------+  gen0 full (700 allocs - deallocs)
   |  GEN 0   |------------------------------+
   | 700 slot |  survivors get promoted      |
   +----------+                              v
        ^                              +----------+
        |                              |  GEN 1   |  gen1 collected
        |                              | 10 slot  |  every 10 gen0s
        |                              +----------+
        |                                   |
        |                                   v
        |                              +----------+
        |                              |  GEN 2   |  full collection:
        |                              | 10 slot  |  scans everything
        |                              +----------+
        |                                   |
        +-----------------------------------+
             long-lived objects end up here
             (gen2 collections are the expensive ones)
```

Only **container** objects are tracked by the GC. A plain `int`, `str`, `bytes`, or a `float` cannot participate in a cycle, so it is never tracked — that's a huge saving.

---

## 6. Things that are never freed at all

```
  +-----------------------------------------------------------+
  |  IMMORTAL / CACHED OBJECTS  (ob_refcnt is huge or fixed)  |
  +-----------------------------------------------------------+
  |  None, True, False, Ellipsis, NotImplemented              |
  |  small ints:  -5 .. 256                                   |
  |  single-character latin-1 strings                         |
  |  interned identifiers ("hello", "getattr", ...)           |
  |  type objects (list, dict, int, ...)                      |
  +-----------------------------------------------------------+

  a = 256; b = 256     ->  a is b   == True    (cached)
  a = 257; b = 257     ->  depends on constant folding
  s = sys.intern(x)    ->  forces interning
```

---

## 7. A runnable demo that prints the state

```python
import sys, gc

class Obj:
    __slots__ = ("name", "peer")
    def __init__(self, name):
        self.name = name
        self.peer = None
    def __repr__(self):
        return f"Obj({self.name!r})"

def rc(o):
    # sys.getrefcount's own arg = 1 hidden ref
    # rc()'s parameter `o`     = 1 hidden ref
    return sys.getrefcount(o) - 2

print("--- reference counting --------------------")
a = Obj("A")
print(f"a = Obj('A')       rc(a) = {rc(a)}")   # 1
b = a
print(f"b = a              rc(a) = {rc(a)}")   # 2
c = [a, a]
print(f"c = [a, a]         rc(a) = {rc(a)}")   # 4
del b
print(f"del b              rc(a) = {rc(a)}")   # 3
del c
print(f"del c              rc(a) = {rc(a)}")   # 1

print("\n--- reference cycles ----------------------")
a.peer = Obj("B")
a.peer.peer = a
print(f"cycle formed       rc(a) = {rc(a)}")   # 2
print(f"gc count={gc.get_count()}  thresholds={gc.get_threshold()}")
del a
gc.collect()
print("del a + gc.collect() -> cycle A<->B reclaimed")

print("\n--- cached / interned objects -------------")
x = 256; y = 256
print(f"256 is 256              -> {x is y}")   # True
s1 = "hello"; s2 = "hello"
print(f"'hello' is 'hello'      -> {s1 is s2}")  # True

print("\n--- allocation counters -------------------")
print("allocated blocks:", sys.getallocatedblocks())
```

Expected:

```
--- reference counting --------------------
a = Obj('A')       rc(a) = 1
b = a              rc(a) = 2
c = [a, a]         rc(a) = 4
del b              rc(a) = 3
del c              rc(a) = 1

--- reference cycles ----------------------
cycle formed       rc(a) = 2
gc count=[...]  thresholds=(700, 10, 10)
del a + gc.collect() -> cycle A<->B reclaimed
```

---

## 8. Watching the heap grow — `tracemalloc`

```python
import tracemalloc

tracemalloc.start()
snap1 = tracemalloc.take_snapshot()

data = [bytearray(1000) for _ in range(1000)]     # ~1 MB

snap2 = tracemalloc.take_snapshot()
for stat in snap2.compare_to(snap1, "lineno")[:3]:
    print(stat)

print(f"current = {tracemalloc.get_traced_memory()[0]:,} bytes")
print(f"peak    = {tracemalloc.get_traced_memory()[1]:,} bytes")
```

```
demo.py:6: size=1004 KiB (+1004 KiB), count=1001 (+1001)
current = 1,028,364 bytes
peak    = 1,028,364 bytes
```

Each `bytearray(1000)` is >512 bytes, so it bypasses pymalloc and goes straight to `malloc`.

---

## 9. Cheat sheet

```
 +--------------------------+----------------------------------------+
 | Concept                  | Number / rule                          |
 +--------------------------+----------------------------------------+
 | Name storage             | C stack or a dict/array on the heap    |
 | Object storage           | Heap, always                           |
 | Free trigger             | ob_refcnt == 0 -> immediate dealloc    |
 | pymalloc threshold       | objects <= 512 bytes                   |
 | Alignment / size classes | 16 B, 32 classes (16..512)             |
 | Pool                     | 4096 bytes, one size class per pool    |
 | Arena                    | 256 KiB, holds 64 pools                |
 | Memory returned to OS    | Almost never (arenas can be released)  |
 | GC threshold             | (700, 10, 10) for gen0/1/2             |
 | GC tracks                | Containers only, not ints/str/floats   |
 | Cached ints              | -5 .. 256                              |
 | Cyclic garbage           | Needs gc.collect(), refcount can't do it|
 +--------------------------+----------------------------------------+
```

### The three failure modes to remember

```
  1. LEAK BY CYCLE      A -> B -> A with no external root.
                        Fix: gc.collect(), or use weakref.

  2. LEAK BY CACHE      A global dict that only ever grows.
                        Fix: bounded LRU, or explicit clear().

  3. LEAK BY FRAME      A traceback / exception holding a frame
                        that holds a big object alive.
                        Fix: del tb, or break the chain early.
```

The whole system is: **refcount for the 99% case (deterministic, immediate), a generational tracing GC for the 1% that cycles, and a slab allocator underneath so both are cheap.**