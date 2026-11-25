---
topic: os_sim
mode: swarm
legacy_title: "Betriebssystem-Simulator: Prozesse, virtueller Speicher, Journaling-Dateisystem, Shell"
---
# Operating System Simulator: Processes, Virtual Memory, Journaling File System, Shell

## Goal
Build, in pure Python 3 (standard library only), a textbook-style yet complete operating
system simulator. It runs programs written in its own small machine language and provides
process management, scheduling, virtual memory, a journaling file system on a simulated
block device and a shell. This task is meant for **swarm mode**: modules with clear
interfaces that can be developed in parallel. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Machine**: a simple register CPU with its own instruction set and assembler,
   interrupts (timer, I/O, system calls, page faults), kernel/user mode.
2. **Processes and threads**: PCB, fork/exec/wait/exit, zombies and orphans, signals
   (SIGKILL, SIGTERM, SIGCHLD, handlers), threads with their own stacks.
3. **Scheduler** as interchangeable strategies: FCFS, round robin, priorities with aging,
   multilevel feedback queue, CFS-like (vruntime with a red-black tree), multi-core
   simulation with load balancing; metrics (turnaround, waiting and response time).
4. **Synchronization**: mutex, semaphore, condition variables, deadlock detection
   (wait-for graph) and the banker's algorithm.
5. **Virtual memory**: two-level page tables, TLB with statistics, demand paging,
   copy-on-write on fork, page replacement (FIFO, LRU, Clock, second chance, working
   set), swap space, memory-mapped files (mmap); heap allocator with a buddy system and a
   slab allocator.
6. **Block device and file system**: superblock, inodes (direct, single and double
   indirect blocks), bitmaps, directories, hard and symbolic links, permissions (rwx,
   owner), **journaling** (write-ahead, transactions, replay after a crash), buffer cache,
   `fsck`.
7. **System calls and VFS**: open/read/write/lseek/close/dup2/pipe/stat/mkdir/unlink,
   file descriptor tables, blocking pipes, device files (/dev/null, console).
8. **Shell**: pipes, redirections, background jobs, job control, environment variables,
   built-in commands (cd, ls, cat, echo, ps, kill, jobs), scripts.
9. **Userland programs** in the machine language: `cat`, `wc`, `grep` (simple), `sort`,
   a producer-consumer example.

## Test Strategy (pytest)
- Comprehensive unit tests per module; scheduler metrics against hand-computed textbook
  examples.
- Page replacement: page fault counts for reference strings against known results
  (including Belady's anomaly with FIFO).
- File system: model-based tests with 10,000 random operations against an in-memory
  model; crash at random points + journal replay + fsck = consistent.
- Integration tests: shell scripts with pipes and background jobs produce the expected
  output.
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; architecture and interfaces in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
