---
topic: text
spec_docs: false
legacy_title: Tabellenkalkulations-Engine mit Formelsprache, Neuberechnung und XLSX-Export
---
# Spreadsheet Engine with a Formula Language, Recalculation and XLSX Export

## Goal
Build, in pure Python 3 (standard library only), the core of a spreadsheet: a formula
language with a parser and evaluation, a dependency graph with incremental recalculation,
more than 120 functions, several worksheets, undo/redo, CSV import and export to the real
XLSX format (Office Open XML via `zipfile` and `xml`). Plus a terminal frontend. Scope: at
least 8 hours of focused work.

## Functional Requirements
1. **Cell addresses**: A1 and R1C1 notation, relative/absolute references (`$A$1`),
   ranges, whole columns/rows, references to other sheets (`'Sheet 2'!B3`), named ranges.
2. **Formula language**: tokenizer and parser with correct operator precedence
   (including percent, exponent, concatenation `&`, comparison, intersection/union
   operators), array constants `{1,2;3,4}`, error values (`#DIV/0!`, `#REF!`, `#NAME?`,
   `#VALUE!`, `#N/A`, `#NUM!`, `#CIRCULAR`), type coercion as in common spreadsheets.
3. **Functions** (at least 120): math (SUM, SUMIF/SUMIFS, PRODUCT, the ROUND family,
   MOD …), statistics (AVERAGE, MEDIAN, STDEV, LARGE, RANK …), logic (IF, IFS, AND, OR,
   IFERROR), text (LEFT, MID, FIND, REPLACE, TEXT with format codes, CONCATENATE,
   TEXTJOIN), date/time (DATE, TODAY via an injectable clock, NETWORKDAYS, EDATE), lookup
   (VLOOKUP, HLOOKUP, INDEX, MATCH, XLOOKUP), finance (PV, FV, PMT, RATE, NPV, IRR),
   dynamic arrays with spilling (FILTER, SORT, UNIQUE, SEQUENCE).
4. **Recalculation**: dependency graph, dirty marking, topological recalculation of only
   the affected cells, cycle detection with an error value, volatile functions, iterative
   calculation (optionally with a maximum number of iterations).
5. **Editing**: inserting and deleting rows/columns with correct adjustment of all
   references (including `#REF!`), copy/paste with relative adjustment, fill, sorting
   ranges, **undo/redo** via the command pattern.
6. **Formatting**: number formats (date, percent, currency, custom format codes) and
   display output.
7. **Import/export**: CSV with type inference, your own JSON format, **XLSX export and
   import** (values, formulas, several sheets, shared strings, number formats) so that the
   file opens in common programs.
8. **Terminal UI** with `curses` (navigation, input, formula bar) as an optional frontend.

## Test Strategy (pytest)
- Parser tests (precedence, error cases) and at least 400 function tests with expected
  values (including error values and type coercion).
- Recalculation: only affected cells are recalculated (counter); cycles are detected;
  model-based tests with 2000 random edits against a full recalculation.
- Inserting/deleting rows: references in all formulas adjusted correctly.
- XLSX: round trip export → import yields an identical workbook; XML structure validated.
- At least 350 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; function reference in docs/FUNCTIONS.md, architecture in
  DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
