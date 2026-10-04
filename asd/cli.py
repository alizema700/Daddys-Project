"""Frozen harness: Laborschritte und Verifier als CLI, aufrufbar von Agenten (z. B. unter Omnigent).

  python -m asd.cli <befehl> --domain <d> [--projekt <p>] [--agent <name>] ...

Befehle: selftest | wissen | fragen [--add-json f] | plan | options --frage <id> | waehle (wähle) --option <id> --grund "..."
         | experiment --spec-json <datei|json> (oder --op/--args) | pruefe (prüfe) --claim-json <datei|json>
         | redteam --claim <id> [--auto] [--gegen-json <datei|json>] | folgefragen --aus <runde|claim|frage> --json <datei|json>
         | reopen --annahme <id> --claim <id> --grund "..." | doku | status | claim --claim <id>
         | hypothese --text "..." [--kriterium-json ..] [--vorhersagen-json ..] [--pruefung-json ..] [--frage F]
         | hypothesen   (vorläufiger Status jeder Hypothese aus den Experimenten + Richtung, die der Code daraus ableitet)

Nur `prüfe` schreibt bestätigte Claims in state.json. Jede Aktion wird nach projects/<p>/record.jsonl angehängt.
Der Verifier selbst (Domain.check) bleibt unverändert; die CLI ruft ihn nur auf."""
import argparse, json, os, sys, time

from .domains.base import get_domain
from .lab_loop import Project, wissen_text, faden_of, faden_fortschritt, now
from . import planner

T0 = time.time()                                                   # Start dieses CLI-Aufrufs (Dauer je Befehl ins Protokoll)
LEAK_CFG = os.environ.get("ASD_LEAK_GUARD", "omni/leak_guard.json")


def leak_terms(D):
    t = [s.lower() for s in getattr(D, "recherche_sperre", [])]
    if os.path.exists(LEAK_CFG):
        cfg = json.load(open(LEAK_CFG)); t += [s.lower() for s in cfg.get("begriffe", [])]
    return t


def wissen_gefiltert(P, D):
    """wissen_text ohne gesperrte Quellen (Leckschutz für Replay-Läufe)."""
    terms = leak_terms(D)
    if not terms: return wissen_text(P)
    alt = P.s["wissen"]
    P.s["wissen"] = [w for w in alt if not any(x in (str(w.get("quelle", "")) + " " + str(w.get("text", "")) + " " + str(w.get("url", ""))).lower() for x in terms)]
    try: return wissen_text(P)
    finally: P.s["wissen"] = alt


def lade_json(x):
    """Datei ODER inline-JSON (Agenten brauchen so keine Schreibrechte)."""
    x = (x or "").strip()
    return json.loads(x) if x[:1] in "{[" else json.load(open(x))


class CLI:
    def __init__(self, a):
        self.a = a; self.D = get_domain(a.domain); self.pname = a.projekt or a.domain
        self.D.projekt = self.pname; self.P = Project(self.pname)
        self.agent = a.agent or os.environ.get("OMNI_AGENT") or os.environ.get("OMNIGENT_AGENT_NAME") or "unbekannt"

    def sperre(self):
        """Exklusive Dateisperre + Zustand neu laden: parallele Agenten (z. B. zwei Researcher) dürfen state.json nicht gegenseitig
        überschreiben. Schwere Rechnungen laufen VOR der Sperre; die Sperre endet mit dem Prozess."""
        import fcntl
        self._lockf = open(f"{self.P.dir}/.lock", "w"); fcntl.flock(self._lockf, fcntl.LOCK_EX)
        self.P.s = json.load(open(self.P.path)) if os.path.exists(self.P.path) else self.P.s

    def record(self, befehl, ids=None, ergebnis=None, ein=None, aus=None):
        """Gemeinsames Forschungsprotokoll: jede Aktion mit Eingabe- und Ausgabe-IDs (daraus ist jede Entscheidung rekonstruierbar)."""
        ids = ids or {}
        rp = f"{self.P.dir}/record.jsonl"
        if not os.path.exists(rp) or os.path.getsize(rp) == 0:          # ERSTER Ledger-Eintrag: Hash der Präregistrierung, vor jedem Ergebnis
            import hashlib
            pr = f"{self.P.dir}/prereg.md"; h = hashlib.sha256(open(pr, "rb").read()).hexdigest() if os.path.exists(pr) else None
            with open(rp, "a") as f:
                f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": "ledger", "befehl": "praeregistrierung", "eingabe_ids": {},
                                    "ausgabe_ids": {"prereg_sha256": h}, "ergebnis": "prereg.md" if h else "keine prereg.md vorhanden"}, ensure_ascii=False) + "\n")
        with open(rp, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "agent": self.agent, "befehl": befehl,
                                "eingabe_ids": ein if ein is not None else {k: v for k, v in ids.items() if k in ("frage", "claim", "option", "aus", "annahme")},
                                "ausgabe_ids": aus if aus is not None else {k: v for k, v in ids.items() if k not in ("frage", "claim", "option", "aus", "annahme")},
                                "ergebnis": ergebnis, "dauer_s": round(time.time() - T0, 2)}, ensure_ascii=False, default=str) + "\n")

    def frage(self, qid):
        q = next((x for x in self.P.s["fragen"] if x["id"] == qid), None)
        if not q: raise SystemExit(f"Frage {qid} nicht gefunden")
        return q

    # --- Befehle ---------------------------------------------------------------------------------------
    def selftest(self):
        from . import selftest
        ok, _ = selftest.run(self.a.domain, log=lambda m: None)
        print("PASS" if ok else "FAIL"); self.record("selftest", ergebnis="PASS" if ok else "FAIL"); return 0 if ok else 1

    def wissen(self):
        t = wissen_gefiltert(self.P, self.D); print(t[:6000]); self.record("wissen", ergebnis=f"{len(t)} Zeichen"); return 0

    def fragen(self):
        if self.a.add_json:
            neu = lade_json(self.a.add_json); neu = neu.get("fragen", neu) if isinstance(neu, dict) else neu; ids = []
            for q in neu:
                qid = f"F{len(self.P.s['fragen']) + 1}"
                parent = next((x for x in self.P.s["fragen"] if x["id"] == q.get("aus_frage")), None)
                q.update(id=qid, status="offen", faden_id=faden_of(self.P, parent) if parent else qid, quelle=f"agent:{self.agent}")
                self.P.s["fragen"].append(q); ids.append(qid)
            self.P.save(); print("NEU " + json.dumps(ids)); self.record("fragen --add-json", {"fragen": ids}); return 0
        offen = [q for q in self.P.s["fragen"] if q["status"] == "offen"]
        for q in offen: print(f"[{q['id']}] (Faden {faden_of(self.P, q)}) {q['frage'][:300]}" + (f"  lit_offen={q['lit_offen']}" if q.get("lit_offen") else ""))
        if not offen: print("(keine offenen Fragen; der learner kann mit `fragen --add-json` neue anlegen)")
        self.record("fragen", {"offen": [q["id"] for q in offen]}); return 0

    def folgefragen(self):
        """Neue Fragen aus einer Runde/einem Claim speichern (learner). --aus <runden-id|claim-id|frage-id>, --json <datei|inline>."""
        neu = lade_json(self.a.json); neu = neu.get("fragen", neu) if isinstance(neu, dict) else neu; ids = []
        quelle = next((q for q in self.P.s["fragen"] if q["id"] == self.a.aus), None)
        if quelle is None:
            c = next((c for c in self.P.s["claims"] if c["id"] == self.a.aus), None)
            r = next((r for r in self.P.s["runden"] if str(r.get("runde")) == str(self.a.aus).lstrip("R")), None) if not c else None
            fid = (c or {}).get("frage_id") or (r or {}).get("frage")
            quelle = next((q for q in self.P.s["fragen"] if q["id"] == fid), None)
        for q in neu:
            qid = f"F{len(self.P.s['fragen']) + 1}"
            q.update(id=qid, status="offen", aus=self.a.aus, faden_id=faden_of(self.P, quelle) if quelle else qid, quelle=f"agent:{self.agent}")
            self.P.s["fragen"].append(q); ids.append(qid)
        self.P.save(); print("NEU " + json.dumps(ids))
        self.record("folgefragen", ein={"aus": self.a.aus}, aus={"fragen": ids}); return 0

    def reopen(self):
        """Frühere Annahme nach einem überraschenden Ergebnis wieder öffnen; der Plan muss sich danach ändern."""
        an = next((x for x in self.P.s.get("annahmen", []) if x["id"] == self.a.annahme), None)
        if not an: raise SystemExit(f"Annahme {self.a.annahme} nicht gefunden")
        if not self.a.grund or len(self.a.grund) < 10: raise SystemExit("reopen braucht --grund")
        an["status"] = "wiedereröffnet"; an.setdefault("historie", []).append({"ts": now(), "agent": self.agent, "grund": self.a.grund, "claim": self.a.claim})
        for qid in an.get("fragen", []):
            q = next((x for x in self.P.s["fragen"] if x["id"] == qid), None)
            if q: q["status"] = "offen"
        self.P.save()
        self.P.append("decisions.md", f"| {now()} | {self.agent.upper()} | REOPEN Annahme {an['id']}: {an['text'][:120]} | {self.a.grund[:200]} (Beleg {self.a.claim}) |")
        print("REOPEN " + json.dumps({"annahme": an["id"], "status": an["status"], "wieder_offen": an.get("fragen", [])}, ensure_ascii=False))
        self.record("reopen", ein={"annahme": an["id"], "claim": self.a.claim}, aus={"fragen": an.get("fragen", [])}, ergebnis=self.a.grund); return 0

    def plan(self):
        """Offene Fragen plus Empfehlung nach Faden-Regel (im Faden bleiben, solange die letzten 2 Runden einen Claim brachten)."""
        offen = [q for q in self.P.s["fragen"] if q["status"] == "offen"]
        akt = self.P.s.get("aktive_frage"); empf, grund = None, ""
        if akt:
            fa = faden_of(self.P, self.frage(akt)); im = [q for q in offen if faden_of(self.P, q) == fa]
            runden_faden = [r for r in self.P.s["runden"] if r.get("faden_id") == fa]
            if im and (len(runden_faden) < 2 or faden_fortschritt(self.P, fa)):
                empf, grund = im[0]["id"], f"im Faden {fa} bleiben (Fortschritt oder < 2 Runden)"
            elif im: grund = f"Faden {fa}: 2 Runden ohne neuen bestätigten Claim -> Themenwechsel per `wähle --frage` mit Begründung erlaubt"
        if not empf and offen:
            empf = sorted(offen, key=lambda q: (not q.get("lit_offen"), -float(q.get("machbarkeit") or 0.5)))[0]["id"]; grund = grund or "beste offene Frage (lit_offen, Machbarkeit)"
        for q in offen: print(f"[{q['id']}] (Faden {faden_of(self.P, q)}) {q['frage'][:200]}")
        print(f"EMPFEHLUNG {json.dumps({'frage': empf, 'grund': grund}, ensure_ascii=False)}")
        self.record("plan", {"empfehlung": empf}, grund); return 0

    def options(self):
        q = self.frage(self.a.frage); O = planner.options(self.D, q, self.P.s)
        self.P.s["letzte_optionen"] = {"frage": q["id"], "optionen": O, "ts": now()}; self.P.save()
        for o in O: print(json.dumps({k: o[k] for k in ("id", "art", "beschreibung", "kosten", "erwarteter_gewinn")}, ensure_ascii=False))
        self.record("options", {"frage": q["id"], "optionen": [o["id"] for o in O]}); return 0

    def waehle(self):
        a = self.a
        if not a.grund or len(a.grund.strip()) < 10: raise SystemExit("wähle braucht --grund (mindestens 10 Zeichen)")
        if a.frage:                                               # aktive Frage setzen / Themenwechsel
            q = self.frage(a.frage); alt = self.P.s.get("aktive_frage")
            wechsel = alt and faden_of(self.P, self.frage(alt)) != faden_of(self.P, q)
            if wechsel and faden_fortschritt(self.P, faden_of(self.P, self.frage(alt))) and not a.erzwinge:
                raise SystemExit(f"Faden {faden_of(self.P, self.frage(alt))} hat Fortschritt: im Faden bleiben (oder --erzwinge mit Begründung)")
            self.P.s["aktive_frage"] = q["id"]
            self.P.append("decisions.md", f"| {now()} | {self.agent.upper()} | {'THEMENWECHSEL' if wechsel else 'Frage'} -> [{q['id']}] {q['frage'][:100]} | {a.grund[:200]} |")
        if a.option:
            lo = self.P.s.get("letzte_optionen") or {}
            O = lo.get("optionen", []); o = next((x for x in O if x["id"] == a.option), None)
            if not o: raise SystemExit(f"Option {a.option} nicht in den letzten Optionen ({[x['id'] for x in O]}); erst `options` aufrufen")
            verw = [x for x in O if x["id"] != o["id"]]
            ent = {"ts": now(), "agent": self.agent, "frage": lo["frage"], "gewaehlt": o, "verworfen": verw, "grund": a.grund}
            self.P.s.setdefault("entscheidungen", []).append(ent); self.P.s["aktive_frage"] = lo["frage"]; self.P.s["aktive_option"] = o
            q = self.frage(lo["frage"])
            self.P.append("decisions.md", f"| {now()} | {self.agent.upper()} | [{q['id']}] Option {o['id']} ({o['art']}, Kosten {o['kosten']}, Gewinn {o['erwarteter_gewinn']}); "
                          f"verworfen: {', '.join(x['id'] + ' (' + x['art'] + ')' for x in verw)} | {a.grund[:200]} |")
            self.P.append("prereg.md", f"\n## {now()}, vor dem Experiment (Omnigent, {self.agent})\n- Frage [{q['id']}]: {q['frage']}\n- Option {o['id']} ({o['art']}): {o['beschreibung']}\n"
                          f"- Erwartete Verifier-Aufrufe: {o['kosten']}\n- Verworfen: {', '.join(x['id'] + ' ' + x['art'] for x in verw)}\n- Begründung: {a.grund}")
        self.P.save(); print("OK " + json.dumps({"aktive_frage": self.P.s.get("aktive_frage"), "option": (self.P.s.get("aktive_option") or {}).get("id")}))
        self.record("waehle", {"frage": self.P.s.get("aktive_frage"), "option": a.option}, a.grund); return 0

    def experiment(self):
        if self.a.spec_json:
            sp = lade_json(self.a.spec_json); self.a.op = sp.get("op", self.a.op); args = sp.get("args", {})
        else: args = json.loads(self.a.args or "{}")
        from .discovery import _jsonfest
        r = _jsonfest(self.D.run_op(self.a.op, args))
        self.sperre()
        self.P.s.setdefault("experimente", []).append({"ts": now(), "agent": self.agent, "op": self.a.op, "args": args, "frage": self.P.s.get("aktive_frage")})
        eid = f"E{len(self.P.s['experimente'])}"
        if len(json.dumps(r, default=str)) <= 20000: self.P.s["experimente"][-1]["ergebnis"] = r     # für die nachträgliche Auswertung von Hypothesen
        from . import hypothesen
        aend = hypothesen.bewerte_experimente(self.P.s, [{"op": self.a.op, "args": args, "ergebnis": r, "id": eid}], quelle=f"asd.cli:{self.agent}")
        self.P.save()
        print(f"EXPERIMENT {eid} " + json.dumps(r, ensure_ascii=False)[:4000])
        if aend: print("HYPOTHESEN " + json.dumps([{"hypothese": h, "vorher": a_, "jetzt": n_} for h, a_, n_ in aend], ensure_ascii=False))
        self.record("experiment", ergebnis=str(r)[:300], ein={"frage": self.P.s.get("aktive_frage"), "option": self.a.option or (self.P.s.get("aktive_option") or {}).get("id")},
                    aus={"experiment": eid, "op": self.a.op}); return 0

    def pruefe(self):
        c = lade_json(self.a.claim_json); D = self.D
        ps = c.get("pruefungen") or ([c["pruefung"]] if isinstance(c.get("pruefung"), dict) else ([c] if "typ" in c else []))
        ps = [p for p in ps if isinstance(p, dict)]
        from .mcp_schemas import validate_claim, CLAIMS
        from .omni_policies import claim_hash
        extra = [k for k in c if k not in ("frage_id", "antwort", "zahl", "pruefung", "pruefungen", "begruendung", "benutzt", "frage")]
        if self.D.name in CLAIMS:
            neu = []
            for p in ps:
                pc, ign, fehler = validate_claim(self.D.name, p)
                if fehler: extra.append("; ".join(fehler))
                neu.append(pc or p)
            ps = neu
        h = claim_hash(ps)
        if extra or h in {w.get("claim_hash") for w in self.P.s.get("widerlegt", []) if isinstance(w, dict)}:
            grund = ("Schema: " + "; ".join(map(str, extra))) if extra else f"bereits vom Verifier abgelehnt (Claim-Hash {h}); bitte verfeinern statt wiedervorlegen"
            print("RESULT " + json.dumps({"bestanden": False, "level": "hypothesis", "grund": grund, "claim_id": None, "claim_hash": h}, ensure_ascii=False))
            self.record("pruefe", ein={"frage": c.get("frage_id")}, aus={"claim": None}, ergebnis={"bestanden": False, "grund": grund, "claim_hash": h}); return 0
        if not ps: ok, why, lvl = False, "keine Prüfung (pruefung/pruefungen) im Claim-JSON", "hypothesis"
        else:
            res = [D.check(p)[:2] for p in ps]
            ok = all(bool(o) for o, _ in res) and (("antwort" not in c and "zahl" not in c) or all(D.consistent(c, p) for p in ps))
            why = " | ".join(w for _, w in res) + ("" if ok or not all(o for o, _ in res) else " | Antwort passt nicht zur Prüfung (consistent)")
            lvl = D.level(ps[0]) if ok else "hypothesis"
        self.sperre(); self.P.s["verifier_aufrufe"] = self.P.s.get("verifier_aufrufe", 0) + max(1, len(ps))
        qid = c.get("frage_id") or self.P.s.get("aktive_frage"); runde = len(self.P.s["runden"]) + 1
        q = next((x for x in self.P.s["fragen"] if x["id"] == qid), None)
        ueb = None
        if ok and hasattr(D, "ueberraschung"):
            try: ueb = D.ueberraschung(ps[0], self.P.s)
            except Exception as e: ueb = None
        if ok:
            cid = f"{D.name}-O{runde}"
            self.P.s["claims"].append({"id": cid, "frage": q["frage"] if q else c.get("frage", ""), "text": D.describe(ps[0]), "pruefung": ps[0],
                                       "alle_pruefungen": ps, "grund": why, "level": lvl, "status": "bestätigt", "red_team": [], "runde": runde,
                                       "relevanz": D.relevanz(ps[0]), "quelle": f"omnigent:{self.agent}",
                                       "option": self.a.option or (self.P.s.get("aktive_option") or {}).get("id"),
                                       "benutzt": [b for b in (c.get("benutzt") or []) if any(x["id"] == b and x.get("status") == "bestätigt" for x in self.P.s["claims"])]})
            if q: q["status"] = "beantwortet"
            self._nach_claim(cid, out_extra := {})
        else:
            cid = None; out_extra = {}
            self.P.s["widerlegt"].append({"frage_id": qid, "frage": q["frage"] if q else "", "runde": runde,
                                          "gruende": [{"stufe": f"omnigent:{self.agent}", "pruefungstyp": ps[0].get("typ") if ps else None, "grund": why[:240]}],
                                          "claim_hash": h})
        self.P.s["runden"].append({"runde": runde, "frage": qid, "status": "beantwortet" if ok else "ungeprüft", "red_team": [], "sek": 0,
                                   "faden_id": faden_of(self.P, q) if q else None, "quelle": "omnigent"})
        self.P.save()
        out = {"bestanden": bool(ok), "level": lvl, "grund": why[:400], "claim_id": cid, **out_extra}
        if ueb:
            out["ueberraschung"] = True; out["widerspricht_annahme"] = ueb["annahme"]; out["ueberraschung_grund"] = ueb["grund"]
            self.P.s["claims"][-1]["ueberraschung"] = ueb; self.P.save()
        for hy in self.P.s.get("hypothesen", []):                        # präregistrierte Agenten-Hypothesen zu dieser Frage auswerten
            if hy.get("status") != "offen" or (hy.get("kriterium") or {}).get("frage") != qid: continue
            erw = hy["kriterium"].get("erwartet"); ist = {"bestanden": bool(ok), "abgelehnt": not ok, "ueberraschung": bool(ueb), "keine_ueberraschung": bool(ok) and not ueb}.get(erw)
            if ist is None: continue
            hy["status"] = "bestätigt" if ist else "widerlegt"; hy["ausgewertet_durch"] = cid or "abgelehnte Behauptung"; hy["ausgewertet"] = now()
            out["hypothese_" + hy["status"]] = hy["id"]
            self.P.append("decisions.md", f"| {now()} | VERIFIER | HYPOTHESE {hy['id']} {hy['status'].upper()} (agent-generiert von {hy['agent']}, präregistriert, sha256 {hy['sha256'][:12]}): "
                                          f"{hy['text'][:100]} | Kriterium '{erw}', Ergebnis {'bestanden' if ok else 'abgelehnt'}{' + Überraschung' if ueb else ''}; Plan muss sich ändern |" if not ist else
                          f"| {now()} | VERIFIER | Hypothese {hy['id']} bestätigt (Vorhersage eingetroffen) | Kriterium '{erw}' |")
        self.P.save()
        print("RESULT " + json.dumps(out, ensure_ascii=False))
        self.record("pruefe", ein={"frage": qid, "option": self.a.option or (self.P.s.get("aktive_option") or {}).get("id")}, aus={"claim": cid}, ergebnis=out); return 0

    def _nach_claim(self, cid, out):
        """Automatische Verstärkung (Domain.auto_verstaerkung, z. B. Lean), Konsistenz gegen alle bestätigten Claims, Hypothesen-Abgleich."""
        from . import konsistenz, hypothesen
        c = next(x for x in self.P.s["claims"] if x["id"] == cid)
        for p2 in (self.D.auto_verstaerkung(c["pruefung"]) if hasattr(self.D, "auto_verstaerkung") else []) or []:
            ok2, why2, _ = self.D.check(p2)
            if ok2:
                c.update(verstaerkt_von=c["pruefung"], pruefung=p2, level=self.D.level(p2), text=self.D.describe(p2), grund=why2); out["verstaerkt"] = c["level"]
                self.P.append("decisions.md", f"| {now()} | PRÜFER | {cid} automatisch verstärkt zu {c['level']} | {str(why2)[:160]} |"); break
        inc = konsistenz.neuer_claim(self.P.s, self.D, cid)
        if inc:
            out["inkonsistent"] = [[a, b] for a, b, _ in inc]
            for a, b, betr in inc: self.P.append("decisions.md", f"| {now()} | KONSISTENZ | {a} ⟂ {b}: beide angefochten | abhängig ungültig: {betr} |")
        best = hypothesen.abgleich_claims(self.P.s)
        if best: out["hypothesen_bestaetigt"] = [h for h, _ in best]

    def hypothesen(self):
        """Hypothesen mit vorläufigem Status (aus Experimenten) und der Richtung, die der Code daraus ableitet (nur lesen)."""
        from . import hypothesen as H
        print(H.tabelle(self.P.s)); r = H.richtung(self.P.s)
        print("RICHTUNG " + json.dumps(r, ensure_ascii=False)); self.record("hypothesen", aus={"richtung": r and r["hypothese"]}, ergebnis=r and r["modus"]); return 0

    def redteam(self):
        c0 = next((x for x in self.P.s["claims"] if x["id"] == self.a.claim), None)
        if not c0: raise SystemExit(f"Claim {self.a.claim} nicht gefunden")
        gs = []
        if self.a.auto: gs += [dict(x, quelle="auto") for x in self.D.angriffe(c0["pruefung"])]        # domänen-generierte, gezielte Angriffe
        if self.a.gegen_json:
            g = lade_json(self.a.gegen_json); gs += (g.get("gegenpruefungen", [g]) if isinstance(g, dict) else g)[:3]
        if not gs: raise SystemExit("redteam braucht --auto und/oder --gegen-json")
        erg = []
        for x in gs[:6]:
            p = x.get("pruefung", x) if isinstance(x, dict) else None
            if not isinstance(p, dict) or not p: continue
            ok, why = self.D.check(p)[:2]
            relevant = bool(self.D.widerspricht(c0["pruefung"], p))                # könnte der Claim fallen, wenn diese Prüfung besteht?
            gueltig = not str(why).startswith(("Prüfung nicht ausführbar", "unbekannter Prüfungstyp"))
            erg.append({"pruefung": p, "idee": (x.get("idee") if isinstance(x, dict) else "") or "", "quelle": x.get("quelle", "agent") if isinstance(x, dict) else "agent",
                        "bestanden": bool(ok), "relevant": relevant, "gueltig": gueltig, "widerspruch": bool(ok and relevant), "grund": why[:200], "agent": self.agent})
        self.sperre(); c = next(x for x in self.P.s["claims"] if x["id"] == self.a.claim)
        self.P.s["verifier_aufrufe"] = self.P.s.get("verifier_aufrufe", 0) + len(erg); out = []
        for e in erg:
            c["red_team"].append(e); out.append({k: e[k] for k in ("bestanden", "relevant", "gueltig", "widerspruch", "grund")})
            if e["widerspruch"] and c["status"] != "angefochten":
                from . import tms
                betroffen = tms.widerrufen(self.P.s, c["id"], f"Red-Team-Widerspruch: {e['grund'][:120]}", status="angefochten")
                if betroffen: self.P.append("decisions.md", f"| {now()} | TMS | {c['id']} angefochten -> abhängig ungültig: {betroffen} | Wahrheitspflege (asd/tms.py) |")
        c["red_team_wirksam"] = sum(1 for v in c["red_team"] if v.get("gueltig") and v.get("relevant"))
        self.P.save()
        hinweis = "" if any(e["gueltig"] and e["relevant"] for e in erg) else " HINWEIS: keine Gegenprüfung war gültig UND relevant; das zählt nicht als Votum (redteam --auto nutzen)"
        print("REDTEAM " + json.dumps({"claim": c["id"], "status": c["status"], "wirksame_gegenpruefungen": c["red_team_wirksam"], "gegenpruefungen": out}, ensure_ascii=False) + hinweis)
        self.record("redteam", ein={"claim": c["id"]}, aus={"gegenpruefungen": [f"{c['id']}-RT{i + 1}" for i in range(len(c["red_team"]) - len(out), len(c["red_team"]))]},
                    ergebnis={"status": c["status"], "n": len(out)}); return 0

    def hypothese(self):
        """Agent-generierte Hypothese mit maschinenprüfbarem Erfolgskriterium VOR dem Experiment festschreiben (Hash in prereg.md und Ledger).
        --text "...", --kriterium-json '{"frage": "F26", "erwartet": "bestanden|abgelehnt|ueberraschung|keine_ueberraschung"}'"""
        import hashlib
        vh = lade_json(self.a.vorhersagen_json) if self.a.vorhersagen_json else None; zp = lade_json(self.a.pruefung_json) if self.a.pruefung_json else None
        kr = lade_json(self.a.kriterium_json) if self.a.kriterium_json else None
        if kr is None and not (vh or zp): raise SystemExit("hypothese braucht --kriterium-json und/oder --vorhersagen-json / --pruefung-json")
        if kr is not None and (kr.get("erwartet") not in ("bestanden", "abgelehnt", "ueberraschung", "keine_ueberraschung") or not kr.get("frage")):
            raise SystemExit("kriterium braucht frage und erwartet in {bestanden, abgelehnt, ueberraschung, keine_ueberraschung}")
        if not self.a.text or len(self.a.text) < 10: raise SystemExit("hypothese braucht --text")
        if vh or zp:
            from . import hypothesen as H
            try: hy = H.neu(self.P.s, self.a.text, vh, zp, self.a.frage or None, origin=f"AGENT:{self.agent}", agent=self.agent, kriterium=kr)
            except ValueError as e: raise SystemExit(f"hypothese: {e}")
            H.bewerte_experimente(self.P.s, H.protokollierte_experimente(self.P.dir, self.P.s), quelle="nachträglich")
            hid, h = hy["id"], hy["sha256"]
        else:
            hid = f"H{len(self.P.s.get('hypothesen', [])) + 1}"
            h = hashlib.sha256(json.dumps({"text": self.a.text, "kriterium": kr}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            self.P.s.setdefault("hypothesen", []).append({"id": hid, "agent": self.agent, "origin": f"AGENT:{self.agent}", "text": self.a.text, "kriterium": kr,
                                                          "sha256": h, "ts": now(), "status": "offen"})
        self.P.append("prereg.md", f"\n## Hypothese {hid} ({now()}, agent-generiert von {self.agent}, vor dem Experiment)\n- Aussage: {self.a.text}\n"
                                   f"- Erfolgskriterium (maschinell geprüft): {json.dumps(kr, ensure_ascii=False)}\n"
                                   + (f"- Vorhersagen: {json.dumps(vh, ensure_ascii=False)}\n" if vh else "") + (f"- Ziel-Prüfung: {json.dumps(zp, ensure_ascii=False)}\n" if zp else "")
                                   + f"- sha256: {h}")
        self.P.save(); print("HYPOTHESE " + json.dumps({"id": hid, "sha256": h[:16]})); self.record("hypothese", ein={"frage": (kr or {}).get("frage") or self.a.frage}, aus={"hypothese": hid, "sha256": h[:16]}, ergebnis=self.a.text); return 0

    def claim(self):
        """Inhalt eines Claims lesen (Typ, Prüfung, Stufe, Status, Red-Team-Voten) -- nur lesen."""
        c = next((x for x in self.P.s["claims"] if x["id"] == self.a.claim), None)
        if not c: raise SystemExit(f"Claim {self.a.claim} nicht gefunden")
        out = {k: c.get(k) for k in ("id", "text", "level", "status", "pruefung", "benutzt", "origin")} | {"red_team_voten": len(c.get("red_team") or [])}
        print("CLAIM " + json.dumps(out, ensure_ascii=False, default=str)[:6000]); self.record("claim", ein={"claim": c["id"]}); return 0

    def doku(self):
        """Experimente (run_op) und Prüfungstypen (check) der Domäne, direkt aus dem Code."""
        print(self.D.primitive_doc + "\n\n" + self.D.claim_doc); self.record("doku"); return 0

    def status(self):
        s = self.P.s; best = [c for c in s["claims"] if c["status"] == "bestätigt"]
        faeden = sorted({faden_of(self.P, q) for q in s["fragen"] if q["status"] == "offen"})
        print(json.dumps({"runden": len(s["runden"]), "claims_bestaetigt": [c["id"] for c in best], "angefochten": [c["id"] for c in s["claims"] if c["status"] == "angefochten"],
                          "negative": len(s["widerlegt"]), "offene_faeden": faeden, "aktive_frage": s.get("aktive_frage"), "verifier_aufrufe": s.get("verifier_aufrufe", 0),
                          "budget_verifier": s.get("budget_verifier") or "unbegrenzt",
                          "budget_rest": (s["budget_verifier"] - s.get("verifier_aufrufe", 0)) if s.get("budget_verifier") else "unbegrenzt",
                          "annahmen": [{"id": x["id"], "status": x.get("status", "aktiv")} for x in s.get("annahmen", [])]},
                         ensure_ascii=False))
        self.record("status"); return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m asd.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("befehl", choices=["selftest", "wissen", "fragen", "plan", "options", "wähle", "waehle", "experiment", "prüfe", "pruefe", "redteam", "folgefragen", "reopen", "doku", "hypothese", "hypothesen", "claim", "status"])
    ap.add_argument("--domain", default=os.environ.get("ASD_DOMAIN", "lattice")); ap.add_argument("--projekt", default=os.environ.get("ASD_PROJEKT", ""))
    ap.add_argument("--agent", default=""); ap.add_argument("--frage", default=""); ap.add_argument("--option", default="")
    ap.add_argument("--grund", default=""); ap.add_argument("--erzwinge", action="store_true"); ap.add_argument("--add-json", default="")
    ap.add_argument("--op", default=""); ap.add_argument("--args", default="{}"); ap.add_argument("--claim-json", default="")
    ap.add_argument("--claim", default=""); ap.add_argument("--gegen-json", default=""); ap.add_argument("--auto", action="store_true", help="redteam: domänen-generierte Angriffe")
    ap.add_argument("--spec-json", default=""); ap.add_argument("--aus", default=""); ap.add_argument("--json", default=""); ap.add_argument("--annahme", default=""); ap.add_argument("--text", default=""); ap.add_argument("--kriterium-json", default="")
    ap.add_argument("--vorhersagen-json", default=""); ap.add_argument("--pruefung-json", default="")
    a = ap.parse_args(argv)
    cmd = {"wähle": "waehle", "prüfe": "pruefe"}.get(a.befehl, a.befehl)
    cli = CLI(a)
    if cmd in ("options", "waehle", "folgefragen", "reopen", "hypothese") or (cmd == "fragen" and a.add_json): cli.sperre()
    return getattr(cli, cmd)()


if __name__ == "__main__":
    sys.exit(main())
