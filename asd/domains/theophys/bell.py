"""Bell-Ungleichungen in Korrelator-Form B = Σ_xy c_xy E(x, y).

klassisch(): Maximum über alle deterministischen Strategien a_x, b_y ∈ {±1} (exakte Aufzählung) und eine optimale Strategie.
quantenwert(): Wert für das Singulett mit Messrichtungen in einer Ebene, E(x, y) = −cos(α_x − β_y), exakt symbolisch."""
from fractions import Fraction
from itertools import product

import sympy as sp

from .ausdruck import rational, parse, FormelFehler

MAX_EINSTELLUNGEN = 6


def koeffizienten(c):
    if not isinstance(c, list) or not c or len(c) > MAX_EINSTELLUNGEN or any(not isinstance(r, list) or len(r) != len(c[0]) or len(r) > MAX_EINSTELLUNGEN for r in c):
        raise FormelFehler(f"koeffizienten: rechteckige Matrix bis {MAX_EINSTELLUNGEN} x {MAX_EINSTELLUNGEN}")
    return [[rational(v) for v in r] for r in c]


def klassisch(c):
    C = koeffizienten(c); m, n = len(C), len(C[0]); best, arg = None, None
    for a in product((1, -1), repeat=m):
        for b in product((1, -1), repeat=n):
            v = sum(C[x][y] * a[x] * b[y] for x in range(m) for y in range(n))
            if best is None or v > best: best, arg = v, (a, b)
    return best, {"a": list(arg[0]), "b": list(arg[1])}


def quantenwert(c, winkel_a, winkel_b):
    C = koeffizienten(c)
    if len(winkel_a) != len(C) or len(winkel_b) != len(C[0]): raise FormelFehler("Zahl der Winkel passt nicht zu den Koeffizienten")
    A = [parse(w) for w in winkel_a]; B = [parse(w) for w in winkel_b]
    if any(x.free_symbols for x in A + B): raise FormelFehler("Winkel müssen Zahlen sein (z. B. pi/4)")
    return sp.nsimplify(sp.simplify(sum(sp.Rational(C[x][y].numerator, C[x][y].denominator) * (-sp.cos(A[x] - B[y])) for x in range(len(A)) for y in range(len(B)))))
