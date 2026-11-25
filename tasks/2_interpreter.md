---
legacy_title: Interpreter für die Programmiersprache "Kiesel"
---
# Interpreter for the Programming Language "Pebble"

## Goal
Design and implement, in pure Python 3 (standard library only), the statically typed
scripting language **Pebble** with a complete toolchain: lexer, parser, type checker,
compiler to bytecode, bytecode VM with its own garbage collector, standard library and
REPL.

## Language Scope
1. **Types**: `int` (arbitrary size), `float`, `bool`, `str`, `nil`, arrays `[T]`, maps
   `{K: V}`, function types `fn(A, B) -> C`, user-defined `struct`s and `enum`s with
   payloads (algebraic data types), optional types `T?`.
2. **Declarations**: `let` (immutable), `var` (mutable), functions with type annotations,
   local type inference for variables, closures with capture by reference, recursive and
   mutually recursive functions.
3. **Control flow**: `if/else` as an expression, `while`, `for x in range/array/map`,
   `break`, `continue`, `return`, `match` with patterns (literals, enum variants with
   destructuring, wildcard `_`, guards) and exhaustiveness checking.
4. **Generics** for functions (`fn map<T, U>(xs: [T], f: fn(T) -> U) -> [U]`) with type
   inference at the call site.
5. **Error handling**: a built-in `Result`-like enum and the `?` operator; runtime errors
   (division by zero, index out of bounds) with a stack trace and line number.
6. **Modules**: `import "file.pb"` with namespaces and cycle detection.

## Components
1. **Lexer** with positions, strings with escapes and interpolation (`"Hello {name}"`),
   nested comments.
2. **Parser** (Pratt parser for expressions) produces a typed AST; meaningful error
   messages with a source excerpt and marker (`^^^`), error recovery so that several
   errors are reported per run.
3. **Type checker**: scopes, inference (Hindley-Milner-style for generics/lambdas in a
   simplified form is sufficient), checking of mutability, return types on all paths,
   exhaustiveness of `match`.
4. **Compiler** to stack bytecode: constant pool, jumps, local slots, upvalues for
   closures; simple optimizations (constant folding, dead code elimination). A
   disassembler prints bytecode in readable form.
5. **VM**: call stack with frames, tail-call optimization, heap objects (strings, arrays,
   maps, structs, closures) in its own heap model.
6. **Garbage collector**: mark-and-sweep (optionally generational) over the own heap,
   roots = stack, globals, open upvalues; statistics (number of collections, freed
   objects); a stress mode that collects on every allocation.
7. **Standard library**: `print`, `len`, `push/pop`, `keys/values`, string functions
   (`split`, `join`, `trim`, `replace`, `find`), math, `sort` with a comparison function,
   `map/filter/reduce`, reading/writing files, `time`.
8. **REPL** (`python -m pebble`) with multi-line input, definitions kept between inputs,
   `:type expression`, `:dis function`, `:gc`.
9. **Example programs** in `examples/`: N-Queens, a JSON parser written in Pebble, a
   Brainfuck interpreter written in Pebble, prime sieve, binary tree with enums.

## Test Strategy (pytest)
- Lexer/parser tests including error cases and the error message format.
- Type checker: at least 60 positive and negative cases.
- Golden tests: every program in `tests/programs/*.pb` has an expected output `*.out`
  (at least 40 programs).
- GC tests: stress mode over all golden tests must produce the same outputs; after the
  program ends all unreachable objects are freed.
- Property tests: randomly generated arithmetic expressions are compared with Python's
  evaluation (fixed seed, 300 cases).
- At least 200 test cases in total.

## Acceptance Criteria
- `python3 -m pytest -q` passes, all example programs run.
- Language reference in `docs/LANGUAGE.md`, architecture in DESIGN.md, PROGRESS.md up to
  date.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
