---
topic: distributed
spec_docs: false
---
# Raft-Konsens und linearisierbarer Key-Value-Store mit Fehlerinjektion

## Ziel
Implementiere in reinem Python 3 (nur Standardbibliothek) einen replizierten
Key-Value-Store auf Basis des Raft-Konsensprotokolls und beweise seine Korrektheit mit
einem Jepsen-artigen Testframework: deterministische Simulation, Fehlerinjektion und ein
Linearisierbarkeits-Checker. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Deterministischer Simulator**: virtuelle Uhr, Nachrichtennetz mit Verzögerung,
   Verlust, Duplikaten, Umordnung, Netzwerkpartitionen (beliebige Teilmengen,
   asymmetrisch), Knotenabstürze mit Verlust des flüchtigen Zustands, Neustarts,
   Uhren-Drift. Jeder Lauf ist per Seed reproduzierbar.
2. **Raft** vollständig nach dem Paper (Extended Version): Leader-Wahl mit
   randomisierten Timeouts, Log-Replikation, Commit-Regel (nur Einträge des aktuellen
   Terms direkt), persistenter Zustand (currentTerm, votedFor, Log) über eine simulierte
   Platte mit fsync-Semantik, PreVote, CheckQuorum, Leader-Lease für Lesezugriffe,
   ReadIndex für linearisierbare Reads.
3. **Log-Kompaktierung**: Snapshots, InstallSnapshot-RPC in Chunks, Wiederanlauf aus
   Snapshot + Log.
4. **Mitgliedschaftsänderungen**: Joint Consensus (oder Single-Server-Changes mit
   korrekter Behandlung), Learner-Knoten, Leader-Transfer.
5. **Key-Value-Store** als Zustandsmaschine: `get`, `put`, `delete`, `cas`
   (compare-and-swap), Transaktionen über mehrere Schlüssel, Client-Sessions mit
   Request-IDs zur Deduplizierung (exactly-once Semantik).
6. **Client-Bibliothek** mit Leader-Erkennung, Redirects, Timeouts und Wiederholungen.
7. **Linearisierbarkeits-Checker** (Wing-Gong/Knossos-Prinzip mit Memoisierung) für
   Historien aus Aufrufen und Antworten inklusive unbestimmter Ergebnisse (Timeouts).
8. **Nemesis-Szenarien**: zufällige Partitionen, Leader isolieren, Mehrheit/Minderheit
   trennen, Abstürze während Snapshot-Übertragung, Uhrensprünge.
9. **Visualisierung**: Textausgabe der Zeitleiste (wer war wann Leader, Terms, Commits).

## Teststrategie (pytest)
- Unit-Tests für jede RPC-Regel (Abbildung 2 des Raft-Papers Punkt für Punkt).
- Sicherheitseigenschaften als Invarianten nach jedem Simulationsschritt geprüft:
  Election Safety, Leader Append-Only, Log Matching, Leader Completeness,
  State Machine Safety.
- Mindestens 200 randomisierte Simulationsläufe (feste Seeds) mit Nemesis und
  Linearisierbarkeitsprüfung der gesamten Historie.
- Checker selbst mit bekannten linearisierbaren und nicht linearisierbaren Historien
  testen (mindestens 30 Fälle).
- Liveness: nach Ende aller Störungen wird innerhalb begrenzter Zeit ein Leader gewählt
  und alle Anfragen werden beantwortet.
- Mindestens 250 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; DESIGN.md erklärt alle Designentscheidungen; ein
  Bericht in `docs/RESULTS.md` fasst Simulationsläufe und gefundene/behobene Fehler
  zusammen.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
