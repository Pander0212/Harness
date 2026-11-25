---
topic: database
legacy_title: LSM-Tree-Speicher-Engine mit MVCC und Crash-Recovery
---
# LSM-Tree Storage Engine with MVCC and Crash Recovery

## Goal
Build, in pure Python 3 (standard library only), an embedded key-value storage engine
based on the log-structured merge principle (comparable to LevelDB/RocksDB) with
snapshots, MVCC transactions and guaranteed crash consistency. Scope: at least 8 hours of
focused work.

## Functional Requirements
1. **Write-ahead log** with a record format (blocks, fragmentation across block
   boundaries, CRC32C implemented yourself), group commit, configurable sync policy.
2. **Memtable** as a skip list with sequence numbers and deletion markers (tombstones);
   immutable memtables during flush.
3. **SSTables**: data blocks with prefix compression and restart points, index block,
   filter block with a **Bloom filter** (configurable bits per key), footer with a magic
   number, optional compression (zlib) per block, checksums.
4. **Version management**: MANIFEST file with version edits, CURRENT file, atomic
   switch, recovery after a crash.
5. **Compaction**: leveled compaction (L0 overlapping, L1+ disjoint) with score
   computation, size-tiered as an alternative; dropping obsolete versions while respecting
   open snapshots; background thread with clean shutdown.
6. **Iterators**: merging iterator over memtables and all levels, forward and backward,
   `seek`, range queries, prefix scans.
7. **MVCC and transactions**: snapshots (consistent read view), optimistic transactions
   with conflict detection at commit (snapshot isolation), WriteBatch.
8. **Block cache** (LRU with capacity in bytes) and a table cache for open files.
9. **Tools**: `dump` for SSTables and the MANIFEST, `check` for consistency checks,
   statistics (write/read amplification, Bloom filter hits).
10. **Benchmark** in the style of `db_bench`: fillseq, fillrandom, readrandom, readseq,
    overwrite, deleterandom with results in DESIGN.md.

## Test Strategy (pytest)
- Unit tests for skip list, Bloom filter (check the false-positive rate statistically),
  block format, CRC32C against reference values.
- Model-based test: 50,000 random operations (put/delete/get/scan/snapshot/transaction)
  against a simple `dict` model, with compactions in between.
- **Crash tests**: the process is interrupted at random points (simulated crashes via
  truncated files, missing fsyncs); after reopening, all acknowledged writes are present
  and the database is consistent.
- Concurrency: several reader threads during write load and compaction.
- At least 250 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; file formats fully documented in DESIGN.md; benchmark
  results documented.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
