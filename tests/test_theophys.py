"""Domäne Theoretische Physik: Selbsttest, Sandbox, Prüfer-Eigenschaften und eine Labor-Runde Ende-zu-Ende mit festem Schein-LLM
(kein API-Aufruf, kein Netz).  pytest tests/test_theophys.py"""
import json, os, types

import pytest

from asd.domains.base import get_domain
from asd.domains.theophys import ausdruck as A
from asd import selftest, hypothesen as H

D = get_domain("theophys")
HB = {"name": "heisenberg"}


def test_selbsttest_bestanden():
    ok, rows = selftest.run("theophys", log=lambda m: None)
    assert ok, [r for r in rows if not r["korrekt"]]


@pytest.mark.parametrize("s", ["__import__('os')", "x.__class__", "open('f')", "Integer(1)", "lambda: 1", "a;b", "x['y']"])
def test_formel_sandbox(s):
    with pytest.raises(A.FormelFehler): A.parse(s)


def test_toleranzfeld_und_unbekannte_felder_abgelehnt():
    ok, why, _ = D.check({"typ": "spektrum", "modell": HB, "N": 4, "index": 0, "wert": "-2", "toleranz": "1"})
    assert not ok and "Toleranz" in why
    ok, why, _ = D.check({"typ": "spektrum", "modell": HB, "N": 4, "index": 0, "wert": "-2", "kommentar": "x"})
    assert not ok and "unbekannte Felder" in why


def test_numerischer_bereich_ist_observed_und_exakter_rigoros():
    assert D.level({"typ": "spektrum", "modell": HB, "N": 10, "sektor": {"up": 5}, "index": 0, "wert": "-1"}) == "computed_rigorous"
    assert D.level({"typ": "spektrum", "modell": HB, "N": 12, "index": 0, "intervall": ["-5.4", "-5.3"]}) == "observed"
    assert D.level({"typ": "qm_eigenwert", "potential": "x^2", "index": 0, "wert": "1"}) == "observed"


def test_gegenbeispiel_fuer_cegis():
    ok, why, ev = D.check({"typ": "schranke", "ausdruck": "x^4 - 3*x^2*y + y^2 + 1", "bereich": {"x": ["-2", "2"], "y": ["-1", "1"]}, "untere": "0"})
    gb = D.gegenbeispiel(None, why, ev)
    assert not ok and gb["art"] == "zertifiziertes_gegenbeispiel"
    import sympy as sp
    pt = {k: sp.Rational(v) for k, v in gb["parameter"].items()}
    assert A.parse("x^4 - 3*x^2*y + y^2 + 1").subs({sp.Symbol(k): v for k, v in pt.items()}) <= 0


def test_red_team_angriffe_widersprechen_und_bestehen_nicht():
    p = {"typ": "spektrum", "modell": HB, "N": 6, "index": 0, "intervall": ["-2.80277564", "-2.80277563"]}
    assert D.check(p)[0]
    for g in D.angriffe(p):
        assert D.widerspricht(p, g["pruefung"]) and not D.check(g["pruefung"])[0]


@pytest.mark.skipif(not __import__("asd.lean_check", fromlist=["x"]).lean_bin(), reason="Lean nicht installiert")
def test_lean_verstaerkung():
    p = {"typ": "klassische_schranke", "koeffizienten": [["1", "1"], ["1", "-1"]], "schranke": 2}
    v = D.auto_verstaerkung(p)
    assert v and D.level(v[0]) == "proved_lean" and D.check(v[0])[0]
    assert not D.check(dict(p, schranke=3, beweis="lean"))[0]


# ---------------------------------------------------------------- Ende-zu-Ende: Hypothese steuert das Labor --------------------
def _schein_llm(prompt, system="", repairs=2, **kw):
    if "theoretischer Physiker" in system:                                     # Forscher
        if "Runde 1:" in prompt:
            return {"ueberlegung": "Lücke für mehrere N", "plan": [{"op": "spin_spektrum", "args": {"modell": HB, "N": n, "anzahl": 2}} for n in (4, 6, 8)]}
        return {"antwort": "Lücke positiv", "zahl": None, "konfidenz": 0.9, "pruefung": {"typ": "gap", "modell": HB, "N": 6, "gap_min": "1/2"}, "begruendung": "b"}
    if "Red-Team" in system: return {"gegenpruefungen": []}
    if "Lern-Agent" in system: return {"fragen": []}
    if "Hypothesen-Agent" in system: return {"hypothesen": []}
    return {"fragen": [], "id": "F1", "begruendung": "b"}


def test_labor_runde_hypothese_steuert_und_wird_bestaetigt(tmp_path, monkeypatch):
    import asd.lab_loop as LL, asd.discovery as disc, asd.novelty as nov
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(LL, "ask_json", _schein_llm); monkeypatch.setattr(disc, "ask_json", _schein_llm)
    monkeypatch.setattr(nov, "check_claim", lambda D, c, salt="": {"status": "nicht_geprueft", "grund": "Test"})
    P = LL.Project("tp"); D.projekt = "tp"; P.s["fragen"].append({"id": "F1", "frage": "Hat die Heisenberg-Kette eine Lücke?", "status": "offen", "faden_id": "F1"})
    H.neu(P.s, "Die Heisenberg-Kette mit gerader Länge hat eine positive Lücke", frage="F1",
          vorhersagen=[{"op": "spin_spektrum", "wenn": {"modell": HB}, "feld": "gap", "relation": ">", "wert": 0}],
          pruefung={"typ": "gap", "modell": HB, "N": 4, "gap_min": "1/2"})
    log = []; a = types.SimpleNamespace(gezielt=False, fragen="")
    assert LL.runde_ausfuehren(P, D, a, 1, log.append)
    h = P.s["hypothesen"][0]
    assert h["vorlaeufig"]["status"] == "vorlaeufig_gestuetzt" and h["vorlaeufig"]["stuetzend"] == 3      # drei Experimente, kein Widerspruch
    assert any(c["status"] == "bestätigt" and c["pruefung"]["typ"] == "gap" for c in P.s["claims"])
    assert "HYPOTHESEN-STEUERUNG" in open(f"{P.dir}/decisions.md").read()
    assert LL.runde_ausfuehren(P, D, a, 2, log.append)                                                   # Richtung jetzt: beweisen
    assert h["status"] == "bestätigt", log
    assert any(c.get("hypothese") == h["id"] and c["status"] == "bestätigt" for c in P.s["claims"])
    assert "beweisen" in open(f"{P.dir}/decisions.md").read()
