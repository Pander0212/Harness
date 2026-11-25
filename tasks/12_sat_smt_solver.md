---
topic: algorithms
spec_docs: false
legacy_title: CDCL-SAT-Solver und SMT-Solver für lineare Arithmetik und Bitvektoren
---
# CDCL SAT Solver and SMT Solver for Linear Arithmetic and Bit-Vectors

## Goal
Build, in pure Python 3 (standard library only), a modern CDCL SAT solver and on top of it
a DPLL(T)-style SMT solver with theories for linear arithmetic and bit-vectors, including
an SMT-LIB 2 frontend. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **SAT core**: DIMACS parser, two watched literals, unit propagation, conflict analysis
   with first UIP, clause learning, non-chronological backjumping, VSIDS or EVSIDS with a
   heap, phase saving, restarts (Luby and glucose-style), deletion of learned clauses by
   LBD, clause minimization.
2. **Preprocessing**: subsumption, self-subsuming resolution, bounded variable
   elimination, pure literals.
3. **Incremental solving** with assumptions and extraction of the unsat core (final
   conflict).
4. **Proofs**: DRAT proof output for UNSAT and your own simple DRAT checker (RUP check) for
   verification; model check for SAT.
5. **Encodings**: Tseitin transformation, cardinality constraints (sequential counter,
   totalizer), pseudo-Boolean inequalities.
6. **SMT (DPLL(T))**: theory interface with propagation and conflict explanation; **linear
   real arithmetic** with the simplex method per Dutertre/de Moura (bounds, pivoting,
   explanations), **linear integer arithmetic** via branch and bound; **bit-vectors** via
   bit-blasting (addition, multiplication, comparisons, shifts, extract/concat).
7. **SMT-LIB 2 frontend**: `declare-fun`, `define-fun`, `assert`, `check-sat`,
   `get-model`, `push`/`pop`, `set-logic` (subsets of QF_LRA, QF_LIA, QF_BV, QF_UF).
8. **Applications**: Sudoku and N-Queens solvers, graph coloring, verification of a small
   loop via bounded model checking.

## Test Strategy (pytest)
- Differential tests against a simple brute-force solver for 2000 random small formulas
  (3-SAT near the phase transition, fixed seed).
- Every UNSAT answer is verified with the DRAT checker, every SAT answer via its model.
- Known benchmarks (e.g. pigeonhole, random 3-SAT with 150 variables) within time limits;
  document run times.
- Simplex: tests against exact solutions with `fractions.Fraction`; bit-vector results
  against direct Python evaluation.
- SMT-LIB scripts with expected outputs (at least 40 files).
- At least 250 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; DESIGN.md with heuristics and measurements.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
