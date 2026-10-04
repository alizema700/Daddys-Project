"""Dauerbetrieb (Supervisor) für das Labor.

Zyklus: asd.lab_loop (--runden 5, Themenwechsel statt Stopp) -> asd.paper (inkl. Referee-Durchgang) -> Qualitätskriterium.
Wiederholt, bis publikationsreif() gilt oder --max-runden Zyklen erreicht sind. Abstürze werden geloggt und neu gestartet
(der Zustand liegt in projects/<domain>/state.json), Rate-Limits/Quota werden exponentiell abgewartet (1, 2, 4 ... 30 min).

  tmux new -s lab 'caffeinate -dims python run_forever.py --domain <name>'
  Status:  tail -f logs/<name>/status.md     Abstürze: logs/<name>/supervisor.log     Laborausgabe: logs/<name>/lab.log
"""
import argparse, datetime, json, os, shutil, subprocess, sys, time, traceback

from asd.llm import ist_rate_limit
from asd.quality import publikationsreif

WARTE_MIN, WARTE_MAX = 60.0, 1800.0      # Rate-Limit: 1 min, verdoppelt, höchstens 30 min


def jetzt(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Supervisor:
    def __init__(self, a):
        self.a = a; self.logdir = f"logs/{a.domain}"; os.makedirs(self.logdir, exist_ok=True)
        self.proj = f"projects/{a.domain}"; self.fehler = 0
        if a.test_fehler: os.environ.update(ASD_RL_BASIS_SEK="2", ASD_RL_MAX_SEK="8")
        global WARTE_MIN, WARTE_MAX
        if a.test_fehler: WARTE_MIN, WARTE_MAX = 2.0, 8.0

    def log(self, msg, datei="supervisor.log"):
        line = f"[{jetzt()}] {msg}"; print(line, flush=True)
        with open(f"{self.logdir}/{datei}", "a") as f: f.write(line + "\n")

    def status(self, zeile):
        neu = not os.path.exists(f"{self.logdir}/status.md")
        with open(f"{self.logdir}/status.md", "a") as f:
            if neu: f.write(f"# Dauerbetrieb {self.a.domain}\n\n| Zeit | Zyklus | Laborrunden | bestätigte Claims | Hauptresultate | Neuheit | Referee (schwer/gesamt) | Kriterium |\n|---|---|---|---|---|---|---|---|\n")
            f.write(zeile + "\n")

    def schritt(self, name, cmd, env_extra=None):
        """Führt einen Schritt als Kindprozess aus. Rückgabe: True bei Erfolg. Rate-Limit -> warten und wiederholen (nie abbrechen)."""
        warte = WARTE_MIN
        while True:
            env = dict(os.environ, **{k: v for k, v in (env_extra or {}).items() if not k.startswith("_")})
            self.log(f"{name}: {' '.join(cmd)}")
            out = []
            with open(f"{self.logdir}/lab.log", "a") as lf:
                lf.write(f"\n===== {jetzt()} {name} =====\n")
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                for line in p.stdout:
                    lf.write(line); lf.flush(); out.append(line)
                    if self.a.verbose: print("   " + line, end="", flush=True)
                p.wait()
            tail = "".join(out[-60:])
            if p.returncode == 0: return True
            if ist_rate_limit(tail) and "Traceback" not in tail[-300:] or "RateLimitError" in tail:
                self.log(f"{name}: Rate-Limit/Quota erkannt, warte {warte:.0f} s und versuche erneut")
                time.sleep(warte); warte = min(warte * 2, WARTE_MAX); env_extra = (env_extra or {}).get("_danach", {}); continue
            self.log(f"{name}: ABSTURZ (exit {p.returncode}). Traceback/Ausgabe:\n{tail}")
            if "Pflichtphasen" in tail:
                raise SystemExit(f"{name}: Phasen-Gates nicht bestanden; der Dauerbetrieb braucht Phasen 1-4 (bzw. --ohne-gates). Siehe {self.logdir}/supervisor.log")
            return False

    def zustand(self):
        try: return json.load(open(f"{self.proj}/state.json"))
        except Exception: return {"claims": [], "runden": []}

    def bewerten(self):
        from asd.domains.base import get_domain
        D = get_domain(self.a.domain); s = self.zustand()
        ref = f"{self.proj}/referee.json" if os.path.exists(f"{self.proj}/referee.json") else f"{self.proj}/referee_report.md"
        ok, grund = publikationsreif(s, ref, f"{self.proj}/pruefprotokoll.json", D)
        rel = lambda c: c.get("relevanz") or (D.relevanz(c["pruefung"]) if c.get("pruefung") and hasattr(D, "relevanz") else None)
        best = [c for c in s["claims"] if c.get("status") == "bestätigt"]
        haupt = [c for c in best if rel(c) == "hauptresultat"]
        try: W = json.load(open(f"{self.proj}/referee.json")).get("weaknesses", [])
        except Exception: W = []
        schwer = sum(1 for w in W if str(w.get("severity", "major")).lower() == "major")
        return ok, grund, s, best, haupt, W, schwer

    def statuszeile(self, zyklus, ok, grund, s, best, haupt, W, schwer):
        neu = ", ".join(f"{c['id'].split('-')[-1]}:{(c.get('neuheit') or {}).get('status', '-')}" for c in haupt) or "-"
        self.status(f"| {jetzt()} | {zyklus} | {sum(1 for r in s['runden'] if r.get('frage'))} | {len(best)} | "
                    f"{', '.join(c['id'].split('-')[-1] for c in haupt) or '-'} | {neu} | {schwer}/{len(W)}"
                    + (": " + "; ".join(str(w.get('title'))[:50] for w in W if str(w.get('severity', 'major')).lower() == 'major') if schwer else "")
                    + f" | {'ERFÜLLT' if ok else 'offen'}: {grund[:160]} |")

    def zyklus(self, n):
        py = sys.executable; a = self.a; gates = ["--ohne-gates"] if a.ohne_gates else []
        fault = {}
        if a.test_fehler and n == 1 and not self.fehler: fault = {"ASD_FAULT_CRASH": "1"}           # Test: künstlicher Absturz
        elif a.test_fehler and n == 1 and self.fehler == 1:                                         # Test: Rate-Limit, das den Kindprozess
            fault = {"ASD_FAULT_CRASH": "ratelimit", "_danach": {"ASD_FAULT_RATELIMIT": "2"}}      # beendet, danach 2 Rate-Limits im LLM-Aufruf
        lab = [py, "-m", "asd.lab_loop", "--domain", a.domain, "--runden", str(a.runden_pro_zyklus), "--themenwechsel",
               "--stopp-ohne-fortschritt", "3"] + (["--fragen", a.fragen] if a.fragen and n == 1 and not self.zustand()["runden"] else []) + gates
        if not self.schritt("Labor", lab, fault): return None
        if self.zustand().get("ausstehend"):
            self.log("Experimenteller Modus: wartet auf Messdaten (siehe projects/<domain>/auftraege/*_protokoll.md); prüfe in 15 min erneut")
            return "wartet"
        paper = [py, "-m", "asd.paper", "--domain", a.domain, "--autoren", a.autoren, "--affiliation", a.affiliation, "--sprache", a.sprache] + gates
        if not self.schritt("Paper+Referee", paper): return None
        return "ok"

    def lauf(self):
        a = self.a; n = 1
        self.log(f"Dauerbetrieb gestartet: Domäne {a.domain}, {"unbegrenzt viele" if not a.max_runden else f"max. {a.max_runden}"} Zyklen à {a.runden_pro_zyklus} Laborrunden")
        while not a.max_runden or n <= a.max_runden:
            try:
                r = self.zyklus(n)
                if r is None:                                   # Absturz: neu starten, Zyklus wiederholen
                    self.fehler += 1; w = min(a.pause_nach_absturz * 2 ** min(self.fehler - 1, 6), WARTE_MAX)
                    self.log(f"Neustart von Zyklus {n} in {w:.0f} s (Absturz Nr. {self.fehler}; Zustand bleibt in state.json)"); time.sleep(w); continue
                if r == "wartet":
                    self.statuszeile(n, False, "wartet auf Messdaten", *self.bewerten()[2:]); time.sleep(a.warte_messdaten); continue
                self.fehler = 0
                ok, grund, *rest = self.bewerten(); self.statuszeile(n, ok, grund, *rest)
                self.log(f"Zyklus {n} fertig: {grund}")
                if ok: return self.abschluss(grund)
                n += 1
            except SystemExit: raise
            except KeyboardInterrupt: self.log("vom Nutzer beendet"); return 130
            except Exception:                                   # Fehler im Supervisor selbst: loggen und weiter
                self.fehler += 1; self.log("Supervisor-Fehler:\n" + traceback.format_exc()); time.sleep(min(a.pause_nach_absturz * self.fehler, WARTE_MAX))
        self.log(f"--max-runden {a.max_runden} erreicht, Qualitätskriterium nicht erfüllt.")
        self.status(f"\n**{jetzt()}: gestoppt nach {a.max_runden} Zyklen, nicht publikationsreif.** Letzter Stand: siehe oben; Paper: {self.proj}/paper.pdf\n")
        return 2

    def abschluss(self, grund):
        a = self.a; gates = ["--ohne-gates"] if a.ohne_gates else []
        self.log("Qualitätskriterium erfüllt: baue finales Paper")
        self.schritt("Finales Paper", [sys.executable, "-m", "asd.paper", "--domain", a.domain, "--autoren", a.autoren,
                                       "--affiliation", a.affiliation, "--sprache", a.sprache] + gates)
        for ext in ("pdf", "tex", "md"):
            if os.path.exists(f"{self.proj}/paper.{ext}"): shutil.copy(f"{self.proj}/paper.{ext}", f"{self.proj}/paper_final.{ext}")
        self.status(f"\n**{jetzt()}: ABGESCHLOSSEN. {grund}. Finales Paper: {self.proj}/paper_final.pdf, Gutachten: {self.proj}/referee_report.md**\n")
        self.log("Abschluss gemeldet, Prozess beendet sich."); return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--max-runden", type=int, default=0, help="höchstens so viele Zyklen (Labor -> Paper -> Referee); 0 = unbegrenzt (Standard)")
    ap.add_argument("--runden-pro-zyklus", type=int, default=5, help="Laborrunden je Zyklus")
    ap.add_argument("--fragen", default="", help="Startfragen (nur beim allerersten Zyklus eines leeren Projekts)")
    ap.add_argument("--autoren", default="Verifier-Gated Discovery Lab"); ap.add_argument("--affiliation", default="")
    ap.add_argument("--sprache", default="en", choices=["en", "de"])
    ap.add_argument("--ohne-gates", action="store_true", help="Phasen-Gates übergehen (als Abweichung protokolliert)")
    ap.add_argument("--pause-nach-absturz", type=float, default=30.0, help="Sekunden vor dem Neustart (verdoppelt sich bei Folgeabstürzen)")
    ap.add_argument("--warte-messdaten", type=float, default=900.0, help="experimenteller Modus: Sekunden zwischen zwei Prüfungen auf Messdaten")
    ap.add_argument("--verbose", action="store_true", help="Ausgabe der Kindprozesse auch im Terminal")
    ap.add_argument("--test-fehler", action="store_true", help="TEST: künstlicher Absturz und simuliertes Rate-Limit im ersten Zyklus")
    a = ap.parse_args()
    sys.exit(Supervisor(a).lauf())


if __name__ == "__main__":
    main()
