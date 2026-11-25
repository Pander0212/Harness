---
topic: numerics
spec_docs: false
legacy_title: "Numerik-Bibliothek: Lineare Algebra, Eigenwerte, ODEs, FFT und Optimierung"
---
# Numerics Library: Linear Algebra, Eigenvalues, ODEs, FFT and Optimization

## Goal
Build, in pure Python 3 (standard library only, in particular `math`, `cmath`,
`fractions`), a numerics library with dense and sparse matrices, decompositions,
eigenvalue methods, ODE solvers, FFT, interpolation, quadrature and optimization –
implemented with numerical care and checked against analytical solutions. Scope: at least
8 hours of focused work.

## Functional Requirements
1. **Dense matrices/vectors** with operator overloading, basic broadcasting, norms,
   condition number estimation; an exact variant with `Fraction`.
2. **Decompositions**: LU with partial pivoting, Cholesky, LDLᵀ, QR (Householder and
   Givens), **SVD** (Golub-Kahan bidiagonalization + implicit QR), solving linear
   systems, determinant, inverse, pseudoinverse, least squares.
3. **Eigenvalues**: power method, inverse iteration, Hessenberg reduction, QR algorithm
   with Wilkinson shifts for general and symmetric matrices (Jacobi method as an
   alternative), complex eigenvalues.
4. **Sparse matrices**: COO, CSR, CSC with conversions; matrix-vector product; iterative
   solvers CG, BiCGSTAB, GMRES(m) with Jacobi and ILU(0) preconditioning.
5. **Nonlinear equations**: bisection, Brent, Newton (also multi-dimensional with a
   numerical Jacobian), Broyden.
6. **Interpolation and approximation**: Lagrange/Newton, natural and clamped cubic
   splines, Chebyshev approximation, polynomial fitting.
7. **Quadrature**: adaptive Simpson, Gauss-Legendre (nodes computed), Romberg,
   Gauss-Kronrod with error estimate, improper integrals.
8. **ODEs**: Euler, RK4, adaptive Dormand-Prince (RK45) with dense output, stiff solvers
   (implicit Euler, BDF2, Rosenbrock), event detection.
9. **FFT**: radix-2 Cooley-Tukey, Bluestein for arbitrary lengths, real FFT,
   convolution, inverse FFT, 2D FFT.
10. **Optimization**: gradient descent with line search (Wolfe), BFGS and L-BFGS,
    Nelder-Mead, simplex method for linear programs (two-phase, Bland's rule).

## Test Strategy (pytest)
- Every decomposition: reconstruction error ‖A − product‖ below tolerance for 200 random
  matrices (fixed seed), including ill-conditioned ones (Hilbert matrices) with documented
  tolerances.
- Eigenvalues against known matrices (companion matrices of polynomials, symmetric
  tridiagonal matrices with closed-form solutions).
- ODE solvers against analytical solutions; the measured order of convergence matches
  theory (log-log slope).
- FFT against a naive DFT; Parseval; quadrature against known integrals.
- Optimization: Rosenbrock, quadratic forms, LP examples with known optima.
- At least 300 test cases.

## Acceptance Criteria
- `python3 -m pytest -q` passes; accuracy and run-time measurements in DESIGN.md.

Work test-driven: tests first, run all tests after every feature, keep DESIGN.md and
PROGRESS.md up to date. Do not stop until everything is finished and all tests pass.
