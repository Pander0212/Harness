---
topic: text
spec_docs: false
---
# Tabellenkalkulations-Engine mit Formelsprache, Neuberechnung und XLSX-Export

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) den Kern einer Tabellenkalkulation:
Formelsprache mit Parser und Auswertung, Abhängigkeitsgraph mit inkrementeller
Neuberechnung, über 120 Funktionen, mehrere Arbeitsblätter, Undo/Redo, CSV-Import und
Export im echten XLSX-Format (Office Open XML über `zipfile` und `xml`). Dazu ein
Terminal-Frontend. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Zelladressen**: A1- und R1C1-Notation, relative/absolute Bezüge (`$A$1`),
   Bereiche, ganze Spalten/Zeilen, Bezüge auf andere Blätter (`'Blatt 2'!B3`),
   benannte Bereiche.
2. **Formelsprache**: Tokenizer und Parser mit korrekter Operatorpräzedenz (inkl.
   Prozent, Potenz, Verkettung `&`, Vergleich, Schnittmengen-/Vereinigungsoperator),
   Array-Konstanten `{1,2;3,4}`, Fehlerwerte (`#DIV/0!`, `#REF!`, `#NAME?`, `#VALUE!`,
   `#N/A`, `#NUM!`, `#CIRCULAR`), Typkoerzion wie in gängigen Tabellenkalkulationen.
3. **Funktionen** (mindestens 120): Mathematik (SUMME/SUM, SUMMEWENN/SUMIFS,
   PRODUKT, RUNDEN-Familie, REST …), Statistik (MITTELWERT, MEDIAN, STABW, KGRÖSSTE,
   RANG …), Logik (WENN, WENNS, UND, ODER, WENNFEHLER), Text (LINKS, TEIL, FINDEN,
   ERSETZEN, TEXT mit Formatcodes, VERKETTEN, TEXTKETTE), Datum/Zeit (DATUM, HEUTE als
   injizierbare Uhr, NETTOARBEITSTAGE, EDATUM), Nachschlagen (SVERWEIS, WVERWEIS,
   INDEX, VERGLEICH, XVERWEIS), Finanzen (BW, ZW, RMZ, ZINS, NBW, IKV), dynamische
   Arrays mit Überlauf (FILTER, SORTIEREN, EINDEUTIG, SEQUENZ). Englische
   Funktionsnamen als Alias.
4. **Neuberechnung**: Abhängigkeitsgraph, Dirty-Markierung, topologische Neuberechnung
   nur betroffener Zellen, Zyklenerkennung mit Fehlerwert, volatile Funktionen,
   iterative Berechnung (optional mit Maximaliterationen).
5. **Bearbeitung**: Zeilen/Spalten einfügen und löschen mit korrekter Anpassung aller
   Bezüge (inkl. `#REF!`), Kopieren/Einfügen mit relativer Anpassung, Füllen,
   Sortieren von Bereichen, **Undo/Redo** als Befehlsmuster.
6. **Formatierung**: Zahlenformate (Datum, Prozent, Währung, benutzerdefinierte
   Formatcodes) und Anzeigeausgabe.
7. **Import/Export**: CSV mit Typinferenz, eigenes JSON-Format, **XLSX-Export und
   -Import** (Werte, Formeln, mehrere Blätter, gemeinsame Strings, Zahlenformate),
   so dass die Datei in gängigen Programmen öffnet.
8. **Terminal-UI** mit `curses` (Navigation, Eingabe, Formelleiste) als optionales
   Frontend.

## Teststrategie (pytest)
- Parser-Tests (Präzedenz, Fehlerfälle) und mindestens 400 Funktionstests mit
  erwarteten Werten (inkl. Fehlerwerte und Typkoerzion).
- Neuberechnung: nur betroffene Zellen werden neu berechnet (Zähler); Zyklen werden
  erkannt; modellbasierte Tests mit 2000 zufälligen Bearbeitungen gegen eine vollständige
  Neuberechnung.
- Einfügen/Löschen von Zeilen: Bezüge in allen Formeln korrekt angepasst.
- XLSX: Round-Trip Export → Import ergibt identische Arbeitsmappe; XML-Struktur validiert.
- Mindestens 350 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Funktionsreferenz in docs/FUNCTIONS.md, Architektur in
  DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
