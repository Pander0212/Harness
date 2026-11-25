---
topic: database
---
# LSM-Tree-Speicher-Engine mit MVCC und Crash-Recovery

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) eine eingebettete Key-Value-
Speicher-Engine nach dem Log-Structured-Merge-Prinzip (vergleichbar mit LevelDB/RocksDB)
mit Snapshots, MVCC-Transaktionen und garantierter Crash-Konsistenz. Umfang: mindestens
8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Write-Ahead-Log** mit Record-Format (Blöcke, Fragmentierung über Blockgrenzen,
   CRC32C selbst implementiert), Gruppen-Commit, konfigurierbare Sync-Politik.
2. **Memtable** als Skip-List mit Sequenznummern und Löschmarkern (Tombstones);
   unveränderliche Memtables während des Flushes.
3. **SSTables**: Datenblöcke mit Präfix-Kompression und Restart-Points, Index-Block,
   Filterblock mit **Bloom-Filter** (konfigurierbare Bits pro Schlüssel), Footer mit
   magischer Zahl, optionale Kompression (zlib) pro Block, Prüfsummen.
4. **Versionsverwaltung**: MANIFEST-Datei mit Versions-Edits, CURRENT-Datei,
   atomarer Wechsel, Wiederherstellung nach Absturz.
5. **Compaction**: Leveled Compaction (L0 überlappend, L1+ disjunkt) mit Score-
   Berechnung, Size-tiered als Alternative; Entfernen veralteter Versionen unter
   Beachtung offener Snapshots; Hintergrund-Thread mit sauberem Stopp.
6. **Iteratoren**: Merging-Iterator über Memtables und alle Levels, vorwärts und
   rückwärts, `seek`, Bereichsabfragen, Präfix-Scans.
7. **MVCC und Transaktionen**: Snapshots (konsistente Lesesicht), optimistische
   Transaktionen mit Konflikterkennung beim Commit (Snapshot Isolation), WriteBatch.
8. **Block-Cache** (LRU mit Kapazität in Bytes) und Table-Cache für offene Dateien.
9. **Werkzeuge**: `dump` für SSTables und MANIFEST, `check` zur Konsistenzprüfung,
   Statistiken (Write/Read-Amplification, Bloom-Treffer).
10. **Benchmark** im Stil von `db_bench`: fillseq, fillrandom, readrandom, readseq,
    overwrite, deleterandom mit Ergebnissen in DESIGN.md.

## Teststrategie (pytest)
- Unit-Tests für Skip-List, Bloom-Filter (False-Positive-Rate statistisch prüfen),
  Blockformat, CRC32C gegen Referenzwerte.
- Modellbasierter Test: 50.000 zufällige Operationen (put/delete/get/scan/Snapshot/
  Transaktion) gegen ein einfaches `dict`-Modell, mit Compactions zwischendurch.
- **Crash-Tests**: Prozess wird an zufälligen Stellen (simulierte Abstürze durch
  abgeschnittene Dateien, fehlende fsyncs) unterbrochen; nach dem Wiederöffnen sind alle
  bestätigten Schreibvorgänge vorhanden und die Datenbank ist konsistent.
- Nebenläufigkeit: mehrere Leser-Threads während Schreiblast und Compaction.
- Mindestens 250 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Dateiformate vollständig in DESIGN.md dokumentiert;
  Benchmark-Ergebnisse dokumentiert.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
