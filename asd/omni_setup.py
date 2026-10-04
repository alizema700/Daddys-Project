"""Legt ein frisches Projekt für einen Omnigent-Lauf an (Kopie des Zustands eines Quellprojekts + Annahmen + Startfragen).
  python -m asd.omni_setup --quelle proofreading --projekt omni_proofreading"""
import argparse, json, os, shutil, time

ap = argparse.ArgumentParser(); ap.add_argument("--quelle", default="proofreading"); ap.add_argument("--projekt", default="omni_proofreading")
ap.add_argument("--budget-verifier", type=int, default=0, help="0 = unbegrenzt (Standard)"); ap.add_argument("--frage", default=""); a = ap.parse_args()
src, dst = f"projects/{a.quelle}", f"projects/{a.projekt}"
shutil.rmtree(dst, ignore_errors=True); os.makedirs(dst)
s = json.load(open(f"{src}/state.json"))
for f in ("fakten.json", "lueckenkarte.md"):
    if os.path.exists(f"{src}/{f}"): shutil.copy(f"{src}/{f}", dst)
def _faelle(p):
    return p.get("faelle", []) if p.get("typ") == "erreichbar_liste" else ([p] if p.get("typ") == "erreichbar" else [])
cx = sorted({f["topologie"] for c in s["claims"] if c.get("status") == "bestätigt" for f in _faelle(c["pruefung"])
             if str(f.get("topologie", "")).startswith("fam2_") and float(f.get("eta_max", 1)) <= 1e-4})
n = len(s["fragen"])
fz = {"id": f"F{n + 1}", "frage": a.frage or "Gibt es unter den 35 offenen Topologien der Familie mit höchstens zwei gebundenen Zuständen (fam2_*) weitere, "
      "die eta <= e^{-2 Delta} = 1e-4 erreichen (exaktes Zertifikat erreichbar_liste), oder lässt sich die Schranke für weitere Mitglieder beweisen?",
      "status": "offen", "faden_id": f"F{n + 1}", "quelle": "omnigent-start", "machbarkeit": 0.7}
fk = {"id": f"F{n + 2}", "frage": "Ist die Klassifikation der Familie (bewiesen / Gegenbeispiel / offen) mit allen bisher zertifizierten Aussagen konsistent und vollständig gezählt?",
      "status": "zurückgestellt", "faden_id": f"F{n + 2}", "quelle": "omnigent-start"}
for q in s["fragen"]:
    if q["status"] == "offen": q["status"] = "zurückgestellt"
s["fragen"] += [fz, fk]
s["annahmen"] = [{"id": "A1", "status": "aktiv", "schwelle": 1e-4, "gegenbeispiele": cx, "fragen": [fk["id"]],
                  "text": f"Klassifikation 50 / {len(cx)} / {88 - 50 - len(cx)}: genau {cx} verletzen eta >= e^(-2 Delta) unter den 88 Topologien"}]
s["runden_vor_omnigent"] = len(s["runden"]); s["budget_verifier"] = a.budget_verifier or None; s["verifier_aufrufe"] = 0
json.dump(s, open(f"{dst}/state.json", "w"), ensure_ascii=False, indent=1)
open(f"{dst}/decisions.md", "w").write(f"| Zeit | Agent | Entscheidung | Beleg |\n|---|---|---|---|\n| {time.strftime('%Y-%m-%d %H:%M:%S')} | SETUP | Projekt aus {src} kopiert; Annahme A1; Startfrage {fz['id']} | asd/omni_setup.py |\n")
open(f"{dst}/prereg.md", "w").write(f"# Präregistrierung Omnigent-Lauf ({time.strftime('%Y-%m-%d %H:%M')})\n\n- Startfrage {fz['id']}: {fz['frage']}\n"
                                    f"- Erwartung (Annahme A1): {s['annahmen'][0]['text']}\n- Budget: {a.budget_verifier or 'unbegrenzt'} Verifier-Aufrufe\n")
print(json.dumps({"projekt": a.projekt, "startfrage": fz["id"], "annahme": s["annahmen"][0]["text"]}, ensure_ascii=False))
