---
topic: network
mode: swarm
legacy_title: Persistenter Message-Broker mit MQTT-3.1.1-Protokoll und Clustering
---
# Persistent Message Broker with the MQTT 3.1.1 Protocol and Clustering

## Goal
Build, in pure Python 3 (standard library only, `asyncio` allowed), a message broker that
speaks the **MQTT 3.1.1 protocol** byte-exactly (real MQTT clients should be able to
connect), stores messages durably and forwards messages within a cluster of several nodes.
Meant for **swarm mode**. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Protocol**: encoding/decoding of all packet types (CONNECT, CONNACK, PUBLISH,
   PUBACK, PUBREC, PUBREL, PUBCOMP, SUBSCRIBE, SUBACK, UNSUBSCRIBE, UNSUBACK, PINGREQ,
   PINGRESP, DISCONNECT), variable-length encoding, strict validation with disconnection
   on protocol violations.
2. **Sessions**: clean sessions and persistent sessions, client ID takeover, keep-alive
   with timeout (1.5×), last will and testament, username/password (password file with
   salted hashes).
3. **QoS 0/1/2** with complete state machines, packet IDs, redelivery after reconnect,
   inflight window, queue limits.
4. **Topics**: topic tree with the wildcards `+` and `#`, `$SYS` topics with statistics,
   **retained messages**, access control (ACL file per user and pattern).
5. **Persistence**: append-only log with segments for messages and session state,
   recovery after a crash, compaction.
6. **Clustering**: several broker nodes exchange subscriptions via gossip and forward
   messages; loop avoidance; node failure and return.
7. **Bridge** to a second broker and a **client library** (synchronous and asyncio) with
   automatic reconnect.
8. **Tools**: `pub`/`sub` command-line clients, a load generator, statistics output.

## Test Strategy (pytest)
- Packet encoding tests with byte sequences from the specification; fuzzing of the
  decoder (5000 random byte sequences must not crash the broker).
- Conformance tests per normative statement of the specification (MQTT-x.x.x-y) where
  sensible – at least 100 of them.
- QoS 2 guarantee: exactly-once delivery despite connection drops at every point of the
  handshake.
- Cluster tests with 3 nodes in the same process; crash and restart with persistence.
- Load test: 100 clients, 50,000 messages, no losses with QoS 1/2; document throughput.
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; architecture and storage format in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
