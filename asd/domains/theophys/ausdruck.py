"""Formeln aus Agenten-JSON sicher einlesen und rigoros auswerten.

parse(): nur Zahlen, Bezeichner, + - * / ^ ** ( ) , und eine feste Liste mathematischer Funktionen. Jeder andere Bezeichner wird ein
Symbol. Kein Attributzugriff, keine Strings, kein '__'. Gleitkommazahlen werden exakt rational gelesen (0.1 -> 1/10).
arb_eval(): rigorose Intervall-Auswertung eines SymPy-Ausdrucks über einer Box (python-flint arb, Ball-Arithmetik)."""
import re
from fractions import Fraction

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, convert_xor, rationalize

FUNKTIONEN = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot, "sec": sp.sec, "csc": sp.csc, "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
              "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh, "coth": sp.coth, "asinh": sp.asinh, "acosh": sp.acosh, "atanh": sp.atanh,
              "exp": sp.exp, "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt, "Abs": sp.Abs, "abs": sp.Abs, "sign": sp.sign, "gamma": sp.gamma,
              "zeta": sp.zeta, "erf": sp.erf, "factorial": sp.factorial, "binomial": sp.binomial, "besselj": sp.besselj, "bessely": sp.bessely,
              "polylog": sp.polylog, "Heaviside": sp.Heaviside, "atan2": sp.atan2, "floor": sp.floor, "ceiling": sp.ceiling, "Min": sp.Min, "Max": sp.Max,
              "re": sp.re, "im": sp.im, "conjugate": sp.conjugate}
KONSTANTEN = {"pi": sp.pi, "E": sp.E, "I": sp.I, "oo": sp.oo, "EulerGamma": sp.EulerGamma, "Catalan": sp.Catalan, "GoldenRatio": sp.GoldenRatio}
ANNAHMEN = {"positiv": {"positive": True}, "positive": {"positive": True}, "reell": {"real": True}, "real": {"real": True},
            "nichtnegativ": {"nonnegative": True}, "nonnegative": {"nonnegative": True}, "ganz": {"integer": True}, "integer": {"integer": True},
            "negativ": {"negative": True}, "komplex": {}, "natuerlich": {"integer": True, "positive": True}}
ZEICHEN = re.compile(r"^[A-Za-z0-9_+\-*/^().,\s]*$")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
MAXLEN = 4000
TRANS = standard_transformations + (convert_xor, rationalize)


class FormelFehler(ValueError):
    pass


def symbole(namen, annahmen=None):
    annahmen = annahmen or {}
    out = {}
    for n in namen:
        a = annahmen.get(n, "")
        if a and a not in ANNAHMEN: raise FormelFehler(f"unbekannte Annahme {a!r} für {n} (erlaubt: {sorted(ANNAHMEN)})")
        out[n] = sp.Symbol(n, **ANNAHMEN.get(a, {}))
    return out


def parse(s, annahmen=None):
    """Formel-String -> SymPy-Ausdruck (exakt). Wirft FormelFehler bei allem, was keine reine Formel ist."""
    if isinstance(s, bool): raise FormelFehler("Wahrheitswert ist keine Formel")
    if isinstance(s, (int, Fraction)): return sp.Rational(s)
    if isinstance(s, float): return sp.Rational(str(s))
    if not isinstance(s, str): raise FormelFehler(f"Formel muss ein String sein, nicht {type(s).__name__}")
    if len(s) > MAXLEN: raise FormelFehler("Formel zu lang")
    if "__" in s or not ZEICHEN.match(s): raise FormelFehler(f"unerlaubte Zeichen in {s[:80]!r}")
    if re.search(r"[A-Za-z_]\w*\s*\.", s): raise FormelFehler("Attributzugriff nicht erlaubt")
    if re.search(r"\.\s*[A-Za-z_]", s): raise FormelFehler("Attributzugriff nicht erlaubt")
    namen = set(NAME.findall(s))
    if namen & {"Integer", "Float", "Rational", "Symbol", "Function", "lambda"}: raise FormelFehler("reservierter Bezeichner")
    lokal = {}
    sym = symbole([n for n in namen if n not in FUNKTIONEN and n not in KONSTANTEN], annahmen)
    lokal.update(sym); lokal.update({n: FUNKTIONEN[n] for n in namen if n in FUNKTIONEN}); lokal.update({n: KONSTANTEN[n] for n in namen if n in KONSTANTEN})
    glob = {"Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational, "Symbol": sp.Symbol, "__builtins__": {}}
    try: e = parse_expr(s, local_dict=lokal, global_dict=glob, transformations=TRANS, evaluate=True)
    except Exception as ex: raise FormelFehler(f"Formel nicht lesbar: {type(ex).__name__}: {str(ex)[:120]}")
    if not isinstance(e, sp.Basic): raise FormelFehler("keine Formel")
    return e


def rational(x):
    """Exakte rationale Zahl aus int, Bruch-String ("3/4"), Dezimal-String oder Formel ohne Symbole."""
    if isinstance(x, bool): raise FormelFehler("Wahrheitswert ist keine Zahl")
    if isinstance(x, int): return Fraction(x)
    if isinstance(x, float): return Fraction(str(x))
    if isinstance(x, str):
        try: return Fraction(x.strip())
        except (ValueError, ZeroDivisionError): pass
    e = parse(x)
    if not e.is_Rational: raise FormelFehler(f"{x!r} ist keine rationale Zahl")
    return Fraction(int(e.p), int(e.q))


def ist_null(e, zeit_vereinfachen=True):
    """Symbolischer Nullnachweis. -> True (bewiesen 0), False (nachweislich != 0 an einem rationalen Punkt), None (unentschieden)."""
    e = sp.sympify(e)
    if e == 0: return True
    for f in (sp.simplify, lambda x: sp.simplify(sp.expand(sp.trigsimp(x))), lambda x: sp.nsimplify(sp.simplify(sp.expand_log(sp.powsimp(x, force=False))))):
        try:
            if f(e) == 0: return True
        except Exception: pass
    try:
        if e.equals(0) is True: return True
    except Exception: pass
    return None


def punkte_test(e, symbole_, n=12, seed=7):
    """Falsifikation: Auswertung an rationalen Punkten (hohe Präzision). -> (punkt, wert) eines klar von 0 verschiedenen Werts oder None."""
    import random
    rnd = random.Random(seed); syms = sorted(e.free_symbols, key=str)
    for _ in range(n):
        pt = {}
        for s in syms:
            if s.is_integer: v = sp.Integer(rnd.randint(1, 9))
            elif s.is_positive or s.is_nonnegative: v = sp.Rational(rnd.randint(1, 40), rnd.randint(1, 13))
            else: v = sp.Rational(rnd.randint(-40, 40), rnd.randint(1, 13))
            pt[s] = v
        try: w = sp.N(e.subs(pt), 50)
        except Exception: continue
        if w.is_number and not w.has(sp.nan, sp.zoo) and abs(complex(w)) > 1e-30: return {str(k): str(v) for k, v in pt.items()}, str(sp.N(w, 15))
    return None


# ---------------------------------------------------------------- rigorose Intervall-Auswertung ----------------------------------
def _arb():
    import flint
    flint.ctx.prec = 128
    return flint


def arb_intervall(lo, hi):
    F = _arb(); lo, hi = Fraction(lo), Fraction(hi)
    mid = (lo + hi) / 2; rad = (hi - lo) / 2
    m = F.arb(F.fmpq(mid.numerator, mid.denominator)); r = F.arb(F.fmpq(rad.numerator, rad.denominator))
    return m + r * F.arb(0, 1)                                     # [mid - rad, mid + rad], Rundung nach außen


def arb_eval(e, box):
    """Rigorose Einschließung von e über box {Symbol-Name: (lo, hi)}. Wirft FormelFehler bei nicht unterstützten Teilen."""
    F = _arb()
    def ev(x):
        if x.is_Integer: return F.arb(int(x))
        if x.is_Rational: return F.arb(F.fmpq(int(x.p), int(x.q)))
        if x is sp.pi: return F.arb.pi()
        if x is sp.E: return F.arb(1).exp()
        if x.is_Symbol:
            if str(x) not in box: raise FormelFehler(f"Variable {x} ohne Bereich")
            return arb_intervall(*box[str(x)])
        if x.is_Add:
            s = F.arb(0)
            for a in x.args: s = s + ev(a)
            return s
        if x.is_Mul:
            s = F.arb(1)
            for a in x.args: s = _mul(s, ev(a))
            return s
        if x.is_Pow:
            b, n = x.args
            if n.is_Integer:
                bb = ev(b); k = int(n)
                p = _ipow(F, bb, abs(k))
                return p if k >= 0 else F.arb(1) / p
            if n == sp.Rational(1, 2): return ev(b).sqrt()
            bb = ev(b)
            if not bb > 0: raise FormelFehler("nicht-ganzzahlige Potenz mit nicht positiver Basis")
            return (ev(n) * bb.log()).exp()
        fn = {sp.exp: "exp", sp.log: "log", sp.sin: "sin", sp.cos: "cos", sp.tan: "tan", sp.sinh: "sinh", sp.cosh: "cosh", sp.tanh: "tanh",
              sp.atan: "atan", sp.sqrt: "sqrt"}.get(x.func)
        if fn and len(x.args) == 1:
            a = ev(x.args[0])
            if fn == "log" and not a > 0: raise FormelFehler("log eines nicht sicher positiven Intervalls")
            return getattr(a, fn)()
        if x.func == sp.Abs: return _abs(ev(x.args[0]))
        raise FormelFehler(f"Intervall-Auswertung unterstützt {x.func} nicht")
    return ev(sp.sympify(e))


def _abs(x):
    """|x| als Intervall [0, max] bzw. ±x (arb abs liefert für Bälle um 0 einen Ball, der negative Werte enthält)."""
    lo, hi = arb_grenzen(x)
    if lo >= 0: return x
    if hi <= 0: return -x
    return arb_intervall(0, max(-lo, hi))


def _ipow(F, x, k):
    """x^k für ganze k >= 0 durch Multiplikation (arb ** int liefert für Bälle um 0 NaN); gerade k über |x| (enger, nicht negativ)."""
    if k == 0: return F.arb(1)
    basis = _abs(x) if k % 2 == 0 else x; out = F.arb(1)
    while k:
        if k & 1: out = _mul(out, basis)
        basis = _mul(basis, basis) if k > 1 else basis; k >>= 1
    return out


def _mul(a, b):
    """Intervall-Produkt über die Endpunkte (enger als Ball-Arithmetik): [min, max] der vier Endpunktprodukte, rigoros nach außen gerundet."""
    al, ah = arb_grenzen(a); bl, bh = arb_grenzen(b)
    p = [al * bl, al * bh, ah * bl, ah * bh]
    return arb_intervall(min(p), max(p))


def arb_grenzen(a):
    """arb -> (untere, obere) Schranke als Fraction, rigoros: Mittelpunkt und Radius sind exakte Binärzahlen, also [mid − rad, mid + rad] exakt."""
    if not a.is_finite(): raise FormelFehler("Intervall-Auswertung nicht endlich")
    m, r = _exakt(a.mid()), _exakt(a.rad())
    return m - r, m + r


def _exakt(x):
    """Exakte Binärzahl (arb mit Radius 0) als Fraction."""
    m, e = x.man_exp()
    return Fraction(int(m)) * (Fraction(2) ** int(e))


def _frac(x):
    """Kompatibilität: untere Schranke eines arb (siehe arb_grenzen)."""
    return arb_grenzen(x)[0]
