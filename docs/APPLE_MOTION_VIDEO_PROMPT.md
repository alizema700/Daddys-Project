# Prompt: prob — technical video in Apple-keynote motion style (≈ 2:00, with voice)

Paste everything below the line into Claude Code inside this repository.

---

You are building our **technical video** for Hack-Nation Challenge #3 (Databricks, "Agentic Scientific Discovery"). Deadline today 15:00 Zürich. Build it **in code** so every frame is reproducible from this repo: Remotion (React) for motion, a TTS voice for narration, ffmpeg for the final mux. Work in a new folder `video/` and do not touch anything else.

## 0 · Hard rules (the jury checks these)
1. **Every number comes from `results/FROZEN.json`** (read it at build time, never type it by hand). If a value is missing, render `—` and print a warning. Do not round differently than the file.
2. **No fake UI or fake results.** Animated diagrams and type are fine. Anything that shows real data or our site is a real screenshot/screen recording from `frontend/screenshots/` or a fresh `python frontend/screenshots.py` run, placed inside a device frame.
3. Name what is *not* shown: "no human baseline measured" (README). No "first", "novel", "proved for all" unless a claim carries it.
4. Source of truth for the architecture: `README.md` (agent table, policy table), `omni/config.yaml`, `omni/agents/*`. The diagram is `docs/flowchart/prob_flow.html`; rebuild it as Remotion components with the same layout, colors and node names.

## 1 · Look (Apple keynote, dark)
- 1920×1080, 30 fps, H.264, ~120 s. Safe margins 120 px.
- Background `#060C17` → `#0B1A2C` vertical gradient, one soft teal radial glow (`#0F4C5C`, 55 %) that drifts slowly (±40 px over 20 s).
- Accent teal `#2BC4D6`; reject `#E5615F`; policy/human `#E3A93C`; text `#EEF3F8`; muted `#8C98AA`.
- Agent colors: Lead `#3D6FDB`, Scout `#4D86E6`, Planner `#16929F`, Researcher `#2E9460`, Verifier `#22B3C9`, Red team `#D14C4C`, Learner `#7C5DD8`, Scribe `#5D6878`, Scientist (human) `#C98A1E`.
- Type: Instrument Sans (headlines 96–120 px, weight 700, tracking −2.5 %), Instrument Serif *italic* for the one accent phrase per scene, JetBrains Mono for ids, commands and file names. Never more than 8 words on screen at once outside the diagram.
- Cards: radius 22, fill white 4.5 %, 1 px border white 10 %, inner top highlight; the Verifier card alone glows.

## 2 · Motion language (Apple Motion feel)
- Springs everywhere: Remotion `spring({damping: 200, mass: 0.9, stiffness: 120})` for moves; text enters with blur 12 px → 0, y +24 → 0, opacity 0 → 1 over 18 frames, words staggered by 3 frames.
- Camera: one slow push-in per scene (scale 1.00 → 1.04), cuts land on narration beats. Between scenes a 12-frame cross-dissolve with a slight scale-through; no wipes, no spins, no glitch.
- Diagram: edges draw on with stroke-dashoffset; a glowing pulse (`#BFF6FF`, blur 3) travels each handoff; the node it reaches lifts (scale 1.03, border → teal) for 10 frames.
- Numbers count up with tabular figures, easing out over 24 frames, and land exactly on the FROZEN value.
- Reject = card shakes 6 px twice and turns red border; Certificate = small teal square "∎" stamps in with a scale overshoot 0.6 → 1.08 → 1.
- Device frames: real screenshots sit in a MacBook-style frame (draw it in CSS: rounded dark bezel, thin highlight), floating with a soft shadow, slow parallax.
- Respect pacing: one idea per scene, ~6–12 s each.

## 3 · Voice
- English, calm, precise, ~150 words/min, no hype. Use ElevenLabs if `ELEVENLABS_API_KEY` is set (voice: a neutral, warm narrator, stability 0.55, similarity 0.75, style 0.15), otherwise OpenAI TTS `gpt-4o-mini-tts` if `OPENAI_API_KEY` is set (voice `alloy`, instruction: "calm technical keynote narrator"), otherwise macOS `say -v Samantha` as fallback. Generate one WAV per scene into `video/audio/`, measure each duration, and set each scene's length = voice length + 0.6 s.
- Music: soft ambient pad, −24 LUFS under voice, ducked −8 dB while speaking. Only royalty-free or self-generated; if none is available, no music.
- Subtitles: burn-in optional, always export `video/out/prob_technical.srt` from the script.

## 4 · Storyboard and narration
Build each scene as its own Remotion composition section. `{…}` = value from `results/FROZEN.json` (path given).

| # | Scene (on screen) | Narration |
|---|---|---|
| 1 | Black. The word **prob** fades in, then the headline "Agents propose." and, in teal italic serif, "Only code accepts." | "AI agents can now write scientific claims faster than anyone can check them. prob is a research lab where agents propose, and only code is allowed to accept." |
| 2 | Full diagram assembles node by node (Question → Lead → Planner ∥ Scout → Researcher → Verifier → Certificate). | "A question goes to a lead agent. It dispatches a planner and a scout in parallel, orchestrated by Omnigent." |
| 3 | Zoom on Planner: two option cards side by side, "expected gain" bars vs. "verifier calls" cost, one gets chosen. | "The planner never guesses. It compares at least two code-generated experiments by expected gain against verifier cost, within a fixed budget." |
| 4 | Researcher → Verifier. First claim bounces back red with reason text "rate outside [e^-10, e^10]"; second passes, ∎ stamps. Chips: `computed_rigorous`, `proved_lean`. | "The researcher runs the experiment and submits a typed claim. Only the verifier decides, with exact rational arithmetic, symbolic proofs or Lean. Here a claim fails on one rate. The next one passes and gets a certificate." |
| 5 | Amber dashed arc from Verifier back to Planner, label "surprise → reopen assumption A1". | "When a verified result contradicts a preregistered assumption, the lab reopens that assumption and re-plans." |
| 6 | Certificate → Red team (red card attacks, then "confirmed") → Learner → arrow back to Lead. | "A red team on a different model tries to break every result. A learner turns confirmed results into the next questions." |
| 7 | Policy band rises from the bottom; chips flip in: DENY harness_only, DENY verifier_only, DENY leak_guard, ASK publish_gate. One DENY flashes amber on a tool call. | "Policies bound what each agent can touch. Agents act only through a frozen harness. Writing to the lab state directly is denied. Publishing waits for a human." |
| 8 | Hash chain: blocks link left to right; text `record.jsonl · sha256`; then Databricks Delta + MLflow logos as plain wordmarks in muted white. | "Every call is a line in a hash-chained research record, exported to Delta tables and MLflow on Databricks." |
| 9 | Big numbers count up: `{replay.…speedup H8b}`× vs heuristic, CI `{…}`, `{replay.n_seeds}` paired seeds; second line `{…H8a}`× vs random. Small grey footnote: "no human baseline measured". | "On a preregistered replay benchmark with {n_seeds} paired seeds, the lab needs {H8b} times fewer verifier calls than a hand-written heuristic, and {H8a} times fewer than random search." |
| 10 | Grid of `{flaggschiff.topologien}` small tiles fills in: teal = proved, red = counterexample, empty = open; counters `{bewiesen}` · `{verletzt}` · `{offen}`. | "On a real question in molecular proofreading it decided {bewiesen plus verletzt} of {topologien} designs: {bewiesen} proved, {verletzt} broken by an exact counterexample, {offen} still open." |
| 11 | Real screenshot in device frame: run page; cursor clicks "Re-verify" → PASS ∎; "Tamper" → FAIL. | "You don't have to trust us. The certificate re-runs in your browser. Change one number by a tenth of a percent, and it fails." |
| 12 | Terminal card types `claude mcp add probatum -- uvx --from git+https://github.com/alizema700/Daddys-Project probatum-mcp`. | "And the same verifier runs as an MCP server in your own Claude." |
| 13 | Final: diagram shrinks to a small mark, headline "Claims you can check." and the repo URL in mono. | "prob. Claims you can check." |

Read the speedups from `results/FROZEN.json → replay` (H8a, H8b and their CIs); if the key names differ, find them with `python -c "import json;print(json.load(open('results/FROZEN.json'))['replay'].keys())"`. Do not reuse numbers from this prompt; the placeholders above are the only allowed form.

## 5 · Build steps
1. `npx create-video@latest video --template blank` (TypeScript), add `@remotion/google-fonts` for the three families.
2. `video/src/frozen.ts` loads `../results/FROZEN.json` at build time; `video/src/script.ts` holds the narration with placeholders filled from it.
3. `video/tts.py` writes `video/audio/scene_XX.wav` + `durations.json`.
4. Components: `Background`, `Headline`, `Node`, `Edge` (draw-on + pulse), `PolicyChip`, `HashChain`, `CountUp`, `TileGrid`, `DeviceFrame`, `Terminal`.
5. `npx remotion render Prob video/out/prob_technical.mp4 --codec h264 --crf 18`, then mix music with ffmpeg (`loudnorm` to −16 LUFS integrated).
6. Export stills of scenes 2, 4, 9 as PNG for the README.

## 6 · Check before you hand it over
- Run a script that prints every number shown on screen next to its FROZEN.json path; any mismatch fails the build.
- Watch the render once at 1× and list: scene timings, any text on screen longer than 8 words, any overlap or clipped text.
- Total length 1:45–2:15. Report the final path, duration and the TTS engine used.
