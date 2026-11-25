---
topic: devtools
mode: swarm
legacy_title: Build-System mit Remote-Cache und Paketmanager mit PubGrub-Resolver
---
# Build System with Remote Cache and Package Manager with a PubGrub Resolver

## Goal
Build, in pure Python 3 (standard library only), two cooperating developer tools: an
incremental, parallel build system (conceptually like Bazel/Ninja) and a package manager
with the PubGrub dependency resolver. Meant for **swarm mode**. Scope: at least 8 hours
of focused work.

## Functional Requirements – Build System
1. **Build description** in your own safe configuration language (parser, variables,
   functions, lists, glob patterns, includes) with rules, targets and dependencies.
2. **Dependency graph**: cycle detection with an understandable error message (the
   path), topological scheduling, selecting targets by pattern.
3. **Incrementality**: content hashes of inputs, command line and environment; action
   keys; a database of the last build; only outdated actions run; "early cutoff" when an
   output does not change.
4. **Parallel execution** with a worker pool, resource limits (CPU, memory tokens), abort
   on error or `--keep-going`, progress display, critical path.
5. **Cache**: local content-addressed cache and a **remote cache** over HTTP (your own
   small cache server using `http.server`), hash verification, eviction (LRU).
6. **Light sandboxing**: actions run in temporary directories with only their declared
   inputs; undeclared dependencies are detected.
7. **Tools**: `query` (dependencies, reverse dependencies), `graph` (DOT output),
   `clean`, `explain` (why was this rebuilt?).

## Functional Requirements – Package Manager
8. **Package format** (metadata, semantic versions with pre-releases, range syntax like
   `^1.2`, `~2.0`, `>=1,<3`), a local registry directory and an HTTP registry.
9. **PubGrub resolver**: incompatibilities, unit propagation, conflict resolution with
   learning, a **human-readable explanation** when unsolvable (derivation tree as in the
   PubGrub article), version preference (newest first, lockfile preference).
10. **Lockfile**, installation into a project directory, integrity checks (SHA-256),
    `add`/`remove`/`update`/`tree`/`why`.

## Test Strategy (pytest)
- Build: scenarios with projects of dozens of targets (e.g. code generation, "compiling"
  via Python scripts, archiving); after changing exactly one file, exactly the expected
  actions run; cache hits locally and remotely; parallel runs are deterministic.
- Resolver: all examples from the PubGrub documentation with expected solutions and error
  explanations; 500 randomly generated registries against a brute-force solver (fixed
  seed).
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; user manual in docs/, architecture in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
