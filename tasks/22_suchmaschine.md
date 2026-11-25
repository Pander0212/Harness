---
topic: text
spec_docs: false
---
# Volltext-Suchmaschine mit komprimiertem Index, BM25 und Abfragesprache

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) eine Volltext-Suchmaschine
(konzeptionell wie Lucene) mit Analysepipeline, segmentiertem, komprimiertem
invertiertem Index, Ranking, Abfragesprache, Snippets und Rechtschreibkorrektur, plus
kleiner Web-Oberfläche. Ein Testkorpus wird prozedural erzeugt bzw. aus im Projekt
enthaltenen Texten gebildet. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Analyse**: Unicode-Normalisierung, Tokenisierung (Wortgrenzen, Zahlen, E-Mails,
   URLs), Kleinschreibung, Stoppwörter, **Stemming** (Porter für Englisch, einfacher
   Stemmer für Deutsch), Synonyme, n-Gramme für Präfixsuche; konfigurierbare Analyzer
   pro Feld.
2. **Dokumentmodell** mit Feldern (Text, Schlüsselwort, Zahl, Datum), gespeicherte
   Felder, Dokument-IDs, Updates und Löschungen (Tombstones).
3. **Index**: Segmente (unveränderlich), Postings mit Positionen und Häufigkeiten,
   Kompression mit Delta-Kodierung + VByte und PForDelta, Skip-Listen, Term-Wörterbuch
   als FST oder sortiertes Array mit Präfixkompression, Normen pro Feld; Segment-Merging
   mit Merge-Policy; Commit-Punkte und Crash-Sicherheit.
4. **Abfragen**: Term, boolesch (AND/OR/NOT, `+`/`-`), Phrase (mit Slop), Präfix,
   Wildcard, Fuzzy (Levenshtein-Automat), Bereich (Zahl/Datum), Feldsuche, Boosting;
   **Abfragesprache** mit Parser und Fehlermeldungen.
5. **Ranking**: TF-IDF und **BM25** (Parameter k1/b je Feld), WAND bzw. MaxScore für
   schnelle Top-k-Suche, Facetten und Filter, Sortierung nach Feldern.
6. **Ergebnisdarstellung**: Snippets mit Hervorhebung (bestes Fenster), Paginierung,
   „Meinten Sie …“ (Rechtschreibkorrektur über Termstatistik und Edit-Distanz).
7. **Server**: HTTP-JSON-API und kleine HTML-Suchseite (`http.server`), Indexierung von
   Verzeichnissen mit Textdateien.
8. **Bewertung**: Relevanz-Testsammlung mit Anfragen und erwarteten relevanten
   Dokumenten; Metriken Precision@k, MAP, nDCG.

## Teststrategie (pytest)
- Analyse- und Stemmer-Tests (Porter-Referenzbeispiele).
- Kompression: Round-Trip für 10.000 zufällige Postinglisten.
- Abfrageergebnisse gegen eine naive Volltextsuche über denselben Korpus (300
  generierte Abfragen, identische Treffermengen; Scores gegen Referenzformel).
- WAND/MaxScore liefert dieselben Top-k wie die vollständige Auswertung.
- Crash-Tests beim Commit; Merge erhält alle Dokumente.
- Mindestens 280 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Indexformat und Messungen (Indexgröße, Abfragezeit,
  nDCG) in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
