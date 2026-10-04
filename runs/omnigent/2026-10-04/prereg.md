# Präregistrierung Omnigent-Lauf (2026-10-04 02:20)

- Startfrage F20: Gibt es unter den 35 offenen Topologien der Familie mit höchstens zwei gebundenen Zuständen (fam2_*) weitere, die eta <= e^{-2 Delta} = 1e-4 erreichen (exaktes Zertifikat erreichbar_liste), oder lässt sich die Schranke für weitere Mitglieder beweisen?
- Erwartung (Annahme A1): Klassifikation 50 / 3 / 35: genau ['fam2_11', 'fam2_66', 'fam2_9'] verletzen eta >= e^(-2 Delta) unter den 88 Topologien
- Budget: 40 Verifier-Aufrufe

## 2026-10-04 02:21:07, vor dem Experiment (Omnigent, planner)
- Frage [F20]: Gibt es unter den 35 offenen Topologien der Familie mit höchstens zwei gebundenen Zuständen (fam2_*) weitere, die eta <= e^{-2 Delta} = 1e-4 erreichen (exaktes Zertifikat erreichbar_liste), oder lässt sich die Schranke für weitere Mitglieder beweisen?
- Option O2 (tiefe_rechnung): Tiefe, möglichst zertifizierte Rechnung an wenigen, gezielt gewählten Punkten; genau eine Behauptung prüfen.
- Erwartete Verifier-Aufrufe: 1
- Verworfen: O1 breiter_scan
- Begründung: O2 has the higher expected gain (0.65 vs 0.35) at 1 verifier call versus 3 for O1; the budget is ample (40 of 40 left), but the cheaper, deeper check is still the better use of it.

## 2026-10-04 02:26:32, vor dem Experiment (Omnigent, planner)
- Frage [F21]: Ist die Klassifikation der Familie (bewiesen / Gegenbeispiel / offen) mit allen bisher zertifizierten Aussagen konsistent und vollständig gezählt?
- Option O2 (tiefe_rechnung): Tiefe, möglichst zertifizierte Rechnung an wenigen, gezielt gewählten Punkten; genau eine Behauptung prüfen.
- Erwartete Verifier-Aufrufe: 1
- Verworfen: O1 breiter_scan
- Begründung: O2 costs 1 call with the higher expected gain (0.65), against 3 calls and 0.35 for O1 (broad scan); 38 of 40 calls remain.

## 2026-10-04 02:28:18, vor dem Experiment (Omnigent, planner)
- Frage [F24]: Wie verallgemeinern sich die thermodynamischen Unsicherheitsrelationen auf Proofreading-Systeme mit unvollständiger Information oder partieller Beobachtbarkeit der molekularen Zustände?
- Option O2 (tiefe_rechnung): Tiefe, möglichst zertifizierte Rechnung an wenigen, gezielt gewählten Punkten; genau eine Behauptung prüfen.
- Erwartete Verifier-Aufrufe: 1
- Verworfen: O1 breiter_scan
- Begründung: O2 has the higher expected gain (0.65 vs 0.35) at a third of the cost (1 vs 3 verifier calls); the broad scan O1 is rejected as costlier and less precise, and the budget (34 of 40 left) easily covers O2.
