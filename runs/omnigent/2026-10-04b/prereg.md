# Präregistrierung Omnigent-Lauf (2026-10-04 03:51)

- Startfrage F26: Welche der 27 noch offenen Topologien der Familie mit höchstens zwei gebundenen Zuständen (fam2_*) erreichen eta < e^{-2 Delta} = 1e-4 (exaktes Zertifikat erreichbar_liste), und für welche lässt sich die Schranke eta >= 1/D**2 beweisen?
- Erwartung (Annahme A1): Klassifikation 50 / 11 / 27: genau ['fam2_11', 'fam2_35', 'fam2_39', 'fam2_41', 'fam2_43', 'fam2_45', 'fam2_58', 'fam2_66', 'fam2_67', 'fam2_75', 'fam2_9'] verletzen eta >= e^(-2 Delta) unter den 88 Topologien
- Budget: 40 Verifier-Aufrufe

## 2026-10-04 03:51:29, vor dem Experiment (Omnigent, planner)
- Frage [F26]: Welche der 27 noch offenen Topologien der Familie mit höchstens zwei gebundenen Zuständen (fam2_*) erreichen eta < e^{-2 Delta} = 1e-4 (exaktes Zertifikat erreichbar_liste), und für welche lässt sich die Schranke eta >= 1/D**2 beweisen?
- Option O2 (tiefe_rechnung): Tiefe, möglichst zertifizierte Rechnung an wenigen, gezielt gewählten Punkten; genau eine Behauptung prüfen.
- Erwartete Verifier-Aufrufe: 1
- Verworfen: O1 breiter_scan
- Begründung: Deep certified computation on one claim has the highest expected gain (0.65) for only 1 verifier call; budget 40 left.

## 2026-10-04 03:51:30, vor dem Experiment (Omnigent, planner)
- Frage [F26]: Welche der 27 noch offenen Topologien der Familie mit höchstens zwei gebundenen Zuständen (fam2_*) erreichen eta < e^{-2 Delta} = 1e-4 (exaktes Zertifikat erreichbar_liste), und für welche lässt sich die Schranke eta >= 1/D**2 beweisen?
- Option O1 (breiter_scan): Breiter Scan über viele Parameterwerte mit geringer Präzision, danach bis zu 3 Kandidaten-Behauptungen prüfen.
- Erwartete Verifier-Aufrufe: 3
- Verworfen: O2 tiefe_rechnung
- Begründung: Broad low-precision scan complements the deep check by finding candidate claims; costs 3, and together with O2 (1) the 4 calls are well within the 40 budget.

## 2026-10-04 03:56:16, vor dem Experiment (Omnigent, planner)
- Frage [F27]: Ist die Klassifikation der Familie (bewiesen / Gegenbeispiel / offen) mit allen bisher zertifizierten Aussagen konsistent und vollständig gezählt?
- Option O2 (tiefe_rechnung): Tiefe, möglichst zertifizierte Rechnung an wenigen, gezielt gewählten Punkten; genau eine Behauptung prüfen.
- Erwartete Verifier-Aufrufe: 1
- Verworfen: O1 breiter_scan
- Begründung: O2 has the higher expected gain (0.65 vs 0.35) at cost 1 versus 3, and F27 is a single consistency claim. O1's broad scan is rejected as costlier and less targeted. Budget is 36 of 40, so it is not a constraint.
