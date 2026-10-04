"""Allgemeine Relativitätstheorie, symbolisch exakt (SymPy). Konventionen (fest, im Paper als C-modell):
Γ^a_bc = ½ g^ad (∂_b g_dc + ∂_c g_db − ∂_d g_bc);  R^a_bcd = ∂_c Γ^a_db − ∂_d Γ^a_cb + Γ^a_ce Γ^e_db − Γ^a_de Γ^e_cb;
R_bd = R^a_bad;  R = g^bd R_bd;  G_ab = R_ab − ½ R g_ab;  K = R_abcd R^abcd;  Einheiten G = c = 1."""
import sympy as sp

from .ausdruck import parse, symbole, FormelFehler

DIM_MAX = 4


def metrik(spec):
    """spec: {"koordinaten": [..], "metrik": n x n Formeln | "diag": [n Formeln], "annahmen": {name: positiv|reell|...}}
    -> (koordinaten-Symbole, Matrix g)."""
    ko = spec.get("koordinaten")
    if not isinstance(ko, list) or not 2 <= len(ko) <= DIM_MAX or len(set(ko)) != len(ko): raise FormelFehler(f"koordinaten: 2..{DIM_MAX} verschiedene Namen")
    ann = dict(spec.get("annahmen") or {})
    n = len(ko)
    if "diag" in spec:
        d = spec["diag"]
        if not isinstance(d, list) or len(d) != n: raise FormelFehler("diag braucht so viele Einträge wie Koordinaten")
        g = sp.diag(*[parse(x, ann) for x in d])
    else:
        m = spec.get("metrik")
        if not isinstance(m, list) or len(m) != n or any(not isinstance(r, list) or len(r) != n for r in m): raise FormelFehler("metrik muss n x n sein")
        g = sp.Matrix([[parse(x, ann) for x in r] for r in m])
    if any(sp.simplify(g[i, j] - g[j, i]) != 0 for i in range(n) for j in range(n)): raise FormelFehler("Metrik nicht symmetrisch")
    X = [symbole([k], ann)[k] for k in ko]
    # Symbole der Metrik mit denselben Annahmen wie die Koordinaten vereinheitlichen
    rep = {s: x for s in g.free_symbols for x in X if str(s) == str(x) and s != x}
    g = g.xreplace(rep)
    det = sp.simplify(g.det())
    if det == 0: raise FormelFehler("Metrik entartet (det g = 0)")
    return X, g


def kruemmung(X, g, vereinfache=sp.simplify):
    n = len(X); gi = sp.simplify(g.inv())
    Gam = [[[vereinfache(sum(gi[a, d] * (sp.diff(g[d, c], X[b]) + sp.diff(g[d, b], X[c]) - sp.diff(g[b, c], X[d])) for d in range(n)) / 2)
             for c in range(n)] for b in range(n)] for a in range(n)]
    Riem = [[[[vereinfache(sp.diff(Gam[a][d][b], X[c]) - sp.diff(Gam[a][c][b], X[d]) + sum(Gam[a][c][e] * Gam[e][d][b] - Gam[a][d][e] * Gam[e][c][b] for e in range(n)))
               for d in range(n)] for c in range(n)] for b in range(n)] for a in range(n)]
    Ric = sp.Matrix(n, n, lambda b, d: vereinfache(sum(Riem[a][b][a][d] for a in range(n))))
    R = vereinfache(sum(gi[b, d] * Ric[b, d] for b in range(n) for d in range(n)))
    G = sp.Matrix(n, n, lambda a, b: vereinfache(Ric[a, b] - R * g[a, b] / 2))
    # Kretschmann: R_abcd R^abcd  mit R_abcd = g_ae R^e_bcd
    Rl = [[[[sum(g[a, e] * Riem[e][b][c][d] for e in range(n)) for d in range(n)] for c in range(n)] for b in range(n)] for a in range(n)]
    Ru = [[[[sum(gi[b, f] * gi[c, h] * gi[d, k] * Riem[a][f][h][k] for f in range(n) for h in range(n) for k in range(n))
             for d in range(n)] for c in range(n)] for b in range(n)] for a in range(n)]
    K = vereinfache(sum(Rl[a][b][c][d] * Ru[a][b][c][d] for a in range(n) for b in range(n) for c in range(n) for d in range(n)))
    return {"Gamma": Gam, "Riemann": Riem, "Ricci": Ric, "R": R, "Einstein": G, "Kretschmann": K, "ginv": gi}


def kompakt(k, X):
    n = len(X)
    nz = lambda M: {f"{i}{j}": str(M[i, j]) for i in range(n) for j in range(n) if M[i, j] != 0}
    return {"ricci_skalar": str(k["R"]), "kretschmann": str(k["Kretschmann"]), "ricci_nicht_null": nz(k["Ricci"]), "einstein_nicht_null": nz(k["Einstein"])}
