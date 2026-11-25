---
topic: game_engine
legacy_title: 2D-Physik-Engine mit Constraint-Solver und deterministischer Wiedergabe
---
# 2D Physics Engine with Constraint Solver and Deterministic Replay

## Goal
Build, in pure Python 3 (standard library only), a complete 2D rigid-body physics engine
comparable to Box2D (conceptually, no code copied), including collision detection, an
iterative constraint solver, joints and deterministic simulation. Visualization via SVG
output of individual frames. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Math**: vectors, 2×2 matrices, rotations, transforms, AABBs, numerically robust
   helper functions.
2. **Shapes**: circles, convex polygons (from point clouds via convex hull), capsules,
   edge chains for static terrain; mass, center of mass and moment of inertia from
   density.
3. **Broadphase**: dynamic AABB tree with rotations/balancing and fat AABBs;
   alternatively sweep and prune; pair management.
4. **Narrowphase**: SAT for polygons, GJK + EPA for general convex shapes, contact
   manifolds with clipping (up to 2 contact points), feature IDs for warm starting.
5. **Solver**: sequential impulses with warm starting, accumulation and clamping,
   friction (Coulomb), restitution with a threshold, position correction (Baumgarte or
   split impulses), sub-stepping.
6. **Joints**: revolute (with limits and motor), prismatic, distance (with spring), weld,
   mouse joint, rope.
7. **More features**: sleep/wake system with islands, continuous collision detection
   (time of impact) for fast objects, sensors/triggers, collision filtering
   (categories/masks), ray casts and AABB queries, event callbacks (begin/end contact).
8. **Determinism**: identical inputs yield bit-identical results; saving/loading the
   complete world state; replay file.
9. **Scenes and visualization**: pyramid with 20 levels, chain bridge, ragdoll, Newton's
   cradle, vehicle with suspension; export of frames as SVG and of an animation as SVG
   with SMIL.

## Test Strategy (pytest)
- Geometry and collision tests with analytically known results (circle-circle,
  polygon-polygon in many orientations; GJK distance against brute force).
- Physical invariants: momentum conservation in elastic collisions, energy decrease with
  friction, free fall against the analytical solution.
- Stability: a pyramid with 20 levels stays standing for 1000 steps and falls asleep.
- Joint constraints are satisfied within a tolerance.
- Determinism: two runs and a save/load run produce identical states.
- At least 220 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; performance measurements (bodies per step) in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
