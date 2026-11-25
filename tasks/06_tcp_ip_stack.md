---
topic: network
spec_docs: true
legacy_title: TCP/IP-Stack im Userspace mit Netzwerksimulator
---
# User-Space TCP/IP Stack with Network Simulator

## Goal
Implement, in pure Python 3 (standard library only), a complete TCP/IP stack that runs
on top of your own deterministic network simulator. The simulator models links with
latency, bandwidth, packet loss, duplicates, reordering and bit errors. Several simulated
hosts and routers exchange real, byte-exact encoded packets. Scope: a large project for at
least 8 hours of focused work.

## Functional Requirements
1. **Simulator** (`netsim/`): discrete event simulation with a virtual clock, links with
   configurable latency/bandwidth/queue size (drop-tail and RED), loss and corruption
   models with a seed, capture in pcap format (readable by Wireshark).
2. **Ethernet** (frames, MAC addresses, broadcast), **switch** with MAC learning and
   aging.
3. **ARP** with cache, timeouts, gratuitous ARP, queue for unresolved packets.
4. **IPv4**: header encoding including checksum, TTL, fragmentation and reassembly (with
   timeouts, overlapping fragments), routing table with longest-prefix match, routers with
   several interfaces.
5. **ICMP**: echo (ping with RTT statistics), destination unreachable, time exceeded, a
   `traceroute` tool.
6. **UDP** with pseudo-header checksum and a socket API (`bind`, `sendto`, `recvfrom`).
7. **TCP** per RFC 9293: three-way handshake, all states including `TIME_WAIT`,
   simultaneous open/close, sequence numbers with wraparound, sliding window, flow
   control, zero-window probing, Nagle, delayed ACK, retransmission timer per RFC 6298
   (SRTT/RTTVAR, Karn), fast retransmit/fast recovery, SACK (RFC 2018), window scaling
   and timestamps (RFC 7323), keepalive, RST handling.
8. **Congestion control**: Reno and CUBIC as interchangeable strategies, measurement of
   cwnd over time (CSV export).
9. **Socket API** in the style of `socket` (`listen`, `accept`, `connect`, `send`,
   `recv`, `close`, `shutdown`) with a blocking and an event-driven variant.
10. **Applications** on top of the stack: echo server, simple HTTP/1.0 client and server,
    file transfer with checksum comparison, DNS resolver (UDP) against a simulated DNS
    server.

## Test Strategy (pytest)
- Encoding tests for every protocol with known byte sequences (checksums computed by
  hand).
- TCP state machine: tests for every transition including edge cases (RST in every state,
  late segments, sequence number wraparound).
- Robustness: transfer 5 MB over links with 0 %, 1 %, 5 % and 20 % loss, reordering and
  duplicates – data must arrive bit-exact (fixed seeds).
- Compare Reno vs. CUBIC on a link with a large bandwidth-delay product (document
  throughput).
- Fragmentation and routing tests across topologies with at least 3 routers.
- pcap files are read back and validated with your own parser.
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes completely; README with an architecture diagram (ASCII),
  DESIGN.md, PROGRESS.md; measurement results (throughput, retransmissions) documented.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
