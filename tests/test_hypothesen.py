"""Hypothesen mit vorläufigem Status, Richtung, Planer-Option, Konsistenz (domänenunabhängig, ohne LLM).  pytest tests/test_hypothesen.py"""
import json

import pytest

from asd import hypothesen as H, planner, konsistenz


def _state():
    return {"fragen": [{"id": "F1", "frage": "Ist die Lücke positiv?", "status": "offen", "faden_id": "F1"}], "claims": [], "runden": [], "widerlegt": []}


def _exp(n, gap, i=0):
    return {"op": "spin_spektrum", "args": {"N": n, "modell": {"name": "heisenberg"}}, "ergebnis": {"gap": gap, "eigenwerte": [-1.0, -1.0 + gap]}, "id": f"E{i}"}


def test_validierung_lehnt_toleranz_und_unbekannte_relation_ab():
    s = _state()
    with pytest.raises(ValueError): H.neu(s, "Die Lücke ist positiv für alle N", [{"op": "x", "feld": "gap", "relation": ">", "wert": 0, "toleranz": 1}])
    with pytest.raises(ValueError): H.neu(s, "Die Lücke ist positiv für alle N", [{"op": "x", "feld": "gap", "relation": "~~", "wert": 0}])
    with pytest.raises(ValueError): H.neu(s, "kurz", [])


def test_status_uebergaenge_und_richtung():
    s = _state()
    h = H.neu(s, "Die Lücke ist positiv für alle N", [{"op": "spin_spektrum", "feld": "gap", "relation": ">", "wert": 0}], frage="F1")
    assert H.richtung(s)["modus"] == "testen" and h["vorlaeufig"]["status"] == "offen"
    assert H.bewerte_experimente(s, [_exp(4, 1.0, 1)]) == [("H1", "offen", "schwach_gestuetzt")]
    H.bewerte_experimente(s, [_exp(6, 0.68, 2)])
    assert h["vorlaeufig"]["status"] == "vorlaeufig_gestuetzt" and H.richtung(s)["modus"] == "beweisen"
    H.bewerte_experimente(s, [_exp(6, 0.68, 2)])                                   # gleiches Experiment zählt nicht doppelt
    assert h["vorlaeufig"]["stuetzend"] == 2
    H.bewerte_experimente(s, [_exp(8, 0.0, 3), _exp(10, -0.1, 4)])
    assert h["vorlaeufig"]["status"] == "vorlaeufig_widerlegt" and H.richtung(s)["modus"] == "verfeinern"
    assert h["vorlaeufig"]["punkte"] == 2 - 3 * 2
    H.bewerte_experimente(s, [_exp(12, 0.5, 5), _exp(14, 0.4, 6), _exp(16, 0.3, 7)])
    assert h["vorlaeufig"]["status"] == "umstritten" and H.richtung(s)["modus"] == "entscheiden"


def test_wenn_filter_fehler_und_fehlende_felder_zaehlen_nicht():
    s = _state()
    h = H.neu(s, "Bei N = 4 ist die Lücke genau 1", [{"op": "spin_spektrum", "wenn": {"N": 4}, "feld": "gap", "relation": "≈", "wert": 1}])
    H.bewerte_experimente(s, [_exp(6, 0.5), {"op": "spin_spektrum", "args": {"N": 4}, "ergebnis": {"fehler": "x"}},
                              {"op": "spin_spektrum", "args": {"N": 4}, "ergebnis": {"anderes": 1}}])
    assert h["vorlaeufig"]["status"] == "offen"
    H.bewerte_experimente(s, [_exp(4, 1.0000000001)])                              # ≈ mit fester Toleranz 1e-6
    assert h["vorlaeufig"]["stuetzend"] == 1


def test_menschliche_hypothese_hat_vorrang_und_stillstand_laesst_ruhen():
    s = _state(); v = [{"op": "spin_spektrum", "feld": "gap", "relation": ">", "wert": 0}]
    a = H.neu(s, "Agenten-Hypothese über die Lücke", v, origin="AGENT:x"); m = H.neu(s, "Menschliche Hypothese über die Lücke", v)
    assert H.richtung(s)["hypothese"] == m["id"]
    for r in range(H.MAX_STILLSTAND): H.runde_abschliessen(m, r, "offen")
    assert H.richtung(s)["hypothese"] == a["id"]


def test_abgleich_und_verifizieren_mit_pruefer():
    s = _state(); p = {"typ": "wert", "x": 3, "y": 9}
    h = H.neu(s, "Das Quadrat von drei ist neun", pruefung=p)
    s["claims"].append({"id": "C1", "status": "bestätigt", "pruefung": dict(p, beweis="lean")})
    assert H.abgleich_claims(s) == [("H1", "C1")] and h["status"] == "bestätigt" and H.richtung(s) is None

    class D:
        def check_cegis(self, p): return (False, "falsch", {}, {"art": "wert", "berechnet": 9})
    h2 = H.neu(s, "Das Quadrat von drei ist zehn", pruefung={"typ": "wert", "x": 3, "y": 10})
    ok, _, gb = H.verifizieren(D(), h2)
    assert not ok and gb and h2["status"] == "widerlegt"


def test_planer_option_folgt_dem_status_und_ohne_hypothesen_unveraendert():
    class Dom: pass
    s = _state(); ohne = [o["art"] for o in planner.options(Dom(), s["fragen"][0], s)]
    assert ohne == ["tiefe_rechnung", "breiter_scan"]
    H.neu(s, "Die Lücke ist positiv für alle N", [{"op": "spin_spektrum", "feld": "gap", "relation": ">", "wert": 0}], frage="F1")
    H.bewerte_experimente(s, [_exp(4, 1.0, 1), _exp(6, 0.7, 2)])
    O = planner.options(Dom(), s["fragen"][0], s)
    assert O[0]["art"] == "hypothese_beweisen" and "AUFTRAG (beweisen)" in O[0]["vorgehen"]


def test_wissen_abschnitt_leer_ohne_hypothesen():
    assert H.wissen_abschnitt(_state()) == ""
    s = _state(); s["hypothesen"] = [{"id": "H1", "text": "alt", "kriterium": {"frage": "F1", "erwartet": "bestanden"}, "status": "offen"}]
    assert H.wissen_abschnitt(s) == ""                                              # Altbestand (asd.cli) ohne Vorhersagen ändert nichts


def test_konsistenz_ficht_widersprechende_claims_an():
    class D:
        def widerspricht(self, p, q): return p["typ"] == q["typ"] == "wert" and p["x"] == q["x"] and p["y"] != q["y"]
    s = {"claims": [{"id": "A", "status": "bestätigt", "pruefung": {"typ": "wert", "x": 3, "y": 9}},
                    {"id": "B", "status": "bestätigt", "pruefung": {"typ": "wert", "x": 2, "y": 4}},
                    {"id": "C", "status": "bestätigt", "pruefung": {"typ": "wert", "x": 3, "y": 10}},
                    {"id": "D", "status": "bestätigt", "pruefung": {"typ": "wert", "x": 5, "y": 1}, "benutzt": ["C"]}]}
    assert konsistenz.widersprueche(s, D()) == [("A", "C")]
    out = konsistenz.neuer_claim(s, D(), "C")
    st = {c["id"]: c["status"] for c in s["claims"]}
    assert out and st == {"A": "angefochten", "B": "bestätigt", "C": "angefochten", "D": "abhängig_ungültig"}
