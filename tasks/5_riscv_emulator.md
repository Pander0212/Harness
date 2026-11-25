---
legacy_title: RISC-V-Emulator (RV32IM) mit Assembler und Debugger
---
# RISC-V Emulator (RV32IM) with Assembler and Debugger

## Goal
Implement, in pure Python 3 (standard library only), a complete **RV32IM** emulator
including assembler, disassembler, ELF loader and interactive debugger. Correctness is
demonstrated with extensive instruction test cases.

## Functional Requirements
1. **CPU core**: 32 registers (x0 hard-wired to 0), PC, all RV32I base instructions
   (LUI, AUIPC, JAL, JALR, branches, loads/stores for byte/halfword/word with sign
   extension, ALU immediate and register operations, FENCE as a no-op, ECALL, EBREAK) and
   the M extension (MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU) with exactly specified
   behavior on division by zero and overflow.
2. **Decoder** for all formats (R, I, S, B, U, J) with correct immediate reconstruction;
   illegal instructions raise an exception.
3. **Memory**: little-endian, sparsely allocated per page, memory regions with
   permissions (r/w/x), faulting accesses as exceptions; memory-mapped UART (output to
   stdout) and a timer.
4. **Privilege/CSRs (basic)**: machine-mode CSRs `mstatus`, `mtvec`, `mepc`, `mcause`,
   `mtval`, `cycle`, `instret`, CSR instructions (Zicsr), trap handling with `MRET`.
5. **Syscalls** via ECALL (Linux-like convention: `write`, `exit`, `read`, `brk`) so that
   small programs run.
6. **Assembler**: two-pass assembler for RV32IM syntax with labels, directives (`.text`,
   `.data`, `.word`, `.half`, `.byte`, `.ascii`, `.asciz`, `.align`, `.globl`, `.equ`),
   pseudo-instructions (`li` with large constants, `la`, `mv`, `nop`, `j`, `ret`,
   `call`, `beqz`, `bnez`, `neg`, `not`, `seqz`), `%hi`/`%lo`; meaningful error messages
   with line numbers. Output as raw binary and as ELF32.
7. **Disassembler** whose output can be assembled again (round trip).
8. **ELF loader** for statically linked ELF32 RISC-V programs (load program headers, set
   entry point, prepare the stack with argc/argv).
9. **Debugger** (`python -m rvemu debug program`): single step, breakpoints on addresses
   and labels, watchpoints on memory, show and modify registers/memory, disassembly
   around the PC, reverse step via an execution journal, execution trace to a file.
10. **Example programs** in assembly: Fibonacci, bubble sort, prime sieve, recursive
    factorial, string reversal via UART, matrix multiplication with MUL.

## Architecture Guidelines
Package `rvemu/` with modules `decoder.py`, `cpu.py`, `memory.py`, `csr.py`,
`assembler.py`, `disassembler.py`, `elf.py`, `debugger.py`, `devices.py`, `cli.py`.
Performance: target at least 300,000 instructions/s (e.g. via pre-decoded instruction
caches); measure and document in DESIGN.md.

## Test Strategy (pytest)
- Several tests for **every** instruction including edge cases (sign, overflow, x0 as
  destination, alignment) – at least 250 parametrized cases.
- Encode/decode round trip over random valid instructions (fixed seed, 2000 cases).
- Assembler tests: known encodings (with reference values from the specification),
  pseudo-instructions, error messages.
- Program tests: the example programs produce the expected outputs/register values.
- Debugger tests via a scriptable interface (breakpoints, watchpoints, reverse step).
- Trap tests (illegal instruction, faulting access, ECALL) with correct `mcause` values.

## Acceptance Criteria
- `python3 -m pytest -q` passes, README with examples, DESIGN.md, PROGRESS.md complete.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
