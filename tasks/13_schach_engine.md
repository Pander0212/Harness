---
topic: game_engine
spec_docs: false
legacy_title: Schach-Engine mit Bitboards, Perft-Verifikation und UCI
---
# Chess Engine with Bitboards, Perft Verification and UCI

## Goal
Implement, in pure Python 3 (standard library only), a strong chess engine. Move
generation must be provably exact (perft), the search modern and as efficient as Python
allows. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Board representation** with 64-bit bitboards (Python int), piece lists, Zobrist
   hashing with incremental updates, reading/writing FEN.
2. **Move generation**: all rules including castling (with checks on traversed squares),
   en passant (including the pin case), promotion, check evasion, pinned pieces; sliding
   pieces via magic bitboards or Kogge-Stone; fully legal generation; make/unmake with an
   undo stack.
3. **Rules**: checkmate, stalemate, fifty-move rule, threefold repetition, insufficient
   material; SAN and UCI notation in both directions; reading and writing PGN.
4. **Evaluation**: material, piece-square tables with tapered eval (middlegame/endgame),
   pawn structure (doubled, isolated, passed pawns) with a pawn hash table, mobility, king
   safety, bishop pair; static exchange evaluation.
5. **Search**: iterative deepening, PVS/negamax with alpha-beta, aspiration windows,
   transposition table with a replacement strategy, quiescence search with SEE pruning,
   null-move pruning, late move reductions, killer moves, history heuristic, check
   extensions, mate distance pruning, time management.
6. **Opening book** from a small PGN collection; endgames: reliably find mate in KQK/KRK.
7. **UCI protocol** (`uci`, `isready`, `position`, `go` with wtime/btime/depth/movetime,
   `stop`, `info` output) so that the engine runs in GUIs.
8. **Self-play tournament** between engine versions with an Elo estimate.

## Test Strategy (pytest)
- **Perft** for the starting position up to depth 4 and for the well-known test positions
  ("Kiwipete", positions 3–6 from the Chess Programming Wiki) with the published node
  counts; perft divide as a debugging tool.
- Zobrist: incremental hash == freshly computed hash after 10,000 random moves.
- Tactics suite: at least 50 mate puzzles (mate in 1–3) and tactical positions must be
  solved.
- SAN/PGN round trips, rule edge cases (draw rules), UCI dialogs.
- At least 250 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; nodes per second and Elo measurements in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
