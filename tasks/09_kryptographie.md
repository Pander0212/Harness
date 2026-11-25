---
topic: crypto
legacy_title: Kryptographie-Bibliothek von Grund auf mit TLS-1.3-artigem Protokoll
---
# Cryptography Library from Scratch with a TLS-1.3-Like Protocol

## Goal
Implement, in pure Python 3 – without `hashlib`, `hmac`, `secrets` or `ssl` for the actual
algorithms (allowed only for comparison tests and random numbers from `os.urandom`) – a
cryptography library and on top of it a simplified but cryptographically complete
TLS 1.3 handshake protocol. All algorithms are checked against official test vectors.
Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Hash functions**: SHA-256, SHA-512, SHA-384, SHA3-256/512 and SHAKE128/256
   (Keccak), BLAKE2b; streaming API (`update`/`digest`/`copy`).
2. **MACs and KDFs**: HMAC, HKDF (extract/expand, RFC 5869), PBKDF2, scrypt.
3. **Block cipher AES-128/192/256** (table-based and reference implementation) with the
   modes ECB (tests only), CBC with PKCS#7, CTR and **GCM** (GHASH, RFC-compliant tags).
4. **ChaCha20-Poly1305** (RFC 8439) including XChaCha20.
5. **Big integers and number theory**: modular exponentiation, Miller-Rabin, extended
   Euclidean algorithm, CRT; **RSA** with key generation, OAEP and PSS.
6. **Elliptic curves**: X25519 (RFC 7748, Montgomery ladder, aim for constant flow),
   Ed25519 signatures (RFC 8032), P-256 ECDSA with deterministic k (RFC 6979).
7. **Encodings**: Base64, PEM, a subset of ASN.1 DER for reading/writing keys.
8. **TLS-1.3-like protocol** over an in-memory transport: ClientHello/ServerHello with key
   exchange (X25519), key schedule per RFC 8446 (early, handshake, application secrets),
   encrypted handshake messages, certificate (your own simple format, signed with
   Ed25519), CertificateVerify, Finished, record layer with AES-GCM and
   ChaCha20-Poly1305, key update, session resumption with PSK. Attacks such as downgrade
   and tampered records must be detected.

## Test Strategy (pytest)
- Official test vectors: NIST (SHA, AES, GCM), RFC 4231 (HMAC), RFC 5869, RFC 8439,
  RFC 7748, RFC 8032, RFC 6979 – at least 150 vectors.
- Differential tests against `hashlib`/`hmac` with 1000 random inputs (fixed seed).
- Property tests: decrypt(encrypt(x)) = x, signature verification, flipping any bit
  causes an error.
- Protocol tests: full handshake, resumption, all error paths (wrong signature, wrong
  Finished, replay, downgrade).
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; DESIGN.md describes security assumptions and known
  limitations (e.g. side channels in Python); README with examples.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
