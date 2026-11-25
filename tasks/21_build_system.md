---
topic: devtools
mode: swarm
---
# Build-System mit Remote-Cache und Paketmanager mit PubGrub-Resolver

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) zwei zusammenspielende
Entwicklerwerkzeuge: ein inkrementelles, paralleles Build-System (konzeptionell wie
Bazel/Ninja) und einen Paketmanager mit dem PubGrub-Abhängigkeitsauflöser. Gedacht für
den **Schwarm-Modus**. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen – Build-System
1. **Build-Beschreibung** in einer eigenen, sicheren Konfigurationssprache (Parser,
   Variablen, Funktionen, Listen, Glob-Muster, Includes) mit Regeln, Zielen und
   Abhängigkeiten.
2. **Abhängigkeitsgraph**: Zyklenerkennung mit verständlicher Fehlermeldung (Pfad),
   topologische Planung, Ziele nach Muster auswählen.
3. **Inkrementalität**: Inhalts-Hashes von Eingaben, Befehlszeile und Umgebung;
   Aktionsschlüssel; Datenbank des letzten Builds; nur veraltete Aktionen laufen;
   „Early Cutoff“, wenn eine Ausgabe sich nicht ändert.
4. **Parallele Ausführung** mit Worker-Pool, Limit für Ressourcen (CPU, Speicher-Token),
   Abbruch bei Fehler oder `--keep-going`, Fortschrittsanzeige, kritischer Pfad.
5. **Cache**: lokaler inhaltsadressierter Cache und **Remote-Cache** über HTTP (eigener
   kleiner Cache-Server mit `http.server`), Prüfung von Hashes, Bereinigung (LRU).
6. **Sandboxing light**: Aktionen laufen in temporären Verzeichnissen nur mit
   deklarierten Eingaben; nicht deklarierte Abhängigkeiten werden erkannt.
7. **Werkzeuge**: `query` (Abhängigkeiten, umgekehrte Abhängigkeiten), `graph`
   (DOT-Ausgabe), `clean`, `explain` (warum wurde neu gebaut?).

## Funktionale Anforderungen – Paketmanager
8. **Paketformat** (Metadaten, semantische Versionen mit Vorabversionen, Bereichs-
   syntax wie `^1.2`, `~2.0`, `>=1,<3`), lokales Registry-Verzeichnis und
   HTTP-Registry.
9. **PubGrub-Resolver**: Inkompatibilitäten, Unit Propagation, Konfliktauflösung mit
   Lernen, **menschenlesbare Erklärung** bei Unlösbarkeit (Ableitungsbaum wie im
   PubGrub-Artikel), Versionspräferenz (neueste zuerst, Lockfile-Präferenz).
10. **Lockfile**, Installation in ein Projektverzeichnis, Integritätsprüfung (SHA-256),
    `add`/`remove`/`update`/`tree`/`why`.

## Teststrategie (pytest)
- Build: Szenarien mit Projekten aus Dutzenden Zielen (z. B. Codegenerierung,
  „Kompilieren“ per Python-Skripten, Archivieren); nach Änderung genau einer Datei laufen
  genau die erwarteten Aktionen; Cache-Treffer lokal und remote; parallele Läufe sind
  deterministisch.
- Resolver: alle Beispiele aus der PubGrub-Dokumentation mit erwarteten Lösungen und
  Fehlererklärungen; 500 zufällig generierte Registries gegen einen Brute-Force-Löser
  (fester Seed).
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Benutzerhandbuch in docs/, Architektur in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
