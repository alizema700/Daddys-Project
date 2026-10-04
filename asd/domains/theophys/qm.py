"""Eindimensionale Quantenmechanik: H = −1/(2m) d²/dx² + V(x) auf [a, b] mit Dirichlet-Rand (ħ = 1).

Finite Differenzen 2. Ordnung (tridiagonal, scipy eigh_tridiagonal). Der Prüfer rechnet mit ZWEI eigenen Gittern (n und 2n) und
extrapoliert nach Richardson (Fehler O(h²)); Konvergenzkriterium und Toleranz liegen fest im Prüfer. Stufe: observed (numerisch)."""
import numpy as np
import sympy as sp

from .ausdruck import parse, rational, FormelFehler

N_PRUEFER = 4000; TOL_REL = 1e-6; KONV_REL = 1e-4


def _V(potential):
    e = parse(potential, {"x": "reell"}); x = sp.Symbol("x", real=True)
    if e.free_symbols - {x}: raise FormelFehler(f"Potential darf nur von x abhängen, enthält {sorted(map(str, e.free_symbols - {x}))}")
    return sp.lambdify(x, e, "numpy")


def eigenwerte(potential, masse=1, intervall=(-10, 10), n=2000, anzahl=6):
    a, b = (float(rational(intervall[0])), float(rational(intervall[1])))
    m = float(rational(masse))
    if not b > a or m <= 0: raise FormelFehler("intervall [a, b] mit a < b, masse > 0")
    n = int(n)
    if not 50 <= n <= 200000: raise FormelFehler("gitter in [50, 200000]")
    from scipy.linalg import eigh_tridiagonal
    x = np.linspace(a, b, n + 2)[1:-1]; h = (b - a) / (n + 1)
    V = np.asarray(_V(potential)(x), dtype=float) * np.ones_like(x)
    if not np.all(np.isfinite(V)): raise FormelFehler("Potential nicht endlich auf dem Gitter")
    d = 1.0 / (m * h * h) + V; e = -0.5 / (m * h * h) * np.ones(n - 1)
    k = max(1, min(int(anzahl), n))
    return [float(w) for w in eigh_tridiagonal(d, e, select="i", select_range=(0, k - 1), eigvals_only=True)]


def pruefer_wert(potential, masse, intervall, k):
    """Unabhängige Rechnung des Prüfers: Gitter N_PRUEFER und 2·N_PRUEFER, Richardson. -> (E_extrapoliert, |E2 − E1|)."""
    E1 = eigenwerte(potential, masse, intervall, N_PRUEFER, k + 1)[k]; E2 = eigenwerte(potential, masse, intervall, 2 * N_PRUEFER, k + 1)[k]
    return (4 * E2 - E1) / 3, abs(E2 - E1)
