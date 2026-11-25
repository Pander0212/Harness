---
topic: database
mode: swarm
legacy_title: Spaltenorientierte DataFrame-Bibliothek mit Lazy-Query-Optimierer
---
# Columnar DataFrame Library with a Lazy Query Optimizer

## Goal
Build, in pure Python 3 (standard library only), a columnar DataFrame library with its own
type system, CSV/JSON input and output, an expression engine, grouping, joins, window
functions and a lazy API with a query optimizer. Meant for **swarm mode** (clearly
separable modules). Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Columns and types**: Int64, Float64, Bool, Utf8, Date, Datetime, Decimal,
   Categorical, List; null masks (bitmaps); type-safe operations and casts with clear
   errors.
2. **I/O**: CSV reader (dialects, quotes, multi-line fields, type inference from a
   sample, encodings, streaming large files in chunks), CSV writer, JSON Lines, your own
   binary columnar format with statistics per block (min/max/null count).
3. **Expression engine**: `col("a") * 2 + col("b")`, comparisons, logical operators,
   `when/then/otherwise`, string functions (contains, replace, regex extract, split),
   date functions, `is_null`/`fill_null`, aggregations.
4. **Operations**: select, filter, with_columns, sort (several keys, stable, nulls
   first/last), unique, head/tail, sample, explode, pivot/melt, concat.
5. **Group-by** with hash aggregation (sum, mean, min, max, count, n_unique, first, last,
   median, quantile, std) and several keys.
6. **Joins**: inner, left, right, outer, semi, anti, cross; hash join and sort-merge join;
   as-of join for time series; handling of duplicate column names.
7. **Window functions**: `over(partition)`, rank/dense_rank/row_number, cumulative sums,
   rolling windows, lag/lead.
8. **Lazy API and optimizer**: logical plan, predicate pushdown, projection pushdown (also
   into the CSV scan), constant folding, common subexpression elimination, join ordering
   by cardinality estimation; `explain()` shows the plan before/after.
9. **SQL frontend** (subset: SELECT/WHERE/GROUP BY/HAVING/ORDER BY/JOIN/LIMIT) on the same
   logical plan.

## Test Strategy (pytest)
- Differential tests against `sqlite3`: 400 generated queries over identical data (SQL
  frontend and expression API) must produce the same results.
- Optimizer: results with/without optimization identical for all test queries; plan tests
  check that filters are actually pushed down.
- CSV tests with difficult files (embedded line breaks, missing values, mixed types).
- Null semantics in all operations; performance test with 1 million rows documented.
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; API documentation in docs/API.md, architecture in
  DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
