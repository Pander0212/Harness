# Eigene SQL-Datenbank in Python (MiniSQL)

## Ziel
Entwickle eine eigenständige relationale Datenbank **MiniSQL** in reinem Python 3 (nur
Standardbibliothek; `sqlite3` darf ausschließlich in den Tests als Referenz verwendet
werden). Die Datenbank speichert Daten persistent in einer Datei, verwendet einen
B+-Baum als Speicherstruktur, ein Write-Ahead-Log (WAL) für Crash-Sicherheit und
unterstützt Transaktionen, JOINs und Aggregationen. Die Korrektheit wird durch einen
automatischen Abgleich mit `sqlite3` über mindestens 500 generierte Testqueries belegt.

## Funktionale Anforderungen
1. **Tokenizer/Lexer** für SQL: Schlüsselwörter (case-insensitive), Bezeichner (auch in
   `"doppelten Anführungszeichen"`), Ganzzahlen, Gleitkommazahlen, Strings mit `''`-Escape,
   Operatoren (`= <> != < <= > >= + - * / % ||`), Kommentare (`--` und `/* */`).
   Fehlermeldungen mit Zeile und Spalte.
2. **Parser** (rekursiver Abstieg mit korrekter Operator-Präzedenz) zu einem AST für:
   - `CREATE TABLE` mit Typen `INTEGER`, `REAL`, `TEXT`, `PRIMARY KEY`, `NOT NULL`,
     `UNIQUE`, `DEFAULT`; `DROP TABLE [IF EXISTS]`; `CREATE INDEX` / `DROP INDEX`.
   - `INSERT INTO t [(cols)] VALUES (...), (...)`, `INSERT ... SELECT`.
   - `UPDATE ... SET ... WHERE ...`, `DELETE FROM ... WHERE ...`.
   - `SELECT [DISTINCT] ... FROM ... [JOIN ... ON ...] [WHERE] [GROUP BY] [HAVING]
     [ORDER BY ... ASC|DESC] [LIMIT n [OFFSET m]]`, Spalten-Aliase, Tabellen-Aliase,
     `*` und `t.*`.
   - Ausdrücke: Arithmetik, Vergleiche, `AND/OR/NOT`, `IS [NOT] NULL`, `BETWEEN`,
     `IN (Liste)`, `IN (Subquery)`, `LIKE` mit `%` und `_`, `CASE WHEN`, skalare
     Subqueries, Funktionen `ABS, LENGTH, UPPER, LOWER, COALESCE, ROUND, SUBSTR`.
   - `BEGIN`, `COMMIT`, `ROLLBACK`.
3. **Semantik** wie SQLite, insbesondere dreiwertige Logik mit `NULL`, Integer-Division,
   Sortierung von `NULL` (zuerst bei ASC), Typaffinität für die definierten Typen.
4. **JOINs**: `INNER JOIN`, `LEFT [OUTER] JOIN`, `CROSS JOIN`, mehrere Joins
   hintereinander, Self-Joins mit Aliasen. Implementiere Nested-Loop-Join und
   zusätzlich Hash-Join für Gleichheitsbedingungen; der Planer wählt automatisch.
5. **Aggregationen**: `COUNT(*)`, `COUNT(x)`, `COUNT(DISTINCT x)`, `SUM`, `AVG`, `MIN`,
   `MAX`, `GROUP BY` über mehrere Spalten und Ausdrücke, `HAVING`.
6. **Speicherschicht**:
   - Seitenbasierte Datei (feste Seitengröße, z. B. 4096 Bytes) mit Pager und
     LRU-Seitencache (konfigurierbare Größe).
   - **B+-Baum** pro Tabelle (Schlüssel = rowid bzw. INTEGER PRIMARY KEY) mit
     Blattverkettung für Range-Scans, Splits und Merges/Umverteilung beim Löschen.
   - Sekundärindizes als eigene B+-Bäume; der Planer nutzt sie für `=` und
     Bereichsbedingungen.
   - Serialisierung von Zeilen in ein kompaktes Binärformat (Varints o. Ä.),
     Overflow-Seiten für lange TEXT-Werte.
7. **WAL und Transaktionen**: Änderungen werden zuerst ins WAL geschrieben (mit
   Prüfsummen), Commit = fsync des WAL, Checkpoint überträgt Seiten in die Hauptdatei.
   Nach einem simulierten Absturz (Prozess endet mitten in einer Transaktion,
   abgeschnittenes WAL) muss die Datenbank beim Öffnen konsistent sein: committete
   Transaktionen vorhanden, nicht committete verschwunden. `ROLLBACK` verwirft alles.
8. **Schnittstellen**: Python-API (`db = minisql.connect(path)`, `db.execute(sql,
   params)` mit `?`-Platzhaltern, Rückgabe von Zeilen als Tupel) und eine interaktive
   CLI (`python -m minisql datei.db`) mit `.tables`, `.schema`, `.quit`.
9. `EXPLAIN` gibt den gewählten Ausführungsplan als Text aus.

## Architekturvorgaben
Paket `minisql/` mit klar getrennten Modulen, z. B. `lexer.py`, `parser.py`, `ast.py`,
`planner.py`, `executor.py` (Volcano-/Iterator-Modell), `btree.py`, `pager.py`, `wal.py`,
`record.py`, `catalog.py`, `cli.py`. Dokumentiere Seitenformat, Record-Format und
WAL-Format in DESIGN.md.

## Teststrategie (pytest)
- Unit-Tests für Lexer, Parser (inkl. Fehlerfälle), Record-Serialisierung, Pager.
- B+-Baum-Tests: 10.000 zufällige Inserts/Deletes mit Abgleich gegen ein `dict`,
  Invarianten-Check (Sortierung, Füllgrad, Höhe) nach jeder Operation in kleinen Läufen.
- Crash-Tests: WAL abschneiden an zufälligen Positionen, Datenbank neu öffnen,
  Konsistenz prüfen.
- **Differenzielles Testen**: ein Generator erzeugt mit festem Seed mindestens 500
  zufällige, gültige Queries (Selects mit Joins, WHERE, GROUP BY, ORDER BY, NULL-Werten,
  Subqueries, sowie UPDATE/DELETE) auf identischen Daten in MiniSQL und `sqlite3`; die
  Ergebnisse müssen übereinstimmen (bei fehlendem ORDER BY als Multimenge vergleichen,
  Gleitkommazahlen mit Toleranz).
- Insgesamt mindestens 150 Testfunktionen (parametrisierte Fälle zählen einzeln).

## Abnahmekriterien
- `python3 -m pytest -q` ist vollständig grün, inklusive der 500+ Vergleichsqueries.
- README.md mit Beispielen, DESIGN.md mit Architektur, PROGRESS.md vollständig abgehakt.
- Ein Benchmark-Skript misst Inserts/s und Point-Lookups/s und dokumentiert die
  Ergebnisse.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
