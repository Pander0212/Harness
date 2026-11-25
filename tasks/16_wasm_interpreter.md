---
topic: emulation
spec_docs: false
legacy_title: "WebAssembly-Laufzeit: Binärformat, Validierung, Interpreter und WAT-Parser"
---
# WebAssembly Runtime: Binary Format, Validation, Interpreter and WAT Parser

## Goal
Implement, in pure Python 3 (standard library only), a WebAssembly runtime following the
WebAssembly 1.0 (MVP) specification plus selected extensions. It loads `.wasm` binaries
and the `.wat` text format, fully validates modules and executes them. Scope: at least
8 hours of focused work.

## Functional Requirements
1. **Binary decoder**: LEB128 (signed/unsigned, length limits), all sections (type,
   import, function, table, memory, global, export, start, element, code, data, custom,
   data count), name section; precise error messages for malformed modules.
2. **WAT parser**: S-expressions, folded and flat instructions, identifiers (`$name`),
   abbreviations (inline export/import), comments; output as binary format (i.e. an
   assembler `wat2wasm`) and a disassembler `wasm2wat`.
3. **Validation** following the algorithm of the specification (operand and control
   stacks, polymorphic stacks after `unreachable`/`br`), all typing rules.
4. **Interpreter**: all numeric instructions for i32/i64/f32/f64 with exact semantics
   (wraparound, traps on division by zero and overflow, NaN handling, f32 rounding via
   `struct`), control flow (block/loop/if/br/br_if/br_table), calls and indirect calls
   with type checks, linear memory with grow and bounds checks, globals, tables.
5. **Extensions**: sign-extension operators, non-trapping float-to-int, multi-value,
   bulk memory (memory.copy/fill/init, data.drop).
6. **Embedding**: importing Python functions, calling exports from Python, a WASI subset
   (`fd_write`, `proc_exit`, `args_get`, `environ_get`, `clock_time_get`) so that simple
   WASI programs run.
7. **Performance**: precompilation of function bodies into an internal representation
   with resolved branch targets; measurement of instructions per second.
8. **Spec test runner**: support for the `.wast` format (`module`, `assert_return`,
   `assert_trap`, `assert_invalid`, `assert_malformed`, `invoke`, `register`).

## Test Strategy (pytest)
- Your own `.wast` test files per instruction group (at least 600 assertions), modeled
  on the official spec tests, including boundary values (INT_MIN, NaN payloads, -0.0,
  infinity).
- Round trip wat → wasm → wat → wasm yields identical binaries.
- Validation: at least 80 invalid modules are rejected with the correct error class.
- Programs: factorial, Fibonacci, sieve of Eratosthenes, quicksort in linear memory, a
  WASI "Hello World".
- At least 300 test cases (parametrized).

## Acceptance Criteria
- `python3 -m pytest -q` passes; supported features and measurements in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
