---
topic: compiler
legacy_title: Scheme-Compiler mit hygienischen Makros, call/cc und eigener VM
---
# Scheme Compiler with Hygienic Macros, call/cc and Its Own VM

## Goal
Build, in pure Python 3 (standard library only), an implementation of a large subset of
R7RS-small Scheme: reader, macro expander, compiler into your own intermediate language,
optimizations and a virtual machine with proper tail calls, first-class continuations and
a garbage collector. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Reader**: lists, dotted pairs, vectors, bytevectors, strings with escapes,
   characters (`#\a`, `#\space`, `#\x41`), numbers (exact integers, rationals, floats),
   `quote`/`quasiquote`/`unquote(-splicing)`, block and datum comments, positions.
2. **Data model**: pairs, symbols (interned), records (`define-record-type`), procedures,
   ports (string ports, file ports), error objects.
3. **Macros**: `syntax-rules` with hygiene (renaming, ellipses including nested ones,
   literals), `let-syntax`/`letrec-syntax`; derived forms (`let*`, `letrec*`, `cond` with
   `=>`, `case`, `do`, `when`, `unless`, named `let`, `guard`, `parameterize`,
   `case-lambda`) via macros.
4. **Compiler**: alpha conversion, closure conversion with free-variable analysis,
   detection of assignments (boxes only when needed), constant folding, inlining of small
   procedures, dead code elimination, bytecode generation for a register or stack VM;
   disassembler.
5. **VM**: proper tail calls (constant stack for tail-recursive loops with 10⁶
   iterations), **call/cc** with full (re-entrant) continuations, `dynamic-wind`,
   exceptions (`raise`, `with-exception-handler`, `error`), multiple return values
   (`values`, `call-with-values`).
6. **Memory**: your own heap for pairs/vectors/closures with a mark-and-sweep or copying
   GC, roots from VM registers and the stack; statistics.
7. **Standard library**: list operations, `map`/`for-each`/`fold`, strings, characters,
   vectors, numeric tower (exact/inexact, `exact->inexact`, `quotient`, `expt`),
   association lists, hash tables, `sort`.
8. **REPL** with error messages including source position and backtrace; running files.

## Test Strategy (pytest)
- Reader and macro tests (including hygiene cases such as `my-or` with a locally bound
  `temp`).
- At least 150 program tests with expected output: classic examples from SICP (streams,
  a metacircular evaluator written in Scheme itself!), generators with call/cc,
  backtracking (`amb`), coroutines.
- Tail calls: a loop with 1,000,000 iterations without stack growth.
- GC stress test: results unchanged, memory use bounded.
- Property tests: optimizations do not change results (compare with/without).
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; supported language scope in docs/LANGUAGE.md;
  architecture in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
