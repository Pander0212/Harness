# RISC-V-Emulator (RV32IM) mit Assembler und Debugger

## Ziel
Implementiere in reinem Python 3 (nur Standardbibliothek) einen vollständigen
**RV32IM**-Emulator samt Assembler, Disassembler, ELF-Loader und interaktivem Debugger.
Die Korrektheit wird mit umfangreichen Instruktions-Testfällen belegt.

## Funktionale Anforderungen
1. **CPU-Kern**: 32 Register (x0 fest 0), PC, alle RV32I-Basisinstruktionen (LUI,
   AUIPC, JAL, JALR, Branches, Loads/Stores in Byte/Halbwort/Wort mit Vorzeichen-
   erweiterung, ALU-Immediate- und Register-Operationen, FENCE als No-op, ECALL,
   EBREAK) sowie die M-Erweiterung (MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU) mit
   exakt spezifiziertem Verhalten bei Division durch 0 und Überlauf.
2. **Dekodierer** für alle Formate (R, I, S, B, U, J) mit korrekter Immediate-
   Rekonstruktion; illegale Instruktionen lösen eine Ausnahme aus.
3. **Speicher**: Little-Endian, seitenweise dünn belegt, Speicherbereiche mit Rechten
   (r/w/x), Fehlzugriffe als Ausnahmen; Memory-mapped UART (Ausgabe auf stdout) und
   ein Timer.
4. **Privilegien/CSRs (Basis)**: Machine-Mode-CSRs `mstatus`, `mtvec`, `mepc`, `mcause`,
   `mtval`, `cycle`, `instret`, CSR-Instruktionen (Zicsr), Trap-Handling mit `MRET`.
5. **Syscalls** über ECALL (Linux-ähnliche Konvention: `write`, `exit`, `read`,
   `brk`), damit kleine Programme laufen.
6. **Assembler**: Zwei-Pass-Assembler für RV32IM-Syntax mit Labels, Direktiven (`.text`,
   `.data`, `.word`, `.half`, `.byte`, `.ascii`, `.asciz`, `.align`, `.globl`,
   `.equ`), Pseudo-Instruktionen (`li` mit großen Konstanten, `la`, `mv`, `nop`, `j`,
   `ret`, `call`, `beqz`, `bnez`, `neg`, `not`, `seqz`), `%hi`/`%lo`; aussagekräftige
   Fehlermeldungen mit Zeilennummer. Ausgabe als Rohbinär und als ELF32.
7. **Disassembler**, dessen Ausgabe wieder assembliert werden kann (Round-Trip).
8. **ELF-Loader** für statisch gelinkte ELF32-RISC-V-Programme (Program Header laden,
   Entry Point setzen, Stack mit argc/argv vorbereiten).
9. **Debugger** (`python -m rvemu debug programm`): Einzelschritt, Breakpoints auf
   Adressen und Labels, Watchpoints auf Speicher, Register/Speicher anzeigen und ändern,
   Disassemblierung um den PC, Rückwärts-Schritt (Reverse-Step) über ein
   Ausführungsjournal, Ausführungs-Trace in Datei.
10. **Beispielprogramme** in Assembler: Fibonacci, Bubblesort, Primzahlsieb, rekursive
    Fakultät, String-Umkehrung über UART, Matrixmultiplikation mit MUL.

## Architekturvorgaben
Paket `rvemu/` mit Modulen `decoder.py`, `cpu.py`, `memory.py`, `csr.py`, `assembler.py`,
`disassembler.py`, `elf.py`, `debugger.py`, `devices.py`, `cli.py`. Performance: Ziel
mindestens 300.000 Instruktionen/s (z. B. durch vorab dekodierte Instruktions-Caches);
messen und in DESIGN.md dokumentieren.

## Teststrategie (pytest)
- Für **jede** Instruktion mehrere Tests inklusive Randfälle (Vorzeichen,
  Überlauf, x0 als Ziel, Ausrichtung) – mindestens 250 parametrisierte Fälle.
- Encode/Decode-Round-Trip über zufällige gültige Instruktionen (fester Seed, 2000 Fälle).
- Assembler-Tests: bekannte Kodierungen (mit Referenzwerten aus der Spezifikation),
  Pseudo-Instruktionen, Fehlermeldungen.
- Programm-Tests: die Beispielprogramme liefern die erwarteten Ausgaben/Registerwerte.
- Debugger-Tests über eine skriptbare Schnittstelle (Breakpoints, Watchpoints,
  Reverse-Step).
- Trap-Tests (illegale Instruktion, Fehlzugriff, ECALL) mit korrekten `mcause`-Werten.

## Abnahmekriterien
- `python3 -m pytest -q` grün, README mit Beispielen, DESIGN.md, PROGRESS.md vollständig.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
