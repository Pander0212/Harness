---
legacy_title: HTTP/1.1-Server und Mini-Webframework "Brise"
---
# HTTP/1.1 Server and Mini Web Framework "Breeze"

## Goal
Implement, in pure Python 3 (standard library only, **without** `http.server`, `wsgiref`
or `urllib` for parsing requests – sockets, `selectors`, `threading` or `asyncio` are
allowed), a standards-compliant HTTP/1.1 server and on top of it a small web framework
**Breeze** with routing, middleware, templates, sessions and static files. Prove
robustness and performance with load tests.

## Server Requirements (RFC 9110/9112)
1. Your own incremental request parser: request line, headers (case-insensitive,
   repeated headers, size limits), `Content-Length` and `Transfer-Encoding: chunked`
   (including trailers), rejection of malformed requests with 400, oversized ones with
   413/431, unknown methods with 501.
2. Persistent connections (keep-alive), pipelining in the correct order,
   `Connection: close`, idle timeouts, `Expect: 100-continue`.
3. Responses with `Content-Length` or chunked streaming (generators), `HEAD` correctly
   without a body, `Date` header, range requests (`Range`, 206, 416) for static files,
   conditional requests (`ETag`, `If-None-Match`, `Last-Modified`, `If-Modified-Since` →
   304), gzip compression with `Accept-Encoding`.
4. Concurrency via a thread pool **or** an event loop with `selectors`; clean shutdown;
   protection against Slowloris (timeouts while reading headers).
5. Access log in Common Log Format.

## Framework Requirements
1. **Routing**: `@app.route("/users/<int:id>", methods=["GET"])`, converters (`int`,
   `str`, `path`, `uuid`), 404/405 with an `Allow` header, URL generation `url_for`.
2. **Request/response objects**: query parameters, form data
   (`application/x-www-form-urlencoded` and `multipart/form-data` with file upload), JSON
   body, cookies (parsing and setting with attributes), redirects, JSON responses.
3. **Middleware chain** (before/after, can short-circuit): logging, CORS, error handling
   with a debug page, request ID.
4. **Template engine** (your own implementation): variables with automatic HTML
   escaping, `{% if %}`, `{% for %}` with `loop.index`, filters (`upper`, `default`,
   `length`, `join`), inheritance with `{% extends %}`/`{% block %}`, `{% include %}`,
   compilation to Python code with a cache.
5. **Sessions**: signed cookies (HMAC-SHA256) and alternatively server-side storage;
   CSRF tokens for forms.
6. **Static files** with MIME types, protection against path traversal.
7. **Example application**: a small notebook with login, creating/editing/deleting notes,
   file upload, JSON API.

## Test Strategy (pytest)
- Parser tests with raw byte streams, also fed byte by byte in fragments.
- Integration tests over real sockets against a server on a random port (keep-alive,
  pipelining, chunked, range, 304, gzip, error codes).
- Fuzz tests: 1000 randomly mutated requests must never crash the server (response 4xx
  or connection closed).
- Template and routing tests; tampering with the session signature must be detected.
- **Load test** (`loadtest.py` + a pytest marker): at least 50 parallel clients, 10,000
  requests, no errors; throughput and latency percentiles (p50/p95/p99) are printed and
  documented in DESIGN.md.
- At least 150 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes, the example application starts, README, DESIGN.md,
  PROGRESS.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
