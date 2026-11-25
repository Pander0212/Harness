# Agent-Harness

Ein schlanker, autonomer Coding-Agent-Harness in Python. Er lässt rund um die Uhr
mehrere Agenten parallel an anspruchsvollen Software-Projekten arbeiten – test-driven,
mit langen Sessions, vielen echten Tool-Calls und großem Kontext. Bedienung über eine
kleine Web-Oberfläche.

- Nur **Python 3**, das Paket **`openai`** und die Standardbibliothek (`pytest` wird für
  die Tests und von den Agenten selbst genutzt).
- OpenAI-kompatible API (Standard: `https://nano-gpt.com/api/v1`).
- Mehrere Agenten als Threads in **einem** Prozess, Warteschlange, Endlosmodus mit
  Aufgaben-Generator, automatische Drosselung bei Fehlern.
- Sparsam: im Leerlauf praktisch keine CPU-Last, typischer RAM-Bedarf unter 200 MB
  (plus das, was die Agenten selbst starten).

## Inhalt

| Datei | Zweck |
|---|---|
| `main.py` | Einstiegspunkt: startet Scheduler und Web-UI |
| `agent.py` | Agent-Kern: Tool-Calling, Wiederholungen, Komprimierung, Statistik |
| `manager.py` | Queue, Parallelität, Drosselung, Endlosmodus, Persistenz |
| `generator.py` | Erzeugt neue, vielfältige Projektaufgaben |
| `sandbox.py` | Pfadschutz, bash-Ausführung, bubblewrap-Sandbox |
| `swarm.py` | Subagenten und Schwarm (parallele Kind-Agenten) |
| `webui.py`, `ui.html` | Web-Oberfläche (http.server + Vanilla-JS) |
| `tasks/*.md` | 25 eingebaute Projektaufgaben (je ca. 8 Stunden Arbeit) |
| `tests/` | Tests für den Harness (mit Fake-API-Client) |
| `harness.service` | systemd-Unit für den Dauerbetrieb |
| `start.sh` / `start.bat` | Start unter Linux/Mac bzw. Windows |

## Schnellstart (lokal, Linux/Mac/Windows)

```bash
git clone <repo-url> harness && cd harness
./start.sh                 # Windows: start.bat doppelklicken
```

`start.sh` legt beim ersten Start ein virtuelles Environment `.venv` an, installiert
`openai` und `pytest` und erzeugt eine `config.json` mit Standardwerten.

Dann im Browser **http://127.0.0.1:8765/** öffnen, unter *Einstellungen* API-Key und
Modell eintragen und *Speichern* – die Agenten starten automatisch.

Alternativ `config.example.json` nach `config.json` kopieren und dort `api_key` und
`model` eintragen.

## Einrichtung auf einem Linux-VPS (Debian/Ubuntu)

```bash
# 1. Pakete
sudo apt update
sudo apt install -y python3 python3-venv git bubblewrap

# 2. Eigener Benutzer ohne Login und ohne sudo-Rechte (siehe unten)
sudo useradd --system --create-home --home-dir /var/lib/harness --shell /usr/sbin/nologin harness

# 3. Code nach /opt/harness
sudo git clone <repo-url> /opt/harness
sudo chown -R harness:harness /opt/harness
cd /opt/harness
sudo -u harness python3 -m venv .venv
sudo -u harness .venv/bin/pip install -r requirements.txt

# 4. Konfiguration
sudo -u harness cp config.example.json config.json
sudo -u harness nano config.json          # api_key und model eintragen
sudo chmod 600 config.json

# 5. Als Dienst starten (siehe "Dauerbetrieb mit systemd")
sudo cp harness.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now harness
sudo journalctl -u harness -f             # Log ansehen
```

Andere Distributionen: `bubblewrap` heißt fast überall so (`dnf install bubblewrap`,
`pacman -S bubblewrap`).

### Zugriff auf das UI per SSH-Tunnel

Das UI lauscht standardmäßig nur auf `127.0.0.1:8765` und ist damit aus dem Internet
nicht erreichbar. Vom eigenen Rechner aus:

```bash
ssh -N -L 8765:127.0.0.1:8765 benutzer@dein-vps
```

Danach lokal **http://127.0.0.1:8765/** öffnen. (Windows: gleiches Kommando in der
PowerShell, oder in PuTTY unter *Connection → SSH → Tunnels* Quellport `8765`, Ziel
`127.0.0.1:8765`.)

### UI direkt freigeben (nicht empfohlen)

In `config.json` `"ui_host": "0.0.0.0"` und ein starkes `"ui_password"` setzen. Ohne
Passwort verweigert der Harness den Start auf einer öffentlichen Adresse. Der Login
erfolgt per HTTP-Basic-Auth (Benutzername beliebig). Da die Verbindung unverschlüsselt
ist, besser einen SSH-Tunnel oder einen Reverse-Proxy mit HTTPS verwenden.

## Dauerbetrieb mit systemd

`harness.service` startet den Harness beim Booten und nach Abstürzen automatisch neu
(`Restart=always`). Bei `systemctl stop/restart` werden laufende Agenten sauber
unterbrochen; nach dem Neustart setzen sie anhand ihrer `PROGRESS.md` fort. Auch nach
einem harten Absturz (Stromausfall, OOM) werden Aufgaben mit Status „läuft“ beim
nächsten Start automatisch vorne in die Queue gestellt und fortgesetzt.

Pfade, Benutzer und `MemoryMax` in der Unit-Datei bei Bedarf anpassen. Liegt der
Harness in einem Home-Verzeichnis, `ProtectHome=true` entfernen.

## Sicherheit: Ordner-Begrenzung und Sandbox

- **Dateiwerkzeuge** (`read_file`, `write_file`, `list_dir`) akzeptieren nur Pfade
  innerhalb von `allowed_dirs` (Standard: `./workspaces`). Pfade werden vollständig
  aufgelöst (`realpath`), d. h. `..`, Symlinks und Präfix-Tricks
  (`/workspaces-evil`) werden erkannt. `config.json` und der `data`-Ordner sind immer
  gesperrt.
- **bash** läuft immer im Workspace der Aufgabe. Ist **bubblewrap** (`bwrap`)
  installiert und funktionsfähig, läuft jeder Befehl in einer Sandbox:
  - das gesamte Dateisystem ist **read-only**, nur `allowed_dirs` sind beschreibbar,
  - `/home` und `/root` sind ausgeblendet (leeres tmpfs), außer den erlaubten Ordnern,
  - eigenes `/tmp`, eigener PID-Namensraum, `config.json` ist überblendet,
  - API-Keys werden aus der Umgebung entfernt.
  - `no_new_privs` ist gesetzt: `sudo`/setuid-Programme können keine Rechte erlangen.
  - `/mnt` und `/media` sind ausgeblendet (unter WSL also auch die Windows-Laufwerke).
  - Netzwerk ist erlaubt (z. B. für `pip`); mit `"sandbox_network": false` abschaltbar.
- Ohne funktionierende Sandbox startet der Harness **keine Agenten** und zeigt den
  Grund im UI (`require_sandbox`). Nur wer bewusst ohne Sandbox arbeiten will, setzt
  `"sandbox": "none"` in `config.json`.

bwrap installieren: `sudo apt install bubblewrap`. Test:
`bwrap --ro-bind / / --dev /dev --proc /proc true && echo ok`. Schlägt das unter
Ubuntu 24.04+ fehl, blockiert AppArmor unprivilegierte User-Namespaces; Abhilfe:
`sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` (dauerhaft per Datei
in `/etc/sysctl.d/`). Ist bwrap auf deinem System setuid installiert (ältere
Distributionen), in `harness.service` die Zeile `NoNewPrivileges=true` entfernen.

### Agenten unter einem eigenen Linux-Benutzer ausführen

Zusätzlich zur Sandbox (oder wenn bwrap nicht verfügbar ist) sollte der Harness unter
einem eigenen, unprivilegierten Benutzer laufen. Dann können die Agenten höchstens das
beschädigen, was diesem Benutzer gehört:

```bash
sudo useradd --system --create-home --home-dir /var/lib/harness --shell /usr/sbin/nologin harness
sudo chown -R harness:harness /opt/harness
sudo chmod 700 /opt/harness
# Der Benutzer gehört in keine Gruppe mit Sonderrechten (sudo, docker, adm …):
id harness
```

Manuell starten: `sudo -u harness /opt/harness/start.sh`. Die mitgelieferte
`harness.service` verwendet bereits `User=harness`. Eigene Dateien anderer Benutzer
sollten nicht weltweit lesbar sein (`chmod 700 ~`).

### Windows / alter Laptop

**Einrichtung unter Windows 10/11 (einmalig):**

1. **Python installieren:** https://www.python.org/downloads/windows/ → „Download
   Python 3.x“. Im Installer **unten den Haken „Add python.exe to PATH“ setzen**,
   dann „Install Now“.
2. **Git for Windows installieren:** https://git-scm.com/download/win (alle
   Standardoptionen übernehmen). Die Agenten führen ihre Befehle in Git Bash aus.
3. **Harness herunterladen:** auf GitHub „Code → Download ZIP“, entpacken (z. B. nach
   `C:\harness`) – oder `git clone`.
4. **`start.bat` doppelklicken.** Beim ersten Start wird `.venv` angelegt und
   `openai`/`pytest` installiert (dauert 1–2 Minuten). Danach öffnet sich das UI im
   Browser (http://127.0.0.1:8765/). Dort API-Key und Modell eintragen.

`start.sh` ist nur für Linux/Mac – unter Windows immer `start.bat` verwenden.
Meldet `start.bat`, dass Python fehlt, obwohl es installiert ist: Python erneut
installieren und den PATH-Haken setzen, oder unter *Einstellungen → Apps →
App-Ausführungsaliase* die beiden Einträge „python.exe“ / „python3.exe“ (Microsoft
Store) ausschalten.

**Windows-Sandbox (eingebaut, ohne Zusatzsoftware):** Jeder Befehl der Agenten läuft
mit einem eingeschränkten Windows-Token:

- Integritätsstufe *Low*: Schreiben **nur** in den zugewiesenen Ordnern
  (`allowed_dirs`, Standard `workspaces\`). Windows, Programme, Benutzerprofil,
  Registry, `.venv` und der Harness selbst sind schreibgeschützt.
- Keine Admin-Rechte: alle Privilegien entfernt, die Administratoren-Gruppe ist
  deaktiviert. `config.json` (API-Key) und `data\` sind für die Agenten nicht einmal
  lesbar.
- Stufe *streng* (wenn das System sie unterstützt): zusätzlich kein Lesezugriff auf
  dein Benutzerprofil (Dokumente, Desktop, Downloads, AppData).
- Job-Objekt: Unterprozesse können nicht ausbrechen, Speicherlimit
  (`win_job_memory_mb`), kein Zugriff auf Zwischenablage, kein Herunterfahren.

Beim Start prüft der Harness das alles mit einem **Selbsttest** (Schreiben im Workspace
ok, Schreiben außerhalb blockiert, `config.json` unlesbar, keine Admin-Rechte, ggf.
Profil unlesbar). Im UI steht dann grün „Sandbox aktiv: …“. Schlägt der Test fehl,
werden **keine Agenten gestartet** (`require_sandbox`), und das UI zeigt den Grund.
Die zuletzt funktionierende Stufe wird in `data\\sandbox_level.txt` gemerkt und beim
nächsten Start zuerst getestet. Netzwerkzugriff bleibt erlaubt. Ordner auf anderen Laufwerken, die „Jeder“ lesen darf,
bleiben lesbar. Bestätige nie eine UAC-Abfrage, die du nicht selbst ausgelöst hast.

Das Fenster von `start.bat` muss offen bleiben, solange die Agenten arbeiten
(Energiesparmodus ausschalten). Für 8 GB RAM `max_parallel` auf 2–3 und
`max_total_subagents` auf 2–3 setzen.

## Konfiguration (`config.json`)

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `api_key`, `model`, `base_url` | – | Zugang zur OpenAI-kompatiblen API |
| `max_parallel` | 4 | gleichzeitige Agenten (im UI 1–20) |
| `max_hours` | 36 | maximale aktive Laufzeit je Aufgabe |
| `context_limit` / `compress_at` | 200000 / 170000 | Kontextgröße / Schwelle für Komprimierung |
| `max_output_tokens` | 8192 | `max_tokens` pro Antwort (an das Limit des Modells anpassen) |
| `stream` | true | Antworten streamen: Live-Fortschritt im UI, Hänger-Erkennung |
| `stall_timeout` | 300 | so viele Sekunden ohne neue Daten gelten als Hänger → neuer Versuch |
| `tool_output_limit` | 15000 | Kürzung der Tool-Ausgaben (Anfang + Ende) |
| `bash_timeout` / `bash_max_timeout` | 600 / 3600 | Sekunden |
| `max_retries` | 10 | Wiederholungen pro Anfrage (im UI 0–100) |
| `retry_delays` | [5] | Wartezeit(en) in s vor Wiederholung 1, 2, …; der letzte Wert gilt weiter |
| `retry_after_max` | 60 | bei 429 mit `Retry-After`: höchstens so lange warten |
| `retry_overloaded_forever` | true | bei Überlastung („busy“, 429/502/503/504/529) endlos weiter versuchen |
| `overload_delay` | 5 | Sekunden zwischen Versuchen bei Überlastung (±`retry_jitter`) |
| `spec_docs` | true | vor dem Start `docs/SPEC.md` und `docs/TESTPLAN.md` erzeugen |
| `spec_doc_tokens` | 7000 | Zielumfang je Dokument (unter `max_output_tokens` halten) |
| `allowed_dirs` | ["./workspaces"] | beschreibbare/lesbare Ordner |
| `endless_mode` | true | bei leerer Queue neue Aufgaben generieren |
| `verify_on_finish` | true | `finish` nur akzeptieren, wenn `pytest` grün ist |
| `archive_finished` | false | fertige Workspaces als `.tar.gz` nach `archive/` |
| `subagents_enabled` | true | Werkzeuge `subagent`/`swarm` für Hauptagenten |
| `max_subagents` | 4 | max. Arbeitspakete pro Schwarm |
| `max_total_subagents` | 8 | max. gleichzeitig laufende Subagenten insgesamt |
| `subagent_max_hours` | 6 | Zeitlimit je Subagent |
| `swarm_ratio` | 0.25 | Anteil generierter Aufgaben im Schwarm-Modus |
| `sandbox` | auto | `auto` (bwrap unter Linux, Token-Sandbox unter Windows) oder `none` |
| `require_sandbox` | true | ohne funktionierende Sandbox keine Agenten starten |
| `win_job_memory_mb` | 2048 | Windows: Speicherlimit je Befehl (0 = aus) |
| `win_sandbox_level` | auto | Windows: `auto` (erst streng, dann Low), `strict` oder `lowil` erzwingen |
| `price_input_per_m` / `price_output_per_m` | 0.135 / 2.25 | $ pro 1 Mio. Tokens |
| `max_log_mb` / `log_keep` | 50 / 5 | Rotation der Gesprächsprotokolle |
| `ui_host`, `ui_port`, `ui_password` | 127.0.0.1, 8765, "" | Web-UI |

## Funktionsweise

### Agent
Jeder Agent arbeitet in `workspaces/<aufgabe>/` mit den Werkzeugen `bash`,
`read_file`, `write_file`, `list_dir` und `finish`. Der Systemprompt verlangt
test-driven Arbeit, Tests nach jedem Feature, einen Ansatzwechsel nach drei
gleichen Fehlschlägen und die Pflege von `DESIGN.md` und `PROGRESS.md`. `finish`
wird nur akzeptiert, wenn `python3 -m pytest` im Workspace grün ist (abschaltbar).

Ein Agent stoppt bei `finish`, nach `max_hours` aktiver Laufzeit oder nach vier
Antworten ohne Tool-Call in Folge.

**Kontext-Komprimierung:** Erreicht der Kontext 170k Tokens, fasst das Modell den
Verlauf selbst zusammen. Danach beginnt ein neuer Verlauf aus Systemprompt, Aufgabe,
Zusammenfassung sowie dem aktuellen Inhalt von `PROGRESS.md`, `DESIGN.md` und der
Dateiliste; der Agent liest die relevanten Dateien anschließend neu ein.

### Spezifikation und Testkatalog vor dem Start
Bevor ein Hauptagent mit einer neuen Aufgabe beginnt, schreibt das Modell eine
ausführliche, verbindliche Spezifikation (`docs/SPEC.md`: Architektur, exakte
Schnittstellen, Datenformate, Randfälle, Beispiele) und einen Testkatalog
(`docs/TESTPLAN.md`: nummerierte Testfälle mit konkreten Erwartungen), je etwa
`spec_doc_tokens` Tokens. Der Agent liest beide vollständig, implementiert danach und
setzt die Testfälle als pytest-Tests um; nach jeder Komprimierung wird er erneut darauf
verwiesen. Subagenten lesen die für ihr Paket relevanten Abschnitte. Lange Dokumente
werden über `continue` fortgesetzt und zusammengesetzt. Schlägt die Erzeugung fehl,
startet die Aufgabe ohne Dokumente.

### Subagenten und Schwarm
Hauptagenten haben zwei zusätzliche Werkzeuge:

- **`subagent`** – delegiert eine abgegrenzte Teilaufgabe (Modul implementieren,
  Testsuite schreiben, Fehlerursache suchen, Review) an einen Kind-Agenten mit
  frischem Kontext. Der Aufruf blockiert, bis der Subagent `finish` meldet, und
  liefert dessen Bericht samt Liste der geänderten Dateien zurück.
- **`swarm`** – startet bis zu `max_subagents` Kind-Agenten **parallel** im selben
  Workspace. Jedes Arbeitspaket braucht einen eigenen, überschneidungsfreien
  Schreibbereich (`scope`); `write_file` setzt ihn durch, überlappende oder fehlende
  Bereiche werden abgelehnt. Danach integriert der Hauptagent und testet alles.

Subagenten haben einen eigenen Systemprompt, eigene Logs/Protokolle unter
`data/tasks/<id>/sub/<nr>-<name>/`, nutzen dieselbe Fehlerbehandlung (4 Retries) und
können selbst keine weiteren Subagenten starten. Ihre Tokens und Kosten fließen in die
Statistik der Aufgabe ein (live im UI, mit eigener Zeile pro laufendem Subagenten).
Stop/Herunterfahren beendet auch alle Subagenten; ein Auth-Fehler eines Subagenten
bricht die Aufgabe ab. `max_total_subagents` begrenzt die gleichzeitig laufenden
Subagenten über alle Aufgaben (wichtig für den Laptop).

**Schwarm-Modus pro Aufgabe:** Beim Hinzufügen oder per Button „→ Schwarm“ wird eine
Aufgabe zur Koordinator-Aufgabe. Der Hauptagent bekommt dann einen
Koordinator-Prompt: Architektur und Schnittstellen in `DESIGN.md`, Arbeitspakete in
`PLAN.md`, Pakete in Wellen per `swarm` verteilen, integrieren, gesamte Testsuite grün.
Generierte Aufgaben werden mit Wahrscheinlichkeit `swarm_ratio` (Standard 0,25) im
Schwarm-Modus gestartet.

### Fehlerbehandlung
- 429, 5xx, Timeouts, Verbindungsfehler, leere/abgelehnte/abgebrochene Antworten:
  bis zu 10 Wiederholungen im Abstand von 5 s (beides im UI einstellbar). Schickt
  der Anbieter bei 429 einen `Retry-After`-Header, wird so lange gewartet (max. 60 s). War eine Antwort
  abgeschnitten, wird der Teil übernommen und `continue` angehängt.
- **Überlastung** („… is busy, please try again“, „overloaded“, HTTP 429/502/503/504/529
  – auch wenn die Meldung als normaler Antworttext kommt): Es wird **endlos** alle 5 s
  (mit ±20 % Streuung) weiter versucht, ohne dass die Aufgabe abbricht. Diese Versuche
  zählen nicht gegen `max_retries`; das UI zeigt „überlastet – Versuch n“.
- Kontext zu lang (400/413 mit „context/token/length“): erst komprimieren, dann
  erneut senden.
- 401/403: sofortiger Abbruch, rotes Banner im UI, **keine** weiteren Starts, bis die
  Einstellungen gespeichert wurden (oder „Sperre aufheben“).
- Nach allen erfolglosen Wiederholungen: Status „fehler“, Workspace bleibt erhalten,
  sofort startet die nächste Aufgabe. „Fortsetzen“ nimmt sie später wieder auf.
- Streaming: Das UI zeigt bei jeder laufenden Anfrage Bezeichnung, Dauer und bisher
  empfangene Tokens (z. B. „⇄ SPEC.md · 45s · ~3,1 k Tok.“). Kommen `stall_timeout`
  Sekunden lang keine Daten, wird neu versucht; bereits empfangener Text bleibt
  erhalten und wird mit `continue` fortgesetzt.
- 3 Abbrüche innerhalb von 10 Minuten senken die Parallelität um 1 (Anzeige im UI);
  nach 30 fehlerfreien Minuten wird sie schrittweise wieder erhöht. Mit dem Button
  „Drosselung zurücksetzen“ im UI sofort wieder volle Parallelität.

### Eingebaute Aufgaben
`tasks/*.md` enthält 25 große Projekte (u. a. SQL-Datenbank, Interpreter, Git-Klon,
HTTP-Server, RISC-V-Emulator, TCP/IP-Stack, Raft, LSM-Speicher, Kryptographie,
Pathtracer, Bild-Codecs, SAT/SMT-Solver, Schach-Engine, Physik-Engine, OS-Simulator,
WebAssembly, Scheme-Compiler, DataFrames, Numerik, Autograd/Transformer, Build-System,
Suchmaschine, Regex/Parser-Generator, MQTT-Broker, Tabellenkalkulation), jeweils auf
etwa 8 Stunden Arbeit ausgelegt. Neue Dateien in `tasks/` werden bei jedem Start erkannt
und hinten an die Queue gehängt. Ein optionaler Kopf steuert die Aufgabe:

```
---
spec_docs: false     # keine SPEC.md/TESTPLAN.md vorab (true = immer, fehlt = Einstellung)
mode: swarm          # als Schwarm-Koordinator starten
topic: crypto        # Themenbereich (für Statistik und Generator)
---
# Titel der Aufgabe
...
```

Im UI lässt sich beides pro Aufgabe umschalten („SPEC: Std./an/aus“, „→ Schwarm“).

### Endlosmodus und Aufgaben-Generator
Ist die Queue leer, erzeugt ein Generator-Aufruf eine neue, ausführliche
Projektaufgabe. Der Themenbereich wird vorab gewichtet gewählt (16 Bereiche wie
Compiler, Datenbanken, Netzwerke, Kryptographie, Numerik, verteilte Systeme …): Die
letzten drei Bereiche sind gesperrt, häufig genutzte und als „schwach“ markierte
Bereiche werden seltener gewählt. Die vollständige Liste bisheriger Projekte
(`data/history.json`) wird mitgegeben; zu ähnliche Titel, zu kurze Beschreibungen
oder fehlende Teststrategie führen zu einer Überarbeitungsrunde.

**Qualitätscheck:** Beendete Projekte mit weniger als 20 Tool-Calls oder ohne einzige
grüne Testsuite werden als „schwach“ markiert.

### Daten und Logs
```
data/state.json                  Queue und Aufgabenstatus
data/history.json                alle abgeschlossenen Projekte
data/harness.log                 Harness-Log (rotiert, 3 × 10 MB)
data/tasks/<id>/task.md          Aufgabentext
data/tasks/<id>/stats.json       Token-Statistik und Kosten
data/tasks/<id>/conversation.jsonl  vollständiges Gesprächsprotokoll (rotiert, gzip)
data/tasks/<id>/agent.log        Kurzlog des Agenten
workspaces/<id>/                 Arbeitsordner des Agenten
archive/<id>.tar.gz              archivierte Workspaces (optional)
```

## Web-Oberfläche
- Oben: Tokens gesamt, verdiente $ gesamt, $ pro Stunde (gleitender Schnitt der
  letzten Stunde), Hochrechnung auf 24 h, Parallelität, Queue-Länge.
- Pro Aufgabe: Status (wartet / läuft / retry x/10 / fertig / fehler / schwach /
  gestoppt), aktueller Kontext, Calls, Tool-Calls, Retries, Komprimierungen, Tokens,
  Kosten, Laufzeit, letzte Fehlermeldung, Log (letzte 30 Zeilen).
- Buttons: Start (sofort), Stop, Neustart (Workspace verwerfen), Fortsetzen,
  Reihenfolge ändern, Löschen, Aufgabentext anzeigen; Endlosmodus an/aus; Pause.
- Aufgaben hinzufügen, Einstellungen (API-Key, Modell, Parallelität, `max_hours`,
  `allowed_dirs` …) bearbeiten und speichern.

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

Die Tests verwenden einen Fake-API-Client und prüfen u. a. die Wiederholungen mit
Wartezeiten und `continue`, Auth-Sperre, Abbruch und Weiterschalten, Drosselung und
Erholung, Pfadschutz (`..`, Symlinks), Kürzung, Komprimierung, Queue, Generator,
Fortsetzen nach Neustart, Subagenten/Schwarm (echte Parallelität, Scope-Schutz,
globales Limit, Fehler- und Stop-Weitergabe) und die Web-API.
