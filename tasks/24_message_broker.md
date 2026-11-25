---
topic: network
mode: swarm
---
# Persistenter Message-Broker mit MQTT-3.1.1-Protokoll und Clustering

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek, `asyncio` erlaubt) einen
Message-Broker, der das **MQTT-3.1.1-Protokoll** byte-genau spricht (echte MQTT-Clients
sollen sich verbinden können), Nachrichten dauerhaft speichert und in einem Cluster aus
mehreren Knoten Nachrichten weiterleitet. Gedacht für den **Schwarm-Modus**. Umfang:
mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Protokoll**: Kodierung/Dekodierung aller Pakettypen (CONNECT, CONNACK, PUBLISH,
   PUBACK, PUBREC, PUBREL, PUBCOMP, SUBSCRIBE, SUBACK, UNSUBSCRIBE, UNSUBACK, PINGREQ,
   PINGRESP, DISCONNECT), variable Längenkodierung, strikte Validierung mit
   Verbindungsabbruch bei Protokollverletzungen.
2. **Sitzungen**: Clean Session und persistente Sitzungen, Client-ID-Übernahme,
   Keep-Alive mit Timeout (1,5×), Last Will and Testament, Benutzername/Passwort
   (Passwortdatei mit gesalzenen Hashes).
3. **QoS 0/1/2** mit vollständigem Zustandsautomaten, Paket-IDs, Wiederholung nach
   Wiederverbindung, Inflight-Fenster, Warteschlangenlimits.
4. **Topics**: Topic-Baum mit Wildcards `+` und `#`, `$SYS`-Topics mit Statistiken,
   **Retained Messages**, Zugriffssteuerung (ACL-Datei pro Benutzer und Muster).
5. **Persistenz**: Append-only-Log mit Segmenten für Nachrichten und Sitzungszustand,
   Wiederherstellung nach Absturz, Kompaktierung.
6. **Clustering**: mehrere Broker-Knoten tauschen Abonnements per Gossip aus und
   leiten Nachrichten weiter; Schleifenvermeidung; Knotenausfall und -rückkehr.
7. **Bridge** zu einem zweiten Broker und **Client-Bibliothek** (synchron und asyncio)
   mit automatischer Wiederverbindung.
8. **Werkzeuge**: `pub`/`sub`-Kommandozeilenclients, Lastgenerator, Statistik-Ausgabe.

## Teststrategie (pytest)
- Paket-Kodierungstests mit Byte-Folgen aus der Spezifikation; Fuzzing des Decoders
  (5000 zufällige Bytefolgen dürfen den Broker nicht zum Absturz bringen).
- Konformitätstests pro Normative Statement der Spezifikation (MQTT-x.x.x-y), so weit
  sinnvoll – mindestens 100 Stück.
- QoS-2-Garantie: genau-einmal-Zustellung trotz Verbindungsabbrüchen an jeder Stelle
  des Handshakes.
- Cluster-Tests mit 3 Knoten im selben Prozess; Absturz und Wiederanlauf mit Persistenz.
- Lasttest: 100 Clients, 50.000 Nachrichten, keine Verluste bei QoS 1/2; Durchsatz
  dokumentieren.
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Architektur und Speicherformat in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
