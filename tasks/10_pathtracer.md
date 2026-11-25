---
topic: image
spec_docs: false
---
# Physikalisch basierter Pathtracer mit Szenenbeschreibungssprache

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek; Bildausgabe als PNG über einen
selbst geschriebenen Encoder mit `zlib`) einen physikalisch basierten Renderer. Wegen
der Rechenintensität ist effiziente Programmierung (Beschleunigungsstrukturen,
Multiprocessing über `multiprocessing`) ausdrücklich Teil der Aufgabe. Umfang:
mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Mathematik**: Vektoren, Matrizen 4×4, Quaternionen, Transformationen,
   Orthonormalbasen, numerisch robuste Schnittberechnungen.
2. **Geometrie**: Kugeln, Ebenen, Dreiecke (Möller-Trumbore), Dreiecksnetze aus
   OBJ-Dateien (inkl. Normalen und Texturkoordinaten), Instanzen mit Transformationen,
   Quader, Zylinder.
3. **Beschleunigung**: BVH mit Surface-Area-Heuristik, Binning-Konstruktion,
   flache Traversierung; Statistik über getestete Knoten.
4. **Kamera**: Lochkamera und Dünne-Linse (Tiefenschärfe), Bewegungsunschärfe.
5. **Materialien**: Lambert, Spiegel, Dielektrikum mit Fresnel (Glas), raue Metalle
   mit GGX-Mikrofacetten, Emission; Texturen (Schachbrett, Bild aus PPM/PNG,
   Perlin-Rauschen).
6. **Integrator**: Pathtracing mit Russian Roulette, **Next Event Estimation** mit
   Flächenlichtern, **Multiple Importance Sampling**, Umgebungslicht.
7. **Sampling**: stratifiziert und Low-Discrepancy (Halton/Sobol), Rekonstruktionsfilter.
8. **Ausgabe**: eigener PNG-Encoder (Chunks, CRC, Filter pro Zeile mit Heuristik),
   Tone-Mapping (Reinhard, ACES), Gamma; PPM-Ausgabe; Fortschrittsanzeige.
9. **Szenensprache**: eigenes Textformat mit Parser (Kameras, Materialien, Objekte,
   Lichter, Includes, Variablen) und Fehlermeldungen mit Zeilennummer.
10. **Parallelisierung** in Kacheln mit `multiprocessing`, deterministisch pro Seed.
11. **Beispielszenen**: Cornell Box, Glaskugeln mit Kaustiken, Tiefenschärfe-Szene,
    Mesh-Szene mit mindestens 10.000 Dreiecken.

## Teststrategie (pytest)
- Analytische Tests für Schnitte (inkl. Randfälle: streifende Strahlen, Treffer auf
  Kanten), Transformationen und BVH (Ergebnis identisch zu Brute Force bei 1000
  Zufallsstrahlen).
- Energieerhaltung: Weißer Ofen-Test (diffuse Kugel in gleichmäßiger Umgebung muss
  Umgebungsfarbe ergeben, innerhalb statistischer Toleranz).
- Konvergenztests: Mittelwert eines Pixels konvergiert gegen Referenz bei steigender
  Samplezahl; MIS reduziert Varianz gegenüber reinem BSDF-Sampling messbar.
- PNG-Encoder: Dateien werden mit einem eigenen Decoder zurückgelesen; Szenenparser mit
  gültigen und fehlerhaften Eingaben.
- Mindestens 200 Testfälle; gerenderte Beispielbilder unter `renders/`.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Renderzeiten und Bilder in DESIGN.md dokumentiert.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
