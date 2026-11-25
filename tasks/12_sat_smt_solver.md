---
topic: algorithms
spec_docs: false
---
# CDCL-SAT-Solver und SMT-Solver für lineare Arithmetik und Bitvektoren

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) einen modernen CDCL-SAT-Solver und
darauf einen SMT-Solver im DPLL(T)-Stil mit Theorien für lineare Arithmetik und
Bitvektoren, inklusive SMT-LIB-2-Frontend. Umfang: mindestens 8 Stunden konzentrierter
Arbeit.

## Funktionale Anforderungen
1. **SAT-Kern**: DIMACS-Parser, Two-Watched-Literals, Unit Propagation, Konflikt-
   analyse mit First-UIP, Klausellernen, nicht-chronologisches Backjumping, VSIDS bzw.
   EVSIDS mit Heap, Phasen-Saving, Restarts (Luby und glucose-artig), Löschen gelernter
   Klauseln nach LBD, Klauselminimierung.
2. **Präprozessierung**: Subsumption, Self-Subsuming Resolution, Bounded Variable
   Elimination, Pure Literals.
3. **Inkrementelles Lösen** mit Assumptions und Ermittlung des Unsat-Kerns
   (Final Conflict).
4. **Beweise**: DRAT-Beweisausgabe für UNSAT und ein eigener, einfacher DRAT-Checker
   (RUP-Prüfung) zur Verifikation; Modellprüfung für SAT.
5. **Kodierungen**: Tseitin-Transformation, Kardinalitätsbedingungen (Sequential
   Counter, Totalizer), Pseudo-Boolean-Ungleichungen.
6. **SMT (DPLL(T))**: Theorie-Schnittstelle mit Propagation und Konflikterklärung;
   **Lineare reelle Arithmetik** mit dem Simplex-Verfahren nach Dutertre/de Moura
   (Bounds, Pivotieren, Erklärungen), **lineare ganzzahlige Arithmetik** per
   Branch-and-Bound; **Bitvektoren** per Bit-Blasting (Addition, Multiplikation,
   Vergleiche, Shifts, Extrakt/Konkatenation).
7. **SMT-LIB-2-Frontend**: `declare-fun`, `define-fun`, `assert`, `check-sat`,
   `get-model`, `push`/`pop`, `set-logic` (QF_LRA, QF_LIA, QF_BV, QF_UF-Teilmenge).
8. **Anwendungen**: Sudoku- und N-Damen-Löser, Graphfärbung, Programmverifikation einer
   kleinen Schleife per Bounded Model Checking.

## Teststrategie (pytest)
- Differenztests gegen einen einfachen Brute-Force-Solver für 2000 zufällige kleine
  Formeln (3-SAT nahe der Phasenübergangsschwelle, fester Seed).
- Jede UNSAT-Antwort wird mit dem DRAT-Checker verifiziert, jede SAT-Antwort per Modell.
- Bekannte Benchmarks (z. B. Pigeonhole, zufällige 3-SAT mit 150 Variablen) innerhalb
  von Zeitlimits; Laufzeiten dokumentieren.
- Simplex: Tests gegen exakte Lösungen mit `fractions.Fraction`; Bitvektor-Ergebnisse
  gegen direkte Python-Auswertung.
- SMT-LIB-Skripte mit erwarteten Ausgaben (mindestens 40 Dateien).
- Mindestens 250 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; DESIGN.md mit Heuristiken und Messungen.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
