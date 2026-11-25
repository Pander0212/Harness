---
topic: emulation
spec_docs: false
---
# WebAssembly-Laufzeit: Binärformat, Validierung, Interpreter und WAT-Parser

## Ziel
Implementiere in reinem Python 3 (nur Standardbibliothek) eine WebAssembly-Laufzeit
nach der Spezifikation WebAssembly 1.0 (MVP) plus ausgewählter Erweiterungen. Sie lädt
`.wasm`-Binärdateien und das Textformat `.wat`, validiert Module vollständig und führt
sie aus. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Binärdecoder**: LEB128 (signed/unsigned, Längengrenzen), alle Sektionen (Type,
   Import, Function, Table, Memory, Global, Export, Start, Element, Code, Data, Custom,
   DataCount), Namenssektion; präzise Fehlermeldungen bei fehlerhaften Modulen.
2. **WAT-Parser**: S-Ausdrücke, gefaltete und flache Instruktionen, Bezeichner
   (`$name`), Abkürzungen (inline export/import), Kommentare; Ausgabe als Binärformat
   (also ein Assembler `wat2wasm`) und Disassembler `wasm2wat`.
3. **Validierung** nach dem Algorithmus der Spezifikation (Operanden- und
   Kontrollstapel, polymorphe Stapel nach `unreachable`/`br`), alle Typregeln.
4. **Interpreter**: alle numerischen Instruktionen für i32/i64/f32/f64 mit exakter
   Semantik (Wraparound, Traps bei Division durch 0 und Überlauf, NaN-Behandlung,
   Rundung von f32 über `struct`), Kontrollfluss (block/loop/if/br/br_if/br_table),
   Aufrufe und indirekte Aufrufe mit Typprüfung, lineare Speicher mit grow und
   Grenzprüfung, Globals, Tabellen.
5. **Erweiterungen**: Sign-Extension-Operatoren, Non-trapping float-to-int,
   Multi-Value, Bulk-Memory (memory.copy/fill/init, data.drop).
6. **Einbettung**: Import von Python-Funktionen, Export-Aufrufe aus Python, WASI-
   Teilmenge (`fd_write`, `proc_exit`, `args_get`, `environ_get`, `clock_time_get`),
   damit einfache WASI-Programme laufen.
7. **Leistung**: Vorkompilierung des Funktionsrumpfs in eine interne Darstellung mit
   aufgelösten Sprungzielen; Messung von Instruktionen pro Sekunde.
8. **Spec-Test-Runner**: Unterstützung des `.wast`-Formats (`module`, `assert_return`,
   `assert_trap`, `assert_invalid`, `assert_malformed`, `invoke`, `register`).

## Teststrategie (pytest)
- Eigene `.wast`-Testdateien pro Instruktionsgruppe (mindestens 600 Assertions), nach
  dem Vorbild der offiziellen Spec-Tests, inklusive Randwerte (INT_MIN, NaN-Payloads,
  -0.0, Unendlich).
- Round-Trip wat → wasm → wat → wasm ergibt identische Binärdateien.
- Validierung: mindestens 80 ungültige Module werden mit der richtigen Fehlerklasse
  abgelehnt.
- Programme: Fakultät, Fibonacci, Sieb des Eratosthenes, Quicksort im linearen
  Speicher, ein WASI-„Hello World“.
- Mindestens 300 Testfälle (parametrisiert).

## Abnahmekriterien
- `python3 -m pytest -q` grün; unterstützte Features und Messwerte in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
