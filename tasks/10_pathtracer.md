---
topic: image
spec_docs: false
legacy_title: Physikalisch basierter Pathtracer mit Szenenbeschreibungssprache
---
# Physically Based Path Tracer with a Scene Description Language

## Goal
Build, in pure Python 3 (standard library only; image output as PNG via a self-written
encoder using `zlib`), a physically based renderer. Because of the computational cost,
efficient programming (acceleration structures, parallelism via `multiprocessing`) is
explicitly part of the task. Scope: at least 8 hours of focused work.

## Functional Requirements
1. **Math**: vectors, 4×4 matrices, quaternions, transformations, orthonormal bases,
   numerically robust intersection computations.
2. **Geometry**: spheres, planes, triangles (Möller-Trumbore), triangle meshes from OBJ
   files (including normals and texture coordinates), instances with transformations,
   boxes, cylinders.
3. **Acceleration**: BVH with the surface area heuristic, binned construction, flattened
   traversal; statistics on tested nodes.
4. **Camera**: pinhole and thin lens (depth of field), motion blur.
5. **Materials**: Lambert, mirror, dielectric with Fresnel (glass), rough metals with GGX
   microfacets, emission; textures (checkerboard, image from PPM/PNG, Perlin noise).
6. **Integrator**: path tracing with Russian roulette, **next event estimation** with
   area lights, **multiple importance sampling**, environment light.
7. **Sampling**: stratified and low-discrepancy (Halton/Sobol), reconstruction filters.
8. **Output**: your own PNG encoder (chunks, CRC, per-row filters with a heuristic), tone
   mapping (Reinhard, ACES), gamma; PPM output; progress display.
9. **Scene language**: your own text format with a parser (cameras, materials, objects,
   lights, includes, variables) and error messages with line numbers.
10. **Parallelization** in tiles with `multiprocessing`, deterministic per seed.
11. **Example scenes**: Cornell box, glass spheres with caustics, a depth-of-field scene,
    a mesh scene with at least 10,000 triangles.

## Test Strategy (pytest)
- Analytical tests for intersections (including edge cases: grazing rays, hits on
  edges), transformations and BVH (results identical to brute force for 1000 random
  rays).
- Energy conservation: white furnace test (a diffuse sphere in a uniform environment
  must yield the environment color, within statistical tolerance).
- Convergence tests: the mean of a pixel converges to a reference with increasing sample
  count; MIS measurably reduces variance compared with pure BSDF sampling.
- PNG encoder: files are read back with your own decoder; scene parser with valid and
  invalid inputs.
- At least 200 test cases; rendered example images under `renders/`.

## Acceptance Criteria
- `python3 -m pytest -q` passes; render times and images documented in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
