---
legacy_title: Eigene SQL-Datenbank in Python (MiniSQL)
---
# Your Own SQL Database in Python (MiniSQL)

## Goal
Build a standalone relational database **MiniSQL** in pure Python 3 (standard library
only; `sqlite3` may be used exclusively in the tests as a reference). The database stores
data persistently in a file, uses a B+ tree as its storage structure, a write-ahead log
(WAL) for crash safety, and supports transactions, JOINs and aggregations. Correctness is
demonstrated by automatically comparing against `sqlite3` across at least 500 generated
test queries.

## Functional Requirements
1. **Tokenizer/lexer** for SQL: keywords (case-insensitive), identifiers (also in
   `"double quotes"`), integers, floats, strings with `''` escapes, operators
   (`= <> != < <= > >= + - * / % ||`), comments (`--` and `/* */`). Error messages with
   line and column.
2. **Parser** (recursive descent with correct operator precedence) producing an AST for:
   - `CREATE TABLE` with types `INTEGER`, `REAL`, `TEXT`, `PRIMARY KEY`, `NOT NULL`,
     `UNIQUE`, `DEFAULT`; `DROP TABLE [IF EXISTS]`; `CREATE INDEX` / `DROP INDEX`.
   - `INSERT INTO t [(cols)] VALUES (...), (...)`, `INSERT ... SELECT`.
   - `UPDATE ... SET ... WHERE ...`, `DELETE FROM ... WHERE ...`.
   - `SELECT [DISTINCT] ... FROM ... [JOIN ... ON ...] [WHERE] [GROUP BY] [HAVING]
     [ORDER BY ... ASC|DESC] [LIMIT n [OFFSET m]]`, column aliases, table aliases,
     `*` and `t.*`.
   - Expressions: arithmetic, comparisons, `AND/OR/NOT`, `IS [NOT] NULL`, `BETWEEN`,
     `IN (list)`, `IN (subquery)`, `LIKE` with `%` and `_`, `CASE WHEN`, scalar
     subqueries, functions `ABS, LENGTH, UPPER, LOWER, COALESCE, ROUND, SUBSTR`.
   - `BEGIN`, `COMMIT`, `ROLLBACK`.
3. **Semantics** like SQLite, in particular three-valued logic with `NULL`, integer
   division, ordering of `NULL` (first for ASC), type affinity for the defined types.
4. **JOINs**: `INNER JOIN`, `LEFT [OUTER] JOIN`, `CROSS JOIN`, several joins in a row,
   self-joins with aliases. Implement nested-loop join and additionally hash join for
   equality conditions; the planner chooses automatically.
5. **Aggregations**: `COUNT(*)`, `COUNT(x)`, `COUNT(DISTINCT x)`, `SUM`, `AVG`, `MIN`,
   `MAX`, `GROUP BY` over several columns and expressions, `HAVING`.
6. **Storage layer**:
   - Page-based file (fixed page size, e.g. 4096 bytes) with a pager and an LRU page
     cache (configurable size).
   - **B+ tree** per table (key = rowid or INTEGER PRIMARY KEY) with leaf chaining for
     range scans, splits and merges/redistribution on delete.
   - Secondary indexes as separate B+ trees; the planner uses them for `=` and range
     conditions.
   - Serialization of rows into a compact binary format (varints or similar), overflow
     pages for long TEXT values.
7. **WAL and transactions**: changes are first written to the WAL (with checksums),
   commit = fsync of the WAL, a checkpoint transfers pages into the main file. After a
   simulated crash (process ends in the middle of a transaction, truncated WAL) the
   database must be consistent when reopened: committed transactions present,
   uncommitted ones gone. `ROLLBACK` discards everything.
8. **Interfaces**: Python API (`db = minisql.connect(path)`, `db.execute(sql, params)`
   with `?` placeholders, rows returned as tuples) and an interactive CLI
   (`python -m minisql file.db`) with `.tables`, `.schema`, `.quit`.
9. `EXPLAIN` prints the chosen execution plan as text.

## Architecture Guidelines
Package `minisql/` with clearly separated modules, e.g. `lexer.py`, `parser.py`, `ast.py`,
`planner.py`, `executor.py` (Volcano/iterator model), `btree.py`, `pager.py`, `wal.py`,
`record.py`, `catalog.py`, `cli.py`. Document the page format, record format and WAL
format in DESIGN.md.

## Test Strategy (pytest)
- Unit tests for lexer, parser (including error cases), record serialization, pager.
- B+ tree tests: 10,000 random inserts/deletes compared against a `dict`, invariant check
  (ordering, fill factor, height) after every operation in small runs.
- Crash tests: truncate the WAL at random positions, reopen the database, check
  consistency.
- **Differential testing**: a generator produces, with a fixed seed, at least 500 random
  valid queries (selects with joins, WHERE, GROUP BY, ORDER BY, NULL values, subqueries,
  plus UPDATE/DELETE) on identical data in MiniSQL and `sqlite3`; the results must match
  (compare as multisets when there is no ORDER BY, floats with a tolerance).
- At least 150 test functions in total (parametrized cases count individually).

## Acceptance Criteria
- `python3 -m pytest -q` passes completely, including the 500+ comparison queries.
- README.md with examples, DESIGN.md with the architecture, PROGRESS.md fully checked off.
- A benchmark script measures inserts/s and point lookups/s and documents the results.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
