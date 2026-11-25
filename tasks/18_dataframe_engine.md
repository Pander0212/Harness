---
topic: database
mode: swarm
---
# Spaltenorientierte DataFrame-Bibliothek mit Lazy-Query-Optimierer

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) eine spaltenorientierte
DataFrame-Bibliothek mit eigenem Typsystem, CSV/JSON-Ein- und -Ausgabe, Ausdrucks-
Engine, Gruppierungen, Joins, Fensterfunktionen und einer Lazy-API mit Query-Optimierer.
Gedacht für den **Schwarm-Modus** (klar trennbare Module). Umfang: mindestens 8 Stunden
konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Spalten und Typen**: Int64, Float64, Bool, Utf8, Date, Datetime, Decimal,
   Categorical, Liste; Null-Masken (Bitmaps); typsichere Operationen und Casts mit
   klaren Fehlern.
2. **I/O**: CSV-Reader (Dialekte, Quotes, mehrzeilige Felder, Typinferenz mit
   Stichprobe, Encodings, Streaming großer Dateien in Chunks), CSV-Writer, JSON-Lines,
   ein eigenes binäres Spaltenformat mit Statistik pro Block (Min/Max/Nullzahl).
3. **Ausdrucks-Engine**: `col("a") * 2 + col("b")`, Vergleiche, logische Operatoren,
   `when/then/otherwise`, String-Funktionen (contains, replace, Regex-Extrakt, split),
   Datumsfunktionen, `is_null`/`fill_null`, Aggregationen.
4. **Operationen**: select, filter, with_columns, sort (mehrere Schlüssel, stabil,
   Nulls first/last), unique, head/tail, sample, explode, pivot/melt, concat.
5. **Group-by** mit Hash-Aggregation (sum, mean, min, max, count, n_unique, first, last,
   median, quantile, std) und mehreren Schlüsseln.
6. **Joins**: inner, left, right, outer, semi, anti, cross; Hash-Join und Sort-Merge-
   Join; As-of-Join für Zeitreihen; Behandlung doppelter Spaltennamen.
7. **Fensterfunktionen**: `over(partition)`, rank/dense_rank/row_number, kumulative
   Summen, rollende Fenster, lag/lead.
8. **Lazy-API und Optimierer**: logischer Plan, Predicate Pushdown, Projection Pushdown
   (auch in den CSV-Scan), Konstantenfaltung, Common-Subexpression-Elimination,
   Join-Reihenfolge nach Kardinalitätsschätzung; `explain()` zeigt Plan vor/nach.
9. **SQL-Frontend** (Teilmenge: SELECT/WHERE/GROUP BY/HAVING/ORDER BY/JOIN/LIMIT) auf
   denselben logischen Plan.

## Teststrategie (pytest)
- Differenztests gegen `sqlite3`: 400 generierte Abfragen über identische Daten
  (SQL-Frontend und Ausdrucks-API) müssen dieselben Ergebnisse liefern.
- Optimierer: Ergebnis mit/ohne Optimierung identisch für alle Testabfragen; Plan-Tests
  prüfen, dass Filter tatsächlich nach unten geschoben werden.
- CSV-Tests mit schwierigen Dateien (eingebettete Zeilenumbrüche, fehlende Werte,
  gemischte Typen).
- Null-Semantik in allen Operationen; Leistungstest mit 1 Mio. Zeilen dokumentiert.
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; API-Dokumentation in docs/API.md, Architektur in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
