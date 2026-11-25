# Interpreter für die Programmiersprache "Kiesel"

## Ziel
Entwirf und implementiere in reinem Python 3 (nur Standardbibliothek) die statisch
typisierte Skriptsprache **Kiesel** mit vollständiger Toolchain: Lexer, Parser,
Typchecker, Compiler nach Bytecode, Bytecode-VM mit eigenem Garbage Collector,
Standardbibliothek und REPL.

## Sprachumfang
1. **Typen**: `int` (beliebige Größe), `float`, `bool`, `str`, `nil`, Arrays `[T]`,
   Maps `{K: V}`, Funktionstypen `fn(A, B) -> C`, benutzerdefinierte `struct`s und
   `enum`s mit Payload (algebraische Datentypen), optionale Typen `T?`.
2. **Deklarationen**: `let` (unveränderlich), `var` (veränderlich), Funktionen mit
   Typannotationen, lokale Typinferenz für Variablen, Closures mit Capture by
   reference, rekursive und gegenseitig rekursive Funktionen.
3. **Kontrollfluss**: `if/else` als Ausdruck, `while`, `for x in range/array/map`,
   `break`, `continue`, `return`, `match` mit Mustern (Literale, Enum-Varianten mit
   Destrukturierung, Wildcard `_`, Guards) und Vollständigkeitsprüfung.
4. **Generics** für Funktionen (`fn map<T, U>(xs: [T], f: fn(T) -> U) -> [U]`) mit
   Typinferenz an der Aufrufstelle.
5. **Fehlerbehandlung**: `Result`-ähnliches eingebautes Enum und `?`-Operator;
   Laufzeitfehler (Division durch 0, Index außerhalb) mit Stacktrace und Zeilennummer.
6. **Module**: `import "datei.ks"` mit Namensräumen und Zykluserkennung.

## Komponenten
1. **Lexer** mit Positionsangaben, Strings mit Escapes und Interpolation
   (`"Hallo {name}"`), verschachtelte Kommentare.
2. **Parser** (Pratt-Parser für Ausdrücke) erzeugt einen typisierten AST; aussagekräftige
   Fehlermeldungen mit Quelltextausschnitt und Markierung (`^^^`), Fehlererholung, damit
   mehrere Fehler pro Lauf gemeldet werden.
3. **Typchecker**: Scopes, Inferenz (Hindley-Milner-artig für Generics/Lambdas genügt in
   vereinfachter Form), Prüfung von Mutabilität, Rückgabetypen aller Pfade,
   Vollständigkeit von `match`.
4. **Compiler** nach Stack-Bytecode: Konstantenpool, Sprünge, lokale Slots, Upvalues
   für Closures; einfache Optimierungen (Konstantenfaltung, Entfernen toten Codes).
   Ein Disassembler gibt Bytecode lesbar aus.
5. **VM**: Aufrufstack mit Frames, Tail-Call-Optimierung, Heap-Objekte (Strings,
   Arrays, Maps, Structs, Closures) in einem eigenen Heap-Modell.
6. **Garbage Collector**: Mark-and-Sweep (optional generational) über den eigenen Heap,
   Wurzeln = Stack, Globals, offene Upvalues; Statistiken (Anzahl Sammlungen, befreite
   Objekte); Stresstest-Modus, der bei jeder Allokation sammelt.
7. **Standardbibliothek**: `print`, `len`, `push/pop`, `keys/values`, String-Funktionen
   (`split`, `join`, `trim`, `replace`, `find`), Mathematik, `sort` mit Vergleichsfunktion,
   `map/filter/reduce`, Datei lesen/schreiben, `time`.
8. **REPL** (`python -m kiesel`) mit mehrzeiliger Eingabe, Beibehaltung von Definitionen
   zwischen Eingaben, `:type ausdruck`, `:dis funktion`, `:gc`.
9. **Beispielprogramme** in `examples/`: N-Queens, JSON-Parser in Kiesel, Brainfuck-
   Interpreter in Kiesel, Primzahlsieb, Binärbaum mit Enums.

## Teststrategie (pytest)
- Lexer-/Parser-Tests inkl. Fehlerfälle und Fehlermeldungsformat.
- Typchecker: mindestens 60 positive und negative Fälle.
- Golden-Tests: jedes Programm in `tests/programs/*.ks` hat eine erwartete Ausgabe
  `*.out` (mindestens 40 Programme).
- GC-Tests: Stressmodus über alle Golden-Tests muss dieselben Ausgaben liefern; nach
  Programmende sind alle unerreichbaren Objekte freigegeben.
- Property-Tests: zufällig generierte arithmetische Ausdrücke werden mit Pythons
  Auswertung verglichen (fester Seed, 300 Fälle).
- Insgesamt mindestens 200 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` ist grün, alle Beispielprogramme laufen.
- Sprachreferenz in `docs/LANGUAGE.md`, Architektur in DESIGN.md, PROGRESS.md aktuell.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
