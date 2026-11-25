---
topic: numerics
spec_docs: false
---
# Numerik-Bibliothek: Lineare Algebra, Eigenwerte, ODEs, FFT und Optimierung

## Ziel
Entwickle in reinem Python 3 (nur Standardbibliothek, insbesondere `math`, `cmath`,
`fractions`) eine numerische Bibliothek mit dichten und dünnbesetzten Matrizen,
Zerlegungen, Eigenwertverfahren, ODE-Lösern, FFT, Interpolation, Quadratur und
Optimierung – numerisch sorgfältig implementiert und gegen analytische Lösungen
geprüft. Umfang: mindestens 8 Stunden konzentrierter Arbeit.

## Funktionale Anforderungen
1. **Dichte Matrizen/Vektoren** mit Operatorüberladung, Broadcasting-Grundformen,
   Normen, Konditionszahl-Schätzung; exakte Variante mit `Fraction`.
2. **Zerlegungen**: LU mit Spaltenpivotisierung, Cholesky, LDLᵀ, QR (Householder und
   Givens), **SVD** (Golub-Kahan-Bidiagonalisierung + implizites QR), Lösen linearer
   Systeme, Determinante, Inverse, Pseudoinverse, Least Squares.
3. **Eigenwerte**: Potenzmethode, inverse Iteration, Hessenberg-Reduktion,
   QR-Algorithmus mit Wilkinson-Shifts für allgemeine und symmetrische Matrizen
   (Jacobi-Verfahren als Alternative), komplexe Eigenwerte.
4. **Dünnbesetzte Matrizen**: COO, CSR, CSC mit Konvertierung; Matrix-Vektor-Produkt;
   iterative Löser CG, BiCGSTAB, GMRES(m) mit Jacobi- und ILU(0)-Vorkonditionierung.
5. **Nichtlineare Gleichungen**: Bisektion, Brent, Newton (auch mehrdimensional mit
   numerischer Jacobi-Matrix), Broyden.
6. **Interpolation und Approximation**: Lagrange/Newton, natürliche und eingespannte
   kubische Splines, Chebyshev-Approximation, Polynom-Fit.
7. **Quadratur**: adaptive Simpson, Gauß-Legendre (Knoten berechnet), Romberg,
   Gauß-Kronrod mit Fehlerschätzung, uneigentliche Integrale.
8. **ODEs**: Euler, RK4, adaptive Dormand-Prince (RK45) mit dichter Ausgabe,
   steife Löser (implizites Euler, BDF2, Rosenbrock), Ereigniserkennung.
9. **FFT**: Radix-2 Cooley-Tukey, Bluestein für beliebige Längen, reelle FFT,
   Faltung, inverse FFT, 2D-FFT.
10. **Optimierung**: Gradientenabstieg mit Liniensuche (Wolfe), BFGS und L-BFGS,
    Nelder-Mead, Simplex-Verfahren für lineare Programme (Zweiphasen, Bland-Regel).

## Teststrategie (pytest)
- Jede Zerlegung: Rekonstruktionsfehler ‖A − Produkt‖ unter Toleranz für 200 zufällige
  Matrizen (fester Seed), inklusive schlecht konditionierter (Hilbert-Matrizen) mit
  dokumentierten Toleranzen.
- Eigenwerte gegen bekannte Matrizen (Begleitmatrizen von Polynomen, symmetrische
  Tridiagonalmatrizen mit geschlossenen Lösungen).
- ODE-Löser gegen analytische Lösungen; gemessene Konvergenzordnung entspricht der
  Theorie (Log-Log-Steigung).
- FFT gegen naive DFT; Parseval; Quadratur gegen bekannte Integrale.
- Optimierung: Rosenbrock, quadratische Formen, LP-Beispiele mit bekannten Optima.
- Mindestens 300 Testfälle.

## Abnahmekriterien
- `python3 -m pytest -q` grün; Genauigkeits- und Laufzeitmessungen in DESIGN.md.

Arbeite test-driven: zuerst Tests, nach jedem Feature alle Tests ausführen, DESIGN.md und
PROGRESS.md laufend pflegen. Höre erst auf, wenn alles fertig ist und alle Tests grün sind.
