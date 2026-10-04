# Verbindlicher Workflow (zum Kopieren in Claude Code)

Diesen Block als erste Nachricht in Claude Code einfügen, Platzhalter `<...>` ersetzen. Alle genannten Kommandos existieren
im Repo (geprüft in Phase 0, Stand dieses Commits).

```
# AUFTRAG: Verifier-Gated Research, verbindlicher Workflow

Du arbeitest im Repo „Daddys-Project“ (früher HackNation-Ninja-Turtles) mit dem Framework unter `asd/`.
Ziel: eine **wissenschaftliche Neuheit** im Fachgebiet **<FACHGEBIET>**, belegt durch Code-Zertifikate, als Paper.
Autoren: <NAMEN>, <AFFILIATION>.

## 0. Grundgesetze (gelten immer, Verstoß = sofort stoppen und melden)
G1. Wahr ist nur, was `domain.check()` (Code) bestätigt. Kein LLM, auch nicht du, entscheidet über Wahrheit.
G2. Ins Paper kommt nur die **kanonische Aussage** aus `domain.describe(prüfung)`, nie der Freitext eines Agenten.
G3. Toleranzen, Genauigkeit, Auflösung und Seeds legt **der Prüfer** fest, nie die Behauptung.
G4. Keine Referenz ohne Tool-Beleg (DOI oder arXiv-ID, tatsächlich abgerufen). Kein Zitat ohne Code-Bestätigung im Abstract.
G5. Gleitkomma-Ergebnisse heißen „numerisch“. „Theorem“ nur mit Zertifikat (exakt, Intervall oder Lean).
G6. Präregistrierte Kriterien werden nach dem Lauf nie geändert. Abweichungen kommen nur als datierter Nachtrag in `prereg.md`.
G7. Negative Ergebnisse werden genauso protokolliert und berichtet wie positive.
G8. Du überspringst keine Phase. Jede Phase endet mit dem **Abnahmenachweis** (Kommando-Ausgabe zeigen).
G9. Wenn ein Abnahmekriterium nicht erfüllt ist: nicht weitermachen, Ursache beheben, Phase wiederholen.

## Phase 0: Bestandsaufnahme (Pflicht, 5 Min)
- Lies vollständig: `docs/FRAMEWORK.md`, `CLAUDE.md`, `.claude/skills/verifier-gated-lab/SKILL.md`, `asd/domains/base.py`,
  `asd/domains/proofreading_domain.py` (Vorbild für exakte Zertifikate), `asd/domains/lattice_domain.py` (Vorbild für numerische Prüfer).
- Prüfe, dass existieren: `asd/selftest.py`, `asd/lab_loop.py`, `asd/research.py`, `asd/paper.py`, `asd/new_domain.py`,
  `asd/recheck.py`, `asd/novelty.py`.
- **Abnahme:** Liste der Dateien mit „vorhanden/fehlt“. Fehlt etwas: STOPP und melden, nichts nachbauen ohne Rückfrage.

## Phase 1: Große Recherche (Pflicht, VOR jeder Rechnung)
1. Lege die Domäne an: `python -m asd.new_domain <name>`.
2. Trage in der Domäne ein:
   - `recherche_ziel`: 1–2 Sätze.
   - `recherche_klassiker`: mindestens 8 gezielte Suchen nach Autor + Thema für die Grundlagenarbeiten.
   - `recherche_crossref = True`.
   - `recherche_sperre`: Quellen, die einen Antwortschlüssel enthalten.
3. Starte nur den Scout:
   `python -c "from asd.research import run; from asd.domains.base import get_domain as g; d=g('<name>'); run('<name>', n_queries=40, per_query=30, keep=300, kette=15, spec={'ziel': d.recherche_ziel, 'sperre': d.recherche_sperre, 'klassiker': d.recherche_klassiker, 'crossref': True})"`
- **Abnahme (alle Punkte müssen erfüllt sein):**
  - ≥ 1000 abgerufene Quellen, ≥ 100 gesichtet, ≥ 60 Befunde mit per Code bestätigtem Zitat (`research/kb/<name>/kb.json` → `stats`).
  - Jeder Klassiker aus `recherche_klassiker` ist mit DOI/arXiv-ID im Korpus oder ausdrücklich als „NICHT GEFUNDEN“ markiert
    (Abschnitt „Klassiker-Abdeckung“ am Ende von `known_results.md`, Zahl in `stats.klassiker_gefunden`).
  - `research/kb/<name>/known_results.md` existiert, jede Zeile hat Status bewiesen / numerisch / experimentell / vermutet.
  - Zeige `stats` und die ersten 20 Zeilen von `known_results.md`.
- Ist ein Kriterium verfehlt: Suchanfragen bzw. Klassiker erweitern und wiederholen. **Ohne bestandene Phase 1 keine Phase 2.**

## Phase 2: Lückenkarte (Pflicht, schriftlich)
Erstelle `projects/<name>/lueckenkarte.md` mit 5–10 Einträgen. Jeder Eintrag enthält genau:
- **Lücke:** was laut `known_results.md` offen, nur vermutet oder nur numerisch belegt ist (mit Quellen-ID).
- **Warum offen:** Zitat bzw. Befund-ID, die zeigt, dass es niemand gemacht hat (z. B. „nur 4 Kandidaten verglichen“, „Bereich nicht untersucht“).
- **Neuheitstyp:** (a) Erweiterung eines Bereichs, (b) Gegenbeispiel, (c) Schranke, (d) geschlossene Form, (e) Phasenübergang.
- **Prüfbarkeit:** welcher Prüfungstyp das Resultat zertifizieren könnte; falls keiner existiert: „Prüfer fehlt“.
- **Value of Information:** Neuheit (0–1) × Machbarkeit (0–1) mit einem Satz Begründung.
- **Abnahme:** Tabelle zeigen. Mindestens 3 Lücken mit Neuheitstyp ≠ „Reproduktion“ und Prüfbarkeit ≠ „Prüfer fehlt“.
  Sonst Phase 3 ausführen, bis das erfüllt ist.

## Phase 3: Prüfer bauen (Verifizierer zuerst)
Für JEDE Lücke aus Phase 2 braucht es einen Prüfungstyp. Pflichttypen, wo das Fach es zulässt:
- **erreichbar / wert:** konstruktiver Nachweis (exakt rational, Intervall oder unabhängige Nachrechnung).
- **optimum:** Der Prüfer führt eine EIGENE globale Suche aus (anderer Seed, mehr Starts, höhere Auflösung) und bestätigt, dass nichts Besseres existiert (numerisch).
- **vergleich:** A schlägt B robust in zwei Auflösungen bzw. Methoden.
- **schranke:** Eine Aussage „für alle Parameter gilt ≥ f“ ist per Symbolik (Koeffizienten-Positivität, Matrix-Tree) oder Intervall-Branch-and-Bound bewiesen; Nebenbedingungen (z. B. Budget σ ≤ σ_max) müssen im Prüfer stecken.
- **vorzeichenwechsel / grenzwert:** mit festen Intervallbreiten und Toleranzen im Prüfer.
Zusätzlich je Domäne Pflicht:
- `describe(p)`: kanonische Aussage, genau so stark wie die Prüfung, nicht stärker.
- `widerspricht(p, q)`: wann sich zwei bestandene Prüfungen logisch ausschließen (für das Red-Team).
- `selftest()`: ≥ 3 wahre und ≥ 3 falsche Aussagen (wird von `asd.selftest` erzwungen), davon mindestens eine knapp an der Grenze
  (z. B. 1 % unter einem bekannten Wert), eine Regelverletzung und ein Versuch, die Toleranz über die Behauptung zu lockern.
- **Experimentelle Fächer:** Domäne von `ExperimentalDomain` erben. Der Prüfer ist dann die fest vorab definierte Statistik
  (Permutationstest, Bootstrap-KI, Kontrollen, BH); der Selbsttest läuft mit simulierten Daten und kalibriert die Falsch-Positiv-Rate.
- `python -m asd.verifier_redteam <name>`: Fallen für den Prüfer; jede falsch akzeptierte Falle wird ein Selbsttest-Fall.
- **Abnahme:** `python -m asd.selftest <name>` meldet BESTANDEN, das Prüfer-Red-Team hat 0 blockierende Befunde. Zeige die Ausgabe.
  Jeder später gefundene Fehler wird ein neuer Selbsttest-Fall. `python -m asd.phases <name>` zeigt Phase 3 OK.

## Phase 4: Präregistrierung (Pflicht, committen VOR dem Lauf)
Schreibe in `prereg.md` je Ziel-Lücke: Hypothese, exakter Prüfungstyp mit Parametern, Erfolgskriterium, Abbruchkriterium,
erwartetes Ergebnis, Rundenzahl. Für Vergleiche mit Baselines zusätzlich: Seeds/Wiederholungen, Test, Schwelle, BH-Korrektur.
(Die Labor-Schleife schreibt zusätzlich je Runde einen Eintrag nach `projects/<name>/prereg.md`.)
- **Abnahme:** `git log -1 -- prereg.md` zeigt einen Commit, der zeitlich vor jedem Lauf liegt. Hash nennen.

## Phase 5: Labor laufen lassen (gezielt, nicht frei)
1. Startfragen = die Lücken aus Phase 2 als JSON-Datei `projects/<name>/fragen.json` (Liste `[{"frage": "...", "neuheit": 0.8, "machbarkeit": 0.7}]`,
   nur diese, in VoI-Reihenfolge).
2. `python -m asd.lab_loop --domain <name> --fragen projects/<name>/fragen.json --runden <N>`
3. Nach JEDER Runde liest du `lab_report.md`, `decisions.md` und die neueste `runde*.json` und meldest in 3 Zeilen:
   Frage → geprüfte kanonische Aussage (oder „nicht geprüft“) → Red-Team-Ergebnis (Widerspruch ja/nein).
4. Ist eine Aussage angefochten oder unbrauchbar: Ursache benennen (Prüfer zu schwach? Frage falsch?), Prüfer härten, Selbsttest ergänzen.
5. Experimentell: Das Labor legt Versuchsaufträge an (`auftraege/A<n>_protokoll.md`) und hält an. Menschen messen verblindet in der
   vorgegebenen Reihenfolge, tragen in die CSV ein und starten denselben Befehl erneut; dann wird ausgewertet.
- **Abnahme:** Mindestens 1 geprüfte Aussage pro Ziel-Lücke ODER ein dokumentiertes negatives Ergebnis mit Grund.

## Phase 6: Neuheitsprüfung (Pflicht, vor dem Paper)
`python -m asd.novelty <name>` erzeugt `projects/<name>/neuheit.md` mit den ähnlichsten Befunden der Recherche je Aussage.
Für jede geprüfte Aussage:
- Gilt sie laut `kb.json` / `known_results.md` als bekannt: Label „Reproduktion“.
- Nur wenn nicht gefunden: Label „neu (laut Recherche vom <Datum>, N Quellen)“. Niemals „erstmals“ ohne diese Prüfung.
- Ehrliche Stufe: Reproduktion / neu-numerisch / neu-zertifiziert.
- **Abnahme:** Tabelle Aussage | Stufe | Neuheitslabel | Beleg (claim_id, Zitat-ID).

## Phase 7: Paper
Form wie das Suleman-Paper (Optimal lattices for a three-body power-law energy, 2026). Gemeint sind: dichtes Abstract mit Zahlen, „Summary of results“, nummerierte Theoreme mit „Proof.“/„Certificate.“, eine Remark zur trusted base, Tabellen zertifizierter Daten, Abbildungen, wo sie helfen (`Domain.figures` liefern), nummerierte offene Fragen und ein Methoden-Anhang. Das ist in `asd/paper.py` als `SULEMAN_FORM` hinterlegt.
`python -m asd.paper --domain <name> --autoren "<NAMEN>" --affiliation "<AFFILIATION>"` (Standard Englisch; Titel kommt aus dem Story-Plan, `--titel` überschreibt)
Anforderungen:
- Jede Aussage trägt ihre Stufe; „Theorem“ nur für Zertifikate.
- Ein Abschnitt „Negative Ergebnisse und Red-Team“ und einer „Grenzen“: Modellannahmen, die die Resultate tragen, stehen im Text.
- Literatur nur aus Phase 1, mit DOI/arXiv-ID.
- Agenten nur in Appendix A; Herkunftstabelle in Appendix B; keine `[C-…]`-Marken im PDF.
- **Abnahme:** `pruefprotokoll.json` zeigt 0 Verstöße, `paper.pdf` und `referee_report.md` existieren, `python -m asd.phases <name>` zeigt Phase 7 OK.

## Phase 8: Übergabe
- `projects/<name>/` enthält: `state.json`, `prereg.md`, `decisions.md`, `lab_report.md`, `lueckenkarte.md`, `neuheit.md`, `runde*.json`, `paper.*`.
- Ein Befehl reproduziert die Zertifikate: `python -m asd.recheck <name>` (Selbsttest + erneute Prüfung aller Aussagen in `state.json`).
- Commit und Push. Nenne den Commit-Hash und eine 5-Zeilen-Zusammenfassung:
  1. Neuheiten mit Stufe,
  2. Reproduktionen,
  3. negative Ergebnisse,
  4. bekannte Schwächen,
  5. Stand von `python -m asd.phases <name>` (alle Phasen OK).

## Verbotene Abkürzungen
- Recherche überspringen, verkleinern oder durch eigenes Wissen ersetzen.
- Fragen ohne Lückenkarte frei wählen lassen.
- Einen Prüfer schwächen, damit eine Aussage besteht.
- Eine Aussage als neu bezeichnen ohne Phase 6.
- Phasen zusammenfassen oder „später nachholen“.
```

## Warum genau diese Punkte (aus unseren eigenen Fehlern)
- **Phase 1 mit harten Zahlen:** Ohne sie fällt die Recherche klein aus oder wird übersprungen. Im ersten Proofreading-Lauf
  fehlten die Klassiker fast ganz (Ninio 1975: kein Treffer).
- **Phase 2 und 3 (Suleman-Rezept):** erst die Lücken aus der Literatur, dann ein Prüfer, der Aussagen über Unbekanntes
  bestätigen kann (Optimum, Vergleich, Schranke).
- **G2, G3 und `widerspricht()`** schließen die drei gefundenen Fehler: Der Agenten-Text behauptete mehr als die Prüfung (R1:
  „Knick“), ein Agent setzte die Toleranz selbst (H4, Q8), und das Red-Team war zu streng.
- **Phase 6** verhindert, dass eine Reproduktion als Neuheit verkauft wird.
