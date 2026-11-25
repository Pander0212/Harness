---
topic: crypto
---
# Kryptographie-Bibliothek von Grund auf mit TLS-1.3-artigem Protokoll

## Ziel
Implementiere in reinem Python 3 – ohne `hashlib`, `hmac`, `secrets` oder `ssl` für die
eigentlichen Algorithmen (nur für Vergleichstests und Zufallszahlen aus `os.urandom`
erlaubt) – eine Kryptographie-Bibliothek und darauf ein vereinfachtes, aber
kryptographisch vollständiges TLS-1.3-Handshake-Protokoll. Alle Algorithmen werden gegen
offizielle Testvektoren geprüft. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Hashfunktionen**: SHA-256, SHA-512, SHA-384, SHA3-256/512 und SHAKE128/256
   (Keccak), BLAKE2b; Streaming-API (`update`/`digest`/`copy`).
2. **MACs und KDFs**: HMAC, HKDF (Extract/Expand, RFC 5869), PBKDF2, scrypt.
3. **Blockchiffre AES-128/192/256** (Tabellen- und Referenzimplementierung) mit den Modi
   ECB (nur für Tests), CBC mit PKCS#7, CTR und **GCM** (GHASH, RFC-konforme Tags).
4. **ChaCha20-Poly1305** (RFC 8439) inklusive XChaCha20.
5. **Großzahl- und Zahlentheorie**: modulare Exponentiation, Miller-Rabin, erweiterter
   euklidischer Algorithmus, CRT; **RSA** mit Schlüsselerzeugung, OAEP und PSS.
6. **Elliptische Kurven**: X25519 (RFC 7748, Montgomery-Leiter, konstanter Ablauf
   angestrebt), Ed25519-Signaturen (RFC 8032), P-256 ECDSA mit deterministischem k
   (RFC 6979).
7. **Kodierungen**: Base64, PEM, eine ASN.1-DER-Teilmenge zum Lesen/Schreiben von
   Schlüsseln.
8. **TLS-1.3-ähnliches Protokoll** über einer In-Memory-Transportschicht: ClientHello/
   ServerHello mit Schlüsselaustausch (X25519), Key Schedule nach RFC 8446 (Early,
   Handshake, Application Secrets), verschlüsselte Handshake-Nachrichten,
   Zertifikat (eigenes einfaches Format, signiert mit Ed25519), CertificateVerify,
   Finished, Record Layer mit AES-GCM und ChaCha20-Poly1305, Key Update,
   Session-Resumption mit PSK. Angriffe wie Downgrade und manipulierte Records müssen
   erkannt werden.

## Teststrategie (pytest)
- Offizielle Testvektoren: NIST (SHA, AES, GCM), RFC 4231 (HMAC), RFC 5869, RFC 8439,
  RFC 7748, RFC 8032, RFC 6979 – mindestens 150 Vektoren.
- Differenzielle Tests gegen `hashlib`/`hmac` mit 1000 zufälligen Eingaben (fester Seed).
- Eigenschaftstests: Entschlüsseln(Verschlüsseln(x)) = x, Signatur-Verifikation,
  Manipulation eines beliebigen Bits führt zu Fehler.
- Protokolltests: vollständiger Handshake, Resumption, alle Fehlerpfade (falsche
  Signatur, falsches Finished, Replay, Downgrade).
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; DESIGN.md beschreibt Sicherheitsannahmen und bekannte
  Grenzen (z. B. Seitenkanäle in Python); README mit Beispielen.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
