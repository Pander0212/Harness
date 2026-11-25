---
topic: network
spec_docs: true
---
# TCP/IP-Stack im Userspace mit Netzwerksimulator

## Ziel
Implementiere in reinem Python 3 (nur Standardbibliothek) einen vollständigen
TCP/IP-Stack, der über einem eigenen, deterministischen Netzwerksimulator läuft. Der
Simulator bildet Verbindungen mit Latenz, Bandbreite, Paketverlust, Duplikaten,
Umordnung und Bitfehlern nach. Mehrere simulierte Hosts und Router tauschen echte,
byte-genau kodierte Pakete aus. Umfang: ein großes Projekt für mindestens 8 Stunden
konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Simulator** (`netsim/`): diskrete Ereignissimulation mit virtueller Uhr, Links mit
   konfigurierbarer Latenz/Bandbreite/Queue-Größe (Drop-Tail und RED), Verlust- und
   Störmodelle mit Seed, Mitschnitt im pcap-Format (von Wireshark lesbar).
2. **Ethernet** (Frames, MAC-Adressen, Broadcast), **Switch** mit MAC-Learning und Aging.
3. **ARP** mit Cache, Timeouts, Gratuitous ARP, Warteschlange für unaufgelöste Pakete.
4. **IPv4**: Header-Kodierung inkl. Prüfsumme, TTL, Fragmentierung und Reassemblierung
   (mit Timeouts, überlappenden Fragmenten), Routing-Tabelle mit Longest-Prefix-Match,
   Router mit mehreren Interfaces.
5. **ICMP**: Echo (ping mit RTT-Statistik), Destination Unreachable, Time Exceeded,
   `traceroute`-Werkzeug.
6. **UDP** mit Pseudo-Header-Prüfsumme und Socket-API (`bind`, `sendto`, `recvfrom`).
7. **TCP** nach RFC 9293: Drei-Wege-Handshake, alle Zustände inklusive `TIME_WAIT`,
   simultanes Öffnen/Schließen, Sequenznummern mit Wraparound, Sliding Window,
   Flusskontrolle, Zero-Window-Probing, Nagle, Delayed ACK, Retransmission-Timer nach
   RFC 6298 (SRTT/RTTVAR, Karn), Fast Retransmit/Fast Recovery, SACK (RFC 2018),
   Window Scaling und Timestamps (RFC 7323), Keepalive, RST-Behandlung.
8. **Staukontrolle**: Reno und CUBIC als austauschbare Strategien, Messung von cwnd über
   die Zeit (CSV-Export).
9. **Socket-API** im Stil von `socket` (`listen`, `accept`, `connect`, `send`, `recv`,
   `close`, `shutdown`) mit blockierender und ereignisbasierter Variante.
10. **Anwendungen** über dem Stack: Echo-Server, einfacher HTTP/1.0-Client und -Server,
    Dateiübertragung mit Prüfsummenvergleich, DNS-Resolver (UDP) gegen einen
    simulierten DNS-Server.

## Teststrategie (pytest)
- Kodierungstests für jedes Protokoll mit bekannten Bytefolgen (Prüfsummen von Hand
  nachgerechnet).
- TCP-Zustandsautomat: Tests für jeden Übergang inkl. Randfällen (RST in jedem Zustand,
  verspätete Segmente, Sequenznummer-Wraparound).
- Robustheit: Übertragung von 5 MB über Links mit 0 %, 1 %, 5 % und 20 % Verlust,
  Umordnung und Duplikaten – Daten müssen bitgenau ankommen (feste Seeds).
- Vergleich Reno vs. CUBIC auf einem Link mit großem Bandbreiten-Verzögerungs-Produkt
  (Durchsatz dokumentieren).
- Fragmentierungs- und Routing-Tests über Topologien mit mindestens 3 Routern.
- pcap-Dateien werden mit einem eigenen Parser zurückgelesen und validiert.
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` vollständig grün; README mit Architekturdiagramm (ASCII),
  DESIGN.md, PROGRESS.md; Messergebnisse (Durchsatz, Retransmissions) dokumentiert.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
