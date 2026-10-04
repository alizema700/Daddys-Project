"""Quanten-Spinketten (Spin 1/2) mit exakter Arithmetik.

Operatoren sind Summen von Pauli-Strings mit gaußschen rationalen Koeffizienten: {("X","I","Z",...): (re, im)} (Fractions).
- Modelle (Konvention S = σ/2, ħ = 1):
    xxz       H = J Σ_<ij> (S^x S^x + S^y S^y + Δ S^z S^z)           (heisenberg: Δ = 1)
    xyz       H = Σ_<ij> (Jx S^x S^x + Jy S^y S^y + Jz S^z S^z)
    j1j2      H = J1 Σ_i S_i·S_{i+1} + J2 Σ_i S_i·S_{i+2}
    tfim      H = -J Σ_<ij> Z_i Z_j - h Σ_i X_i                        (Pauli-Konvention)
    terme     H = Σ_k c_k P_k, mit "translation": true über alle Verschiebungen summiert
  rand: "periodisch" (N >= 3) oder "offen".
- Exaktes Spektrum: Matrix im Rechenbasis-Sektor, mit Hauptnenner auf ganze Zahlen skaliert (komplexe Hermitesche Matrix über die
  reelle Einbettung [[A,-B],[B,A]], Vielfachheiten dann halbiert), charakteristisches Polynom (FLINT, exakt) und rigorose Isolation
  aller Wurzeln (acb). Ergebnis: disjunkte Einschließungen [lo, hi] mit Vielfachheit, aufsteigend.
- Sektor {"up": k}: Zustände mit k Spins nach oben; nur erlaubt, wenn [H, S^z_gesamt] = 0 exakt nachgewiesen ist."""
from fractions import Fraction
from itertools import combinations

from .ausdruck import rational, FormelFehler, arb_grenzen

N_MAX = 16                      # Experimente (numerisch)
DIM_EXAKT = 400                 # rigorose Spektren bis zu dieser (reellen) Matrixdimension
DIM_NUMERISCH = 1 << 14         # numerische Spektren bis zu dieser Dimension

_PROD = {("X", "Y"): (1, "Z"), ("Y", "Z"): (1, "X"), ("Z", "X"): (1, "Y"), ("Y", "X"): (3, "Z"), ("Z", "Y"): (3, "X"), ("X", "Z"): (3, "Y")}
_IPOW = [(1, 0), (0, 1), (-1, 0), (0, -1)]


def _cmul(a, b):
    return (a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0])


def _pauli_mal(p, q):
    """Produkt zweier Pauli-Strings -> (Phase als i^k, String)."""
    k = 0; out = []
    for a, b in zip(p, q):
        if a == "I": out.append(b)
        elif b == "I": out.append(a)
        elif a == b: out.append("I")
        else: kk, c = _PROD[(a, b)]; k += kk; out.append(c)
    return k % 4, tuple(out)


def add(A, B, f=(Fraction(1), Fraction(0))):
    C = dict(A)
    for p, c in B.items():
        v = _cmul(c, f); w = C.get(p, (Fraction(0), Fraction(0))); w = (w[0] + v[0], w[1] + v[1])
        if w[0] == 0 and w[1] == 0: C.pop(p, None)
        else: C[p] = w
    return C


def mal(A, B):
    C = {}
    for p, a in A.items():
        for q, b in B.items():
            k, r = _pauli_mal(p, q); v = _cmul(_cmul(a, b), _IPOW[k]); w = C.get(r, (Fraction(0), Fraction(0)))
            w = (w[0] + v[0], w[1] + v[1])
            if w[0] == 0 and w[1] == 0: C.pop(r, None)
            else: C[r] = w
    return C


def kommutator(A, B):
    return add(mal(A, B), mal(B, A), (Fraction(-1), Fraction(0)))


def _koef(c):
    if isinstance(c, (list, tuple)) and len(c) == 2: return (rational(c[0]), rational(c[1]))
    return (rational(c), Fraction(0))


def _string(N, orte_paulis):
    s = ["I"] * N
    for i, a in orte_paulis:
        if s[i] != "I": raise FormelFehler("zwei Pauli-Operatoren am selben Ort")
        s[i] = a
    return tuple(s)


def _bindungen(N, r, rand):
    if rand == "periodisch":
        if N < 2 * r + 1: raise FormelFehler(f"periodisch braucht N >= {2 * r + 1} für Reichweite {r}")
        return [(i, (i + r) % N) for i in range(N)]
    if rand == "offen": return [(i, i + r) for i in range(N - r)]
    raise FormelFehler("rand muss 'periodisch' oder 'offen' sein")


def _pruefe_N(N, nmax=N_MAX):
    if isinstance(N, bool) or not isinstance(N, int) or not 2 <= N <= nmax: raise FormelFehler(f"N muss eine ganze Zahl in [2, {nmax}] sein")
    return N


def operator(spec, N, rand="periodisch"):
    """Operator-Spezifikation -> Pauli-Summe. spec: Modell-Dict, "Sz_gesamt" | "Sx_gesamt" | "Sy_gesamt" | "S2_gesamt" | "paritaet",
    oder {"terme": [{"c": q | [re, im], "p": "XZ", "start": 0}], "translation": bool}."""
    _pruefe_N(N)
    eins = (Fraction(1), Fraction(0)); halb = (Fraction(1, 2), Fraction(0))
    if isinstance(spec, str):
        if spec in ("Sz_gesamt", "Sx_gesamt", "Sy_gesamt"):
            a = spec[1].upper(); return {_string(N, [(i, a)]): halb for i in range(N)}
        if spec == "S2_gesamt":
            S = {}
            for a in "XYZ":
                Sa = {_string(N, [(i, a)]): halb for i in range(N)}; S = add(S, mal(Sa, Sa))
            return S
        if spec == "paritaet": return {tuple("X" * N): eins}
        raise FormelFehler(f"unbekannter Operator {spec!r}")
    if not isinstance(spec, dict): raise FormelFehler("Operator muss String oder Objekt sein")
    name = spec.get("name") or ("terme" if "terme" in spec else None)
    H = {}
    def bind(r, paare, kopplung):
        nonlocal H
        if kopplung == 0: return
        for i, j in _bindungen(N, r, rand):
            for a, b, f in paare: H = add(H, {_string(N, [(i, a), (j, b)]): (kopplung * f, Fraction(0))})
    q = Fraction(1, 4)
    if name in ("xxz", "heisenberg"):
        J = rational(spec.get("J", 1)); D = Fraction(1) if name == "heisenberg" else rational(spec.get("Delta", 1))
        bind(1, [("X", "X", q), ("Y", "Y", q), ("Z", "Z", q * D)], J)
    elif name == "xyz":
        bind(1, [("X", "X", q * rational(spec.get("Jx", 1))), ("Y", "Y", q * rational(spec.get("Jy", 1))), ("Z", "Z", q * rational(spec.get("Jz", 1)))], Fraction(1))
    elif name == "j1j2":
        bind(1, [("X", "X", q), ("Y", "Y", q), ("Z", "Z", q)], rational(spec.get("J1", 1)))
        bind(2, [("X", "X", q), ("Y", "Y", q), ("Z", "Z", q)], rational(spec.get("J2", 0)))
    elif name == "tfim":
        J = rational(spec.get("J", 1)); h = rational(spec.get("h", 0))
        bind(1, [("Z", "Z", Fraction(-1))], J)
        for i in range(N):
            if h: H = add(H, {_string(N, [(i, "X")]): (-h, Fraction(0))})
    elif name == "terme":
        T = spec.get("terme")
        if not isinstance(T, list) or not T or len(T) > 64: raise FormelFehler("terme: Liste mit 1..64 Einträgen")
        for t in T:
            p = str(t.get("p", "")).upper(); c = _koef(t.get("c", 1)); st = int(t.get("start", 0))
            if not p or set(p) - set("IXYZ") or len(p) > N: raise FormelFehler(f"ungültiger Pauli-String {p!r}")
            starts = range(N) if spec.get("translation") else [st]
            for s0 in starts:
                orte = [(s0 + k) for k in range(len(p))]
                if rand == "offen" and orte[-1] >= N: continue
                H = add(H, {_string(N, [(o % N, a) for o, a in zip(orte, p) if a != "I"]): c})
    else:
        raise FormelFehler(f"unbekanntes Modell {name!r} (xxz, heisenberg, xyz, j1j2, tfim, terme)")
    return H


def ist_hermitesch(H):
    """Pauli-Strings sind hermitesch; die Summe ist es genau dann, wenn alle Koeffizienten reell sind."""
    return all(c[1] == 0 for c in H.values())


def _anwenden(p, s, N):
    """Pauli-String auf Basiszustand s (Bit i = 1: Spin unten). -> (Phase i^k, s')."""
    k = 0
    for i, a in enumerate(p):
        b = (s >> i) & 1
        if a == "X": s ^= (1 << i)
        elif a == "Y": k += 1 if b == 0 else 3; s ^= (1 << i)
        elif a == "Z": k += 0 if b == 0 else 2
    return k % 4, s


def basis(N, sektor=None):
    if sektor is None: return list(range(1 << N))
    up = sektor.get("up") if isinstance(sektor, dict) else None
    if isinstance(up, bool) or not isinstance(up, int) or not 0 <= up <= N: raise FormelFehler("sektor braucht {\"up\": k} mit 0 <= k <= N")
    out = []
    for unten in combinations(range(N), N - up):
        s = 0
        for i in unten: s |= 1 << i
        out.append(s)
    return sorted(out)


def sektor_erlaubt(H, N, sektor):
    if sektor is None: return True
    return not kommutator(H, operator("Sz_gesamt", N))


def matrix_exakt(H, N, sektor=None):
    """-> (eintraege {(i,j): (re, im)}, dim) im Sektor."""
    B = basis(N, sektor); idx = {s: i for i, s in enumerate(B)}; M = {}; aussen = {}
    for p, c in H.items():                                   # einzelne Strings (z. B. XX) verlassen den Sektor; nur die Summe nicht
        for j, s in enumerate(B):
            k, t = _anwenden(p, s, N); v = _cmul(c, _IPOW[k])
            ziel, key = (M, (idx[t], j)) if t in idx else (aussen, (t, j))
            w = ziel.get(key, (Fraction(0), Fraction(0))); ziel[key] = (w[0] + v[0], w[1] + v[1])
    if any(v[0] != 0 or v[1] != 0 for v in aussen.values()): raise FormelFehler("Sektor nicht invariant unter dem Operator")
    return {k: v for k, v in M.items() if v[0] != 0 or v[1] != 0}, len(B)


def spektrum_exakt(H, N, sektor=None):
    """Rigorose Einschließung aller Eigenwerte: [(lo, hi, vielfachheit)] aufsteigend, disjunkt. Wirft FormelFehler bei zu großer Dimension."""
    import flint
    if not ist_hermitesch(H): raise FormelFehler("Operator ist nicht hermitesch (komplexe Koeffizienten)")
    if not sektor_erlaubt(H, N, sektor): raise FormelFehler("Sektor unzulässig: [H, S^z_gesamt] != 0")
    M, dim = matrix_exakt(H, N, sektor)
    komplex = any(v[1] != 0 for v in M.values()); D = 2 * dim if komplex else dim
    if D > DIM_EXAKT: raise FormelFehler(f"Dimension {D} > {DIM_EXAKT}: kein rigoroses Spektrum (kleineres N oder Sektor wählen)")
    s = 1
    for v in M.values():
        for x in v: s = s * x.denominator // __import__("math").gcd(s, x.denominator)
    A = [[0] * D for _ in range(D)]
    for (i, j), (re, im) in M.items():
        a, b = int(re * s), int(im * s)
        A[i][j] = a
        if komplex: A[i + dim][j + dim] = a; A[i][j + dim] = -b; A[i + dim][j] = b
    flint.ctx.prec = 256
    P = flint.fmpz_mat(A).charpoly()
    out = []
    for r, m in P.complex_roots():
        if not r.imag.contains(0): raise FormelFehler("nicht-reelle Wurzel: Matrix nicht hermitesch")
        lo, hi = arb_grenzen(r.real)
        out.append((lo / s, hi / s, (m // 2) if komplex else m))
    out.sort(key=lambda x: x[0] + x[1])
    return out, {"dim": dim, "skalierung": s, "komplex": komplex, "charpoly_grad": P.degree(), "charpoly": [int(c) for c in P.coeffs()]}


def eigenwert_k(spek, k):
    """k-ter Eigenwert (0-basiert, mit Vielfachheit gezählt) -> (lo, hi, index_der_wurzel)."""
    n = 0
    for j, (lo, hi, m) in enumerate(spek):
        if k < n + m: return lo, hi, j
        n += m
    raise FormelFehler(f"Index {k} >= Dimension {n}")


def matrix_numerisch(H, N, sektor=None):
    import numpy as np
    from scipy.sparse import coo_matrix
    if not sektor_erlaubt(H, N, sektor): raise FormelFehler("Sektor unzulässig: [H, S^z_gesamt] != 0")
    B = basis(N, sektor); idx = {s: i for i, s in enumerate(B)}; rows, cols, vals = [], [], []
    if len(B) > DIM_NUMERISCH: raise FormelFehler(f"Dimension {len(B)} > {DIM_NUMERISCH}")
    for p, c in H.items():
        cc = complex(float(c[0]), float(c[1]))
        for j, s in enumerate(B):
            k, t = _anwenden(p, s, N)
            if t in idx: rows.append(idx[t]); cols.append(j); vals.append(cc * (1j ** k))   # Beiträge außerhalb heben sich auf (Sektor geprüft)
    M = coo_matrix((np.array(vals), (rows, cols)), shape=(len(B), len(B))).tocsr()
    if not any(abs(v.imag) > 0 for v in vals): M = M.real
    return M


def spektrum_numerisch(H, N, sektor=None, anzahl=6):
    """Niedrigste Eigenwerte numerisch: dicht (dim <= 2048) und unabhängig per Lanczos (dim > 64). -> (werte, info)."""
    import numpy as np
    from scipy.sparse.linalg import eigsh
    M = matrix_numerisch(H, N, sektor); dim = M.shape[0]; anzahl = max(1, min(int(anzahl), dim))
    werte, info = None, {"dim": dim}
    if dim <= 2048:
        werte = np.linalg.eigvalsh(M.toarray())[:anzahl]; info["methode"] = "dicht (eigvalsh)"
    if dim > 64 and anzahl < dim - 1:
        l = np.sort(eigsh(M, k=min(anzahl, dim - 2), which="SA", tol=1e-12, return_eigenvectors=False))
        info["lanczos"] = [float(x) for x in l]
        if werte is None: werte = l; info["methode"] = "Lanczos (eigsh)"
    return [float(x) for x in werte], info


def grundzustand_erwartung(H, O, N, sektor=None):
    import numpy as np
    from scipy.sparse.linalg import eigsh
    M = matrix_numerisch(H, N, sektor); Om = matrix_numerisch(O, N, sektor) if sektor is None or sektor_erlaubt(O, N, sektor) else None
    if Om is None: raise FormelFehler("Observable lässt den Sektor nicht invariant")
    if M.shape[0] <= 2048:
        w, v = np.linalg.eigh(M.toarray()); psi = v[:, 0]
    else:
        w, v = eigsh(M, k=1, which="SA", tol=1e-12); psi = v[:, 0]
    return float(np.real(np.vdot(psi, Om @ psi))), float(w[0])


def zeichen(H, n=6):
    """Kompakte Darstellung einer Pauli-Summe (für Experimente/Belege)."""
    def c2s(c): return str(c[0]) if c[1] == 0 else f"({c[0]}+{c[1]}i)"
    items = sorted(H.items())[:n]
    return [f"{c2s(c)}*{''.join(p)}" for p, c in items] + ([f"... ({len(H)} Terme)"] if len(H) > n else [])
