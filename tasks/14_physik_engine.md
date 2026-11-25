---
topic: game_engine
---
# 2D-Physik-Engine mit Constraint-Solver und deterministischer Wiedergabe

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek) eine vollständige 2D-Starrkörper-
Physik-Engine vergleichbar mit Box2D (konzeptionell, keine Codeübernahme), inklusive
Kollisionserkennung, iterativem Constraint-Solver, Gelenken und deterministischer
Simulation. Visualisierung über SVG-Ausgabe einzelner Frames. Umfang: mindestens
8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Mathematik**: Vektoren, 2×2-Matrizen, Rotationen, Transformationen, AABBs,
   numerisch robuste Hilfsfunktionen.
2. **Formen**: Kreise, konvexe Polygone (aus Punktwolken per Konvexer Hülle),
   Kapseln, Kantenketten für statisches Terrain; Masse, Schwerpunkt und
   Trägheitsmoment aus Dichte.
3. **Broadphase**: dynamischer AABB-Baum mit Rotation/Balancierung und Fat-AABBs;
   alternativ Sweep-and-Prune; Paar-Management.
4. **Narrowphase**: SAT für Polygone, GJK + EPA für allgemeine konvexe Formen,
   Kontaktmannigfaltigkeiten mit Clipping (bis zu 2 Kontaktpunkte), Feature-IDs für
   Warm Starting.
5. **Solver**: Sequential Impulses mit Warm Starting, Akkumulation und Clamping,
   Reibung (Coulomb), Restitution mit Schwellwert, Positionskorrektur (Baumgarte bzw.
   Split Impulses), Sub-Stepping.
6. **Gelenke**: Revolute (mit Limits und Motor), Prismatic, Distance (mit Feder),
   Weld, Mouse-Joint, Rope.
7. **Weitere Features**: Schlaf-/Aufwachsystem mit Inseln, Continuous Collision
   Detection (Time of Impact) für schnelle Objekte, Sensoren/Trigger,
   Kollisionsfilter (Kategorien/Masken), Raycasts und AABB-Abfragen,
   Ereignis-Callbacks (Begin/End Contact).
8. **Determinismus**: identische Eingaben liefern bitgenau identische Ergebnisse;
   Speichern/Laden des kompletten Weltzustands; Replay-Datei.
9. **Szenen und Visualisierung**: Pyramide aus 20 Ebenen, Kettenbrücke, Ragdoll,
   Newton-Pendel, Fahrzeug mit Federung; Export von Frames als SVG und Animation als
   SVG mit SMIL.

## Teststrategie (pytest)
- Geometrie- und Kollisionstests mit analytisch bekannten Ergebnissen (Kreis-Kreis,
  Polygon-Polygon in vielen Orientierungen; GJK-Abstand gegen Brute Force).
- Physikalische Erhaltungsgrößen: Impulserhaltung bei elastischen Stößen,
  Energieabnahme mit Reibung, freier Fall gegen analytische Lösung.
- Stabilität: Pyramide aus 20 Ebenen bleibt 1000 Schritte stabil stehen und schläft ein.
- Gelenk-Constraints werden innerhalb einer Toleranz eingehalten.
- Determinismus: zwei Läufe und Save/Load-Lauf liefern identische Zustände.
- Mindestens 220 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Leistungsmessungen (Körper pro Schritt) in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
