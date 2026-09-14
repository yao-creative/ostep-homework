## Citations for the formalization

Here's where each piece of vocabulary comes from, with what each source actually says and how precisely it maps onto your four-stage boundary.

### 1. Linearization point — Herlihy & Wing, 1990

**M. Herlihy, J. Wing, "Linearizability: A Correctness Condition for Concurrent Objects," *ACM TOPLAS* 12(3), 1990.** PDF: https://cs.brown.edu/people/mph/HerlihyW90/p463-herlihy.pdf

This is the precise origin of "observation must correspond to a single well-defined instant." A later paper glosses it exactly as your $e_i$ tag: "Every outstanding operation will execute exactly one intermediate line between its invocation and response. This is the linearization point of the operation: the point at which it takes effect." And the subtlety you ran into — that this point isn't always the *textually* obvious one — is well documented: "the linearization points of different calls of the same method may correspond to different statements in the method's, or even other method's, program text." That's exactly why `resolve_instructions_done`'s call site (not its definition) was the actual bug — the "point at which DONE takes effect" needed to move, not the function itself.

### 2. Sequence point — ISO C standard, §5.1.2.3 / §6.5

Canonical statement (matches across every source I checked, including the CMU SEI wiki citing the actual ISO/IEC 9899:2011 text): "a sequence point defines any point in a computer program's execution at which it is guaranteed that all side effects of previous evaluations will have been performed, and no side effects from subsequent evaluations have yet been performed." https://en.wikipedia.org/wiki/Sequence_point

This is the cleanest one-sentence definition of your observation cut. C's version is at expression-granularity; yours is at tick-granularity, but the "before fully settled / after not yet started" shape is identical, and it's the sharpest short definition to cite if you want a one-liner in a docstring.

### 3. "Make actions atomic" — Lampson, 1983

**B. Lampson, "Hints for Computer System Design," *SOSP* 1983.** PDF: https://www.cs.princeton.edu/courses/archive/fall15/cos518/papers/hints-design.pdf

Confirmed as a first-class slogan in the paper's own summary figure, listed alongside "Log updates": "Log updates / Make actions atomic". This is the paper you were already working from — worth citing directly rather than paraphrasing, since it's literally titled with the property your bug violated. Saltzer's MIT 6.033 discussion notes are also a good secondary read: https://web.mit.edu/Saltzer/www/publications/recguides/Hints.html — "This paper provides an introduction to 'system thinking'."

### 4. seL4's "incremental consistency" — closest real industrial term to your prologue/epilogue split

**seL4 whitepaper**, https://sel4.systems/About/seL4-whitepaper.pdf — describes exactly the discipline of breaking one logical action into ordered sub-steps, each leaving the system in a *consistent* (observable) state: "seL4 deals with this situation by breaking such operations into short sub-operations, and making it possible to abort and restart the complete operation after each sub-operation, should there be a pending interrupt. The approach is called incremental consistency. Each sub-operation transforms the kernel from a consistent state into another consistent state."

I'll flag honestly: I don't have a verified citation for a specific field name like "`NeedsToBeRescheduled`" in current seL4 source — I asserted that too specifically earlier without checking, and search didn't surface it, so treat that detail as unconfirmed. What *is* well-documented and directly relevant is seL4's scheduling-context/budget accounting being explicitly deferred across kernel entry/exit: "On kernel entry... the kernel updates the current timestamp and stores the time since the last entry... Threads are only charged if the scheduling context changes, in order to avoid reprogramming the timer." — a real instance of "epilogue bookkeeping deferred past the point where it's computed," matching your $e_i>n$ category.

### 5. Functional core, imperative shell — Gary Bernhardt, "Boundaries" (2012 talk)

Talk: https://www.destroyallsoftware.com/talks/boundaries — summarized accurately here: https://github.com/kbilsted/Functional-core-imperative-shell — "'Imperative shell' that wraps and uses your 'functional core'... The core contains no dependencies, but encapsulates the different logic paths... the way to figure out the separation is by doing as much as you can without mutation, and then encapsulating the mutation separately."

This is the best-known industrial name for your dispatch/observation vs. prologue/epilogue split in general — pure computation (dispatch + observation, both side-effect-free with respect to future ticks) surrounded by state-committing edges (prologue reads past commitments, epilogue writes future ones). A concrete recent writeup applying it plainly: "The functional core is code that takes data in and returns data out... The imperative shell is everything else: it reads from the world, calls the core with the data it gathered, and writes the result back to the world."

### Which term to reach for, and when

| Your concept | Best-fit citation | Use when explaining to... |
|---|---|---|
| the observation cut is a forced, unique instant | Herlihy & Wing, linearization point | someone thinking about concurrency/ordering correctness |
| "before fully done, after not yet begun" — the sharpest one-liner | ISO C, sequence point | writing a terse code comment |
| the *design principle* that motivated fixing it | Lampson, "make actions atomic" | justifying the refactor to a reviewer |
| deferring a write past the observation cut without losing correctness | seL4, incremental consistency | someone from an OS/kernel background |
| separating write-free (pure) vs. write-committing (effectful) code at a hard boundary | Bernhardt, functional core / imperative shell | someone from an application/product engineering background |