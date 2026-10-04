"""Klassisches Ising-Modell (J = 1, H = -Σ_<ij> s_i s_j) auf L x M Gittern, exakt.

zustandsdichte(): g[k] = Zahl der Konfigurationen mit k unzufriedenen Bindungen (E = -B + 2k), per Transfermatrix über Spalten
mit ganzzahligen Polynomen. Konsistenz: Σ g = 2^(LM) wird immer geprüft. Periodisch in beiden Richtungen braucht L, M >= 3.
freie_energie(): rigorose Einschließung von f = -(1/(N)) ln Z bzw. ln Z / N bei rationalem K = βJ (arb)."""
from fractions import Fraction

from .ausdruck import FormelFehler

L_MAX = 6; LM_MAX = 64


def _pruefe(L, M, rand):
    for x in (L, M):
        if isinstance(x, bool) or not isinstance(x, int) or x < 1: raise FormelFehler("L, M müssen positive ganze Zahlen sein")
    if min(L, M) > L_MAX or L * M > LM_MAX: raise FormelFehler(f"zu groß: min(L, M) <= {L_MAX}, L*M <= {LM_MAX}")
    if rand not in ("periodisch", "offen"): raise FormelFehler("rand muss 'periodisch' oder 'offen' sein")
    if rand == "periodisch" and min(L, M) < 3: raise FormelFehler("periodisch braucht L, M >= 3 (sonst Doppelbindungen)")
    if L > M: L, M = M, L                                         # Transfer über die längere Richtung
    return L, M


def bindungen(L, M, rand):
    """Liste der Bindungen (i, j) mit Index i = x*L + y (für Lean-Vorlagen und Kontrollen)."""
    idx = lambda x, y: x * L + y; B = []
    for x in range(M):
        for y in range(L):
            if y + 1 < L or rand == "periodisch": B.append((idx(x, y), idx(x, (y + 1) % L)))
            if x + 1 < M or rand == "periodisch": B.append((idx(x, y), idx((x + 1) % M, y)))
    return B


def _polyadd(a, b, shift=0):
    if len(a) < len(b) + shift: a = a + [0] * (len(b) + shift - len(a))
    for i, v in enumerate(b): a[i + shift] += v
    return a


def zustandsdichte(L, M, rand="periodisch"):
    """-> (g, B): g[k] Anzahl Konfigurationen mit k unzufriedenen Bindungen; B Zahl der Bindungen."""
    L, M = _pruefe(L, M, rand)
    per = rand == "periodisch"; S = range(1 << L)
    def innen(s):                                                  # unzufriedene Bindungen innerhalb einer Spalte
        k = sum(((s >> y) & 1) != ((s >> (y + 1)) & 1) for y in range(L - 1))
        if per: k += ((s >> (L - 1)) & 1) != (s & 1)
        return k
    def zwischen(s, t): return bin(s ^ t).count("1")
    inn = [innen(s) for s in S]; g = [0]
    starts = list(S) if per else [None]
    for s0 in starts:
        cur = {s: [0] * inn[s] + [1] for s in ([s0] if per else S)}
        for _ in range(M - 1):
            nxt = {}
            for s, poly in cur.items():
                for t in S:
                    sh = inn[t] + zwischen(s, t); nxt[t] = _polyadd(nxt.get(t, []), poly, sh)
            cur = nxt
        for s, poly in cur.items():
            g = _polyadd(g, poly, zwischen(s, s0) if per else 0)
    while len(g) > 1 and g[-1] == 0: g.pop()
    B = len(bindungen(L, M, rand))
    if sum(g) != 2 ** (L * M): raise FormelFehler(f"interne Konsistenz verletzt: Σ g = {sum(g)} != 2^{L * M}")
    return g, B


def grundzustand(L, M, rand="periodisch"):
    g, B = zustandsdichte(L, M, rand); k0 = next(k for k, v in enumerate(g) if v)
    return -B + 2 * k0, g[k0]


def lnZ_arb(g, B, K):
    """ln Z(K) rigoros, Z = Σ_k g_k exp(K (B - 2k))."""
    import flint
    flint.ctx.prec = 256; K = Fraction(K); k_ = flint.arb(flint.fmpq(K.numerator, K.denominator))
    Z = flint.arb(0)
    for k, v in enumerate(g):
        if v: Z += flint.arb(v) * (k_ * (B - 2 * k)).exp()
    return Z.log()


def freie_energie_intervall(L, M, rand, K):
    """ln Z / N als rigorose Einschließung (lo, hi) in Fractions."""
    from .ausdruck import arb_grenzen
    g, B = zustandsdichte(L, M, rand); a = lnZ_arb(g, B, K) / (L * M)
    return arb_grenzen(a)
