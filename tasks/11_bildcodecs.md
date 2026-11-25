---
topic: compression
legacy_title: "Bild- und Kompressions-Codecs: DEFLATE, PNG, GIF und Baseline-JPEG"
---
# Image and Compression Codecs: DEFLATE, PNG, GIF and Baseline JPEG

## Goal
Implement, in pure Python 3 – **without** `zlib`, `gzip` or `zipfile` for the actual
compression (allowed only in tests as a reference) – a codec library with your own
DEFLATE, PNG encoder/decoder, GIF (LZW) and a baseline JPEG decoder plus encoder. Scope: at
least 8 hours of focused work.

## Functional Requirements
1. **Bit I/O**: bit reader/writer in LSB and MSB order, efficient for large files.
2. **DEFLATE (RFC 1951)**: decompression of all block types (stored, fixed, dynamic
   Huffman); compression with LZ77 (hash chains, lazy matching, configurable levels 1–9)
   and optimal dynamic Huffman codes with length limiting (package-merge); **zlib
   (RFC 1950)** and **gzip (RFC 1952)** containers with Adler-32/CRC-32.
3. **PNG**: all color types and bit depths (1–16 bit, palette, grayscale, alpha), Adam7
   interlacing, all five filters when decoding, adaptive filter selection when encoding,
   chunks (IHDR, PLTE, IDAT across several chunks, tRNS, gAMA, tEXt, zTXt, IEND), CRC
   check, errors on corrupted files.
4. **GIF**: LZW encoding/decoding with variable code length, palettes, transparency,
   animations (several frames, disposal methods), interlacing.
5. **Baseline JPEG**: decoder for Huffman-coded baseline JPEGs (markers SOI, APPn, DQT,
   SOF0, DHT, SOS, DRI, EOI), chroma subsampling 4:4:4/4:2:2/4:2:0, restart markers, IDCT
   (fast AAN variant and an exact reference), YCbCr→RGB; **encoder** with a quality
   parameter, standard Huffman tables and optionally optimized tables.
6. **Image model** with conversions (RGB, RGBA, grayscale, palette with median-cut
   quantization and Floyd-Steinberg dithering), scaling (bilinear, bicubic), rotation,
   cropping.
7. **CLI**: `python -m codecs_lab convert in.png out.jpg --quality 85`, `info`,
   `compress`/`decompress` for gzip files.

## Test Strategy (pytest)
- DEFLATE: round trip with 500 random and structured inputs; compatibility in both
  directions with `zlib` (your output is read by `zlib` and vice versa); compression
  ratio at most 10 % worse than `zlib` level 6 on text corpora.
- PNG: test images of all color types are generated yourself (e.g. with `zlib` as a
  reference encoder) and compared pixel by pixel; error cases (wrong CRC, truncated file).
- JPEG: encoder → decoder round trip with PSNR thresholds per quality level; IDCT
  accuracy against the reference DCT.
- GIF: round trip including animations.
- Performance test: compressing 1 MB in acceptable time (document the result).
- At least 250 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; formats and algorithms documented in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
