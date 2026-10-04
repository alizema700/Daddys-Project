"""Dimensionsanalyse mit Basisdimensionen M, L, T, I, Θ (exakte rationale Exponenten).

dimension(e, dims): Summanden müssen dieselbe Dimension haben, Argumente von exp/log/sin/... müssen dimensionslos sein,
Potenzen mit dimensionsbehafteter Basis brauchen rationale Exponenten. Verletzung -> FormelFehler (Inkonsistenz).
KONSTANTEN: Standardsymbole mit festen Dimensionen (c, hbar, G, k_B, e, epsilon0, mu0, m_e, m_p), überschreibbar."""
from fractions import Fraction

import sympy as sp

from .ausdruck import FormelFehler

BASIS = ("M", "L", "T", "I", "Θ")
KONSTANTEN = {"c": {"L": 1, "T": -1}, "hbar": {"M": 1, "L": 2, "T": -1}, "h": {"M": 1, "L": 2, "T": -1}, "G": {"M": -1, "L": 3, "T": -2},
              "k_B": {"M": 1, "L": 2, "T": -2, "Θ": -1}, "e": {"I": 1, "T": 1}, "epsilon0": {"M": -1, "L": -3, "T": 4, "I": 2},
              "mu0": {"M": 1, "L": 1, "T": -2, "I": -2}, "m_e": {"M": 1}, "m_p": {"M": 1}}
DIMLOS_FUNKTIONEN = (sp.exp, sp.log, sp.sin, sp.cos, sp.tan, sp.sinh, sp.cosh, sp.tanh, sp.asin, sp.acos, sp.atan, sp.atanh, sp.asinh, sp.acosh)


def vektor(d):
    if not isinstance(d, dict) or set(d) - set(BASIS) - {"Theta"}: raise FormelFehler(f"Dimension: Objekt mit Schlüsseln aus {BASIS}")
    d = {("Θ" if k == "Theta" else k): v for k, v in d.items()}
    from .ausdruck import rational
    return tuple(rational(d.get(k, 0)) for k in BASIS)


def dimension(e, dims):
    D = {k: vektor(v) for k, v in {**KONSTANTEN, **(dims or {})}.items()}
    null = tuple(Fraction(0) for _ in BASIS)
    def dm(x):
        if x.is_Number or x in (sp.pi, sp.E, sp.I): return null
        if x.is_Symbol:
            if str(x) not in D: raise FormelFehler(f"Dimension von {x} nicht angegeben")
            return D[str(x)]
        if x.is_Add:
            ds = {dm(a) for a in x.args}
            if len(ds) != 1: raise FormelFehler(f"Inkonsistenz: Summanden mit verschiedener Dimension in {sp.sstr(x)[:120]}")
            return ds.pop()
        if x.is_Mul:
            v = list(null)
            for a in x.args: v = [p + q for p, q in zip(v, dm(a))]
            return tuple(v)
        if x.is_Pow:
            b, n = x.args; db = dm(b)
            if db == null:
                if dm(n) != null: raise FormelFehler("Exponent nicht dimensionslos")
                return null
            if not n.is_Rational: raise FormelFehler("dimensionsbehaftete Basis braucht rationalen Exponenten")
            q = Fraction(int(n.p), int(n.q)); return tuple(p * q for p in db)
        if x.func in DIMLOS_FUNKTIONEN or x.func in (sp.Abs,):
            da = dm(x.args[0])
            if x.func is sp.Abs: return da
            if da != null: raise FormelFehler(f"Argument von {x.func.__name__} nicht dimensionslos")
            return null
        if x.func is sp.sqrt: return tuple(p / 2 for p in dm(x.args[0]))
        raise FormelFehler(f"Dimensionsanalyse unterstützt {x.func} nicht")
    return dm(sp.sympify(e))


def als_dict(v):
    return {k: (str(x) if x.denominator != 1 else int(x)) for k, x in zip(BASIS, v) if x != 0}
