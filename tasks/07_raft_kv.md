---
topic: distributed
spec_docs: false
legacy_title: Raft-Konsens und linearisierbarer Key-Value-Store mit Fehlerinjektion
---
# Raft Consensus and a Linearizable Key-Value Store with Fault Injection

## Goal
Implement, in pure Python 3 (standard library only), a replicated key-value store based on
the Raft consensus protocol and prove its correctness with a Jepsen-style test framework:
deterministic simulation, fault injection and a linearizability checker. Scope: at least
8 hours of focused work.

## Functional Requirements
1. **Deterministic simulator**: virtual clock, message network with delay, loss,
   duplicates, reordering, network partitions (arbitrary subsets, asymmetric), node
   crashes with loss of volatile state, restarts, clock drift. Every run is reproducible
   via a seed.
2. **Raft** fully per the paper (extended version): leader election with randomized
   timeouts, log replication, commit rule (only entries of the current term directly),
   persistent state (currentTerm, votedFor, log) on a simulated disk with fsync
   semantics, PreVote, CheckQuorum, leader lease for reads, ReadIndex for linearizable
   reads.
3. **Log compaction**: snapshots, InstallSnapshot RPC in chunks, restart from snapshot +
   log.
4. **Membership changes**: joint consensus (or single-server changes with correct
   handling), learner nodes, leader transfer.
5. **Key-value store** as the state machine: `get`, `put`, `delete`, `cas`
   (compare-and-swap), transactions over several keys, client sessions with request IDs
   for deduplication (exactly-once semantics).
6. **Client library** with leader discovery, redirects, timeouts and retries.
7. **Linearizability checker** (Wing-Gong/Knossos principle with memoization) for
   histories of invocations and responses, including indeterminate results (timeouts).
8. **Nemesis scenarios**: random partitions, isolate the leader, split majority/minority,
   crashes during snapshot transfer, clock jumps.
9. **Visualization**: text output of the timeline (who was leader when, terms, commits).

## Test Strategy (pytest)
- Unit tests for every RPC rule (Figure 2 of the Raft paper point by point).
- Safety properties checked as invariants after every simulation step: Election Safety,
  Leader Append-Only, Log Matching, Leader Completeness, State Machine Safety.
- At least 200 randomized simulation runs (fixed seeds) with nemesis and a
  linearizability check of the entire history.
- Test the checker itself with known linearizable and non-linearizable histories (at
  least 30 cases).
- Liveness: after all disturbances end, a leader is elected within bounded time and all
  requests are answered.
- At least 250 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; DESIGN.md explains all design decisions; a report in
  `docs/RESULTS.md` summarizes simulation runs and bugs found/fixed.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
