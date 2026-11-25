---
topic: game_engine
spec_docs: false
---
# Schach-Engine mit Bitboards, Perft-Verifikation und UCI

## Ziel
Implementiere in reinem Python 3 (nur Standardbibliothek) eine spielstarke Schach-
Engine. Die Zuggenerierung muss nachweislich exakt sein (Perft), die Suche modern und
so effizient, wie es in Python möglich ist. Umfang: mindestens 8 Stunden konzentrierter
Arbeit.

## Funktionale Anforderungen
1. **Brettdarstellung** mit 64-Bit-Bitboards (Python-int), Figurenlisten, Zobrist-
   Hashing mit inkrementeller Aktualisierung, FEN lesen/schreiben.
2. **Zuggenerierung**: alle Regeln inklusive Rochade (mit Durchzugsprüfung),
   en passant (inklusive Fesselungsfall), Umwandlung, Schach-Evasion, gefesselte
   Figuren; Sliding-Pieces über Magic Bitboards oder Kogge-Stone; vollständig legale
   Generierung; make/unmake mit Undo-Stack.
3. **Regeln**: Matt, Patt, 50-Züge-Regel, dreifache Stellungswiederholung,
   ungenügendes Material; SAN- und UCI-Notation in beide Richtungen; PGN lesen und
   schreiben.
4. **Bewertung**: Material, Piece-Square-Tables mit Tapered Eval (Mittel-/Endspiel),
   Bauernstruktur (Doppel-, isolierte, Freibauern) mit Bauern-Hash-Tabelle, Mobilität,
   Königssicherheit, Läuferpaar; Static Exchange Evaluation.
5. **Suche**: iterative Vertiefung, PVS/Negamax mit Alpha-Beta, Aspiration Windows,
   Transpositionstabelle mit Ersetzungsstrategie, Quiescence Search mit SEE-Pruning,
   Null-Move-Pruning, Late Move Reductions, Killer-Moves, History-Heuristik, Check
   Extensions, Mate-Distance-Pruning, Zeitmanagement.
6. **Eröffnungsbuch** aus einer kleinen PGN-Sammlung; Endspiel: KQK/KRK-Matt sicher
   finden.
7. **UCI-Protokoll** (`uci`, `isready`, `position`, `go` mit wtime/btime/depth/movetime,
   `stop`, `info`-Ausgaben), damit die Engine in GUIs läuft.
8. **Selbstspiel-Turnier** zwischen Engine-Versionen mit Elo-Schätzung.

## Teststrategie (pytest)
- **Perft** für die Standardstellung bis Tiefe 4 und für die bekannten Teststellungen
  („Kiwipete“, Positionen 3–6 aus dem Chess-Programming-Wiki) mit den publizierten
  Knotenzahlen; Perft-Divide als Debug-Werkzeug.
- Zobrist: inkrementeller Hash == neu berechneter Hash nach 10.000 Zufallszügen.
- Taktik-Suite: mindestens 50 Mattaufgaben (Matt in 1–3) und taktische Stellungen
  müssen gelöst werden.
- SAN/PGN-Round-Trips, Regelgrenzfälle (Remisregeln), UCI-Dialoge.
- Mindestens 250 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Knoten pro Sekunde und Elo-Messungen in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
