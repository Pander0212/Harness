"""Aufgaben-Generator: erzeugt neue, vielfältige Projektaufgaben per Modellaufruf."""
import random
import re

# (Schlüssel, deutscher Name fürs UI, englischer Name, englische Beispielideen)
TOPICS = [
    ("compiler", "Compiler & Interpreter", "Compilers & interpreters",
     "compiler for a language subset to bytecode/assembly, optimization passes (SSA, "
     "constant folding, register allocation), type inference"),
    ("database", "Datenbanken & Speicher", "Databases & storage",
     "key-value store with LSM tree, document database, time-series DB, full-text search "
     "with an inverted index, query optimizer"),
    ("network", "Netzwerke & Protokolle", "Networking & protocols",
     "DNS resolver, TCP simulation over UDP, Redis-compatible server, MQTT broker, IRC "
     "server, HTTP/2 framing"),
    ("game_engine", "Spiele-Engines & Simulation", "Game engines & simulation",
     "2D physics engine, ECS engine, chess engine with alpha-beta, roguelike engine "
     "(terminal), puzzle solver"),
    ("crypto", "Kryptographie", "Cryptography",
     "SHA-256/AES/ChaCha20 from scratch with test vectors, RSA with primality tests, "
     "elliptic curves, TLS-like handshake"),
    ("numerics", "Numerik & wissenschaftliches Rechnen", "Numerics & scientific computing",
     "matrix library with LU/QR/SVD, ODE solvers, FFT, symbolic differentiation, "
     "optimization methods"),
    ("parser", "Parser & Formate", "Parsers & formats",
     "JSON/YAML/TOML parser, regex engine (NFA/DFA), parser generator (LL/LALR), "
     "Markdown to HTML, CSV with dialects"),
    ("os_sim", "Betriebssystem-Simulation", "Operating system simulation",
     "process scheduler, virtual memory with paging, file system on a block device, shell "
     "with pipes, memory allocator"),
    ("distributed", "Verteilte Systeme", "Distributed systems",
     "Raft consensus with network simulation, distributed KV store, CRDTs, gossip "
     "protocol, MapReduce framework"),
    ("image", "Bildverarbeitung & Grafik", "Image processing & graphics",
     "PNG encoder/decoder, ray tracer, rasterizer, image filters and edge detection, "
     "baseline JPEG decoder"),
    ("algorithms", "Algorithmen & Datenstrukturen", "Algorithms & data structures",
     "graph library (flows, matching), persistent data structures, CDCL SAT solver, "
     "constraint solver, suffix arrays"),
    ("compression", "Kompression & Kodierung", "Compression & coding",
     "zlib-compatible DEFLATE implementation, LZ77/Huffman, arithmetic coding, BWT "
     "compressor, Reed-Solomon"),
    ("emulation", "Emulation & virtuelle Maschinen", "Emulation & virtual machines",
     "CHIP-8/6502 emulator, WebAssembly interpreter, JVM subset, stack VM with JIT-like "
     "optimization"),
    ("devtools", "Entwicklerwerkzeuge", "Developer tools",
     "build system with dependency graph, linter with AST rules, code formatter, test "
     "runner, package manager resolver (SAT)"),
    ("ml", "Maschinelles Lernen von Grund auf", "Machine learning from scratch",
     "autograd engine, neural network with backprop, decision trees/random forest, "
     "k-means, BPE tokenizer"),
    ("text", "Textverarbeitung & Suche", "Text processing & search",
     "spell checker, diff3/merge tool, template engine, search engine with BM25 ranking, "
     "typesetter"),
]
TOPIC_KEYS = [t[0] for t in TOPICS]
TOPIC_NAMES = {t[0]: t[1] for t in TOPICS}        # UI (deutsch)
TOPIC_NAMES_EN = {t[0]: t[2] for t in TOPICS}     # Prompt (englisch)

GEN_SYSTEM = ("You are an experienced computer science lecturer who designs demanding, "
              "realistic software projects on which an autonomous coding agent works "
              "test-driven for many hours.")

DONE_SENTENCE = "Do not stop until everything is finished and all tests pass."

GEN_PROMPT = """Design a NEW, detailed project assignment.

TOPIC AREA (mandatory): {topic_name}
Example ideas for this area (inspiration only, something else is welcome): {topic_examples}

EXISTING PROJECTS (do not repeat any of them, not even slightly modified):
{history}

REQUIREMENTS FOR THE ASSIGNMENT
- A demanding, self-contained software project in Python 3 (standard library only) with
  pytest. Scope: at least 8 hours of uninterrupted work for an experienced developer – at
  least 8 modules or components, at least 250 test cases, differential or property tests
  against a reference (standard library, brute-force implementation, official test
  vectors or similar), robustness and performance tests with documented measurements.
- Structure as in the style example: goal, detailed functional requirements (numbered,
  concrete), architecture guidelines, test strategy with concrete test cases and a minimum
  number of tests, acceptance criteria.
- Test-driven: tests first, run the tests after every feature, maintain DESIGN.md and
  PROGRESS.md.
- Must end with the sentence: "{done}"
- At least 600 words, written in English.

STYLE EXAMPLE (abridged):
{example}

RESPONSE FORMAT (follow exactly):
TITLE: <short, concise title>
---
<complete assignment in Markdown>"""


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
    m = re.search(r"(?:TITLE|TITEL):\s*(.+)", text or "")
    if not m:
        raise ValueError("No 'TITLE:' line found.")
    title = m.group(1).strip().strip("*#` ")
    rest = text[m.end():]
    if "---" in rest:
        rest = rest.split("---", 1)[1]
    body = rest.strip()
    return title[:120], body


def validate(title, body, existing_titles):
    problems = []
    if is_duplicate(title, existing_titles):
        problems.append(f"The title '{title}' is too similar to an existing project.")
    if len(body.split()) < 400:
        problems.append(f"The description is too short ({len(body.split())} words, "
                        "at least 600 required).")
    if "pytest" not in body.lower():
        problems.append("The test strategy with pytest is missing.")
    return problems


def generate_task(caller, history, example, rng=None, max_attempts=3):
    """caller(messages) -> text. Gibt dict(title, prompt, topic) zurück."""
    topic = choose_topic(history, rng)
    _, _, name, examples = next(t for t in TOPICS if t[0] == topic)
    hist_lines = [f"- {h.get('title')} "
                  f"[{TOPIC_NAMES_EN.get(h.get('topic'), h.get('topic') or '?')}]"
                  for h in history[-300:]] or ["(none yet)"]
    messages = [{"role": "system", "content": GEN_SYSTEM},
                {"role": "user", "content": GEN_PROMPT.format(
                    topic_name=name, topic_examples=examples, history="\n".join(hist_lines),
                    example=example[:3500], done=DONE_SENTENCE)}]
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
            if DONE_SENTENCE not in body:
                body += "\n\n" + DONE_SENTENCE
            return {"title": title, "prompt": body, "topic": topic}
        last_err = " ".join(problems)
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": "The assignment does not meet the "
                         "requirements: " + last_err + " Please revise it completely in the "
                         "required response format."})
    raise ValueError(f"Generator lieferte keine gültige Aufgabe: {last_err}")
