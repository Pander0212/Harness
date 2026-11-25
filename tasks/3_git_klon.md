# Git-Klon "pygit" in Python

## Ziel
Implementiere in reinem Python 3 (nur Standardbibliothek: `zlib`, `hashlib`, `os`,
`struct` usw.) ein Versionskontrollsystem **pygit**, dessen Repository-Format mit
echtem Git kompatibel ist: ein mit pygit erstelltes Repository muss von `git` gelesen
werden können und umgekehrt (falls `git` installiert ist, wird das in Tests geprüft,
sonst werden diese Tests übersprungen).

## Funktionale Anforderungen
1. **Objektdatenbank**: Blob, Tree, Commit, Tag als zlib-komprimierte Loose Objects
   unter `.git/objects`, SHA-1-Adressierung, Lesen von Packfiles (`.pack` + `.idx` v2,
   inklusive OFS_DELTA und REF_DELTA) – Schreiben von Packfiles optional als Bonus.
2. **Index (Staging Area)**: binäres Git-Indexformat Version 2 lesen und schreiben
   (Einträge mit Stat-Daten, Modus, SHA, Flags, Prüfsumme).
3. **Befehle** (CLI `python -m pygit <befehl>`):
   `init`, `hash-object [-w]`, `cat-file -p/-t/-s`, `add <pfade>`, `rm`, `status`
   (staged / unstaged / untracked, wie Git kategorisiert), `commit -m`, `log`
   (inkl. `--oneline`, `--graph` für Merges), `branch` (anlegen, listen, löschen),
   `checkout <branch|commit>` (inkl. Schutz vor Überschreiben lokaler Änderungen),
   `switch -c`, `tag` (leichtgewichtig und annotiert), `diff` (Arbeitsverzeichnis vs.
   Index, Index vs. HEAD, zwei Commits), `merge <branch>`, `reset [--soft|--mixed|--hard]`,
   `show`, `ls-files`, `ls-tree`, `rev-parse` (inkl. `HEAD~2`, `main^`, abgekürzte SHAs).
4. **Refs**: `HEAD` symbolisch und detached, `refs/heads`, `refs/tags`, `packed-refs`
   lesen, Reflog für HEAD schreiben.
5. **.gitignore** mit Mustern (`*`, `**`, `!`-Negation, Verzeichnismuster).
6. **Diff-Algorithmus**: eigene Implementierung des **Myers-Algorithmus** (O(ND)) mit
   Ausgabe im Unified-Format (Hunks mit Kontextzeilen, `@@`-Header), Erkennung binärer
   Dateien.
7. **Merge**: Ermittlung der Merge-Base (gemeinsamer Vorfahre, auch bei mehreren
   Kandidaten korrekt), Fast-Forward, echter Drei-Wege-Merge auf Dateiebene und
   Zeilenebene (diff3-Prinzip) mit **Konflikterkennung**: Konfliktmarker
   `<<<<<<<`, `=======`, `>>>>>>>` wie Git, Konfliktstatus im Index (Stages 1–3),
   `merge --abort`, Abschluss per `commit` erzeugt Merge-Commit mit zwei Eltern.
   Behandle auch Konflikte durch Löschen vs. Ändern.

## Architekturvorgaben
Paket `pygit/` mit Modulen wie `objects.py`, `repo.py`, `index.py`, `refs.py`,
`diff.py` (Myers), `merge.py`, `ignore.py`, `pack.py`, `cli.py`. Formatdetails und
Algorithmen in DESIGN.md dokumentieren.

## Teststrategie (pytest)
- Objekt-Hashes müssen mit den bekannten Werten von Git übereinstimmen (z. B. leerer
  Blob `e69de29...`, leerer Tree `4b825dc...`).
- Myers-Diff: Eigenschaftstest – Anwenden des erzeugten Diffs auf die alte Version
  ergibt die neue Version (500 zufällige Fälle, fester Seed); minimale Editdistanz
  gegenüber einer DP-Referenzimplementierung prüfen.
- Szenario-Tests in temporären Verzeichnissen: Branches anlegen, divergente Änderungen,
  Fast-Forward, konfliktfreier Merge, Merge mit Konflikten, Auflösen und Commit.
- Interoperabilität (nur falls `git` vorhanden): `git fsck`, `git log`, `git status` auf
  pygit-Repos; pygit liest von `git` erzeugte Repos inklusive Packfiles (`git gc`).
- Mindestens 150 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; README mit Befehlsübersicht, DESIGN.md, PROGRESS.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
