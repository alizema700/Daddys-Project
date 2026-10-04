"""Hypothesen mit VORLÄUFIGEM Status: Experimente werden laufend gegen die Vorhersagen einer Hypothese ausgewertet; der Status steuert,
was das Labor als Nächstes tut. Endgültig entscheidet weiterhin nur der Prüfer (Domain.check).

Eine Hypothese (state["hypothesen"]) wird von Menschen ("we postulate", origin HUMAN-PROPOSED) oder Agenten (AGENT:<rolle>) aufgestellt:
  {"id": "H3", "text": "...", "frage": "F12" | None,
   "vorhersagen": [{"op": "<Experiment>", "wenn": {<arg>: <wert>, ...}, "feld": "pfad.im.ergebnis", "relation": "<=", "wert": 0}],
   "pruefung": {<Claim der Domäne, der die Hypothese zertifizieren würde>} | None}
- Jede Vorhersage wird gegen JEDES passende Experiment (gleiche op, Argumente ⊇ "wenn") ausgewertet: +1 stützend, -1 widersprechend.
  Die Toleranz für "≈" ist hier fest (TOL_REL); sie kommt nie aus der Hypothese. Fehlerhafte Experimente zählen nicht.
- Vorläufiger Status (nur Steuerung, nie ein Resultat, Stufe "hypothesis"):
    offen               keine Evidenz
    schwach_gestuetzt   1 stützendes Experiment, kein widersprechendes
    vorlaeufig_gestuetzt  >= MIN_STUETZ stützende, kein widersprechendes
    umstritten          widersprechende vorhanden, aber mehr stützende
    vorlaeufig_widerlegt  widersprechende >= stützende (Falsifikation wiegt schwerer: Punktzahl = stützend - 3 * widersprechend)
- Endgültiger Status (h["status"]): offen | bestätigt (Prüfer hat h["pruefung"] bzw. einen gleichen Claim bestätigt) |
  widerlegt (Prüfer lehnt h["pruefung"] mit Gegenbeispiel ab, oder präregistriertes Kriterium aus asd.cli nicht erfüllt).
- Richtung (richtung()): beweisen (vorläufig gestützt) > entscheiden (umstritten) > verfeinern (vorläufig widerlegt) > testen (offen),
  menschliche Hypothesen vor Agenten-Hypothesen. Der Modus geht als Auftrag an die Forscher und als Option an den Planer.

  python -m asd.hypothesen add  --projekt P [--domain D] --text "..." [--frage F3] [--vorhersagen-json '[...]'] [--pruefung-json '{...}']
  python -m asd.hypothesen list --projekt P          # Status, Evidenz, empfohlene Richtung
  python -m asd.hypothesen bewerte --projekt P       # alle protokollierten Experimente (runde*.json, asd.cli) erneut auswerten
"""
import glob, hashlib, json, os, time
from fractions import Fraction

TOL_REL = 1e-6                 # feste Toleranz für "≈" (vorläufige Auswertung, nicht der Prüfer)
MIN_STUETZ = 2                 # ab so vielen stützenden Experimenten ohne Widerspruch: vorläufig gestützt
GEWICHT_WIDERSPRUCH = 3        # Falsifikation wiegt schwerer als Bestätigung
RELATIONEN = ("<", "<=", ">", ">=", "==", "!=", "≈", "in", "enthaelt")
MODUS = {"offen": "testen", "schwach_gestuetzt": "testen", "vorlaeufig_gestuetzt": "beweisen", "umstritten": "entscheiden",
         "vorlaeufig_widerlegt": "verfeinern"}
PRIO = {"beweisen": 0, "entscheiden": 1, "verfeinern": 2, "testen": 3}
MAX_STILLSTAND = 3             # nach so vielen bearbeiteten Runden ohne Statusänderung ruht eine Hypothese (kein Endlos-Steuern)


def runde_abschliessen(h, runde, status_vorher):
    """Nach einer Runde, in der h die Richtung bestimmt hat: Stillstand zählen (ändert sich der Status nicht, ruht h nach MAX_STILLSTAND Runden)."""
    h.setdefault("runden", []).append(runde)
    neu_ = h.get("status") if h.get("status", "offen") != "offen" else (h.get("vorlaeufig") or {}).get("status")
    h["stillstand"] = 0 if neu_ != status_vorher else h.get("stillstand", 0) + 1


def now(): return time.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- Anlegen ---------------------------------------------------------
def validiere_vorhersage(v):
    f = []
    if not isinstance(v, dict): return ["Vorhersage ist kein Objekt"]
    if not isinstance(v.get("op"), str) or not v["op"]: f.append("op fehlt")
    if not isinstance(v.get("feld"), str) or not v["feld"]: f.append("feld fehlt")
    if v.get("relation") not in RELATIONEN: f.append(f"relation muss eine von {RELATIONEN} sein")
    if "wert" not in v: f.append("wert fehlt")
    if "wenn" in v and not isinstance(v["wenn"], dict): f.append("wenn muss ein Objekt sein")
    extra = set(v) - {"op", "wenn", "feld", "relation", "wert", "beschreibung"}
    if extra: f.append(f"unbekannte Felder {sorted(extra)} (Toleranzen legt der Code fest)")
    return f


def neu(state, text, vorhersagen=None, pruefung=None, frage=None, origin="HUMAN-PROPOSED", agent="mensch", kriterium=None, verfeinert_aus=None):
    if not text or len(str(text).strip()) < 10: raise ValueError("Hypothese braucht einen Text (>= 10 Zeichen)")
    vorhersagen = list(vorhersagen or [])
    fehler = [f"Vorhersage {i + 1}: {e}" for i, v in enumerate(vorhersagen) for e in validiere_vorhersage(v)]
    if fehler: raise ValueError("; ".join(fehler))
    if pruefung is not None and not isinstance(pruefung, dict): raise ValueError("pruefung muss ein Claim-Objekt sein")
    hs = state.setdefault("hypothesen", []); hid = f"H{len(hs) + 1}"
    kern = {"text": text, "vorhersagen": vorhersagen, "pruefung": pruefung, "kriterium": kriterium}
    h = {"id": hid, "agent": agent, "origin": origin, "text": text, "frage": frage or (kriterium or {}).get("frage"), "vorhersagen": vorhersagen,
         "pruefung": pruefung, "sha256": hashlib.sha256(json.dumps(kern, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
         "ts": now(), "status": "offen", "evidenz": [], "vorlaeufig": {"status": "offen", "stuetzend": 0, "widersprechend": 0, "punkte": 0}}
    if kriterium: h["kriterium"] = kriterium
    if verfeinert_aus: h["verfeinert_aus"] = verfeinert_aus
    hs.append(h); return h


def aktiv(h):
    """Hypothese, die das Labor noch steuern kann: nicht endgültig entschieden und mit Vorhersagen oder Ziel-Prüfung."""
    return h.get("status", "offen") == "offen" and bool(h.get("vorhersagen") or h.get("pruefung"))


# ---------------------------------------------------------------- Auswertung ------------------------------------------------------
def _zahl(x):
    if isinstance(x, bool): return None
    if isinstance(x, (int, float, Fraction)): return Fraction(x) if not isinstance(x, float) else x
    if isinstance(x, str):
        try: return Fraction(x.strip())
        except (ValueError, ZeroDivisionError): pass
        try: return float(x)
        except ValueError: return None
    return None


def _feld(erg, pfad):
    for teil in str(pfad).split("."):
        if isinstance(erg, list): erg = erg[int(teil)]
        elif isinstance(erg, dict): erg = erg[teil]
        else: raise KeyError(teil)
    return erg


def _vergleich(ist, rel, soll):
    if rel == "in":
        lo, hi = (_zahl(soll[0]), _zahl(soll[1])) if isinstance(soll, (list, tuple)) and len(soll) == 2 else (None, None)
        z = _zahl(ist)
        if None in (lo, hi, z): return None
        return lo <= z <= hi
    if rel == "enthaelt":
        if isinstance(ist, (list, str)): return soll in ist
        return None
    a, b = _zahl(ist), _zahl(soll)
    if a is None or b is None:                                       # nicht-numerisch: nur Gleichheit
        if rel == "==": return ist == soll
        if rel == "!=": return ist != soll
        return None
    if rel == "≈": return abs(float(a) - float(b)) <= max(TOL_REL * max(abs(float(a)), abs(float(b))), 1e-12)
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b}[rel]


def passt(v, op, args):
    if v["op"] != op: return False
    args = args or {}
    return all(k in args and (args[k] == w or _zahl(args[k]) is not None and _zahl(args[k]) == _zahl(w)) for k, w in (v.get("wenn") or {}).items())


def bewerte_eintrag(v, op, args, erg):
    """-> (+1 | -1 | None, istwert). None: passt nicht, Fehler oder Feld fehlt (zählt nicht)."""
    if not passt(v, op, args) or not isinstance(erg, (dict, list)) or (isinstance(erg, dict) and "fehler" in erg): return None, None
    try: ist = _feld(erg, v["feld"])
    except (KeyError, IndexError, ValueError, TypeError): return None, None
    r = _vergleich(ist, v["relation"], v["wert"])
    return (None if r is None else (1 if r else -1)), ist


def vorlaeufig(h):
    s = sum(1 for e in h.get("evidenz", []) if e["ergebnis"] > 0); w = sum(1 for e in h.get("evidenz", []) if e["ergebnis"] < 0)
    if w == 0: st = "offen" if s == 0 else ("schwach_gestuetzt" if s < MIN_STUETZ else "vorlaeufig_gestuetzt")
    else: st = "umstritten" if s > w else "vorlaeufig_widerlegt"
    return {"status": st, "stuetzend": s, "widersprechend": w, "punkte": s - GEWICHT_WIDERSPRUCH * w}


def _exp_key(op, args, i):
    return hashlib.sha256(json.dumps([op, args, i], sort_keys=True, default=str).encode()).hexdigest()[:16]


def bewerte_experimente(state, experimente, quelle=""):
    """experimente: [{"op", "args", "ergebnis", "id"?}]. Wertet alle aktiven Hypothesen aus; dasselbe Experiment zählt je Vorhersage einmal.
    -> [(hid, alter_status, neuer_status)] für jede Statusänderung."""
    aenderungen = []
    for h in state.get("hypothesen", []):
        if not h.get("vorhersagen") or h.get("status", "offen") != "offen": continue
        h.setdefault("evidenz", []); alt = (h.get("vorlaeufig") or {}).get("status", "offen"); seen = {e["key"] for e in h["evidenz"]}
        for e in experimente:
            if not isinstance(e, dict) or "op" not in e: continue
            for i, v in enumerate(h["vorhersagen"]):
                k = _exp_key(e["op"], e.get("args"), i)
                if k in seen: continue
                r, ist = bewerte_eintrag(v, e["op"], e.get("args"), e.get("ergebnis"))
                if r is None: continue
                seen.add(k)
                h["evidenz"].append({"key": k, "vorhersage": i, "op": e["op"], "args": e.get("args"), "ist": ist if isinstance(ist, (int, float, str, bool)) else str(ist)[:200],
                                     "relation": v["relation"], "soll": v["wert"], "ergebnis": r, "quelle": quelle or e.get("quelle", ""), "experiment": e.get("id"), "ts": now()})
        h["vorlaeufig"] = vorlaeufig(h)
        if h["vorlaeufig"]["status"] != alt: aenderungen.append((h["id"], alt, h["vorlaeufig"]["status"]))
    return aenderungen


def abgleich_claims(state):
    """Hypothesen, deren Ziel-Prüfung schon als bestätigter Claim vorliegt, endgültig bestätigen. -> [(hid, claim_id)]"""
    from .omni_policies import claim_hash
    best = {}
    for c in state.get("claims", []):
        if c.get("status") != "bestätigt": continue
        for p in [c.get("pruefung")] + list(c.get("alle_pruefungen") or []) + list(c.get("verstaerkt_von") and [c["verstaerkt_von"]] or []):
            if isinstance(p, dict): best.setdefault(claim_hash([_ohne_beweis(p)]), c["id"])
    out = []
    for h in state.get("hypothesen", []):
        if h.get("status", "offen") == "offen" and isinstance(h.get("pruefung"), dict):
            cid = best.get(claim_hash([_ohne_beweis(h["pruefung"])]))
            if cid:
                h["status"] = "bestätigt"; h["ausgewertet_durch"] = cid; h["ausgewertet"] = now(); out.append((h["id"], cid))
    return out


def _ohne_beweis(p):
    return {k: v for k, v in p.items() if k != "beweis"}


def verifizieren(D, h):
    """Ziel-Prüfung der Hypothese dem PRÜFER vorlegen. -> (ok, grund, gegenbeispiel). Bei Ablehnung mit Gegenbeispiel: endgültig widerlegt."""
    p = h.get("pruefung")
    if not isinstance(p, dict): return False, "keine Ziel-Prüfung", None
    ok, why, _, gb = D.check_cegis(p)
    if not ok and gb:
        h["status"] = "widerlegt"; h["gegenbeispiel"] = gb; h["ausgewertet"] = now(); h["ausgewertet_durch"] = "Prüfer (Gegenbeispiel)"
    elif not ok:
        h.setdefault("pruefversuche", []).append({"ts": now(), "grund": str(why)[:300]})
    return bool(ok), why, gb


# ---------------------------------------------------------------- Richtung ---------------------------------------------------------
def richtung(state, nur_frage=None):
    """Welche Hypothese als Nächstes, in welchem Modus? -> {"hypothese", "modus", "frage", "grund", "status"} oder None."""
    kand = []
    for h in state.get("hypothesen", []):
        if not aktiv(h) or (nur_frage and h.get("frage") != nur_frage): continue
        vl = h.get("vorlaeufig") or vorlaeufig(h); m = MODUS.get(vl["status"], "testen")
        if m == "verfeinern" and h.get("verfeinert_durch"): continue           # schon durch eine verfeinerte Hypothese ersetzt
        if h.get("stillstand", 0) >= MAX_STILLSTAND: continue                  # ruht: so viele Runden ohne Statusänderung
        mensch = 0 if str(h.get("origin", "")).startswith("HUMAN") else 1
        kand.append((PRIO[m], mensch, len(h.get("runden", [])), -abs(vl["punkte"]), h["id"], h, m, vl))
    if not kand: return None
    _, _, _, _, _, h, m, vl = sorted(kand, key=lambda x: x[:5])[0]
    grund = {"beweisen": f"{vl['stuetzend']} Experimente stützen {h['id']}, keines widerspricht: jetzt zertifizieren (Prüfer/Lean)",
             "entscheiden": f"{h['id']} ist umstritten ({vl['stuetzend']} stützend, {vl['widersprechend']} widersprechend): entscheidendes Experiment",
             "verfeinern": f"{vl['widersprechend']} Experiment(e) widersprechen {h['id']}: Gültigkeitsbereich bestimmen und verfeinern",
             "testen": f"{h['id']} hat {'keine' if not vl['stuetzend'] else 'erst eine'} Evidenz: Vorhersagen experimentell testen"}[m]
    return {"hypothese": h["id"], "modus": m, "frage": h.get("frage"), "grund": grund, "status": vl["status"]}


def auftrag(h, modus):
    """Arbeitsauftrag an die Forscher (wird an die Frage angehängt)."""
    vl = h.get("vorlaeufig") or vorlaeufig(h)
    kopf = (f"HYPOTHESE {h['id']} ({'von Menschen aufgestellt' if str(h.get('origin', '')).startswith('HUMAN') else 'agent-generiert'}; "
            f"vorläufiger Status {vl['status']}: {vl['stuetzend']} stützende, {vl['widersprechend']} widersprechende Experimente; NICHT geprüft): {h['text']}")
    vh = f"\nVorhersagen (werden per Code gegen jedes Experiment ausgewertet): {json.dumps(h.get('vorhersagen') or [], ensure_ascii=False)[:1500]}" if h.get("vorhersagen") else ""
    zp = f"\nZiel-Prüfung, die die Hypothese zertifizieren würde: {json.dumps(h['pruefung'], ensure_ascii=False)[:1500]}" if h.get("pruefung") else ""
    wid = [e for e in h.get("evidenz", []) if e["ergebnis"] < 0][-5:]
    wtxt = ("\nWidersprechende Experimente: " + "; ".join(f"{e['op']} {json.dumps(e['args'], ensure_ascii=False)[:120]} -> {e['ist']} (vorhergesagt {e['relation']} {e['soll']})" for e in wid)) if wid else ""
    tun = {"testen": "Führe Experimente aus, die genau diese Vorhersagen testen (passende op und Argumente), über einen möglichst weiten, aber relevanten Parameterbereich. "
                     "Formuliere danach die stärkste prüfbare Behauptung, die die Experimente stützen.",
           "beweisen": "Die Experimente stützen die Hypothese. Formuliere jetzt die prüfbare Behauptung, die sie ZERTIFIZIERT: exakt/rigoros statt numerisch, "
                       "möglichst allgemein, und mit formalem Beweis (\"beweis\": \"lean\"), wo der Prüfungstyp das anbietet.",
           "entscheiden": "Die Experimente widersprechen sich. Wiederhole die strittigen Experimente mit höherer Genauigkeit/größerem System und entscheide mit einer "
                          "prüfbaren Behauptung, welche Seite gilt.",
           "verfeinern": "Experimente widersprechen der Hypothese. Bestimme, wo sie gilt und wo nicht (Grenzfall, Parameterbereich), und formuliere eine "
                         "EINGESCHRÄNKTE, prüfbare Behauptung, die die widersprechenden Fälle ausschließt."}[modus]
    return f"{kopf}{vh}{zp}{wtxt}\nAUFTRAG ({modus}): {tun}"


def frage_fuer(state, h, faden_of=None):
    """Offene Frage, an der die Hypothese bearbeitet wird; legt bei Bedarf eine neue an (Faden der ursprünglichen Frage)."""
    q = next((x for x in state.get("fragen", []) if x["id"] == h.get("frage")), None)
    if q is not None and q.get("status") == "offen": return q
    qid = f"F{len(state.setdefault('fragen', [])) + 1}"
    fid = (faden_of(q) if (q is not None and faden_of) else (q or {}).get("faden_id")) or qid
    nq = {"id": qid, "frage": f"Hypothese {h['id']}: {h['text']}", "status": "offen", "faden_id": fid, "quelle": f"hypothese:{h['id']}",
          "hypothese": h["id"], "machbarkeit": 0.7}
    state["fragen"].append(nq); h["frage"] = qid
    return nq


def wissen_abschnitt(state):
    """Kontext für Agenten: vorläufige Hypothesenstände. Leer, wenn es keine Hypothesen gibt (Prompts anderer Projekte bleiben unverändert)."""
    hs = state.get("hypothesen") or []
    zeilen = []
    for h in hs:
        if not (h.get("vorhersagen") or h.get("pruefung")): continue
        vl = h.get("vorlaeufig") or vorlaeufig(h)
        st = h.get("status", "offen"); st = st if st != "offen" else f"vorläufig {vl['status']} ({vl['stuetzend']}:{vl['widersprechend']})"
        zeilen.append(f"- [{h['id']}] {st}: {h['text'][:200]}")
    return ("Hypothesen (Status aus Experimenten bzw. Prüfer; vorläufige Stände sind KEINE Resultate):\n" + "\n".join(zeilen)) if zeilen else ""


def tabelle(state):
    L = ["| Hypothese | Herkunft | endgültig | vorläufig | stützend | widersprechend | Richtung | Text |", "|---|---|---|---|---|---|---|---|"]
    r = richtung(state) or {}
    for h in state.get("hypothesen", []):
        vl = h.get("vorlaeufig") or vorlaeufig(h)
        rr = MODUS.get(vl["status"], "testen") if aktiv(h) else "-"
        L.append(f"| {h['id']}{' ←' if r.get('hypothese') == h['id'] else ''} | {h.get('origin', '?')} | {h.get('status', 'offen')} | {vl['status']} | {vl['stuetzend']} | "
                 f"{vl['widersprechend']} | {rr} | {h['text'][:100].replace('|', '/')} |")
    if r: L.append(f"\nNächste Richtung: {r['hypothese']} -> {r['modus']} ({r['grund']})")
    return "\n".join(L)


# ---------------------------------------------------------------- Protokollierte Experimente -------------------------------------
def protokollierte_experimente(projekt_dir, state):
    """Alle Experimente mit Ergebnis: Labor-Runden (runde*.json) und asd.cli (state["experimente"], sofern das Ergebnis gespeichert ist)."""
    ex = []
    for f in sorted(glob.glob(f"{projekt_dir}/runde*.json")):
        try: r = json.load(open(f))
        except (OSError, json.JSONDecodeError): continue
        for e in r.get("experimente", []): ex.append({"op": e.get("op"), "args": e.get("args"), "ergebnis": e.get("ergebnis"), "id": f"{os.path.basename(f)[:-5]}:E{e.get('id')}",
                                                   "quelle": os.path.basename(f)})
    for i, e in enumerate(state.get("experimente", []), 1):
        if "ergebnis" in e: ex.append({"op": e.get("op"), "args": e.get("args"), "ergebnis": e["ergebnis"], "id": f"E{i}", "quelle": "asd.cli"})
    return ex


def main():
    import argparse
    ap = argparse.ArgumentParser(prog="python -m asd.hypothesen"); ap.add_argument("befehl", choices=["add", "list", "bewerte"])
    ap.add_argument("--projekt", required=True); ap.add_argument("--domain", default=""); ap.add_argument("--text", default="")
    ap.add_argument("--frage", default=""); ap.add_argument("--vorhersagen-json", default=""); ap.add_argument("--pruefung-json", default="")
    ap.add_argument("--agent", default="mensch"); a = ap.parse_args()
    d = f"projects/{a.projekt}"; p = f"{d}/state.json"
    if not os.path.exists(p): raise SystemExit(f"{p} fehlt (erst ein Projekt anlegen, z. B. mit asd.lab_loop)")
    s = json.load(open(p))
    lade = lambda x: (json.loads(x) if x.strip()[:1] in "[{" else json.load(open(x))) if x else None
    if a.befehl == "add":
        h = neu(s, a.text, lade(a.vorhersagen_json), lade(a.pruefung_json), a.frage or None,
                origin="HUMAN-PROPOSED" if a.agent == "mensch" else f"AGENT:{a.agent}", agent=a.agent)
        with open(f"{d}/prereg.md", "a") as f:
            f.write(f"\n## Hypothese {h['id']} ({now()}, {h['origin']}, vor ihrer Auswertung)\n- Aussage: {h['text']}\n- Vorhersagen: {json.dumps(h['vorhersagen'], ensure_ascii=False)}\n"
                    f"- Ziel-Prüfung: {json.dumps(h['pruefung'], ensure_ascii=False)}\n- sha256: {h['sha256']}\n")
        print(f"HYPOTHESE {h['id']} angelegt (sha256 {h['sha256'][:16]})")
    if a.befehl in ("add", "bewerte"):
        ae = bewerte_experimente(s, protokollierte_experimente(d, s), quelle="nachträglich")
        bc = abgleich_claims(s)
        for hid, alt, neu_ in ae: print(f"{hid}: {alt} -> {neu_}")
        for hid, cid in bc: print(f"{hid}: bestätigt durch {cid}")
        json.dump(s, open(p, "w"), ensure_ascii=False, indent=1, default=str)
    print(tabelle(s))


if __name__ == "__main__":
    main()
