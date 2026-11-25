# HTTP/1.1-Server und Mini-Webframework "Brise"

## Ziel
Implementiere in reinem Python 3 (nur Standardbibliothek, **ohne** `http.server`,
`wsgiref` oder `urllib` für das Parsen von Requests – Sockets, `selectors`, `threading`
bzw. `asyncio` sind erlaubt) einen standardkonformen HTTP/1.1-Server und darauf ein
kleines Webframework **Brise** mit Routing, Middleware, Templates, Sessions und
statischen Dateien. Belege Robustheit und Leistung mit Lasttests.

## Server-Anforderungen (RFC 9110/9112)
1. Eigener inkrementeller Request-Parser: Request-Line, Header (case-insensitive,
   mehrfach vorkommende Header, Obergrenzen für Größe), `Content-Length` und
   `Transfer-Encoding: chunked` (inkl. Trailer), Ablehnung fehlerhafter Anfragen mit
   400, zu großer mit 413/431, unbekannter Methoden mit 501.
2. Persistente Verbindungen (Keep-Alive), Pipelining in korrekter Reihenfolge,
   `Connection: close`, Idle-Timeouts, `Expect: 100-continue`.
3. Antworten mit `Content-Length` oder chunked Streaming (Generatoren), `HEAD`
   korrekt ohne Body, `Date`-Header, Bereichsanfragen (`Range`, 206, 416) für statische
   Dateien, bedingte Anfragen (`ETag`, `If-None-Match`, `Last-Modified`,
   `If-Modified-Since` → 304), gzip-Kompression bei `Accept-Encoding`.
4. Nebenläufigkeit über einen Thread-Pool **oder** eine Event-Loop mit `selectors`;
   sauberes Herunterfahren; Schutz vor Slowloris (Timeouts beim Header-Lesen).
5. Zugriffs-Log im Common Log Format.

## Framework-Anforderungen
1. **Routing**: `@app.route("/users/<int:id>", methods=["GET"])`, Konverter
   (`int`, `str`, `path`, `uuid`), 404/405 mit `Allow`-Header, URL-Generierung
   `url_for`.
2. **Request/Response-Objekte**: Query-Parameter, Formulardaten
   (`application/x-www-form-urlencoded` und `multipart/form-data` mit Dateiupload),
   JSON-Body, Cookies (Parsen und Setzen mit Attributen), Redirects, JSON-Antworten.
3. **Middleware-Kette** (vorher/nachher, Abbruch möglich): Logging, CORS,
   Fehlerbehandlung mit Debug-Seite, Request-ID.
4. **Template-Engine** (eigene Implementierung): Variablen mit automatischem
   HTML-Escaping, `{% if %}`, `{% for %}` mit `loop.index`, Filter (`upper`, `default`,
   `length`, `join`), Vererbung mit `{% extends %}`/`{% block %}`, `{% include %}`,
   Kompilierung zu Python-Code mit Cache.
5. **Sessions**: signierte Cookies (HMAC-SHA256) und alternativ serverseitiger
   Speicher; CSRF-Token für Formulare.
6. **Statische Dateien** mit MIME-Typen, Schutz vor Path-Traversal.
7. **Beispielanwendung**: kleines Notizbuch mit Login, Notizen anlegen/bearbeiten/
   löschen, Datei-Upload, JSON-API.

## Teststrategie (pytest)
- Parser-Tests mit rohen Byte-Strömen, auch byteweise zerstückelt zugeführt.
- Integrationstests über echte Sockets gegen einen Server auf zufälligem Port
  (Keep-Alive, Pipelining, chunked, Range, 304, gzip, Fehlercodes).
- Fuzz-Tests: 1000 zufällig mutierte Requests dürfen den Server nie zum Absturz
  bringen (Antwort 4xx oder Verbindungsabbruch).
- Template- und Routing-Tests, Session-Signatur-Manipulation muss erkannt werden.
- **Lasttest** (`loadtest.py` + pytest-Marker): mindestens 50 parallele Clients,
  10.000 Requests, keine Fehler; Durchsatz und Latenz-Perzentile (p50/p95/p99) werden
  ausgegeben und in DESIGN.md dokumentiert.
- Mindestens 150 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün, Beispielanwendung startbar, README, DESIGN.md, PROGRESS.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
