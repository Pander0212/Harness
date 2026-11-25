---
topic: os_sim
mode: swarm
---
# Betriebssystem-Simulator: Prozesse, virtueller Speicher, Journaling-Dateisystem, Shell

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) einen lehrbuchnahen, aber
vollständigen Betriebssystem-Simulator. Er führt Programme einer eigenen kleinen
Maschinensprache aus und bietet Prozessverwaltung, Scheduling, virtuellen Speicher,
ein Dateisystem mit Journaling auf einem simulierten Blockgerät und eine Shell. Diese
Aufgabe ist für den **Schwarm-Modus** gedacht: Module mit klaren Schnittstellen,
parallel entwickelbar. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Maschine**: einfache Register-CPU mit eigenem Befehlssatz und Assembler,
   Interrupts (Timer, I/O, Systemaufrufe, Page Faults), Kernel-/User-Modus.
2. **Prozesse und Threads**: PCB, fork/exec/wait/exit, Zombies und Waisen, Signale
   (SIGKILL, SIGTERM, SIGCHLD, Handler), Threads mit eigenem Stack.
3. **Scheduler** als austauschbare Strategien: FCFS, Round Robin, Prioritäten mit Aging,
   Multilevel Feedback Queue, CFS-artig (vruntime mit Rot-Schwarz-Baum), Mehrkern-
   Simulation mit Lastausgleich; Kennzahlen (Durchlauf-, Warte-, Antwortzeit).
4. **Synchronisation**: Mutex, Semaphore, Condition Variables, Deadlock-Erkennung
   (Wartegraph) und Bankier-Algorithmus.
5. **Virtueller Speicher**: zweistufige Seitentabellen, TLB mit Statistik,
   Demand Paging, Copy-on-Write beim fork, Seitenersetzung (FIFO, LRU, Clock,
   Second Chance, Working Set), Swap-Bereich, Speicherabbildung von Dateien (mmap);
   Heap-Allokator mit Buddy-System und Slab-Allokator.
6. **Blockgerät und Dateisystem**: Superblock, Inodes (direkte, einfach- und
   doppelt-indirekte Blöcke), Bitmaps, Verzeichnisse, harte und symbolische Links,
   Rechte (rwx, Besitzer), **Journaling** (Write-Ahead, Transaktionen, Replay nach
   Absturz), Puffer-Cache, `fsck`.
7. **Systemaufrufe und VFS**: open/read/write/lseek/close/dup2/pipe/stat/mkdir/unlink,
   Dateideskriptortabellen, Pipes mit Blockierung, Gerätedateien (/dev/null, Konsole).
8. **Shell**: Pipes, Umleitungen, Hintergrundjobs, Jobkontrolle, Umgebungsvariablen,
   eingebaute Befehle (cd, ls, cat, echo, ps, kill, jobs), Skripte.
9. **Userland-Programme** in der eigenen Maschinensprache: `cat`, `wc`, `grep`
   (einfach), `sort`, ein Producer-Consumer-Beispiel.

## Teststrategie (pytest)
- Pro Modul umfassende Unit-Tests; Scheduler-Kennzahlen gegen von Hand berechnete
  Beispiele aus Lehrbüchern.
- Seitenersetzung: Fehlseitenzahlen für Referenzstrings gegen bekannte Ergebnisse
  (inkl. Beladys Anomalie bei FIFO).
- Dateisystem: modellbasierte Tests mit 10.000 zufälligen Operationen gegen ein
  In-Memory-Modell; Absturz an zufälligen Punkten + Journal-Replay + fsck = konsistent.
- Integrationstests: Shell-Skripte mit Pipes und Hintergrundjobs liefern erwartete
  Ausgaben.
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Architektur und Schnittstellen in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
