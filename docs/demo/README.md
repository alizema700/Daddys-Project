# prob Live-Demo: Projektordner und technische Daten

## Dateien
| Datei | Zweck |
|---|---|
| `prob_live_demo.mp4` | fertiges Video, ohne Ton |
| `prob_live_demo.html` | dieselbe Demo als abspielbare Seite (Fonts und Paper eingebettet, läuft offline) |
| `src.html` | Quelltext der Demo (ohne eingebettete Fonts/Paper) |
| `build.py` | baut `prob_live_demo.html` aus `src.html` + Fonts + `paper_p1.b64` |
| `paper_p1.b64` | erste Seite von `projects/omni_proofreading/paper.pdf` (210 dpi, JPEG) |
| `narration.json` | Sprechertext mit Startzeit je Zeile |
| `voice.py` | legt die Stimme aufs Video (say / OpenAI / ElevenLabs) |

## Video
- Länge **60,0 s**, 1920 × 1080, **30 fps** (1800 Frames), H.264, yuv420p, CRF 17, faststart. Komprimierte Fassung zum Teilen: CRF 22, ca. 16 MB.
- Frame-genau gerendert: jeder Frame ist `render(t)` einer reinen Zeitfunktion (Playwright-Screenshot je Frame, dann ffmpeg). Keine Ruckler durch Bildschirmaufnahme.
- **Geschwindigkeit:** Die Animation ist auf 68 s Zeitachse gebaut und wird mit **Faktor 68/60 = 1,133** abgespielt (13 % schneller), damit sie genau 60 s dauert. Im Browser gilt derselbe Faktor.

## Ablauf (Sekunden im fertigen Video)
| Zeit | Was passiert |
|---|---|
| 0,0 | Landing, Cursor „Claude · test agent“ erscheint |
| 3,5 | Klick ins Eingabefeld, Frage wird getippt (ca. 3,9 s, ~20 Zeichen/s) |
| 8,9 | „Recorded“ gewählt |
| 10,0 | Klick „Research“ |
| 10,5 | Übergang ins Lab (0,9 s Blur-Überblendung) |
| 11,5 | Lead dispatch |
| 12,6 | Planner vergleicht O2 und O1 |
| 15,2 | Policy DENY (harness_only) |
| 16,9 | Researcher, Experiment E12 |
| 18,9 | Verifier lehnt ab (fam2_13, \|log k\| = 10.06), Karte wackelt |
| 22,6 | O19 verifiziert |
| 25,2 | O20 verifiziert, Surprise gegen A1 |
| 27,9 | A1 wieder geöffnet → F27 |
| 30,5 | Red team: confirmed |
| 32,8 | Learner: F28, F29 |
| 35,1 | O21 verifiziert |
| 38,8 | Klick auf O20 in „Verified results“ |
| 41,6 | Re-verify → PASS |
| 44,2 | Eine Rate ×1.001 → FAIL |
| 47,3 | Fast-Forward: Uhr, 88 Netzwerke füllen sich auf 50 / 11 / 27 |
| 51,9 | Freigabe durch Scientist, Paper steigt auf |
| 53,5 | Zoom auf Titel (2,0×) |
| 55,5 | Zoom auf Abstract (2,15×) |
| 57,4 | Endkarte |

## Bewegung
- **Kamera:** eine durchgehende Fläche, keine Schnitte. Zoom-Stufen 1,0× bis 1,85×; jede Fahrt ca. 1,0–1,6 s (im fertigen Video), Easing quintisch ein/aus, Zoom logarithmisch interpoliert, dazu ±0,6 % „Atmen“ gegen Standbilder.
  Wichtige Zooms: Eingabefeld 1,75× (ab 4,1 s) · Planner 1,55× (12,5 s) · Ablehnung 1,75× (19,1 s) · Inspector 1,85× (40,6 s) · zurück auf 1,0× (48,0 s).
- **Cursor:** kubisches Easing zwischen Wegpunkten, Größe bleibt bei jedem Zoom gleich. Klick = Ring (0,6 s) und kurzes Eindrücken des Cursors und Buttons.
- **Events:** einblenden in ca. 0,6 s (Blur 6 px → 0, 28 px nach oben), Häkchen springt mit Überschwinger auf, abgelehnte Karte wackelt zweimal.
- **Untertitel:** Pille unten, einblenden in ca. 0,4 s.

## Stimme
- 18 Zeilen, ca. 120 Wörter. Startzeiten in `narration.json`.
- `voice.py` misst jede Zeile; ist sie länger als ihr Fenster (bis 0,15 s vor der nächsten), wird sie beschleunigt, **höchstens 1,25×**. Lautheit danach auf −16 LUFS.
- Ausführen: `python3 docs/demo/voice.py --engine elevenlabs --voice <VOICE_ID>` (mit `ELEVENLABS_API_KEY`), Tempo mit `--rate`.

## Laufgeschwindigkeit des Labors (aus `results/FROZEN.json`, Lauf 2026-10-04b)
| Größe | Wert |
|---|---|
| Laufzeit gesamt | 6 min |
| Frage → Zertifikat (Median, n = 3) | 234 s |
| Latenz je Schritt (Median, n = 4) | 24 s (8–36 s; ohne Kaltstart 21 s) |
| Zeit in Agenten/LLM · Verifier · Experimenten | 98 s · 129 s · 362 s |
| Zertifizierte Claims · abgelehnte | 3 · 2 |
| Zertifikate pro Stunde | 27,9 |
| Kosten gesamt · pro Zertifikat | 1,01 USD · 0,34 USD |
| Wartezeit auf Menschen | 0 min |
| Hash-Kette | 63 Glieder, intakt (Kopf 2669b734ee86) |

Replay-Benchmark (25 gepaarte Seeds): Lab braucht im Mittel 2,0 Verifier-Aufrufe bis zum Treffer, Heuristik 7,92 (**3,96×**, 95 %-KI 3,34–4,80), Zufall 10,52 (**5,26×**). Ein Vergleich mit Menschen wurde nicht gemessen.

## Neu bauen
```bash
python3 docs/demo/build.py          # src.html -> prob_live_demo.html
# Video: jede Frame t = i/30 * 68/60 per Playwright rendern, dann ffmpeg -framerate 30
```
