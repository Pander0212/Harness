---
topic: text
spec_docs: false
legacy_title: Volltext-Suchmaschine mit komprimiertem Index, BM25 und Abfragesprache
---
# Full-Text Search Engine with a Compressed Index, BM25 and a Query Language

## Goal
Build, in pure Python 3 (standard library only), a full-text search engine (conceptually
like Lucene) with an analysis pipeline, a segmented, compressed inverted index, ranking, a
query language, snippets and spelling correction, plus a small web interface. A test
corpus is generated procedurally or built from texts included in the project. Scope: at
least 8 hours of focused work.

## Functional Requirements
1. **Analysis**: Unicode normalization, tokenization (word boundaries, numbers, e-mail
   addresses, URLs), lowercasing, stop words, **stemming** (Porter for English, a simple
   stemmer for German), synonyms, n-grams for prefix search; configurable analyzers per
   field.
2. **Document model** with fields (text, keyword, number, date), stored fields, document
   IDs, updates and deletions (tombstones).
3. **Index**: segments (immutable), postings with positions and frequencies, compression
   with delta encoding + VByte and PForDelta, skip lists, term dictionary as an FST or a
   sorted array with prefix compression, norms per field; segment merging with a merge
   policy; commit points and crash safety.
4. **Queries**: term, Boolean (AND/OR/NOT, `+`/`-`), phrase (with slop), prefix,
   wildcard, fuzzy (Levenshtein automaton), range (number/date), field search, boosting;
   a **query language** with a parser and error messages.
5. **Ranking**: TF-IDF and **BM25** (k1/b parameters per field), WAND or MaxScore for fast
   top-k retrieval, facets and filters, sorting by fields.
6. **Result presentation**: snippets with highlighting (best window), pagination, "did
   you mean …" (spelling correction via term statistics and edit distance).
7. **Server**: HTTP JSON API and a small HTML search page (`http.server`), indexing
   directories of text files.
8. **Evaluation**: a relevance test collection with queries and expected relevant
   documents; metrics precision@k, MAP, nDCG.

## Test Strategy (pytest)
- Analysis and stemmer tests (Porter reference examples).
- Compression: round trip for 10,000 random posting lists.
- Query results against a naive full-text search over the same corpus (300 generated
  queries, identical hit sets; scores against the reference formula).
- WAND/MaxScore returns the same top-k as the full evaluation.
- Crash tests during commit; merging keeps all documents.
- At least 280 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; index format and measurements (index size, query time,
  nDCG) in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
