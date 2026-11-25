---
topic: parser
legacy_title: Regex-Engine, Lexer-Generator und LALR(1)-Parser-Generator
---
# Regex Engine, Lexer Generator and LALR(1) Parser Generator

## Goal
Build, in pure Python 3 – without the `re` module (allowed only in tests as a reference) –
a regex engine with several execution strategies as well as a lexer generator and an
LALR(1) parser generator (conceptually like lex/yacc) that together produce parsers for
real languages. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Regex parser**: literals, escapes, character classes (including ranges, negation,
   `\d\w\s` and Unicode categories via `unicodedata`), quantifiers (`* + ? {m,n}`, greedy
   and lazy), groups (capturing, non-capturing, named), alternation, anchors
   (`^ $ \b \B \A \z`), flags (i, m, s, x).
2. **Execution**: Thompson NFA simulation (linear time), **lazy DFA** with a cache,
   **DFA minimization** (Hopcroft), a backtracking engine for backreferences and
   lookahead/lookbehind; automatic choice of strategy; capture groups also in NFA mode
   (Pike VM).
3. **API** similar to `re`: `compile`, `match`, `fullmatch`, `search`, `findall`,
   `finditer`, `sub` (with group references and a function), `split`.
4. **Lexer generator**: token specification via regexes with priorities, longest match,
   states (e.g. for strings/comments), generation of a table DFA, error handling with
   positions; code generation as a standalone Python module.
5. **Parser generator**: grammar DSL with actions, FIRST/FOLLOW, LR(0) automaton,
   **LALR(1) lookaheads** (DeRemer-Pennello or propagation), precedence and associativity
   declarations, conflict reports with examples, error recovery with an `error` token,
   code generation as a Python module; additionally an LL(1) mode with conflict
   detection.
6. **Example languages** generated with the tools: a calculator with variables, a JSON
   parser (fully compliant), a subset of C expressions and statements with an AST, an
   INI/TOML-like format.

## Test Strategy (pytest)
- Differential tests against `re`: 3000 randomly generated pattern/input pairs (fixed
  seed) for `match`, `search`, groups and `sub` within the common feature set.
- Pathological patterns (`(a*)*b` on long inputs) run in linear time in NFA/DFA mode
  (time-limit test).
- DFA minimization: minimal DFA of the same language for known cases (state counts).
- Parser generator: classic grammars from the Dragon Book with expected tables/conflicts;
  the generated JSON parser against `json` on 500 random documents.
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; algorithms in DESIGN.md, user manual in docs/.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
