---
topic: compression
---
# Bild- und Kompressions-Codecs: DEFLATE, PNG, GIF und Baseline-JPEG

## Ziel
Implementiere in reinem Python 3 – **ohne** `zlib`, `gzip` oder `zipfile` für die
eigentliche Kompression (nur in Tests als Referenz) – eine Codec-Bibliothek mit eigenem
DEFLATE, PNG-Encoder/-Decoder, GIF (LZW) und Baseline-JPEG-Decoder samt Encoder. Umfang:
mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Bit-I/O**: Bitleser/-schreiber in LSB- und MSB-Reihenfolge, effizient für große
   Dateien.
2. **DEFLATE (RFC 1951)**: Dekompression aller Blocktypen (stored, fixed, dynamic
   Huffman); Kompression mit LZ77 (Hash-Ketten, Lazy Matching, konfigurierbare Stufen
   1–9) und optimalen dynamischen Huffman-Codes mit Längenbegrenzung (Package-Merge);
   **zlib (RFC 1950)** und **gzip (RFC 1952)** Container mit Adler-32/CRC-32.
3. **PNG**: alle Farbtypen und Bittiefen (1–16 Bit, Palette, Graustufen, Alpha),
   Adam7-Interlacing, alle fünf Filter beim Dekodieren, adaptive Filterwahl beim
   Kodieren, Chunks (IHDR, PLTE, IDAT über mehrere Chunks, tRNS, gAMA, tEXt, zTXt,
   IEND), CRC-Prüfung, Fehler bei beschädigten Dateien.
4. **GIF**: LZW-Kodierung/Dekodierung mit variabler Codelänge, Paletten, Transparenz,
   Animationen (mehrere Frames, Disposal-Methoden), Interlacing.
5. **JPEG Baseline**: Decoder für Huffman-kodierte Baseline-JPEGs (Marker SOI, APPn,
   DQT, SOF0, DHT, SOS, DRI, EOI), Chroma-Subsampling 4:4:4/4:2:2/4:2:0, Restart-
   Marker, IDCT (schnelle AAN-Variante und genaue Referenz), YCbCr→RGB; **Encoder** mit
   Qualitätsparameter, Standard-Huffman-Tabellen und optional optimierten Tabellen.
6. **Bildmodell** mit Konvertierungen (RGB, RGBA, Graustufen, Palette mit
   Median-Cut-Quantisierung und Floyd-Steinberg-Dithering), Skalierung (bilinear,
   bikubisch), Drehung, Zuschnitt.
7. **CLI**: `python -m codecs_lab convert in.png out.jpg --quality 85`, `info`,
   `compress`/`decompress` für gzip-Dateien.

## Teststrategie (pytest)
- DEFLATE: Round-Trip mit 500 zufälligen und strukturierten Eingaben; Kompatibilität in
  beide Richtungen mit `zlib` (eigene Ausgabe wird von `zlib` gelesen und umgekehrt);
  Kompressionsrate höchstens 10 % schlechter als `zlib` Stufe 6 auf Textkorpora.
- PNG: Testbilder aller Farbtypen werden selbst erzeugt (u. a. über `zlib` als
  Referenz-Encoder) und Pixel für Pixel verglichen; Fehlerfälle (falsche CRC,
  abgeschnittene Datei).
- JPEG: Encoder → Decoder Round-Trip mit PSNR-Schwellen je Qualitätsstufe;
  IDCT-Genauigkeit gegen die Referenz-DCT.
- GIF: Round-Trip inklusive Animationen.
- Leistungstest: Kompression von 1 MB in akzeptabler Zeit (Ergebnis dokumentieren).
- Mindestens 250 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Formate und Algorithmen in DESIGN.md dokumentiert.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
