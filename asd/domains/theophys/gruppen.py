"""Gruppentheorie und Eichtheorie, exakt rational.

SU(N)-Darstellungen über Dynkin-Labels a_1..a_{N-1} (oder Namen 1, F, Fbar, adj, S2, A2, S2bar, A2bar):
  dim (Weyl-Formel), C2 = ½ (λ, λ+2ρ) mit Normierung T(F) = ½ (also C2(F) = (N²−1)/(2N), C2(adj) = N), Index T(R) = dim C2 / (N²−1),
  kubischer Anomaliekoeffizient A(R) (A(F) = 1) für die benannten Darstellungen.
Betafunktion (μ dg/dμ = −b0 g³/(16π²) − b1 g⁵/(16π²)²; Machacek–Vaughn ohne Yukawa- und Quartic-Kopplungen):
  b0 = 11/3 C_A − 4/3 Σ_Dirac T − 2/3 Σ_Weyl T − 1/3 Σ_komplex T − 1/6 Σ_reell T
  b1 = 34/3 C_A² − Σ_Dirac (20/3 C_A + 4 C2) T − ½ Σ_Weyl (...) − Σ_komplex (2/3 C_A + 4 C2) T − ½ Σ_reell (...)
Anomalien für linkshändige Weyl-Fermionen unter Π SU(N_a) × Π U(1)_x: SU_a³, SU_a²·U(1)_x, U(1)_x U(1)_y U(1)_z, Gravitation·U(1)_x,
Witten-SU(2) (Zahl der Dubletts gerade)."""
from fractions import Fraction
from itertools import combinations_with_replacement
from math import prod

from .ausdruck import rational, FormelFehler

N_MAX = 12


def _N(N):
    if isinstance(N, bool) or not isinstance(N, int) or not 2 <= N <= N_MAX: raise FormelFehler(f"N muss ganz in [2, {N_MAX}] sein")
    return N


def dynkin(N, rep):
    _N(N); r = N - 1
    if isinstance(rep, dict) and "dynkin" in rep: a = rep["dynkin"]
    elif isinstance(rep, list): a = rep
    else:
        z = [0] * r
        if rep in ("1", 1, "singulett"): a = z
        elif rep == "F": a = [1] + [0] * (r - 1)
        elif rep == "Fbar": a = [0] * (r - 1) + [1]
        elif rep == "adj": a = [1] + [0] * (r - 2) + [1] if r >= 2 else [2]
        elif rep == "S2": a = [2] + [0] * (r - 1)
        elif rep == "S2bar": a = [0] * (r - 1) + [2]
        elif rep == "A2": a = ([0, 1] + [0] * (r - 2)) if r >= 2 else [0]
        elif rep == "A2bar": a = ([0] * (r - 2) + [1, 0]) if r >= 2 else [0]
        else: raise FormelFehler(f"unbekannte Darstellung {rep!r} (1, F, Fbar, adj, S2, A2, S2bar, A2bar oder {{\"dynkin\": [...]}})")
    if not isinstance(a, list) or len(a) != r or any(isinstance(x, bool) or not isinstance(x, int) or x < 0 or x > 20 for x in a):
        raise FormelFehler(f"Dynkin-Labels: {r} ganze Zahlen in [0, 20]")
    return a


def dim(N, rep):
    a = dynkin(N, rep); num = 1; den = 1
    for i in range(1, N):
        for j in range(i + 1, N + 1):
            num *= sum(a[k - 1] + 1 for k in range(i, j)); den *= (j - i)
    return Fraction(num, den)


def casimir(N, rep):
    a = dynkin(N, rep); r = N - 1
    G = lambda i, j: Fraction(min(i, j) * (N - max(i, j)), N)        # inverse Cartan-Matrix von A_{N-1}
    return sum(a[i - 1] * G(i, j) * (a[j - 1] + 2) for i in range(1, r + 1) for j in range(1, r + 1)) / 2


def index(N, rep):
    return dim(N, rep) * casimir(N, rep) / (N * N - 1)


def anomalie_koeff(N, rep):
    a = dynkin(N, rep)
    namen = {tuple(dynkin(N, x)): x for x in ("1", "F", "Fbar", "adj", "S2", "S2bar", "A2", "A2bar")}
    n = namen.get(tuple(a))
    if n is None: raise FormelFehler("kubischer Anomaliekoeffizient nur für 1, F, Fbar, adj, S2, A2 (und Konjugierte)")
    if N == 2: return Fraction(0)
    return Fraction({"1": 0, "adj": 0, "F": 1, "Fbar": -1, "S2": N + 4, "S2bar": -(N + 4), "A2": N - 4, "A2bar": -(N - 4)}[n])


ART = {"dirac": (Fraction(4, 3), Fraction(1)), "weyl": (Fraction(2, 3), Fraction(1, 2)), "komplex": (Fraction(1, 3), Fraction(1)), "reell": (Fraction(1, 6), Fraction(1, 2))}


def beta(N, materie):
    """materie: [{"art": dirac|weyl|komplex|reell, "rep": ..., "anzahl": n}] -> (b0, b1)."""
    _N(N); CA = Fraction(N); b0 = Fraction(11, 3) * CA; b1 = Fraction(34, 3) * CA * CA
    if not isinstance(materie, list) or len(materie) > 32: raise FormelFehler("materie: Liste (höchstens 32 Einträge)")
    for m in materie:
        art = m.get("art")
        if art not in ART: raise FormelFehler(f"art muss eine von {sorted(ART)} sein")
        n = rational(m.get("anzahl", 1))
        if n < 0: raise FormelFehler("anzahl >= 0")
        T = index(N, m.get("rep", "F")); C = casimir(N, m.get("rep", "F")); k1, k2 = ART[art]
        b0 -= k1 * n * T
        b1 -= k2 * n * T * ((Fraction(20, 3) * CA + 4 * C) if art in ("dirac", "weyl") else (Fraction(2, 3) * CA + 4 * C))
    return b0, b1


def anomalien(gruppen, abelsch, felder):
    """gruppen: {"su3": 3, ...}; abelsch: ["Y", ...]; felder: [{"su3": rep, "su2": rep, "Y": q, "anzahl": n}] (linkshändige Weyl-Fermionen).
    -> {bedingung: Fraction}; alle müssen 0 sein (Witten: Rest modulo 2)."""
    if not isinstance(gruppen, dict) or not isinstance(abelsch, list) or not isinstance(felder, list) or not felder or len(felder) > 64:
        raise FormelFehler("gruppen (Objekt), abelsch (Liste), felder (1..64) erwartet")
    for g, N in gruppen.items(): _N(N)
    F = []
    for f in felder:
        n = rational(f.get("anzahl", 1)); reps = {g: f.get(g, "1") for g in gruppen}; q = {x: rational(f.get(x, 0)) for x in abelsch}
        dims = {g: dim(N, reps[g]) for g, N in gruppen.items()}
        F.append((n, reps, q, dims))
    out = {}
    for g, N in gruppen.items():
        andere = lambda d: prod((v for k, v in d.items() if k != g), start=Fraction(1))
        if N >= 3: out[f"{g}^3"] = sum(n * anomalie_koeff(N, reps[g]) * andere(d) for n, reps, q, d in F)
        for x in abelsch: out[f"{g}^2*{x}"] = sum(n * index(N, reps[g]) * andere(d) * q[x] for n, reps, q, d in F)
        if N == 2: out[f"witten_{g}"] = sum(n * andere(d) for n, reps, q, d in F if dynkin(2, reps[g]) == [1]) % 2
    for tri in combinations_with_replacement(abelsch, 3):
        out["*".join(tri)] = sum(n * prod(d.values(), start=Fraction(1)) * prod((q[x] for x in tri), start=Fraction(1)) for n, reps, q, d in F)
    for x in abelsch: out[f"grav*{x}"] = sum(n * prod(d.values(), start=Fraction(1)) * q[x] for n, reps, q, d in F)
    return out


def anomalie_terme(gruppen, abelsch, felder, bedingung):
    """Summanden einer Anomaliebedingung als Faktorlisten (für die Lean-Vorlage), alle rational."""
    terme = []
    for f in felder:
        n = rational(f.get("anzahl", 1)); reps = {g: f.get(g, "1") for g in gruppen}; q = {x: rational(f.get(x, 0)) for x in abelsch}
        d = {g: dim(N, reps[g]) for g, N in gruppen.items()}
        if bedingung.endswith("^3") and bedingung[:-2] in gruppen:
            g = bedingung[:-2]; terme.append([n, anomalie_koeff(gruppen[g], reps[g])] + [v for k, v in d.items() if k != g])
        elif "^2*" in bedingung:
            g, x = bedingung.split("^2*"); terme.append([n, index(gruppen[g], reps[g]), q[x]] + [v for k, v in d.items() if k != g])
        elif bedingung.startswith("grav*"):
            terme.append([n, q[bedingung[5:]]] + list(d.values()))
        else:
            terme.append([n] + list(d.values()) + [q[x] for x in bedingung.split("*")])
    return terme


STANDARDMODELL = [{"su3": "F", "su2": "F", "Y": "1/6", "anzahl": 1}, {"su3": "Fbar", "su2": "1", "Y": "-2/3", "anzahl": 1},
                  {"su3": "Fbar", "su2": "1", "Y": "1/3", "anzahl": 1}, {"su3": "1", "su2": "F", "Y": "-1/2", "anzahl": 1},
                  {"su3": "1", "su2": "1", "Y": "1", "anzahl": 1}]
