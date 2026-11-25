---
topic: compiler
---
# Scheme-Compiler mit hygienischen Makros, call/cc und eigener VM

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) eine Implementierung einer großen
Teilmenge von R7RS-small Scheme: Reader, Makroexpander, Compiler in eine eigene
Zwischensprache, Optimierungen und eine virtuelle Maschine mit echter Endrekursion,
erstklassigen Fortsetzungen und Garbage Collector. Umfang: mindestens 8 Stunden
konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Reader**: Listen, gepunktete Paare, Vektoren, Bytevektoren, Strings mit Escapes,
   Zeichen (`#\a`, `#\space`, `#\x41`), Zahlen (exakte Ganzzahlen, Brüche, Fließkomma),
   `quote`/`quasiquote`/`unquote(-splicing)`, Block- und Datum-Kommentare, Positionen.
2. **Datenmodell**: Paare, Symbole (interniert), Records (`define-record-type`),
   Prozeduren, Ports (String-Ports, Datei-Ports), Fehlerobjekte.
3. **Makros**: `syntax-rules` mit Hygiene (Umbenennung, Ellipsen auch verschachtelt,
   Literale), `let-syntax`/`letrec-syntax`; abgeleitete Formen (`let*`, `letrec*`,
   `cond` mit `=>`, `case`, `do`, `when`, `unless`, `named let`, `guard`,
   `parameterize`, `case-lambda`) über Makros.
4. **Compiler**: Alpha-Konvertierung, Closure-Konvertierung mit Analyse freier
   Variablen, Erkennung von Zuweisungen (Boxen nur bei Bedarf), Konstantenfaltung,
   Inlining kleiner Prozeduren, Elimination toten Codes, Erzeugung von Bytecode für eine
   Register- oder Stack-VM; Disassembler.
5. **VM**: echte Endrekursion (konstanter Stack bei endrekursiven Schleifen mit 10⁶
   Iterationen), **call/cc** mit vollständigen (wiedereintretbaren) Fortsetzungen,
   `dynamic-wind`, Ausnahmen (`raise`, `with-exception-handler`, `error`), Mehrfach-
   rückgabewerte (`values`, `call-with-values`).
6. **Speicher**: eigener Heap für Paare/Vektoren/Closures mit Mark-and-Sweep- oder
   Copying-GC, Wurzeln aus VM-Registern und Stack; Statistik.
7. **Standardbibliothek**: Listenoperationen, `map`/`for-each`/`fold`, Strings, Zeichen,
   Vektoren, numerischer Turm (exakt/inexakt, `exact->inexact`, `quotient`, `expt`),
   assoziative Listen, Hashtabellen, `sort`.
8. **REPL** mit Fehlermeldungen samt Quellposition und Backtrace; Ausführung von Dateien.

## Teststrategie (pytest)
- Reader- und Makrotests (inklusive Hygiene-Fälle wie `my-or` mit lokal gebundenem
  `temp`).
- Mindestens 150 Programmtests mit erwarteter Ausgabe: klassische Beispiele aus SICP
  (Streams, Meta-zirkulärer Evaluator in Scheme selbst!), Generatoren mit call/cc,
  Backtracking (`amb`), Koroutinen.
- Endrekursion: Schleife mit 1.000.000 Iterationen ohne Stack-Wachstum.
- GC-Stresstest: Ergebnisse unverändert, Speicherverbrauch begrenzt.
- Eigenschaftstests: Optimierungen ändern Ergebnisse nicht (Vergleich mit/ohne).
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; unterstützter Sprachumfang in docs/LANGUAGE.md;
  Architektur in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
