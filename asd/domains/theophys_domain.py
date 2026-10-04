"""Domäne: Theoretische Physik (theophys). Berechnungen und Beweise mit unabhängigem Code-Prüfer.

Teilgebiete und ihre Prüfer (Stufe in Klammern; "beweis": "lean" hebt die markierten Typen auf proved_lean):
  Symbolik/Analysis  identitaet, grenzwert, reihenkoeffizient (CAS, computed_rigorous), schranke (Intervall-Branch-and-Bound,
                     computed_rigorous), dimension (Dimensionsanalyse, computed_rigorous)
  Spinketten         spektrum, gap, entartung (exaktes charakteristisches Polynom + rigorose Wurzelisolation bis Dimension 400,
                     darüber zwei numerische Verfahren -> observed), kommutator (exakte Pauli-Algebra)
  Stat. Mechanik     ising_zustandsdichte, ising_grundzustand [lean], ising_freie_energie (Transfermatrix exakt, arb)
  Gravitation        feldgleichung, kruemmungsinvariante (symbolisch exakt)
  Eichtheorie        darstellung, beta_koeffizient [lean], asymptotische_freiheit [lean], banks_zaks [lean], anomaliefrei [lean]
  Quanteninformation klassische_schranke [lean], quantenwert (exakt)
  Quantenmechanik    qm_eigenwert (zwei Gitter + Richardson, observed)
Regeln: Toleranzen, Präzision, Intervallbreiten, Gittergrößen und Zeitlimits legt allein dieser Prüfer fest; Toleranzfelder und unbekannte
Felder in einer Behauptung führen zur Ablehnung. Jede Rechnung läuft mit hartem Zeitlimit in eigenem Prozess (Zeitüberschreitung =
"nicht ausführbar", nie "bestanden")."""
import json, math
from fractions import Fraction

from .base import Domain
from .theophys import ausdruck as A, spin as S, ising as I, gr as GR, gruppen as G, bell as BE, qm as QM, einheiten as U, lean as LN
from .theophys.zeitlimit import mit_zeitlimit, Zeitueberschreitung

BREITE_REL = Fraction(1, 10 ** 6)          # höchstens zulässige relative Breite eines behaupteten Eigenwert-Intervalls
BREITE_REL_F = Fraction(1, 10 ** 10)       # ... eines Intervalls für ln Z / N
MAX_BOXEN = 20000                          # Branch-and-Bound-Boxen für schranke
MAX_VARIABLEN = 3
NUM_TOL = 1e-8                             # numerische Spektren (observed): Abstand zum Intervallrand
LEAN_ISING_MAX = 12                        # Lean-Aufzählung des Ising-Grundzustands bis zu so vielen Spins
VERBOTEN = {"toleranz", "tol", "tolerance", "genauigkeit", "praezision", "precision", "epsilon", "eps", "fehler", "rtol", "atol"}

SCHEMA = {   # typ: (Pflichtfelder, optionale Felder)
    "identitaet": ({"lhs", "rhs"}, {"annahmen", "dimensionen"}),
    "grenzwert": ({"ausdruck", "variable", "punkt", "wert"}, {"richtung", "annahmen"}),
    "reihenkoeffizient": ({"ausdruck", "variable", "punkt", "ordnung", "koeffizient"}, {"annahmen"}),
    "schranke": ({"ausdruck", "bereich"}, {"untere", "obere"}),
    "dimension": ({"ausdruck", "dimensionen", "erwartet"}, set()),
    "spektrum": ({"modell", "N", "index"}, {"rand", "sektor", "intervall", "wert"}),
    "gap": ({"modell", "N"}, {"rand", "sektor", "gap_min", "gap_max"}),
    "entartung": ({"modell", "N", "index", "entartung"}, {"rand", "sektor"}),
    "kommutator": ({"N", "A", "B"}, {"rand"}),
    "ising_zustandsdichte": ({"L", "M", "g"}, {"rand"}),
    "ising_grundzustand": ({"L", "M", "energie", "entartung"}, {"rand", "beweis"}),
    "ising_freie_energie": ({"L", "M", "K", "intervall"}, {"rand"}),
    "feldgleichung": ({"koordinaten", "behauptung"}, {"metrik", "diag", "annahmen", "Lambda"}),
    "kruemmungsinvariante": ({"koordinaten", "invariante", "wert"}, {"metrik", "diag", "annahmen"}),
    "darstellung": ({"N", "rep", "groesse", "wert"}, set()),
    "beta_koeffizient": ({"N", "materie"}, {"b0", "b1", "beweis"}),
    "asymptotische_freiheit": ({"N", "materie"}, {"beweis"}),
    "banks_zaks": ({"N", "materie"}, {"beweis"}),
    "anomaliefrei": ({"gruppen", "abelsch", "felder"}, {"beweis"}),
    "klassische_schranke": ({"koeffizienten", "schranke"}, {"beweis"}),
    "quantenwert": ({"koeffizienten", "winkel_a", "winkel_b", "wert"}, set()),
    "qm_eigenwert": ({"potential", "index", "wert"}, {"masse", "intervall"}),
}
LEAN_TYPEN = {"ising_grundzustand", "beta_koeffizient", "asymptotische_freiheit", "banks_zaks", "anomaliefrei", "klassische_schranke"}
HAUPT = {"schranke", "anomaliefrei", "banks_zaks", "asymptotische_freiheit", "feldgleichung", "klassische_schranke", "gap", "kommutator"}
BEISPIEL = {"darstellung", "reihenkoeffizient", "qm_eigenwert", "quantenwert", "dimension", "grenzwert"}


def _js(x): return json.dumps(x, sort_keys=True, ensure_ascii=False, default=str)
def _f(x): return str(x) if isinstance(x, Fraction) and x.denominator != 1 else (int(x) if isinstance(x, Fraction) else x)


class Abgelehnt(Exception):
    """Prüfung nicht bestanden, mit Beleg/Gegenbeispiel."""
    def __init__(self, grund, beleg=None): super().__init__(grund); self.grund = grund; self.beleg = beleg or {}


# ================================================================ Prüfer (läuft im eigenen Prozess) ================================
def _schema(p):
    if not isinstance(p, dict): raise Abgelehnt("Behauptung ist kein Objekt")
    t = p.get("typ")
    if t not in SCHEMA: raise Abgelehnt(f"unbekannter Prüfungstyp {t!r}")
    pf, opt = SCHEMA[t]; felder = set(p) - {"typ"}
    tol = felder & VERBOTEN
    if tol: raise Abgelehnt(f"Regelverletzung: Toleranzfelder {sorted(tol)} sind nicht erlaubt (Toleranzen legt der Prüfer fest)")
    fehlt = pf - felder; extra = felder - pf - opt
    if fehlt: raise Abgelehnt(f"Pflichtfelder fehlen: {sorted(fehlt)}")
    if extra: raise Abgelehnt(f"unbekannte Felder {sorted(extra)}")
    if "beweis" in p and p["beweis"] != "lean": raise Abgelehnt("beweis darf nur \"lean\" sein")
    return t


def _ganz(x, name, lo=0, hi=10 ** 9):
    if isinstance(x, bool) or not isinstance(x, int) or not lo <= x <= hi: raise Abgelehnt(f"{name} muss eine ganze Zahl in [{lo}, {hi}] sein")
    return x


def _lean(src):
    r = LN.pruefe_quelltext(src)
    if r.get("bestanden") is not True: raise Abgelehnt(("Prüfung nicht ausführbar: " if r.get("bestanden") is None else "") + "Lean: " + r["grund"][:300])
    return r


def _c_identitaet(p):
    ann = p.get("annahmen") or {}
    l, r = A.parse(p["lhs"], ann), A.parse(p["rhs"], ann)
    if p.get("dimensionen") is not None:
        dl, dr = U.dimension(l, p["dimensionen"]), U.dimension(r, p["dimensionen"])
        if dl != dr: raise Abgelehnt(f"Dimensionen verschieden: {U.als_dict(dl)} vs {U.als_dict(dr)}")
    z = A.ist_null(l - r)
    if z: return "CAS: lhs − rhs vereinfacht exakt zu 0", {}
    g = A.punkte_test(l - r)
    if g: raise Abgelehnt(f"lhs − rhs ≠ 0 bei {g[0]} (Wert {g[1]})", {"gegenbeispiel": {"art": "wert", "parameter": g[0], "berechnet": g[1], "behauptet": "0"}})
    raise Abgelehnt("nicht entschieden: CAS konnte lhs − rhs nicht auf 0 vereinfachen (keine Bestätigung)")


def _c_grenzwert(p):
    import sympy as sp
    ann = p.get("annahmen") or {}; e = A.parse(p["ausdruck"], ann); v = sp.Symbol(str(p["variable"]), **A.ANNAHMEN.get(ann.get(p["variable"], ""), {}))
    v = next((s for s in e.free_symbols if str(s) == str(p["variable"])), v)
    pt = A.parse(p["punkt"]); w = A.parse(p["wert"])
    d = p.get("richtung", "+-")
    if d not in ("+", "-", "+-"): raise Abgelehnt("richtung: '+', '-' oder '+-'")
    L = sp.limit(e, v, pt, d if d != "+-" else "+-") if pt not in (sp.oo, -sp.oo) else sp.limit(e, v, pt)
    if isinstance(L, sp.Limit) or L.has(sp.Limit): raise Abgelehnt("Prüfung nicht ausführbar: CAS kann den Grenzwert nicht auswerten")
    if A.ist_null(L - w): return f"CAS: Grenzwert = {L}", {"berechnet": str(L)}
    raise Abgelehnt(f"Grenzwert ist {L}, nicht {w}", {"gegenbeispiel": {"art": "wert", "berechnet": str(L), "behauptet": str(w)}})


def _c_reihe(p):
    import sympy as sp
    ann = p.get("annahmen") or {}; e = A.parse(p["ausdruck"], ann); n = _ganz(p["ordnung"], "ordnung", 0, 40)
    v = next((s for s in e.free_symbols if str(s) == str(p["variable"])), sp.Symbol(str(p["variable"])))
    x0 = A.parse(p["punkt"]); c = A.parse(p["koeffizient"], ann)
    ser = sp.series(e, v, x0, n + 1).removeO()
    k = sp.expand(ser.subs(v, v + x0)).coeff(v, n) if x0 != 0 else sp.expand(ser).coeff(v, n)
    if A.ist_null(k - c): return f"CAS: Koeffizient von (x−{x0})^{n} = {k}", {"berechnet": str(k)}
    raise Abgelehnt(f"Koeffizient ist {k}, nicht {c}", {"gegenbeispiel": {"art": "wert", "berechnet": str(k), "behauptet": str(c)}})


def _c_schranke(p):
    import sympy as sp
    B = p["bereich"]
    if not isinstance(B, dict) or not 1 <= len(B) <= MAX_VARIABLEN: raise Abgelehnt(f"bereich: 1..{MAX_VARIABLEN} Variablen {{x: [lo, hi]}}")
    box = {k: (A.rational(v[0]), A.rational(v[1])) for k, v in B.items()}
    if any(lo >= hi for lo, hi in box.values()): raise Abgelehnt("bereich: lo < hi")
    if ("untere" in p) == ("obere" in p): raise Abgelehnt("genau eines von untere / obere angeben")
    e = A.parse(p["ausdruck"], {k: "reell" for k in box})
    if {str(s) for s in e.free_symbols} - set(box): raise Abgelehnt("ausdruck hat Variablen ohne Bereich")
    c = A.rational(p["untere"] if "untere" in p else p["obere"]); unten = "untere" in p
    f = (e - sp.Rational(c.numerator, c.denominator)) * (1 if unten else -1)          # zu zeigen: f > 0 auf der Box
    syms = {str(s): s for s in f.free_symbols}
    def verletzt(pt):
        """Zertifiziert f(pt) <= 0? Rigoros über arb am Punkt, exakt (CAS) nur wenn das Intervall 0 enthält."""
        lo_, hi_ = A.arb_grenzen(A.arb_eval(f, {k: (v, v) for k, v in pt.items()}))
        if hi_ <= 0: return True
        if lo_ > 0: return False
        return A.ist_null(f.subs({syms[k]: sp.Rational(v.numerator, v.denominator) for k, v in pt.items() if k in syms})) is True
    def melde(pt):
        ist = e.subs({syms[k]: sp.Rational(v.numerator, v.denominator) for k, v in pt.items() if k in syms})
        raise Abgelehnt(f"Schranke verletzt bei {dict((k, str(v)) for k, v in pt.items())}: Wert {sp.N(ist, 15)}",
                        {"gegenbeispiel": {"art": "zertifiziertes_gegenbeispiel", "parameter": {k: str(v) for k, v in pt.items()}, "berechnet": str(sp.N(ist, 30)),
                                           "behauptet": str(c), "verletzt": ("ausdruck > untere" if unten else "ausdruck < obere")}})
    import heapq, random
    rnd = random.Random(12345)                                     # Stichprobe zuerst: schnelle Gegenbeispiele (feste Saat)
    for _ in range(200):
        pt = {k: l + (h - l) * Fraction(rnd.randint(0, 1024), 1024) for k, (l, h) in box.items()}
        if verletzt(pt): melde(pt)
    heap = [(0, 0, box)]; n = 0; zaehler = 1                       # Best-first: Box mit der kleinsten unteren Schranke zuerst
    while heap:
        _, _, b = heapq.heappop(heap); n += 1
        if n > MAX_BOXEN: raise Abgelehnt(f"nicht entschieden nach {MAX_BOXEN} Boxen (keine Bestätigung)")
        lo, _ = A.arb_grenzen(A.arb_eval(f, b))
        if lo > 0: continue
        mid = {k: (l + h) / 2 for k, (l, h) in b.items()}
        if verletzt(mid): melde(mid)
        k = max(b, key=lambda k: b[k][1] - b[k][0]); l_, h_ = b[k]; m_ = (l_ + h_) / 2
        for teil in ({**b, k: (l_, m_)}, {**b, k: (m_, h_)}):
            heapq.heappush(heap, (lo, zaehler, teil)); zaehler += 1
    return f"Intervall-Branch-and-Bound (arb, 128 Bit): {'ausdruck > ' if unten else 'ausdruck < '}{c} auf der ganzen Box, {n} Boxen", {"boxen": n}


def _c_dimension(p):
    e = A.parse(p["ausdruck"]); d = U.dimension(e, p["dimensionen"]); w = U.vektor(p["erwartet"])
    if d == w: return f"Dimension {U.als_dict(d)}", {}
    raise Abgelehnt(f"Dimension ist {U.als_dict(d)}, nicht {U.als_dict(w)}", {"gegenbeispiel": {"art": "wert", "berechnet": U.als_dict(d), "behauptet": p["erwartet"]}})


def _system(p):
    N = _ganz(p["N"], "N", 2, S.N_MAX); rand = p.get("rand", "periodisch"); H = S.operator(p["modell"], N, rand)
    if not S.ist_hermitesch(H): raise Abgelehnt("Hamiltonoperator nicht hermitesch")
    return H, N, rand, p.get("sektor")


def _dim_reell(p):
    H, N, rand, sek = _system(p); M, dim = S.matrix_exakt(H, N, sek)
    return 2 * dim if any(v[1] != 0 for v in M.values()) else dim


def _num_spek(H, N, sek, anzahl):
    w, info = S.spektrum_numerisch(H, N, sek, anzahl)
    if "lanczos" in info and len(w) and abs(info["lanczos"][0] - w[0]) > 1e-9 * max(1, abs(w[0])): raise Abgelehnt("Prüfung nicht ausführbar: numerische Verfahren uneinig")
    return w, info


def _c_spektrum(p):
    import sympy as sp
    H, N, rand, sek = _system(p); k = _ganz(p["index"], "index", 0, 1 << 16)
    if ("intervall" in p) == ("wert" in p): raise Abgelehnt("genau eines von intervall / wert angeben")
    if "intervall" in p:
        lo, hi = (A.rational(p["intervall"][0]), A.rational(p["intervall"][1]))
        if not lo <= hi: raise Abgelehnt("intervall: lo <= hi")
        if hi - lo > BREITE_REL * max(1, abs(lo + hi) / 2): raise Abgelehnt(f"Regelverletzung: Intervall breiter als {float(BREITE_REL):g} (relativ); der Prüfer verlangt eine scharfe Aussage")
    try: spek, info = S.spektrum_exakt(H, N, sek)
    except A.FormelFehler as e:
        if "Dimension" not in str(e): raise
        if "wert" in p: raise Abgelehnt("exakter Wert nur bis Dimension %d prüfbar" % S.DIM_EXAKT)
        w, info = _num_spek(H, N, sek, k + 1)
        if not float(lo) + NUM_TOL <= w[k] <= float(hi) - NUM_TOL: raise Abgelehnt(f"numerisch E_{k} = {w[k]:.12g} liegt nicht im Intervall", {"gegenbeispiel": {"art": "wert", "berechnet": w[k]}})
        return f"numerisch (dicht + Lanczos, Dimension {info['dim']}): E_{k} = {w[k]:.12g} im Intervall", {"stufe": "observed", "berechnet": w[k]}
    elo, ehi, j = S.eigenwert_k(spek, k)
    if "intervall" in p:
        if lo <= elo and ehi <= hi: return f"exakt (charakteristisches Polynom Grad {info['charpoly_grad']}, Wurzelisolation): E_{k} ∈ [{float(elo):.15g}, {float(ehi):.15g}]", {"dim": info["dim"]}
        raise Abgelehnt(f"E_{k} ≈ {float((elo + ehi) / 2):.15g} liegt nicht im Intervall", {"gegenbeispiel": {"art": "wert", "berechnet": float((elo + ehi) / 2), "behauptet": [str(lo), str(hi)]}})
    v = A.parse(p["wert"])
    if v.free_symbols: raise Abgelehnt("wert muss eine Zahl sein")
    x = sp.Symbol("x"); s = info["skalierung"]
    try: m = sp.Poly(sp.minimal_polynomial(v * s, x), x)
    except Exception: raise Abgelehnt("wert ist keine algebraische Zahl (Minimalpolynom nicht bestimmbar)")
    P = sp.Poly(list(reversed(info["charpoly"])), x)
    if not P.rem(m).is_zero: raise Abgelehnt(f"{v} ist kein Eigenwert (Minimalpolynom teilt das charakteristische Polynom nicht)",
                                             {"gegenbeispiel": {"art": "wert", "berechnet": float((elo + ehi) / 2), "behauptet": str(v)}})
    vn = sp.N(v, 90); eps = sp.Rational(1, 10 ** 70)
    def drin(a, b): return sp.Rational(a.numerator, a.denominator) - eps <= vn <= sp.Rational(b.numerator, b.denominator) + eps
    if not drin(elo, ehi): raise Abgelehnt(f"{v} ist ein Eigenwert, aber nicht E_{k} (E_{k} ≈ {float((elo + ehi) / 2):.15g})", {"gegenbeispiel": {"art": "wert", "berechnet": float((elo + ehi) / 2)}})
    if any(drin(a, b) for i, (a, b, _) in enumerate(spek) if i != j): raise Abgelehnt("Prüfung nicht ausführbar: Wurzeln nicht getrennt genug")
    return f"exakt: {v} ist Nullstelle des charakteristischen Polynoms (Minimalpolynom teilt es) und liegt in der isolierten Einschließung von E_{k}", {"dim": info["dim"]}


def _c_gap(p):
    H, N, rand, sek = _system(p)
    if ("gap_min" in p) == ("gap_max" in p): raise Abgelehnt("genau eines von gap_min / gap_max angeben")
    g = A.rational(p.get("gap_min", p.get("gap_max")))
    try:
        spek, info = S.spektrum_exakt(H, N, sek); l0, h0, _ = S.eigenwert_k(spek, 0); l1, h1, _ = S.eigenwert_k(spek, 1)
        unten, oben, art = l1 - h0, h1 - l0, "exakt"
    except A.FormelFehler as e:
        if "Dimension" not in str(e): raise
        w, info = _num_spek(H, N, sek, 2); d = w[1] - w[0]
        unten, oben, art = Fraction(d) - Fraction(NUM_TOL), Fraction(d) + Fraction(NUM_TOL), "numerisch"
    mid = float((unten + oben) / 2)
    if "gap_min" in p and unten > g: return f"{art}: Lücke E_1 − E_0 ≥ {float(unten):.15g} > {g}", ({"stufe": "observed"} if art == "numerisch" else {})
    if "gap_max" in p and oben < g: return f"{art}: Lücke E_1 − E_0 ≤ {float(oben):.15g} < {g}", ({"stufe": "observed"} if art == "numerisch" else {})
    raise Abgelehnt(f"Lücke ≈ {mid:.15g} erfüllt die Behauptung nicht (strikt)", {"gegenbeispiel": {"art": "wert", "berechnet": mid, "behauptet": str(g)}})


def _c_entartung(p):
    H, N, rand, sek = _system(p); k = _ganz(p["index"], "index", 0, 1 << 16); d = _ganz(p["entartung"], "entartung", 1, 1 << 16)
    spek, info = S.spektrum_exakt(H, N, sek); lo, hi, j = S.eigenwert_k(spek, k); m = spek[j][2]
    if m == d: return f"exakt: E_{k} ≈ {float((lo + hi) / 2):.15g} hat Vielfachheit {m}", {}
    raise Abgelehnt(f"Vielfachheit von E_{k} ist {m}, nicht {d}", {"gegenbeispiel": {"art": "wert", "berechnet": m, "behauptet": d}})


def _c_kommutator(p):
    N = _ganz(p["N"], "N", 2, S.N_MAX); rand = p.get("rand", "periodisch")
    C = S.kommutator(S.operator(p["A"], N, rand), S.operator(p["B"], N, rand))
    if not C: return f"exakte Pauli-Algebra: [A, B] = 0 für N = {N}", {}
    raise Abgelehnt(f"[A, B] ≠ 0 ({len(C)} Terme, z. B. {S.zeichen(C, 2)})", {"gegenbeispiel": {"art": "verletzt", "verletzt": "[A,B]=0", "berechnet": S.zeichen(C, 4)}})


def _ising_args(p):
    return _ganz(p["L"], "L", 1, 64), _ganz(p["M"], "M", 1, 64), p.get("rand", "periodisch")


def _c_ising_g(p):
    L, M, r = _ising_args(p); g, B = I.zustandsdichte(L, M, r); w = p["g"]
    if not isinstance(w, list) or any(isinstance(x, bool) or not isinstance(x, int) for x in w): raise Abgelehnt("g: Liste ganzer Zahlen")
    w = list(w)
    while len(w) > 1 and w[-1] == 0: w.pop()
    if w == g: return f"exakte Transfermatrix: Zustandsdichte über {B} Bindungen, Σ g = 2^{L * M}", {}
    k = next((i for i in range(max(len(g), len(w))) if (g[i] if i < len(g) else 0) != (w[i] if i < len(w) else 0)), None)
    raise Abgelehnt(f"g[{k}] ist {g[k] if k < len(g) else 0}", {"gegenbeispiel": {"art": "wert", "parameter": {"k": k}, "berechnet": g[k] if k < len(g) else 0}})


def _c_ising_gz(p):
    L, M, r = _ising_args(p); e0, d0 = I.grundzustand(L, M, r)
    if (e0, d0) != (p["energie"], p["entartung"]): raise Abgelehnt(f"Grundzustand: Energie {e0}, Entartung {d0}", {"gegenbeispiel": {"art": "wert", "berechnet": {"energie": e0, "entartung": d0}}})
    why = f"exakte Transfermatrix: E_0 = {e0}, Entartung {d0}"
    if p.get("beweis") == "lean":
        if L * M > LEAN_ISING_MAX: raise Abgelehnt(f"Lean-Aufzählung nur bis {LEAN_ISING_MAX} Spins")
        Lmin, Mmax = min(L, M), max(L, M); r_ = _lean(LN.satz_ising("ising", L * M, I.bindungen(Lmin, Mmax, r), e0)); why += "; " + r_["grund"]
        return why, {"lean_sha256": r_["sha256"]}
    return why, {}


def _c_ising_f(p):
    L, M, r = _ising_args(p); K = A.rational(p["K"]); lo, hi = (A.rational(p["intervall"][0]), A.rational(p["intervall"][1]))
    if not lo <= hi or hi - lo > BREITE_REL_F * max(1, abs(lo + hi) / 2): raise Abgelehnt(f"Regelverletzung: Intervall leer oder breiter als {float(BREITE_REL_F):g} relativ")
    a, b = I.freie_energie_intervall(L, M, r, K)
    if lo <= a and b <= hi: return f"rigoros (arb, 256 Bit): ln Z / N ∈ [{float(a):.17g}, {float(b):.17g}]", {}
    raise Abgelehnt(f"ln Z / N ≈ {float((a + b) / 2):.17g}", {"gegenbeispiel": {"art": "wert", "berechnet": float((a + b) / 2)}})


def _metrik(p):
    spec = {k: p[k] for k in ("koordinaten", "metrik", "diag", "annahmen") if k in p}
    if ("metrik" in p) == ("diag" in p): raise Abgelehnt("genau eines von metrik / diag angeben")
    return GR.metrik(spec)


def _c_feld(p):
    import sympy as sp
    X, g = _metrik(p); k = GR.kruemmung(X, g); b = p["behauptung"]
    if b == "vakuum": T = k["Ricci"]; text = "R_ab = 0"
    elif b == "einstein_lambda":
        if "Lambda" not in p: raise Abgelehnt("einstein_lambda braucht Lambda")
        lam = A.parse(p["Lambda"], p.get("annahmen") or {}); lam = lam.xreplace({s: x for s in lam.free_symbols for x in g.free_symbols if str(s) == str(x)})
        T = k["Einstein"] + lam * g; text = "G_ab + Λ g_ab = 0"
    else: raise Abgelehnt("behauptung: vakuum | einstein_lambda")
    rest = [(i, j, T[i, j]) for i in range(len(X)) for j in range(len(X)) if A.ist_null(T[i, j]) is not True]
    if not rest: return f"symbolisch exakt: {text} in allen Komponenten", {}
    i, j, v = rest[0]
    raise Abgelehnt(f"{text} verletzt: Komponente ({i},{j}) = {sp.simplify(v)}", {"gegenbeispiel": {"art": "verletzt", "verletzt": text, "berechnet": {f"{i}{j}": str(sp.simplify(v))}}})


def _c_invariante(p):
    X, g = _metrik(p); k = GR.kruemmung(X, g)
    inv = {"ricci_skalar": k["R"], "kretschmann": k["Kretschmann"]}.get(p["invariante"])
    if inv is None: raise Abgelehnt("invariante: ricci_skalar | kretschmann")
    w = A.parse(p["wert"], p.get("annahmen") or {}); w = w.xreplace({s: x for s in w.free_symbols for x in g.free_symbols if str(s) == str(x)})
    if A.ist_null(inv - w): return f"symbolisch exakt: {p['invariante']} = {inv}", {}
    raise Abgelehnt(f"{p['invariante']} = {inv}", {"gegenbeispiel": {"art": "wert", "berechnet": str(inv), "behauptet": str(w)}})


def _c_darstellung(p):
    N = _ganz(p["N"], "N", 2, G.N_MAX); f = {"dim": G.dim, "casimir": G.casimir, "index": G.index, "anomalie": G.anomalie_koeff}.get(p["groesse"])
    if f is None: raise Abgelehnt("groesse: dim | casimir | index | anomalie")
    v = f(N, p["rep"]); w = A.rational(p["wert"])
    if v == w: return f"exakt: {p['groesse']} = {v}", {}
    raise Abgelehnt(f"{p['groesse']} = {v}", {"gegenbeispiel": {"art": "wert", "berechnet": str(v), "behauptet": str(w)}})


def _beta_lean(N, materie, wer):
    """Lean rechnet b0/b1 aus den (in Python exakt bestimmten) Gruppeninvarianten C_A, T(R), C2(R) nach: Produkte und Summe im Kernel,
    alle Faktoren mit dem Hauptnenner auf ganze Zahlen skaliert. -> {name: (Lean-Ausdruck, skalierter Sollwert)}"""
    b0, b1 = G.beta(N, materie)
    CA = Fraction(N); t0 = [[Fraction(11, 3), CA]]; t1 = [[Fraction(34, 3), CA, CA]]
    for m in materie:
        n = A.rational(m.get("anzahl", 1)); T = G.index(N, m.get("rep", "F")); C = G.casimir(N, m.get("rep", "F")); k1, k2 = G.ART[m["art"]]
        t0.append([-k1, n, T])
        t1.append([-k2, n, T, (Fraction(20, 3) * CA + 4 * C) if m["art"] in ("dirac", "weyl") else (Fraction(2, 3) * CA + 4 * C)])
    out = {}
    for name, terme, wert in (("b0", t0, b0), ("b1", t1, b1)):
        if name not in wer: continue
        sk, skala = LN.skaliere_produkte(terme); soll = wert * skala
        assert soll.denominator == 1
        out[name] = (LN.summe(sk), int(soll))
    return out


def _c_beta(p):
    N = _ganz(p["N"], "N", 2, G.N_MAX); b0, b1 = G.beta(N, p["materie"])
    if "b0" not in p and "b1" not in p: raise Abgelehnt("b0 und/oder b1 angeben")
    for k, v in (("b0", b0), ("b1", b1)):
        if k in p and A.rational(p[k]) != v: raise Abgelehnt(f"{k} = {v}", {"gegenbeispiel": {"art": "wert", "berechnet": {"b0": str(b0), "b1": str(b1)}}})
    why = f"exakt: b0 = {b0}, b1 = {b1}"
    if p.get("beweis") == "lean":
        src = "".join(LN.satz_gleich(f"beta_{k}", ausd, int(w)) for k, (ausd, w) in _beta_lean(N, p["materie"], [k for k in ("b0", "b1") if k in p]).items())
        why += "; " + _lean(src)["grund"]
    return why, {}


def _c_af(p, bz=False):
    N = _ganz(p["N"], "N", 2, G.N_MAX); b0, b1 = G.beta(N, p["materie"])
    if not b0 > 0: raise Abgelehnt(f"b0 = {b0} ≤ 0: nicht asymptotisch frei", {"gegenbeispiel": {"art": "wert", "berechnet": {"b0": str(b0), "b1": str(b1)}}})
    if bz and not b1 < 0: raise Abgelehnt(f"b1 = {b1} ≥ 0: kein perturbativer Banks-Zaks-Fixpunkt", {"gegenbeispiel": {"art": "wert", "berechnet": {"b0": str(b0), "b1": str(b1)}}})
    why = f"exakt: b0 = {b0} > 0" + (f", b1 = {b1} < 0, Fixpunkt g*²/(16π²) = {-b0 / b1}" if bz else "")
    if p.get("beweis") == "lean":
        L = _beta_lean(N, p["materie"], ["b0", "b1"] if bz else ["b0"])
        src = LN.satz_kleiner("b0_positiv", 0, f"({L['b0'][0]})")
        if bz: src += f"theorem b1_negativ : ({L['b1'][0]}) < (0 : Int) := by decide\n#print axioms b1_negativ\n"
        why += "; " + _lean(src)["grund"]
    return why, {}


def _c_anomalie(p):
    gr_, ab, fe = p["gruppen"], p["abelsch"], p["felder"]; res = G.anomalien(gr_, ab, fe)
    rest = {k: str(v) for k, v in res.items() if v != 0}
    if rest: raise Abgelehnt(f"Anomalien ungleich 0: {rest}", {"gegenbeispiel": {"art": "verletzt", "verletzt": "Anomaliefreiheit", "berechnet": rest}})
    why = f"exakt: alle {len(res)} Bedingungen = 0 ({', '.join(res)})"
    if p.get("beweis") == "lean":
        src = ""
        for j, k in enumerate(res):
            if k.startswith("witten_"):                                        # Zahl der Dubletts (mit Multiplizität) gerade
                g = k[7:]; terme = [[A.rational(f.get("anzahl", 1))] + [G.dim(N, f.get(h, "1")) for h, N in gr_.items() if h != g] for f in fe if G.dynkin(2, f.get(g, "1")) == [1]]
                if any(x.denominator != 1 for t in terme for x in t): raise Abgelehnt("Witten-Bedingung braucht ganzzahlige Anzahlen")
                src += f"theorem a{j} : ({LN.summe([[int(x) for x in t] for t in terme]) if terme else '(0 : Int)'}) % 2 = 0 := by decide\n#print axioms a{j}\n"
                continue
            sk, _ = LN.skaliere_produkte(G.anomalie_terme(gr_, ab, fe, k))
            src += LN.satz_gleich(f"a{j}", LN.summe(sk), 0)
        why += "; " + _lean(src)["grund"]
    return why, {}


def _c_klassisch(p):
    s = A.rational(p["schranke"]); m, strat = BE.klassisch(p["koeffizienten"])
    if m != s: raise Abgelehnt(f"klassisches Maximum ist {m}", {"gegenbeispiel": {"art": "wert", "berechnet": str(m), "parameter": strat, "behauptet": str(s)}})
    why = f"exakte Aufzählung aller deterministischen Strategien: Maximum {m} (erreicht von {strat})"
    if p.get("beweis") == "lean": why += "; " + _lean(LN.bell_quelltext([[str(v) for v in r] for r in p["koeffizienten"]], str(s)))["grund"]
    return why, {}


def _c_quantenwert(p):
    v = BE.quantenwert(p["koeffizienten"], p["winkel_a"], p["winkel_b"]); w = A.parse(p["wert"])
    if A.ist_null(v - w): return f"exakt: Singulett-Wert = {v}", {}
    raise Abgelehnt(f"Singulett-Wert = {v}", {"gegenbeispiel": {"art": "wert", "berechnet": str(v), "behauptet": str(w)}})


def _c_qm(p):
    k = _ganz(p["index"], "index", 0, 200); iv = p.get("intervall", ["-10", "10"]); m = p.get("masse", 1); w = float(A.rational(p["wert"]))
    E, konv = QM.pruefer_wert(p["potential"], m, iv, k)
    if konv > QM.KONV_REL * max(1, abs(E)): raise Abgelehnt("Prüfung nicht ausführbar: Gitter nicht konvergiert")
    if abs(E - w) <= QM.TOL_REL * max(1, abs(E)): return f"numerisch (Gitter {QM.N_PRUEFER} und {2 * QM.N_PRUEFER}, Richardson): E_{k} = {E:.12g}", {"stufe": "observed"}
    raise Abgelehnt(f"E_{k} = {E:.12g}", {"gegenbeispiel": {"art": "wert", "berechnet": E, "behauptet": w, "abstand": abs(E - w)}})


PRUEFER = {"identitaet": _c_identitaet, "grenzwert": _c_grenzwert, "reihenkoeffizient": _c_reihe, "schranke": _c_schranke, "dimension": _c_dimension,
           "spektrum": _c_spektrum, "gap": _c_gap, "entartung": _c_entartung, "kommutator": _c_kommutator, "ising_zustandsdichte": _c_ising_g,
           "ising_grundzustand": _c_ising_gz, "ising_freie_energie": _c_ising_f, "feldgleichung": _c_feld, "kruemmungsinvariante": _c_invariante,
           "darstellung": _c_darstellung, "beta_koeffizient": _c_beta, "asymptotische_freiheit": _c_af, "banks_zaks": lambda p: _c_af(p, bz=True),
           "anomaliefrei": _c_anomalie, "klassische_schranke": _c_klassisch, "quantenwert": _c_quantenwert, "qm_eigenwert": _c_qm}


def pruefe_intern(p):
    """(ok, grund, beleg). Läuft im eigenen Prozess."""
    try:
        t = _schema(p); why, ev = PRUEFER[t](p); return True, f"Prüfer: {why}", ev
    except Abgelehnt as e: return False, f"Prüfer: {e.grund}"[:600], e.beleg
    except (A.FormelFehler, KeyError, TypeError, ValueError, IndexError, ZeroDivisionError, NotImplementedError, AttributeError) as e:
        return False, f"Prüfung nicht ausführbar: {type(e).__name__}: {str(e)[:300]}", {}


# ================================================================ Experimente (Agenten) =============================================
def _num(x):
    if isinstance(x, Fraction): return str(x) if x.denominator != 1 else int(x)
    return x


def experiment_intern(op, args):
    import sympy as sp
    a = args or {}
    if op == "symbolik":
        ann = a.get("annahmen") or {}; e = A.parse(a["ausdruck"], ann); akt = a.get("aktion", "vereinfache")
        var = lambda: next((s for s in e.free_symbols if str(s) == str(a.get("variable"))), sp.Symbol(str(a.get("variable", "x"))))
        if akt == "vereinfache": r = sp.simplify(e)
        elif akt == "expandiere": r = sp.expand(e)
        elif akt == "faktorisiere": r = sp.factor(e)
        elif akt == "ableitung": r = sp.diff(e, var(), int(a.get("ordnung", 1)))
        elif akt == "integral":
            gr_ = a.get("grenzen"); r = sp.integrate(e, (var(), A.parse(gr_[0]), A.parse(gr_[1]))) if gr_ else sp.integrate(e, var())
        elif akt == "reihe": r = sp.series(e, var(), A.parse(a.get("punkt", 0)), int(a.get("ordnung", 6)))
        elif akt == "grenzwert": r = sp.limit(e, var(), A.parse(a.get("punkt", 0)), a.get("richtung", "+-") if a.get("punkt") not in ("oo", "-oo") else "-")
        elif akt == "loese": r = sp.solve(e, var())
        elif akt == "numerisch": r = sp.N(e, int(min(100, a.get("stellen", 30))))
        elif akt == "differenz": r = sp.simplify(e - A.parse(a["ausdruck2"], ann))
        else: return {"fehler": "aktion: vereinfache|expandiere|faktorisiere|ableitung|integral|reihe|grenzwert|loese|numerisch|differenz"}
        return {"ergebnis": str(r)[:3000], "numerisch": (str(sp.N(r, 20)) if hasattr(r, "free_symbols") and not getattr(r, "free_symbols", True) else None)}
    if op == "auswerten":
        e = A.parse(a["ausdruck"]); out = []
        for pt in (a.get("punkte") or [])[:200]:
            sub = {s: A.parse(pt[str(s)]) for s in e.free_symbols if str(s) in pt}
            out.append(float(sp.N(e.subs(sub), 30)))
        return {"werte": out}
    if op == "minimiere":
        import numpy as np
        from scipy.optimize import minimize
        e = A.parse(a["ausdruck"]); B = a["bereich"]; names = sorted(B); syms = [next((s for s in e.free_symbols if str(s) == n), sp.Symbol(n)) for n in names]
        f = sp.lambdify(syms, e, "numpy"); lo = np.array([float(A.rational(B[n][0])) for n in names]); hi = np.array([float(A.rational(B[n][1])) for n in names])
        rng = np.random.default_rng(int(a.get("seed", 0))); best = None
        for _ in range(int(min(200, a.get("starts", 40)))):
            x0 = lo + rng.random(len(names)) * (hi - lo)
            r = minimize(lambda x: float(f(*x)), x0, bounds=list(zip(lo, hi)))
            if best is None or r.fun < best.fun: best = r
        return {"minimum": float(best.fun), "punkt": {n: float(v) for n, v in zip(names, best.x)}, "hinweis": "numerisch, nicht rigoros"}
    if op == "spin_spektrum":
        N = int(a["N"]); rand = a.get("rand", "periodisch"); H = S.operator(a["modell"], N, rand); sek = a.get("sektor"); anz = int(min(50, a.get("anzahl", 6)))
        sym = {"Sz": not S.kommutator(H, S.operator("Sz_gesamt", N, rand)), "S2": not S.kommutator(H, S.operator("S2_gesamt", N, rand)),
               "paritaet": not S.kommutator(H, S.operator("paritaet", N, rand))}
        out = {"N": N, "symmetrien": sym}
        if a.get("exakt"):
            try:
                spek, info = S.spektrum_exakt(H, N, sek)
                out["exakt"] = [{"wert": float((lo + hi) / 2), "vielfachheit": m, "rational": str(lo) if lo == hi else None} for lo, hi, m in spek[:anz]]
                out["dim"] = info["dim"]
            except A.FormelFehler as e: out["exakt_fehler"] = str(e)
        w, info = S.spektrum_numerisch(H, N, sek, anz); out.update(eigenwerte=w, dim=info["dim"], gap=(w[1] - w[0]) if len(w) > 1 else None, pro_spin=w[0] / N)
        return out
    if op == "spin_observable":
        N = int(a["N"]); rand = a.get("rand", "periodisch"); H = S.operator(a["modell"], N, rand); O = S.operator(a["operator"], N, rand)
        v, e0 = S.grundzustand_erwartung(H, O, N, a.get("sektor")); return {"erwartung": v, "E0": e0, "hinweis": "numerisch, Grundzustand"}
    if op == "spin_kommutator":
        N = int(a["N"]); rand = a.get("rand", "periodisch"); C = S.kommutator(S.operator(a["A"], N, rand), S.operator(a["B"], N, rand))
        return {"null": not C, "terme": len(C), "beispiel": S.zeichen(C, 6)}
    if op == "ising":
        L, M = int(a["L"]), int(a["M"]); r = a.get("rand", "periodisch"); g, B = I.zustandsdichte(L, M, r); e0, d0 = I.grundzustand(L, M, r)
        out = {"bindungen": B, "energie0": e0, "entartung0": d0, "g": g if len(g) <= 80 else g[:80] + ["..."]}
        if a.get("K"):
            out["lnZ_pro_spin"] = {str(k): float(sum(I.freie_energie_intervall(L, M, r, A.rational(k))) / 2) for k in a["K"][:20]}
        return out
    if op == "metrik":
        X, g = GR.metrik(a); return GR.kompakt(GR.kruemmung(X, g), X)
    if op == "gruppe":
        N = int(a["N"]); rep = a.get("rep", "F")
        out = {"dim": _num(G.dim(N, rep)), "casimir": _num(G.casimir(N, rep)), "index": _num(G.index(N, rep))}
        try: out["anomalie"] = _num(G.anomalie_koeff(N, rep))
        except A.FormelFehler: pass
        return out
    if op == "beta":
        N = int(a["N"]); b0, b1 = G.beta(N, a.get("materie", []))
        return {"b0": _num(b0), "b1": _num(b1), "asymptotisch_frei": b0 > 0, "banks_zaks": b0 > 0 and b1 < 0, "fixpunkt_g2_16pi2": _num(-b0 / b1) if b1 else None,
                "b0_float": float(b0), "b1_float": float(b1)}
    if op == "anomalien":
        return {k: _num(v) for k, v in G.anomalien(a["gruppen"], a["abelsch"], a["felder"]).items()}
    if op == "bell":
        m, st = BE.klassisch(a["koeffizienten"]); out = {"klassisch_max": _num(m), "strategie": st}
        if a.get("winkel_a"):
            v = BE.quantenwert(a["koeffizienten"], a["winkel_a"], a["winkel_b"]); out.update(quantenwert=str(v), quantenwert_float=float(v))
        return out
    if op == "schroedinger":
        return {"eigenwerte": QM.eigenwerte(a["potential"], a.get("masse", 1), a.get("intervall", ["-10", "10"]), int(a.get("gitter", 2000)), int(min(50, a.get("anzahl", 6)))),
                "hinweis": "finite Differenzen, numerisch"}
    if op == "dimension":
        return {"dimension": U.als_dict(U.dimension(A.parse(a["ausdruck"]), a.get("dimensionen") or {}))}
    return {"fehler": f"unbekannte op {op}"}


# ================================================================ Domäne ============================================================
class TheoPhys(Domain):
    name = "theophys"
    fachgebiet = "Mathematical Physics"
    recherche_ziel = ("Exakt lösbare und rigoros zertifizierbare Aussagen der theoretischen Physik: Spektren und Lücken von Quanten-Spinketten "
                      "(Heisenberg, XXZ, J1-J2, transversales Ising), exakte Zustandssummen klassischer Gittermodelle, exakte Lösungen der "
                      "Einstein-Gleichungen, Betafunktionen und Anomaliefreiheit von Eichtheorien, Bell-Ungleichungen; offene Vermutungen dazu.")
    recherche_sperre = []
    recherche_klassiker = ["Onsager crystal statistics two-dimensional Ising", "Bethe Theorie der Metalle Eigenwerte lineare Atomkette",
                           "Lieb Schultz Mattis two soluble models antiferromagnetic chain", "Majumdar Ghosh next-nearest-neighbor interaction linear chain",
                           "Haldane continuum dynamics 1-D Heisenberg antiferromagnet", "Affleck Kennedy Lieb Tasaki rigorous results valence-bond ground states",
                           "Gross Wilczek ultraviolet behavior non-abelian gauge theories", "Politzer reliable perturbative results strong interactions",
                           "Banks Zaks phase structure vector-like gauge theories massless fermions", "Caswell asymptotic behavior non-abelian gauge theories two-loop",
                           "Bell Einstein Podolsky Rosen paradox", "Clauser Horne Shimony Holt proposed experiment local hidden-variable",
                           "Tsirelson quantum generalizations Bell inequality", "Kramers Wannier statistics two-dimensional ferromagnet",
                           "Machacek Vaughn two-loop renormalization group equations general quantum field theory", "Kretschmann Schwarzschild curvature invariant"]
    recherche_crossref = True
    recherche_inspire = True
    # Experiment-Gewicht und Agenten (generische Hooks in discovery.py, planner.py, lab_loop.py)
    max_ops = 16; max_ops_folge = 12; experiment_runden = 2; experiment_gewicht = 1.5; hypothesen_agent = True; staerkung = 2
    forscher_rolle = "Du bist ein theoretischer Physiker in einem automatisierten Forschungslabor mit exaktem Code-Prüfer."
    strategien = {
        "numeriker": "Du gehst experimentell vor: viele Rechnungen über einen weiten Parameterbereich (N, Kopplungen, Gittergrößen), dann Muster, Skalierung in N und Extrapolation.",
        "symmetriker": "Du suchst zuerst Symmetrien und Erhaltungsgrößen (Kommutatoren, Sektoren, Gruppentheorie) und nutzt sie, um exakte, scharfe Aussagen zu finden.",
        "exakt": "Du willst Zertifikate: exakte Werte statt Gleitkomma, Allaussagen über Bereiche (schranke), und formale Beweise (\"beweis\": \"lean\"), wo der Typ sie anbietet.",
        "skeptiker": "Du misstraust der naheliegenden Antwort, prüfst Grenzfälle, Konventionen (Vorzeichen, Normierung, Einheiten) und suchst Gegenbeispiele.",
        "stoerungstheoretiker": "Du entwickelst in kleinen Parametern (Reihen, Grenzwerte), vergleichst Ordnungen und prüfst Resultate gegen exakte Rechnungen.",
        "skalierer": "Du denkst in Dimensionen, Grenzfällen und Asymptotik (thermodynamischer Limes, große Kopplung, klassischer Limes) und testest die entscheidende Vorhersage.",
    }
    kaskade = (("numeriker", "haiku"), ("symmetriker", "haiku"), ("exakt", "sonnet"), ("skeptiker", "sonnet"), ("stoerungstheoretiker", "sonnet"), ("skalierer", "opus"))

    kontext = ("Automatisiertes Labor für theoretische Physik. Konventionen: ħ = c = k_B = 1; Spin-1/2-Operatoren S = σ/2; Ising-Kopplung J = 1 mit "
               "H = −Σ s_i s_j; Allgemeine Relativität mit G = c = 1, Signatur (−,+,+,+), Riemann/Ricci wie in Wald/MTW; Betafunktion "
               "μ dg/dμ = −b0 g³/(16π²) − b1 g⁵/(16π²)², Normierung T(F) = ½; Bell-Korrelatoren B = Σ c_xy E(x,y). "
               "Teilgebiete: Spinketten (Spektren, Lücken, Entartungen, Symmetrien), klassisches Ising-Modell auf endlichen Gittern, Metriken und "
               "Krümmung, SU(N)-Eichtheorien (Darstellungen, Betafunktion, Anomalien), Bell-Ungleichungen, 1D-Quantenmechanik, symbolische Analysis "
               "und Schranken. Alles, was du behauptest, muss ein getypter Claim sein, den der Prüfer unabhängig nachrechnet; exakte und formal "
               "bewiesene Claims sind stärker als numerische. Eigene Experimente sind die Grundlage: rechne viel, bevor du behauptest.")
    primitive_doc = """Verfügbare Experimente (JSON {"op": ..., "args": {...}}), alle mit Zeitlimit; Formeln als Strings (z. B. "x^2*sin(x)", "pi/4", "3/2"):
- symbolik {aktion: vereinfache|expandiere|faktorisiere|ableitung|integral|reihe|grenzwert|loese|numerisch|differenz, ausdruck, variable?, punkt?, ordnung?, grenzen?: [a,b], ausdruck2?, annahmen?: {x: positiv|reell|ganz|nichtnegativ}}
- auswerten {ausdruck, punkte: [{x: "1/2", ...}]}           numerische Werte (30 Stellen)
- minimiere {ausdruck, bereich: {x: [lo, hi], ...}, starts?}  numerisches globales Minimum (Multistart), nicht rigoros
- spin_spektrum {modell, N, rand?: periodisch|offen, sektor?: {"up": k}, anzahl?, exakt?: true}  niedrigste Eigenwerte, Lücke, Symmetrien; exakt bis Dimension 400
    modell: {"name": "heisenberg"} | {"name": "xxz", "J", "Delta"} | {"name": "xyz", "Jx", "Jy", "Jz"} | {"name": "j1j2", "J1", "J2"} | {"name": "tfim", "J", "h"}
            | {"terme": [{"c": q | [re, im], "p": "XZ", "start": 0}], "translation": true}     (N <= 16)
- spin_observable {modell, N, rand?, operator, sektor?}   Grundzustandserwartung; operator: Sz_gesamt|Sx_gesamt|Sy_gesamt|S2_gesamt|paritaet|{"terme": ...}
- spin_kommutator {N, rand?, A, B}                       exakter Kommutator (A, B wie modell oder operator)
- ising {L, M, rand?, K?: ["1/2", ...]}                   exakte Zustandsdichte g[k] (k unzufriedene Bindungen), Grundzustand, ln Z / N bei K = βJ
- metrik {koordinaten: [...], diag: [...] | metrik: [[...]], annahmen?}   Ricci-Skalar, Kretschmann, nichtverschwindende Ricci/Einstein-Komponenten
- gruppe {N, rep: 1|F|Fbar|adj|S2|A2|S2bar|A2bar|{"dynkin": [...]}}   dim, Casimir, Index, Anomaliekoeffizient von SU(N)
- beta {N, materie: [{"art": dirac|weyl|komplex|reell, "rep": ..., "anzahl": n}]}   b0, b1, asymptotische Freiheit, Banks-Zaks
- anomalien {gruppen: {"su3": 3, "su2": 2}, abelsch: ["Y"], felder: [{"su3": rep, "su2": rep, "Y": q, "anzahl": n}]}   alle Anomaliesummen (linkshändige Weyl-Fermionen)
- bell {koeffizienten: [[...]], winkel_a?: [...], winkel_b?: [...]}   klassisches Maximum (+ Strategie), Quantenwert des Singuletts
- schroedinger {potential: "x^2/2", masse?, intervall?: [a, b], gitter?, anzahl?}   1D-Eigenwerte (finite Differenzen)
- dimension {ausdruck, dimensionen: {sym: {"M":1,"L":0,"T":0,"I":0,"Θ":0}}}   (c, hbar, G, k_B, e, epsilon0, mu0, m_e, m_p sind vordefiniert)"""
    claim_doc = """Prüfungstypen (nur diese Felder; Toleranzen/Genauigkeiten legt der Prüfer fest, solche Felder führen zur Ablehnung).
"beweis": "lean" ist bei den mit [lean] markierten Typen erlaubt und verlangt zusätzlich einen Lean-4-Beweis (Stufe proved_lean).
- {"typ": "identitaet", "lhs", "rhs", "annahmen"?, "dimensionen"?}                          exakt (CAS); mit dimensionen auch Dimensionsgleichheit
- {"typ": "grenzwert", "ausdruck", "variable", "punkt", "wert", "richtung"?: "+"|"-"}
- {"typ": "reihenkoeffizient", "ausdruck", "variable", "punkt", "ordnung": n, "koeffizient"}
- {"typ": "schranke", "ausdruck", "bereich": {x: [lo, hi]} (<= 3 Variablen), "untere": c | "obere": c}   STRIKT > c bzw. < c auf der ganzen Box (Intervall-Branch-and-Bound)
- {"typ": "dimension", "ausdruck", "dimensionen", "erwartet": {"M": .., "L": .., ...}}
- {"typ": "spektrum", "modell", "N", "rand"?, "sektor"?, "index": k, "intervall": [lo, hi] | "wert": exakte Zahl}   k-ter Eigenwert (ab 0, mit Vielfachheit);
     intervall höchstens 1e-6 relativ breit; exakt (rigoros) bis Dimension 400, darüber numerisch (observed)
- {"typ": "gap", "modell", "N", "rand"?, "sektor"?, "gap_min": q | "gap_max": q}          E_1 − E_0 > gap_min bzw. < gap_max (strikt)
- {"typ": "entartung", "modell", "N", "rand"?, "sektor"?, "index": k, "entartung": d}
- {"typ": "kommutator", "N", "rand"?, "A", "B"}                                          [A, B] = 0 exakt (Symmetrie / Erhaltungsgröße für dieses N)
- {"typ": "ising_zustandsdichte", "L", "M", "rand"?, "g": [...]}  |  {"typ": "ising_grundzustand", "L", "M", "rand"?, "energie", "entartung"} [lean, <= 12 Spins]
- {"typ": "ising_freie_energie", "L", "M", "rand"?, "K", "intervall": [lo, hi]}          ln Z / N, höchstens 1e-10 relativ breit
- {"typ": "feldgleichung", "koordinaten", "diag" | "metrik", "annahmen"?, "behauptung": "vakuum" | "einstein_lambda", "Lambda"?}
- {"typ": "kruemmungsinvariante", "koordinaten", "diag" | "metrik", "annahmen"?, "invariante": "ricci_skalar" | "kretschmann", "wert"}
- {"typ": "darstellung", "N", "rep", "groesse": "dim" | "casimir" | "index" | "anomalie", "wert"}
- {"typ": "beta_koeffizient", "N", "materie", "b0"?, "b1"?} [lean]   |  {"typ": "asymptotische_freiheit", "N", "materie"} [lean]  |  {"typ": "banks_zaks", "N", "materie"} [lean]
- {"typ": "anomaliefrei", "gruppen", "abelsch", "felder"} [lean]
- {"typ": "klassische_schranke", "koeffizienten", "schranke"} [lean]    Maximum über deterministische Strategien = schranke
- {"typ": "quantenwert", "koeffizienten", "winkel_a", "winkel_b", "wert"}  Singulett, exakt
- {"typ": "qm_eigenwert", "potential", "index", "wert", "masse"?, "intervall"?}           numerisch (observed), relative Toleranz 1e-6 im Prüfer"""

    # ---------------------------------------------------------------- Lab und Prüfer
    def run_op(self, op, args):
        try: return mit_zeitlimit(experiment_intern, op, args, sek=float(__import__("os").environ.get("THEOPHYS_ZEIT_EXPERIMENT", "300")))
        except Zeitueberschreitung as e: return {"fehler": str(e)}
        except Exception as e: return {"fehler": f"{type(e).__name__}: {str(e)[:300]}"}

    def check(self, p):
        try: return mit_zeitlimit(pruefe_intern, p)
        except Zeitueberschreitung as e: return False, f"Prüfung nicht ausführbar: {e}", {}
        except Exception as e: return False, f"Prüfung nicht ausführbar: {type(e).__name__}: {str(e)[:300]}", {}

    def gegenbeispiel(self, p, grund, beleg):
        return (beleg or {}).get("gegenbeispiel")

    def level(self, p):
        t = p.get("typ") if isinstance(p, dict) else None
        if t == "qm_eigenwert": return "observed"
        if t in ("spektrum", "gap"):
            try: return "observed" if _dim_reell(p) > S.DIM_EXAKT else "computed_rigorous"
            except Exception: return "observed"
        if t in LEAN_TYPEN and p.get("beweis") == "lean": return "proved_lean"
        return "computed_rigorous"

    def auto_verstaerkung(self, p):
        """Nach Bestätigung automatisch versuchen: derselbe Claim mit Lean-Beweis (nur wenn Lean installiert ist)."""
        if not isinstance(p, dict) or p.get("typ") not in LEAN_TYPEN or p.get("beweis") == "lean" or not LN.lean_bin(): return []
        if p["typ"] == "ising_grundzustand" and p.get("L", 99) * p.get("M", 99) > LEAN_ISING_MAX: return []
        return [dict(p, beweis="lean")]

    def consistent(self, antwort, p):
        return True

    # ---------------------------------------------------------------- Selbsttest
    def selftest(self):
        hb = {"name": "heisenberg"}; mg = {"name": "j1j2", "J1": 1, "J2": "1/2"}
        schw = {"koordinaten": ["t", "r", "th", "ph"], "diag": ["-(1-2*M/r)", "1/(1-2*M/r)", "r^2", "r^2*sin(th)^2"], "annahmen": {"M": "positiv", "r": "positiv"}}
        qcd6 = [{"art": "dirac", "rep": "F", "anzahl": 6}]; qcd16 = [{"art": "dirac", "rep": "F", "anzahl": 16}]
        sm = {"gruppen": {"su3": 3, "su2": 2}, "abelsch": ["Y"], "felder": G.STANDARDMODELL}
        sm_falsch = {**sm, "felder": [dict(f) for f in G.STANDARDMODELL[:4]] + [{"su3": "1", "su2": "1", "Y": "2", "anzahl": 1}]}
        chsh = [["1", "1"], ["1", "-1"]]
        T = [({"typ": "identitaet", "lhs": "sin(x)^2 + cos(x)^2", "rhs": "1"}, True),
             ({"typ": "identitaet", "lhs": "cosh(x)^2 - sinh(x)^2", "rhs": "1"}, True),
             ({"typ": "grenzwert", "ausdruck": "sin(x)/x", "variable": "x", "punkt": "0", "wert": "1"}, True),
             ({"typ": "reihenkoeffizient", "ausdruck": "exp(x)", "variable": "x", "punkt": "0", "ordnung": 3, "koeffizient": "1/6"}, True),
             ({"typ": "schranke", "ausdruck": "x^2 - x + 1", "bereich": {"x": ["-2", "2"]}, "untere": "1/2"}, True),
             ({"typ": "dimension", "ausdruck": "hbar*c/G", "dimensionen": {}, "erwartet": {"M": 2}}, True),
             ({"typ": "spektrum", "modell": hb, "N": 4, "index": 0, "wert": "-2"}, True),
             ({"typ": "spektrum", "modell": mg, "N": 8, "sektor": {"up": 4}, "index": 0, "intervall": ["-3.0000001", "-2.9999999"]}, True),
             ({"typ": "entartung", "modell": mg, "N": 8, "sektor": {"up": 4}, "index": 0, "entartung": 2}, True),
             ({"typ": "gap", "modell": hb, "N": 4, "gap_min": "9/10"}, True),
             ({"typ": "kommutator", "N": 6, "A": hb, "B": "S2_gesamt"}, True),
             ({"typ": "ising_grundzustand", "L": 3, "M": 3, "energie": -18, "entartung": 2}, True),
             ({"typ": "ising_zustandsdichte", "L": 2, "M": 3, "rand": "offen", "g": [2, 0, 12, 18, 18, 12, 0, 2]}, True),
             ({"typ": "ising_freie_energie", "L": 4, "M": 4, "K": "1/2", "intervall": ["1.06908544491", "1.06908544493"]}, True),
             ({"typ": "feldgleichung", **schw, "behauptung": "vakuum"}, True),
             ({"typ": "kruemmungsinvariante", **schw, "invariante": "kretschmann", "wert": "48*M^2/r^6"}, True),
             ({"typ": "darstellung", "N": 3, "rep": "adj", "groesse": "casimir", "wert": 3}, True),
             ({"typ": "beta_koeffizient", "N": 3, "materie": qcd6, "b0": 7, "b1": 26}, True),
             ({"typ": "banks_zaks", "N": 3, "materie": qcd16}, True),
             ({"typ": "anomaliefrei", **sm}, True),
             ({"typ": "klassische_schranke", "koeffizienten": chsh, "schranke": 2}, True),
             ({"typ": "quantenwert", "koeffizienten": chsh, "winkel_a": ["0", "pi/2"], "winkel_b": ["pi/4", "-pi/4"], "wert": "-2*sqrt(2)"}, True),
             ({"typ": "qm_eigenwert", "potential": "x^2/2", "index": 2, "wert": "2.5"}, True),
             # --- falsch: knapp daneben, Konventionsfehler, Regelverletzungen
             ({"typ": "identitaet", "lhs": "sin(x)^2 + cos(x)^2", "rhs": "1 + 1/10^9"}, False),
             ({"typ": "grenzwert", "ausdruck": "sin(x)/x", "variable": "x", "punkt": "0", "wert": "1.0001"}, False),
             ({"typ": "reihenkoeffizient", "ausdruck": "exp(x)", "variable": "x", "punkt": "0", "ordnung": 3, "koeffizient": "1/5"}, False),
             ({"typ": "schranke", "ausdruck": "x^2 - x + 1", "bereich": {"x": ["-2", "2"]}, "untere": "3/4"}, False),      # Gleichheit bei x = 1/2: strikt verletzt
             ({"typ": "dimension", "ausdruck": "hbar*c/G", "dimensionen": {}, "erwartet": {"M": 1}}, False),
             ({"typ": "spektrum", "modell": hb, "N": 4, "index": 0, "wert": "-2.0001"}, False),
             ({"typ": "spektrum", "modell": hb, "N": 4, "index": 0, "intervall": ["-3", "-1"]}, False),                    # zu breit
             ({"typ": "spektrum", "modell": {"name": "tfim", "J": 1, "h": 1}, "N": 4, "sektor": {"up": 2}, "index": 0, "intervall": ["-5.3", "-5.2"]}, False),
             ({"typ": "gap", "modell": hb, "N": 4, "gap_min": 1}, False),                                                  # Gleichheit, strikt verletzt
             ({"typ": "entartung", "modell": mg, "N": 8, "sektor": {"up": 4}, "index": 0, "entartung": 1}, False),
             ({"typ": "kommutator", "N": 4, "A": {"name": "tfim", "J": 1, "h": 1}, "B": "Sz_gesamt"}, False),
             ({"typ": "ising_grundzustand", "L": 3, "M": 3, "energie": -18, "entartung": 4}, False),
             ({"typ": "ising_zustandsdichte", "L": 2, "M": 3, "rand": "offen", "g": [2, 0, 12, 18, 18, 12, 2]}, False),
             ({"typ": "feldgleichung", **{**schw, "diag": ["-(1-2*M/r)", "1/(1-M/r)", "r^2", "r^2*sin(th)^2"]}, "behauptung": "vakuum"}, False),
             ({"typ": "kruemmungsinvariante", **schw, "invariante": "kretschmann", "wert": "12*M^2/r^6"}, False),
             ({"typ": "darstellung", "N": 3, "rep": "F", "groesse": "casimir", "wert": "3/4"}, False),                     # SU(2)-Wert: Konventionsfehler
             ({"typ": "beta_koeffizient", "N": 3, "materie": qcd6, "b0": 7, "b1": -26}, False),
             ({"typ": "asymptotische_freiheit", "N": 3, "materie": [{"art": "dirac", "rep": "F", "anzahl": 17}]}, False),
             ({"typ": "banks_zaks", "N": 3, "materie": [{"art": "dirac", "rep": "F", "anzahl": 8}]}, False),
             ({"typ": "anomaliefrei", **sm_falsch}, False),
             ({"typ": "klassische_schranke", "koeffizienten": chsh, "schranke": 3}, False),
             ({"typ": "quantenwert", "koeffizienten": chsh, "winkel_a": ["0", "pi/2"], "winkel_b": ["pi/4", "-pi/4"], "wert": "-2.83"}, False),
             ({"typ": "qm_eigenwert", "potential": "x^2/2", "index": 2, "wert": "2.5001"}, False),
             ({"typ": "qm_eigenwert", "potential": "x^2/2", "index": 2, "wert": "2.6", "toleranz": 1}, False),          # Toleranz-Lockerung
             ({"typ": "identitaet", "lhs": "__import__('os')", "rhs": "1"}, False),                                     # Regelverletzung
             ({"typ": "erfunden", "wert": 1}, False)]
        if LN.lean_bin():                                                                                            # Lean-Fälle nur mit Lean
            T += [({"typ": "anomaliefrei", **sm, "beweis": "lean"}, True), ({"typ": "klassische_schranke", "koeffizienten": chsh, "schranke": 2, "beweis": "lean"}, True),
                  ({"typ": "ising_grundzustand", "L": 3, "M": 3, "energie": -18, "entartung": 2, "beweis": "lean"}, True),
                  ({"typ": "banks_zaks", "N": 3, "materie": qcd16, "beweis": "lean"}, True),
                  ({"typ": "beta_koeffizient", "N": 3, "materie": qcd6, "b0": 7, "b1": 26, "beweis": "lean"}, True),
                  ({"typ": "anomaliefrei", **sm_falsch, "beweis": "lean"}, False)]
        return T

    # ---------------------------------------------------------------- Aussagen, Stärke, Red Team
    def describe(self, p, lang="de"):
        t = p.get("typ"); r = p.get("rand", "periodisch"); bc = "periodic" if r == "periodisch" else "open"
        lean = " (formally verified in Lean 4)" if p.get("beweis") == "lean" else ""
        sek = f", sector with {p['sektor']['up']} up spins" if isinstance(p.get("sektor"), dict) else ""
        m = p.get("modell"); mod = (m.get("name") or "custom Pauli Hamiltonian") + " " + _js({k: v for k, v in m.items() if k != "name"}) if isinstance(m, dict) else str(m)
        D = {
            "identitaet": lambda: f"Identity: {p['lhs']} = {p['rhs']}" + (f" (assumptions {_js(p['annahmen'])})" if p.get("annahmen") else "") + ".",
            "grenzwert": lambda: f"lim_{{{p['variable']} → {p['punkt']}{p.get('richtung', '') if p.get('richtung') in ('+', '-') else ''}}} {p['ausdruck']} = {p['wert']}.",
            "reihenkoeffizient": lambda: f"The coefficient of ({p['variable']} − {p['punkt']})^{p['ordnung']} in the expansion of {p['ausdruck']} is {p['koeffizient']}.",
            "schranke": lambda: f"For all {', '.join(f'{k} ∈ [{v[0]}, {v[1]}]' for k, v in p['bereich'].items())}: {p['ausdruck']} {'>' if 'untere' in p else '<'} {p.get('untere', p.get('obere'))}.",
            "dimension": lambda: f"{p['ausdruck']} has dimension {_js(p['erwartet'])} (M, L, T, I, Θ).",
            "spektrum": lambda: f"Spin-1/2 chain {mod}, N = {p['N']}, {bc} boundary{sek}: eigenvalue E_{p['index']} " + (f"= {p['wert']}" if 'wert' in p else f"∈ [{p['intervall'][0]}, {p['intervall'][1]}]") + ".",
            "gap": lambda: f"Spin-1/2 chain {mod}, N = {p['N']}, {bc} boundary{sek}: gap E_1 − E_0 " + (f"> {p['gap_min']}" if 'gap_min' in p else f"< {p['gap_max']}") + ".",
            "entartung": lambda: f"Spin-1/2 chain {mod}, N = {p['N']}, {bc} boundary{sek}: E_{p['index']} has multiplicity {p['entartung']}.",
            "kommutator": lambda: f"For N = {p['N']} ({bc}): [{_js(p['A'])}, {_js(p['B'])}] = 0 exactly.",
            "ising_zustandsdichte": lambda: f"Ising model (J = 1) on the {p['L']} × {p['M']} lattice, {bc}: density of states by number of unsatisfied bonds {p['g']}.",
            "ising_grundzustand": lambda: f"Ising model (J = 1) on the {p['L']} × {p['M']} lattice, {bc}: ground-state energy {p['energie']}, degeneracy {p['entartung']}{lean}.",
            "ising_freie_energie": lambda: f"Ising model on the {p['L']} × {p['M']} lattice, {bc}, K = {p['K']}: ln Z / N ∈ [{p['intervall'][0]}, {p['intervall'][1]}].",
            "feldgleichung": lambda: f"The metric {_js(p.get('diag') or p.get('metrik'))} in coordinates {p['koordinaten']} solves " + ("the vacuum Einstein equations R_ab = 0." if p['behauptung'] == 'vakuum' else f"G_ab + Λ g_ab = 0 with Λ = {p.get('Lambda')}."),
            "kruemmungsinvariante": lambda: f"For the metric {_js(p.get('diag') or p.get('metrik'))}: {'Ricci scalar' if p['invariante'] == 'ricci_skalar' else 'Kretschmann scalar'} = {p['wert']}.",
            "darstellung": lambda: f"SU({p['N']}) representation {_js(p['rep'])}: {p['groesse']} = {p['wert']}.",
            "beta_koeffizient": lambda: f"SU({p['N']}) gauge theory with matter {_js(p['materie'])}: " + ", ".join(f"{k} = {p[k]}" for k in ('b0', 'b1') if k in p) + f"{lean}.",
            "asymptotische_freiheit": lambda: f"SU({p['N']}) gauge theory with matter {_js(p['materie'])} is asymptotically free (b0 > 0){lean}.",
            "banks_zaks": lambda: f"SU({p['N']}) gauge theory with matter {_js(p['materie'])} has b0 > 0 and b1 < 0 (two-loop Banks–Zaks fixed point){lean}.",
            "anomaliefrei": lambda: f"Left-handed Weyl fermions {_js(p['felder'])} under {_js(p['gruppen'])} × U(1)^{len(p['abelsch'])} are free of gauge, mixed gravitational and Witten anomalies{lean}.",
            "klassische_schranke": lambda: f"The Bell expression with coefficients {p['koeffizienten']} has local (classical) maximum {p['schranke']}{lean}.",
            "quantenwert": lambda: f"For the singlet with angles {p['winkel_a']}, {p['winkel_b']}, the Bell expression {p['koeffizienten']} equals {p['wert']}.",
            "qm_eigenwert": lambda: f"Numerically, H = −d²/(2m dx²) + {p['potential']} on {p.get('intervall', ['-10', '10'])} (Dirichlet, m = {p.get('masse', 1)}) has E_{p['index']} = {p['wert']} (relative error ≤ 1e-6).",
        }
        try: return D[t]()
        except Exception: return "Check passed: " + _js(p)

    def relevanz(self, p):
        t = p.get("typ")
        return "hauptresultat" if t in HAUPT else ("beispiel" if t in BEISPIEL else "stuetze")

    def staerke(self, p):
        b = {"proved_lean": 2.0, "computed_rigorous": 1.0, "statistical": 0.5, "observed": 0.0}.get(self.level(p), 0)
        n = p.get("N") or (p.get("L", 0) * p.get("M", 0)) or 0
        vol = 0.0
        if p.get("typ") == "schranke":
            try: vol = sum(math.log10(1 + float(A.rational(v[1]) - A.rational(v[0]))) for v in p["bereich"].values())
            except Exception: pass
        return {"hauptresultat": 3, "stuetze": 2, "beispiel": 1}[self.relevanz(p)] + b + (math.log10(n) if n else 0) + vol

    def _schluessel(self, p, ohne):
        return _js({k: v for k, v in p.items() if k not in ohne and k != "beweis"})

    def widerspricht(self, p, q):
        if not isinstance(p, dict) or not isinstance(q, dict): return False
        t, u = p.get("typ"), q.get("typ")
        try:
            if t == u == "spektrum" and self._schluessel(p, {"intervall", "wert"}) == self._schluessel(q, {"intervall", "wert"}):
                ip = (A.rational(p["intervall"][0]), A.rational(p["intervall"][1])) if "intervall" in p else None
                iq = (A.rational(q["intervall"][0]), A.rational(q["intervall"][1])) if "intervall" in q else None
                if ip and iq: return ip[1] < iq[0] or iq[1] < ip[0]
                import sympy as sp
                vp = float(sp.N(A.parse(p["wert"]))) if "wert" in p else None; vq = float(sp.N(A.parse(q["wert"]))) if "wert" in q else None
                if vp is not None and vq is not None: return abs(vp - vq) > 1e-12 * max(1, abs(vp))
                v, i = (vp, iq) if vp is not None else (vq, ip)
                return not float(i[0]) - 1e-15 <= v <= float(i[1]) + 1e-15
            if t == u == "gap" and self._schluessel(p, {"gap_min", "gap_max"}) == self._schluessel(q, {"gap_min", "gap_max"}):
                lo = [A.rational(x["gap_min"]) for x in (p, q) if "gap_min" in x]; hi = [A.rational(x["gap_max"]) for x in (p, q) if "gap_max" in x]
                return bool(lo and hi and min(hi) <= max(lo))
            if t == u == "schranke" and A.parse(p["ausdruck"]) == A.parse(q["ausdruck"]) and ("untere" in p) != ("untere" in q):
                lo = A.rational(p["untere"] if "untere" in p else q["untere"]); hi = A.rational(p["obere"] if "obere" in p else q["obere"])
                bp, bq = p["bereich"], q["bereich"]
                ueber = set(bp) == set(bq) and all(max(A.rational(bp[k][0]), A.rational(bq[k][0])) <= min(A.rational(bp[k][1]), A.rational(bq[k][1])) for k in bp)
                return ueber and hi <= lo
            if t == u == "identitaet" and A.parse(p["lhs"]) == A.parse(q["lhs"]) and p.get("annahmen") == q.get("annahmen"):
                return A.punkte_test(A.parse(p["rhs"], p.get("annahmen")) - A.parse(q["rhs"], q.get("annahmen"))) is not None
            wertfeld = {"grenzwert": "wert", "reihenkoeffizient": "koeffizient", "kruemmungsinvariante": "wert", "darstellung": "wert", "quantenwert": "wert",
                        "klassische_schranke": "schranke", "dimension": "erwartet", "entartung": "entartung", "ising_zustandsdichte": "g"}
            if t == u and t in wertfeld and self._schluessel(p, {wertfeld[t]}) == self._schluessel(q, {wertfeld[t]}):
                a, b = p[wertfeld[t]], q[wertfeld[t]]
                if t in ("dimension",): return U.vektor(a) != U.vektor(b)
                if t in ("entartung", "ising_zustandsdichte"): return a != b
                return A.punkte_test(A.parse(a) - A.parse(b)) is not None or (A.parse(a) - A.parse(b)).is_number and A.parse(a) != A.parse(b)
            if t == u == "ising_grundzustand" and self._schluessel(p, {"energie", "entartung"}) == self._schluessel(q, {"energie", "entartung"}):
                return (p["energie"], p["entartung"]) != (q["energie"], q["entartung"])
            if t == u == "ising_freie_energie" and self._schluessel(p, {"intervall"}) == self._schluessel(q, {"intervall"}):
                return A.rational(p["intervall"][1]) < A.rational(q["intervall"][0]) or A.rational(q["intervall"][1]) < A.rational(p["intervall"][0])
            if t == u == "qm_eigenwert" and self._schluessel(p, {"wert"}) == self._schluessel(q, {"wert"}):
                a, b = float(A.rational(p["wert"])), float(A.rational(q["wert"])); return abs(a - b) > 2 * QM.TOL_REL * max(1, abs(a))
            if {t, u} == {"feldgleichung", "kruemmungsinvariante"}:
                f, k = (p, q) if t == "feldgleichung" else (q, p)
                gleich = all(f.get(x) == k.get(x) for x in ("koordinaten", "diag", "metrik", "annahmen"))
                return gleich and f["behauptung"] == "vakuum" and k["invariante"] == "ricci_skalar" and A.parse(k["wert"]) != 0 and A.parse(k["wert"]).is_number
            if t == u == "beta_koeffizient" and self._schluessel(p, {"b0", "b1"}) == self._schluessel(q, {"b0", "b1"}):
                return any(k in p and k in q and A.rational(p[k]) != A.rational(q[k]) for k in ("b0", "b1"))
            if {t, u} <= {"asymptotische_freiheit", "banks_zaks", "beta_koeffizient"} and t != u and p.get("N") == q.get("N") and _js(p.get("materie")) == _js(q.get("materie")):
                b = p if p["typ"] == "beta_koeffizient" else (q if q["typ"] == "beta_koeffizient" else None)
                if b is None: return False
                o = q if b is p else p
                if "b0" in b and A.rational(b["b0"]) <= 0: return True
                return o["typ"] == "banks_zaks" and "b1" in b and A.rational(b["b1"]) >= 0
        except Exception:
            return False
        return False

    def angriffe(self, p, n=3, seed=0):
        """Gegen-Prüfungen, die nur bestehen können, wenn p falsch ist (widerspricht(p, Gegenprüfung) = True)."""
        t = p.get("typ"); out = []
        try:
            if t == "spektrum" and "intervall" in p:
                lo, hi = A.rational(p["intervall"][0]), A.rational(p["intervall"][1]); w = max(hi - lo, Fraction(1, 10 ** 9))
                for a_, b_ in ((hi + w / 10, hi + w), (lo - w, lo - w / 10)):
                    out.append({"idee": "Eigenwert direkt neben dem behaupteten Intervall", "pruefung": {**{k: v for k, v in p.items() if k != "intervall"}, "intervall": [str(a_), str(b_)]}})
            if t == "gap" and "gap_min" in p: out.append({"idee": "Lücke kleiner als behauptet", "pruefung": {**{k: v for k, v in p.items() if k != "gap_min"}, "gap_max": p["gap_min"]}})
            if t == "gap" and "gap_max" in p: out.append({"idee": "Lücke größer als behauptet", "pruefung": {**{k: v for k, v in p.items() if k != "gap_max"}, "gap_min": p["gap_max"]}})
            if t == "schranke":
                r = experiment_intern("minimiere", {"ausdruck": p["ausdruck"] if "untere" in p else f"-({p['ausdruck']})", "bereich": p["bereich"], "starts": 30})
                pt = r["punkt"]; eps = Fraction(1, 10 ** 6)
                box = {k: [str(Fraction(v).limit_denominator(10 ** 9) - eps), str(Fraction(v).limit_denominator(10 ** 9) + eps)] for k, v in pt.items()}
                box = {k: [str(max(A.rational(b[0]), A.rational(p["bereich"][k][0]))), str(min(A.rational(b[1]), A.rational(p["bereich"][k][1])))] for k, b in box.items()}
                gegen = {"typ": "schranke", "ausdruck": p["ausdruck"], "bereich": box, ("obere" if "untere" in p else "untere"): p.get("untere", p.get("obere"))}
                out.append({"idee": "Schranke am numerischen Extremum unterbieten (CEGIS-Suche)", "pruefung": gegen})
            if t == "klassische_schranke":
                s = A.rational(p["schranke"]); out += [{"idee": "klassisches Maximum höher", "pruefung": {**{k: v for k, v in p.items() if k != "beweis"}, "schranke": str(s + 1)}},
                                                       {"idee": "klassisches Maximum niedriger", "pruefung": {**{k: v for k, v in p.items() if k != "beweis"}, "schranke": str(s - 1)}}]
            if t == "qm_eigenwert":
                w = A.rational(p["wert"]); out.append({"idee": "Eigenwert um 1e-3 verschoben", "pruefung": {**p, "wert": str(w * Fraction(1001, 1000) + Fraction(1, 1000))}})
            if t == "entartung":
                out.append({"idee": "andere Vielfachheit", "pruefung": {**p, "entartung": p["entartung"] + 1}})
            if t == "ising_grundzustand":
                out.append({"idee": "andere Entartung", "pruefung": {**{k: v for k, v in p.items() if k != "beweis"}, "entartung": p["entartung"] + 2}})
        except Exception:
            pass
        return out[:max(n, 2)]

    # ---------------------------------------------------------------- Planer und Modell
    def optionen(self, frage, state):
        from ..planner import generische_optionen
        O = generische_optionen(frage, state); k = len(O)
        best = [c for c in state.get("claims", []) if c.get("status") == "bestätigt"]
        neu = [{"art": "exakt_zertifizieren", "kosten": 1, "erwarteter_gewinn": 0.6, "max_ops": 8,
                "beschreibung": "Kleines System exakt rechnen und als rigorosen Claim (exakter Wert, scharfes Intervall, Schranke) zertifizieren.",
                "vorgehen": "Wähle die kleinste Systemgröße bzw. den einfachsten Fall, in dem die Frage exakt entscheidbar ist; rechne exakt (exakt: true) und formuliere einen rigorosen Claim."},
               {"art": "groesse_erhoehen", "kosten": 3, "erwarteter_gewinn": 0.5, "max_ops": 24,
                "beschreibung": "Viele Experimente über wachsende Systemgröße / Ordnung / Parameter, dann Muster und Skalierung.",
                "vorgehen": "Rechne die Größe für eine Folge von N (bzw. L, Ordnung, Kopplung), extrapoliere und formuliere den stärksten Claim, den das Muster stützt."},
               {"art": "konsistenzpruefung", "kosten": 2, "erwarteter_gewinn": 0.45, "max_ops": 12,
                "beschreibung": "Symmetrie, Erhaltungsgröße, Dimension oder bekannter Grenzfall als exakter Claim (kommutator, dimension, grenzwert).",
                "vorgehen": "Prüfe zuerst Symmetrien (spin_kommutator), Dimensionen und Grenzfälle; zertifiziere die tragende Konsistenzaussage."}]
        lean_offen = [c for c in best if (c.get("pruefung") or {}).get("typ") in LEAN_TYPEN and c.get("level") != "proved_lean"]
        if lean_offen:
            neu.append({"art": "lean_beweis", "kosten": 1, "erwarteter_gewinn": 0.7, "max_ops": 4,
                        "beschreibung": f"Formaler Lean-Beweis für {lean_offen[-1]['id']} (\"beweis\": \"lean\").",
                        "vorgehen": f"Reiche den Claim [{lean_offen[-1]['id']}] mit \"beweis\": \"lean\" ein: {_js(lean_offen[-1]['pruefung'])[:400]}"})
        for j, o in enumerate(neu, k + 1): o.update(id=f"O{j}", faden_id=frage.get("faden_id") or frage.get("id"), frage_id=frage.get("id"))
        return O + neu

    def parameter(self):
        return {"hbar_c_kB": ("1", "natural units ħ = c = k_B = 1; in gravity G = c = 1"),
                "spin": ("1/2", "spin operators S = σ/2; chain Hamiltonians as stated per claim; periodic boundary requires N ≥ 3 (nearest neighbour)"),
                "ising_J": ("1", "Ising coupling, H = −Σ_<ij> s_i s_j, K = βJ"),
                "signature": ("(−,+,+,+)", "metric signature; Riemann tensor R^a_bcd = ∂_c Γ^a_db − ∂_d Γ^a_cb + ΓΓ − ΓΓ, R_bd = R^a_bad"),
                "beta_norm": ("T(F) = 1/2", "μ dg/dμ = −b0 g³/(16π²) − b1 g⁵/(16π²)²; two-loop without Yukawa/quartic couplings"),
                "interval_width": (str(float(BREITE_REL)), "maximal relative width of a certified eigenvalue interval"),
                "exact_dim": (str(S.DIM_EXAKT), "largest real matrix dimension with rigorous (characteristic polynomial) spectra"),
                "qm_grid": (f"{QM.N_PRUEFER}, {2 * QM.N_PRUEFER}", "verifier grids for 1D Schrödinger eigenvalues, Richardson extrapolation, relative tolerance 1e-6"),
                "bnb_boxes": (str(MAX_BOXEN), "maximal boxes in interval branch-and-bound (128-bit arb)")}


DOMAIN = TheoPhys()
