"""Aufgaben-Generator: erzeugt neue, vielfältige Projektaufgaben per Modellaufruf."""
import random
import re

TOPICS = [
    ("compiler", "Compiler & Interpreter", "Compiler für eine Teilsprache nach Bytecode/Assembler, "
     "Optimierungspässe (SSA, Konstantenfaltung, Registerallokation), Typinferenz"),
    ("database", "Datenbanken & Speicher", "Key-Value-Store mit LSM-Tree, Dokumentdatenbank, "
     "Zeitreihen-DB, Volltextsuche mit invertiertem Index, Query-Optimierer"),
    ("network", "Netzwerke & Protokolle", "DNS-Resolver, TCP-Simulation über UDP, "
     "Redis-kompatibler Server, MQTT-Broker, IRC-Server, HTTP/2-Framing"),
    ("game_engine", "Spiele-Engines & Simulation", "2D-Physik-Engine, ECS-Engine, "
     "Schach-Engine mit Alpha-Beta, Roguelike-Engine (Terminal), Rätsellöser"),
    ("crypto", "Kryptographie", "SHA-256/AES/ChaCha20 von Grund auf mit Testvektoren, "
     "RSA mit Primtests, elliptische Kurven, TLS-ähnlicher Handshake"),
    ("numerics", "Numerik & wissenschaftliches Rechnen", "Matrixbibliothek mit LU/QR/SVD, "
     "ODE-Löser, FFT, symbolische Differentiation, Optimierungsverfahren"),
    ("parser", "Parser & Formate", "JSON/YAML/TOML-Parser, Regex-Engine (NFA/DFA), "
     "Parser-Generator (LL/LALR), Markdown-zu-HTML, CSV mit Dialekten"),
    ("os_sim", "Betriebssystem-Simulation", "Prozess-Scheduler, virtueller Speicher mit "
     "Paging, Dateisystem auf Blockgerät, Shell mit Pipes, Speicherallokator"),
    ("distributed", "Verteilte Systeme", "Raft-Konsens mit Netzwerksimulation, verteilter "
     "KV-Store, CRDTs, Gossip-Protokoll, MapReduce-Framework"),
    ("image", "Bildverarbeitung & Grafik", "PNG-Encoder/Decoder, Raytracer, "
     "Rasterizer, Bildfilter und Kantenerkennung, JPEG-Baseline-Decoder"),
    ("algorithms", "Algorithmen & Datenstrukturen", "Graphbibliothek (Flüsse, Matching), "
     "persistente Datenstrukturen, SAT-Solver (CDCL), Constraint-Solver, Suffix-Arrays"),
    ("compression", "Kompression & Kodierung", "DEFLATE-Implementierung kompatibel zu zlib, "
     "LZ77/Huffman, Arithmetische Kodierung, BWT-Kompressor, Reed-Solomon"),
    ("emulation", "Emulation & virtuelle Maschinen", "CHIP-8/6502-Emulator, "
     "WebAssembly-Interpreter, JVM-Teilmenge, Stack-VM mit JIT-artiger Optimierung"),
    ("devtools", "Entwicklerwerkzeuge", "Build-System mit Abhängigkeitsgraph, Linter mit "
     "AST-Regeln, Code-Formatter, Test-Runner, Paketmanager-Resolver (SAT)"),
    ("ml", "Maschinelles Lernen von Grund auf", "Autograd-Engine, neuronales Netz mit "
     "Backprop, Entscheidungsbäume/Random Forest, k-Means, Tokenizer (BPE)"),
    ("text", "Textverarbeitung & Suche", "Rechtschreibprüfung, diff3/Merge-Tool, "
     "Template-Engine, Suchmaschine mit BM25 und Ranking, Typesetter"),
]
TOPIC_KEYS = [t[0] for t in TOPICS]
TOPIC_NAMES = {t[0]: t[1] for t in TOPICS}

GEN_SYSTEM = ("Du bist ein erfahrener Informatik-Dozent und entwirfst anspruchsvolle, "
              "realistische Software-Projekte, an denen ein autonomer Coding-Agent mehrere "
              "Stunden test-driven arbeitet.")

GEN_PROMPT = """Entwirf eine NEUE, ausführliche Projektaufgabe.

THEMENBEREICH (verbindlich): {topic_name}
Beispielideen für diesen Bereich (nur Anregung, gerne etwas anderes): {topic_examples}

BEREITS VORHANDENE PROJEKTE (keines davon wiederholen, auch nicht leicht abgewandelt):
{history}

ANFORDERUNGEN AN DIE AUFGABE
- Anspruchsvolles, in sich geschlossenes Software-Projekt in Python 3 (nur Standardbibliothek)
  mit pytest. Umfang: mindestens 8 Stunden ununterbrochene Arbeit für einen erfahrenen
  Entwickler – mindestens 8 Module bzw. Komponenten, mindestens 250 Testfälle,
  differenzielle oder Eigenschaftstests gegen eine Referenz (Standardbibliothek,
  Brute-Force-Implementierung, offizielle Testvektoren o. Ä.), Robustheits- und
  Leistungstests mit dokumentierten Messwerten.
- Gliederung wie im Stilbeispiel: Ziel, detaillierte funktionale Anforderungen
  (nummeriert, konkret), Architekturvorgaben, Teststrategie mit konkreten Testfällen und
  Mindestanzahl Tests, Abnahmekriterien.
- Test-driven: zuerst Tests, nach jedem Feature Tests laufen lassen, DESIGN.md und
  PROGRESS.md pflegen.
- Muss mit dem Satz enden: "Höre erst auf, wenn alles fertig ist und alle Tests grün sind."
- Mindestens 600 Wörter.

STILBEISPIEL (gekürzt):
{example}

ANTWORTFORMAT (exakt einhalten):
TITEL: <kurzer prägnanter Titel>
---
<vollständige Aufgabenbeschreibung in Markdown>"""


def normalize_title(t):
    return set(w for w in re.findall(r"[a-z0-9äöüß]+", t.lower()) if len(w) > 2)


def is_duplicate(title, existing_titles, threshold=0.6):
    a = normalize_title(title)
    if not a:
        return True
    for t in existing_titles:
        b = normalize_title(t)
        if not b:
            continue
        if a == b or len(a & b) / len(a | b) >= threshold:
            return True
    return False


def choose_topic(history, rng=None, avoid_last=3):
    """Gewichtete Themenwahl: Wechsel erzwingen, häufige und 'schwache' Themen seltener."""
    rng = rng or random.Random()
    counts = {k: 0 for k in TOPIC_KEYS}
    weak = {k: 0 for k in TOPIC_KEYS}
    for h in history:
        k = h.get("topic")
        if k in counts:
            counts[k] += 1
            if h.get("weak"):
                weak[k] += 1
    recent = [h.get("topic") for h in history[-avoid_last:]]
    candidates = [k for k in TOPIC_KEYS if k not in recent] or TOPIC_KEYS
    weights = [1.0 / (1 + counts[k]) * (0.3 ** weak[k]) for k in candidates]
    return rng.choices(candidates, weights=weights, k=1)[0]


def parse_generated(text):
    m = re.search(r"TITEL:\s*(.+)", text or "")
    if not m:
        raise ValueError("Kein 'TITEL:' gefunden")
    title = m.group(1).strip().strip("*#` ")
    rest = text[m.end():]
    if "---" in rest:
        rest = rest.split("---", 1)[1]
    body = rest.strip()
    return title[:120], body


def validate(title, body, existing_titles):
    problems = []
    if is_duplicate(title, existing_titles):
        problems.append(f"Der Titel '{title}' ist einem vorhandenen Projekt zu ähnlich.")
    if len(body.split()) < 400:
        problems.append(f"Die Beschreibung ist zu kurz ({len(body.split())} Wörter, "
                        "mindestens 600 gefordert).")
    if "pytest" not in body.lower():
        problems.append("Die Teststrategie mit pytest fehlt.")
    return problems


def generate_task(caller, history, example, rng=None, max_attempts=3):
    """caller(messages) -> text. Gibt dict(title, prompt, topic) zurück."""
    topic = choose_topic(history, rng)
    _, name, examples = next(t for t in TOPICS if t[0] == topic)
    hist_lines = [f"- {h.get('title')} [{TOPIC_NAMES.get(h.get('topic'), h.get('topic') or '?')}]"
                  for h in history[-300:]] or ["(noch keine)"]
    messages = [{"role": "system", "content": GEN_SYSTEM},
                {"role": "user", "content": GEN_PROMPT.format(
                    topic_name=name, topic_examples=examples, history="\n".join(hist_lines),
                    example=example[:3500])}]
    existing = [h.get("title", "") for h in history]
    last_err = ""
    for _ in range(max_attempts):
        text = caller(messages)
        try:
            title, body = parse_generated(text)
            problems = validate(title, body, existing)
        except ValueError as e:
            problems = [str(e)]
        if not problems:
            if "Höre erst auf" not in body:
                body += "\n\nHöre erst auf, wenn alles fertig ist und alle Tests grün sind."
            return {"title": title, "prompt": body, "topic": topic}
        last_err = " ".join(problems)
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": "Die Aufgabe erfüllt die Vorgaben nicht: "
                         + last_err + " Bitte überarbeite sie vollständig im geforderten "
                         "Antwortformat."})
    raise ValueError(f"Generator lieferte keine gültige Aufgabe: {last_err}")
