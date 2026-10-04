"""Lean-4-Beweise für diskrete und ganzzahlige Aussagen der Domäne (Lean 4 Core, ohne Mathlib).

Grundsatz wie asd/lean_check.py: Die Lean-AUSSAGE erzeugt der Code aus dem geprüften Claim (rationale Daten werden mit dem Hauptnenner
auf ganze Zahlen skaliert); kein Agent schreibt Lean. Taktik fest `decide` (Kernel-Auswertung, kein native_decide, kein sorry).
`#print axioms` wird ausgewertet; erlaubt sind nur propext, Quot.sound, Classical.choice (meist: keine Axiome).
Ohne Lean-Installation: Ergebnis bestanden=None ("nicht ausführbar"), nie "bestanden"."""
import hashlib, math, os, re, subprocess, tempfile
from fractions import Fraction

from ...lean_check import lean_bin, aussage_klassische_schranke

ERLAUBTE_AXIOME = {"propext", "Quot.sound", "Classical.choice"}
KOPF = "set_option maxRecDepth 100000\nset_option maxHeartbeats 0\n\n"
_CACHE = {}


def hauptnenner(xs):
    d = 1
    for x in xs: d = d * Fraction(x).denominator // math.gcd(d, Fraction(x).denominator)
    return d


def lit(n):
    n = int(n); return f"({n})" if n >= 0 else f"(-{-n})"


def summe(terme):
    """terme: Liste von Listen ganzer Zahlen (Faktoren eines Produkts) -> Lean-Int-Ausdruck."""
    if not terme: return "(0 : Int)"
    return " + ".join("(" + " * ".join(lit(f) for f in t) + " : Int)" for t in terme)


def skaliere_produkte(terme):
    """Summe von Produkten rationaler Faktoren -> ganzzahlige Faktorlisten (Lean multipliziert und addiert selbst) und Skalenfaktor:
    Σ_t Π f = (Lean-Summe) / skala, mit skala = d^K (d Hauptnenner aller Faktoren, K längstes Produkt)."""
    terme = [[Fraction(x) for x in t] for t in terme]
    if not terme: return [], Fraction(1)
    d = hauptnenner([x for t in terme for x in t]); K = max(len(t) for t in terme)
    out = [[Fraction(d) ** (K - len(t))] + [x * d for x in t] for t in terme]
    assert all(x.denominator == 1 for t in out for x in t)
    return [[int(x) for x in t] for t in out], Fraction(d) ** K


def satz_gleich(name, ausdruck, wert):
    return f"theorem {name} : {ausdruck} = {lit(wert)} := by decide\n#print axioms {name}\n"


def satz_kleiner(name, a, b):
    return f"theorem {name} : ({a} : Int) < {b} := by decide\n#print axioms {name}\n"


def satz_ising(name, n, kanten, e0):
    """∀ Spins: E >= e0, und ∃ Spins mit E = e0; E = -Σ_(i,j) s_i s_j (J = 1)."""
    bs = " ".join(f"b{i}" for i in range(n))
    E = " + ".join(f"s b{i} * s b{j}" for i, j in kanten)
    return (f"def s (b : Bool) : Int := if b then 1 else -1\n\n"
            f"theorem {name}_schranke : ∀ {bs} : Bool, -({E}) ≥ {lit(e0)} := by decide\n"
            f"theorem {name}_erreicht : ∃ {bs} : Bool, -({E}) = {lit(e0)} := by decide\n"
            f"#print axioms {name}_schranke\n#print axioms {name}_erreicht\n")


def pruefe_quelltext(src, timeout=None):
    """Kompiliert src. -> {"bestanden": True|False|None, "grund", "axiome", "sha256"}."""
    timeout = timeout or float(os.environ.get("THEOPHYS_LEAN_ZEIT", "600"))
    if re.search(r"\bsorry\b|\badmit\b|native_decide|\baxiom\b|implemented_by|extern", src): return {"bestanden": False, "grund": "unerlaubtes Konstrukt im Lean-Quelltext"}
    h = hashlib.sha256(src.encode()).hexdigest()
    if h in _CACHE: return _CACHE[h]
    lean = lean_bin()
    if not lean: return {"bestanden": None, "grund": "nicht ausführbar: Lean nicht verfügbar (elan/lean installieren)", "sha256": h}
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "Claim.lean"), "w").write(KOPF + src)
        try: r = subprocess.run([lean, "Claim.lean"], cwd=d, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired: return {"bestanden": None, "grund": f"Zeitüberschreitung (> {timeout:.0f} s) in Lean", "sha256": h}
    out = (r.stdout + r.stderr).strip()
    ax = sorted({a.strip() for grp in re.findall(r"depends on axioms: \[([^\]]*)\]", out) for a in grp.split(",") if a.strip()})
    fremd = [a for a in ax if a not in ERLAUBTE_AXIOME]
    ok = r.returncode == 0 and "error" not in out.lower() and not fremd
    res = {"bestanden": ok, "axiome": ax, "sha256": h, "lean_quelle": KOPF + src,
           "grund": ("Lean 4 (Kernel, decide) bestätigt " + ", ".join(re.findall(r"^theorem (\w+)", src, re.M)) + (f"; Axiome {ax}" if ax else "; ohne Axiome"))
           if ok else f"Lean lehnt ab (exit {r.returncode}){'; fremde Axiome ' + str(fremd) if fremd else ''}: {out[-300:]}"}
    _CACHE[h] = res
    return res


def bell_quelltext(koeffizienten, schranke):
    return aussage_klassische_schranke({"koeffizienten": koeffizienten, "schranke": schranke}).replace("TAKTIK", "decide")
