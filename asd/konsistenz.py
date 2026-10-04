"""Konsistenzprüfung des Wissensstands eines Projekts (domänenunabhängig).

1. Paarweise: zwei BESTÄTIGTE Claims, die laut Domain.widerspricht() nicht beide wahr sein können, sind ein Prüferfehler oder eine
   Modell-Inkonsistenz. Beide werden "angefochten" (Wahrheitspflege über asd/tms.py, abhängige Claims werden mit ungültig).
2. Hypothesen gegen Claims: eine Hypothese, die vorläufig widerlegt ist, deren Ziel-Prüfung der Prüfer aber bestätigt hat (oder umgekehrt
   endgültig widerlegt, aber als Claim bestätigt), zeigt einen Widerspruch zwischen Experiment und Prüfer.
3. Optional --recheck: jeder bestätigte Claim wird erneut geprüft (inklusive Lean-Beweisen bei "beweis": "lean").

  python -m asd.konsistenz <projekt> [--domain D] [--recheck] [--anwenden]   -> projects/<projekt>/konsistenz.md, Exit 1 bei Befund
In der Labor-Schleife und in `asd.cli pruefe` läuft Punkt 1 automatisch für jeden neuen Claim."""
import json, sys, time


def _best(state):
    return [c for c in state.get("claims", []) if c.get("status") == "bestätigt" and isinstance(c.get("pruefung"), dict)]


def _w(D, p, q):
    try: return bool(D.widerspricht(p, q)) or bool(D.widerspricht(q, p))
    except Exception: return False


def widersprueche(state, D, cid=None):
    """-> [(id_a, id_b)] widersprüchlicher bestätigter Claims (nur Paare mit cid, falls angegeben)."""
    B = _best(state); out = []
    for i, a in enumerate(B):
        for b in B[i + 1:]:
            if cid and cid not in (a["id"], b["id"]): continue
            if _w(D, a["pruefung"], b["pruefung"]): out.append((a["id"], b["id"]))
    return out


def neuer_claim(state, D, cid):
    """Nach dem Eintragen eines Claims: Widersprüche zu allen bestätigten Claims suchen und beide Seiten anfechten.
    -> [(a, b, abhängig_ungültig)] (leer, wenn konsistent)."""
    from . import tms
    out = []
    for a, b in widersprueche(state, D, cid):
        betroffen = []
        for x, y in ((a, b), (b, a)):
            c = next(c for c in state["claims"] if c["id"] == x)
            if c.get("status") == "bestätigt":
                betroffen += tms.widerrufen(state, x, f"Inkonsistenz: widerspricht dem bestätigten Claim {y} (Domain.widerspricht)", status="angefochten")
                c["inkonsistent_mit"] = y
        out.append((a, b, betroffen))
    return out


def hypothesen_befunde(state):
    from .omni_policies import claim_hash
    best = {claim_hash([{k: v for k, v in c["pruefung"].items() if k != "beweis"}]): c["id"] for c in _best(state)}
    out = []
    for h in state.get("hypothesen", []):
        if not isinstance(h.get("pruefung"), dict): continue
        cid = best.get(claim_hash([{k: v for k, v in h["pruefung"].items() if k != "beweis"}]))
        vl = (h.get("vorlaeufig") or {}).get("status")
        if cid and vl == "vorlaeufig_widerlegt":
            out.append((h["id"], cid, "Experimente widersprechen der Hypothese, der Prüfer bestätigt ihre Ziel-Prüfung: Vorhersage oder Experiment prüfen"))
        if cid and h.get("status") == "widerlegt":
            out.append((h["id"], cid, "Hypothese endgültig widerlegt, ihre Ziel-Prüfung ist aber als Claim bestätigt"))
    return out


def main():
    import argparse
    from .domains.base import get_domain
    ap = argparse.ArgumentParser(); ap.add_argument("projekt"); ap.add_argument("--domain", default="")
    ap.add_argument("--recheck", action="store_true"); ap.add_argument("--anwenden", action="store_true", help="Widersprüche im Zustand als angefochten markieren")
    a = ap.parse_args(); D = get_domain(a.domain or a.projekt); D.projekt = a.projekt; p = f"projects/{a.projekt}/state.json"; s = json.load(open(p))
    L = [f"# Consistency report ({a.projekt}, {time.strftime('%Y-%m-%d %H:%M')})", ""]
    W = widersprueche(s, D); H = hypothesen_befunde(s)
    L += ["## Contradicting confirmed claims", ""] + ([f"- {x} ⟂ {y}" for x, y in W] or ["- none"]) + ["", "## Hypotheses vs. verifier", ""]
    L += [f"- {h} / {c}: {g}" for h, c, g in H] or ["- none"]
    fehl = []
    if a.recheck:
        L += ["", "## Re-check of confirmed claims", ""]
        for c in _best(s):
            ok, why, _ = D.check(c["pruefung"])
            if not ok: fehl.append(c["id"])
            L.append(f"- [{'OK' if ok else 'FAIL'}] {c['id']} ({c.get('level')}): {str(why)[:160]}")
    if a.anwenden and W:
        for x, y in W:
            for cid in (x, y):
                c = next(c for c in s["claims"] if c["id"] == cid)
                if c.get("status") == "bestätigt":
                    from . import tms
                    tms.widerrufen(s, cid, f"Inkonsistenz ({x} ⟂ {y})", status="angefochten")
        json.dump(s, open(p, "w"), ensure_ascii=False, indent=1, default=str)
    n = len(W) + len(H) + len(fehl)
    L += ["", f"**{'consistent' if not n else f'{n} finding(s)'}**"]
    open(f"projects/{a.projekt}/konsistenz.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))
    sys.exit(1 if n else 0)


if __name__ == "__main__":
    main()
