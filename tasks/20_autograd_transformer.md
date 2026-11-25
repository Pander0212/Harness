---
topic: ml
---
# Autograd-Engine, neuronale Netze und ein kleiner Transformer von Grund auf

## Ziel
Implementiere in reinem Python 3 (nur Standardbibliothek; kein NumPy) eine Tensor-
Bibliothek mit automatischer Differenzierung, darauf neuronale Netzschichten,
Optimierer, einen BPE-Tokenizer und einen kleinen Decoder-only-Transformer, der auf
einem Textkorpus trainiert wird. Effizienz in reinem Python ist Teil der Aufgabe.
Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Tensoren**: n-dimensionale Arrays (flache Liste + Shape + Strides), Broadcasting,
   Indexierung und Slicing, reshape/transpose/permute als Views, Reduktionen über
   Achsen, matmul (batched), Konkatenation, Datentyp float.
2. **Autograd**: dynamischer Berechnungsgraph, topologische Sortierung, Rückwärtspfad
   für alle Operationen inklusive Broadcasting-Reduktion der Gradienten,
   `no_grad`-Kontext, Gradientenakkumulation, `detach`.
3. **Gradient-Check**: numerische Gradienten (zentrale Differenzen) für jede Operation.
4. **Schichten**: Linear, Embedding, LayerNorm, Dropout, Aktivierungen (ReLU, GELU,
   Tanh, Softmax mit numerisch stabiler Form), Cross-Entropy (stabil, mit Label
   Smoothing), Conv1D, Residual-Blöcke; Parameterverwaltung, `state_dict`, Speichern
   und Laden.
5. **Optimierer**: SGD mit Momentum/Nesterov, Adam, AdamW, Lernraten-Scheduler
   (Warmup + Cosine), Gradient Clipping.
6. **BPE-Tokenizer**: Training auf einem Korpus, Merges, Kodieren/Dekodieren
   (verlustfrei, Bytes-Fallback), Spezial-Token, Speichern/Laden.
7. **Transformer**: Multi-Head-Self-Attention mit kausaler Maske, Positions-Embeddings
   (gelernt und rotierend/RoPE), Feed-Forward, Pre-LN-Blöcke; Training auf einem
   kleinen Korpus (z. B. selbst geschriebene Texte oder Gemeinfreies, das im Projekt
   enthalten ist), Sampling mit Temperatur, Top-k und Top-p; KV-Cache für schnelles
   Generieren.
8. **Klassische Aufgaben**: MLP auf synthetischen Spiralen-Daten, Klassifikation von
   prozedural erzeugten 8×8-Ziffern; Lernkurven als CSV.

## Teststrategie (pytest)
- Gradient-Check für jede Operation und Schicht (mindestens 80 Fälle, verschiedene
  Shapes und Broadcasting-Konstellationen).
- Tensor-Semantik gegen eine naive Referenz (verschachtelte Listen) für 300 zufällige
  Operationen.
- Optimierer gegen von Hand berechnete Schritte; Tokenizer-Round-Trip über Unicode.
- Lernfähigkeit: Spiralen-Datensatz > 95 % Genauigkeit; Transformer überanpasst einen
  kleinen Text (Verlust sinkt unter Schwelle); KV-Cache liefert identische Logits.
- Mindestens 250 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Trainingsergebnisse und Laufzeiten in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
