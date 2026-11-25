---
legacy_title: Git-Klon "pygit" in Python
---
# Git Clone "pygit" in Python

## Goal
Implement, in pure Python 3 (standard library only: `zlib`, `hashlib`, `os`, `struct`
etc.), a version control system **pygit** whose repository format is compatible with real
Git: a repository created with pygit must be readable by `git` and vice versa (if `git`
is installed this is checked in tests, otherwise those tests are skipped).

## Functional Requirements
1. **Object database**: blob, tree, commit, tag as zlib-compressed loose objects under
   `.git/objects`, SHA-1 addressing, reading packfiles (`.pack` + `.idx` v2, including
   OFS_DELTA and REF_DELTA) – writing packfiles is an optional bonus.
2. **Index (staging area)**: read and write the binary Git index format version 2
   (entries with stat data, mode, SHA, flags, checksum).
3. **Commands** (CLI `python -m pygit <command>`):
   `init`, `hash-object [-w]`, `cat-file -p/-t/-s`, `add <paths>`, `rm`, `status`
   (staged / unstaged / untracked, categorized like Git), `commit -m`, `log`
   (including `--oneline`, `--graph` for merges), `branch` (create, list, delete),
   `checkout <branch|commit>` (including protection against overwriting local changes),
   `switch -c`, `tag` (lightweight and annotated), `diff` (working tree vs. index, index
   vs. HEAD, two commits), `merge <branch>`, `reset [--soft|--mixed|--hard]`, `show`,
   `ls-files`, `ls-tree`, `rev-parse` (including `HEAD~2`, `main^`, abbreviated SHAs).
4. **Refs**: symbolic and detached `HEAD`, `refs/heads`, `refs/tags`, reading
   `packed-refs`, writing a reflog for HEAD.
5. **.gitignore** with patterns (`*`, `**`, `!` negation, directory patterns).
6. **Diff algorithm**: your own implementation of the **Myers algorithm** (O(ND)) with
   output in unified format (hunks with context lines, `@@` headers), detection of binary
   files.
7. **Merge**: finding the merge base (common ancestor, correct even with several
   candidates), fast-forward, real three-way merge at file level and line level (diff3
   principle) with **conflict detection**: conflict markers `<<<<<<<`, `=======`,
   `>>>>>>>` like Git, conflict state in the index (stages 1–3), `merge --abort`,
   finishing with `commit` creates a merge commit with two parents. Also handle
   delete-vs-modify conflicts.

## Architecture Guidelines
Package `pygit/` with modules like `objects.py`, `repo.py`, `index.py`, `refs.py`,
`diff.py` (Myers), `merge.py`, `ignore.py`, `pack.py`, `cli.py`. Document format details
and algorithms in DESIGN.md.

## Test Strategy (pytest)
- Object hashes must match the known values from Git (e.g. empty blob `e69de29...`,
  empty tree `4b825dc...`).
- Myers diff: property test – applying the generated diff to the old version yields the
  new version (500 random cases, fixed seed); check minimal edit distance against a DP
  reference implementation.
- Scenario tests in temporary directories: create branches, divergent changes,
  fast-forward, conflict-free merge, merge with conflicts, resolve and commit.
- Interoperability (only if `git` is available): `git fsck`, `git log`, `git status` on
  pygit repositories; pygit reads repositories created by `git`, including packfiles
  (`git gc`).
- At least 150 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; README with a command overview, DESIGN.md, PROGRESS.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
