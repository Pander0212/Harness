---
topic: parser
---
# Regex-Engine, Lexer-Generator und LALR(1)-Parser-Generator

## Ziel
Entwickle in reinem Python 3 – ohne das Modul `re` (nur in Tests als Referenz) – eine
Regex-Engine mit mehreren Ausführungsstrategien sowie einen Lexer- und einen
LALR(1)-Parser-Generator (konzeptionell wie lex/yacc), die zusammen Parser für echte
Sprachen erzeugen. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Regex-Parser**: Literale, Escapes, Zeichenklassen (inkl. Bereiche, Negation,
   `\d\w\s` und Unicode-Kategorien über `unicodedata`), Quantoren (`* + ? {m,n}`,
   gierig und genügsam), Gruppen (einfangend, nicht einfangend, benannt), Alternation,
   Anker (`^ $ \b \B \A \z`), Flags (i, m, s, x).
2. **Ausführung**: Thompson-NFA-Simulation (lineare Zeit), **lazy DFA** mit Cache,
   **DFA-Minimierung** (Hopcroft), Backtracking-Engine für Rückreferenzen und
   Lookahead/Lookbehind; automatische Wahl der Strategie; Capture-Gruppen auch im
   NFA-Modus (Pike-VM).
3. **API** ähnlich `re`: `compile`, `match`, `fullmatch`, `search`, `findall`,
   `finditer`, `sub` (mit Gruppenreferenzen und Funktion), `split`.
4. **Lexer-Generator**: Spezifikation von Token per Regex mit Prioritäten,
   längster Treffer, Zustände (z. B. für Strings/Kommentare), Erzeugung einer
   Tabellen-DFA, Fehlerbehandlung mit Positionen; Codegenerierung als
   eigenständiges Python-Modul.
5. **Parser-Generator**: Grammatik-DSL mit Aktionen, FIRST/FOLLOW, LR(0)-Automat,
   **LALR(1)-Lookaheads** (DeRemer-Pennello oder Propagation), Präzedenz- und
   Assoziativitätsdeklarationen, Konfliktberichte mit Beispielen,
   Fehlerbehandlung mit `error`-Token, Codegenerierung als Python-Modul; zusätzlich
   ein LL(1)-Modus mit Konflikterkennung.
6. **Beispielsprachen**, mit den Generatoren erzeugt: Taschenrechner mit Variablen,
   JSON-Parser (voll konform), eine Teilmenge von C-Ausdrücken und Anweisungen mit AST,
   ein INI/TOML-artiges Format.

## Teststrategie (pytest)
- Differenztests gegen `re`: 3000 zufällig generierte Muster/Eingabe-Paare (fester
  Seed) für `match`, `search`, Gruppen und `sub` im gemeinsamen Funktionsumfang.
- Pathologische Muster (`(a*)*b` auf langen Eingaben) laufen im NFA/DFA-Modus in
  linearer Zeit (Zeitlimit-Test).
- DFA-Minimierung: Minimal-DFA gleicher Sprache für bekannte Fälle (Zustandszahlen).
- Parser-Generator: klassische Grammatiken aus dem Drachenbuch mit erwarteten
  Tabellen/Konflikten; erzeugter JSON-Parser gegen `json` auf 500 Zufallsdokumenten.
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Algorithmen in DESIGN.md, Benutzerhandbuch in docs/.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
