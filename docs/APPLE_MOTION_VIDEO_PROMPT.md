# Prompt: prob — technical video in Apple-keynote motion style (≈ 2:00, with voice)

Paste everything below the line into Claude Code inside this repository.

---

You are building our **technical video** for Hack-Nation Challenge #3 (Databricks, "Agentic Scientific Discovery"). Deadline today 15:00 Zürich. Build it **in code** so every frame is reproducible from this repo: Remotion (React) for motion, a TTS voice for narration, ffmpeg for the final mux. Work in a new folder `video/` and do not touch anything else.

## 0 · Hard rules (the jury checks these)
1. **Every number comes from `results/FROZEN.json`** (read it at build time, never type it by hand). If a value is missing, render `—` and print a warning. Do not round differently than the file.
2. **No fake UI or fake results.** Animated diagrams and type are fine. Anything that shows real data or our site is a real screenshot/screen recording from `frontend/screenshots/` or a fresh `python frontend/screenshots.py` run, placed inside a device frame.
3. Name what is *not* shown: "no human baseline measured" (README). No "first", "novel", "proved for all" unless a claim carries it.
4. Source of truth for the architecture: `README.md` (agent table, policy table), `omni/config.yaml`, `omni/agents/*`. The diagram is `docs/flowchart/prob_flow.html`; rebuild it as Remotion components with the same layout, icons, colors and node names.

## 1 · Look (Apple keynote, dark)
- 1920×1080, 30 fps, H.264, ~120 s. Safe margins 120 px.
- Background `#060C17` → `#0B1A2C` vertical gradient, one soft teal radial glow (`#0F4C5C`, 55 %) that drifts slowly (±40 px over 20 s).
- Accent teal `#2BC4D6`; reject `#E5615F`; policy/human `#E3A93C`; text `#EEF3F8`; muted `#8C98AA`.
- **Agents all look the same:** one neutral card (radius 18, fill white 4.5 %, 1 px border white 11 %). They differ only by a white monoline icon in a small round tile (stroke 1.5, round caps): Question = speech bubble, Lead = flag, Planner = two sliders, Scout = magnifier, Researcher = flask, Red team = crosshair, Learner = circular arrow, Scientist = person, Scribe = pen, Paper = document. Copy the exact icon paths from `ICON` in `docs/flowchart/prob_flow.html`. No per-agent colors.
- Color has meaning only: teal `#2BC4D6` = verifier / accepted, red `#E5615F` = rejected / DENY, amber `#E3A93C` = surprise / human gate (dashed border on Question and Scientist). Text `#EEF3F8`, muted `#8C98AA`.
- **One typeface only: Instrument Sans.** Hierarchy by size and weight (headline 96–120 px / 700, tracking −3 %; names 600; captions 500; labels 400). No serif, no monospace, also not for ids or commands. The accent phrase is the same font in teal.
- Never more than 8 words on screen at once outside the diagram. The Verifier card alone glows.

## 2 · Motion language: one diagram, one camera
- **The whole video is one continuous canvas**: the diagram from `prob_flow.html` (viewBox 0 0 1600 900) is built once; scenes do not cut between slides. A virtual camera flies over it and **zooms into exactly the part the narration is talking about**, then pulls back out.
- Camera move per scene: 1.6–2.0 s, quintic ease-in-out (`t<.5 ? 16t⁵ : 1−(−2t+2)⁵/2`), zoom interpolated in **log space** so the scale change feels constant-speed, center interpolated linearly. Movement starts ~0.3 s before the narration names the part and lands while it is said. Never cut, never snap; hold still while something animates inside the frame. Add a very slow drift (scale +2 % over the hold) so the frame never freezes.
- In Remotion: one `<Diagram>` component inside a wrapper with `transform: scale(s) translate(-x,-y)`, `s` and `x,y` from `interpolate()` over the camera keyframes below; motion blur via `@remotion/motion-blur` `<CameraMotionBlur samples={6} shutterAngle={180}>` during camera moves only.
- Inside the frame: edges draw on (stroke-dashoffset), a soft glowing dot (`#BFF6FF`, blur 3) travels each handoff with cubic ease, the node it reaches lifts (border → teal, scale 1.03) for 0.9 s.
- Text enters with blur 12 px → 0, y +24 → 0, opacity 0 → 1 over 18 frames, words staggered by 3 frames. Captions sit in a frosted pill at the bottom (backdrop blur 14 px).
- Numbers count up with tabular figures over 24 frames and land exactly on the FROZEN value. Reject = card nudges 6 px twice, border red. Certificate = teal square stamps in (scale 0.6 → 1.08 → 1).
- Real screenshots (scenes 11–12) fly in from the canvas as a device frame on the same camera path, no hard cut.

### Camera keyframes (viewBox x, y, width; height = width × 9/16)
| Scene | Target | Shows |
|---|---|---|
| 1 | 0, 0, 1600 | whole diagram |
| 2 | 30, 150, 760 | Question → Lead |
| 3 | 400, 110, 680 | Planner ∥ Scout → Researcher |
| 4 | 720, 110, 860 | Researcher → Verifier → Certificate |
| 5 | 560, 95, 720 | reject loop and surprise arc |
| 6 | 320, 200, 1240 | Red team → Learner → back to Lead |
| 6b | 840, 470, 700 | Scientist (ASK) → Scribe → Paper |
| 7 | 30, 450, 800 | policy band |
| 8 | 770, 450, 800 | shared-record band |
| 9–10 | 1040, 20, 520 then out to 0, 0, 1600 | KPI corner, then full view for the number scenes |
| 13 | 0, 0, 1600 → slow pull-out to 0.85× | end |

The "Guided tour" button in `prob_flow.html` plays exactly these moves; use it as the timing reference.

## 3 · Voice
- English, calm, precise, ~150 words/min, no hype. Use ElevenLabs if `ELEVENLABS_API_KEY` is set (voice: a neutral, warm narrator, stability 0.55, similarity 0.75, style 0.15), otherwise OpenAI TTS `gpt-4o-mini-tts` if `OPENAI_API_KEY` is set (voice `alloy`, instruction: "calm technical keynote narrator"), otherwise macOS `say -v Samantha` as fallback. Generate one WAV per scene into `video/audio/`, measure each duration, and set each scene's length = voice length + 0.6 s.
- Music: soft ambient pad, −24 LUFS under voice, ducked −8 dB while speaking. Only royalty-free or self-generated; if none is available, no music.
- Subtitles: burn-in optional, always export `video/out/prob_technical.srt` from the script.

## 4 · Storyboard and narration
Build each scene as its own Remotion composition section. `{…}` = value from `results/FROZEN.json` (path given).

| # | Scene (on screen) | Narration |
|---|---|---|
| 1 | Black. The word **prob** fades in, then the headline "Agents propose." and, in teal (same font), "Only code accepts." | "AI agents can now write scientific claims faster than anyone can check them. prob is a research lab where agents propose, and only code is allowed to accept." |
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
1. `npx create-video@latest video --template blank` (TypeScript), add `@remotion/google-fonts` and `@remotion/motion-blur`.
2. `video/src/frozen.ts` loads `../results/FROZEN.json` at build time; `video/src/script.ts` holds the narration with placeholders filled from it.
3. `video/tts.py` writes `video/audio/scene_XX.wav` + `durations.json`.
4. Components: `Camera` (keyframes above), `Diagram`, `Node` (shared card + icon), `Edge` (draw-on + pulse), `Caption`, `PolicyChip`, `HashChain`, `CountUp`, `TileGrid`, `DeviceFrame`, `Terminal`. Load only Instrument Sans via `@remotion/google-fonts`.
5. `npx remotion render Prob video/out/prob_technical.mp4 --codec h264 --crf 18`, then mix music with ffmpeg (`loudnorm` to −16 LUFS integrated).
6. Export stills of scenes 2, 4, 9 as PNG for the README.

## 6 · Check before you hand it over
- Run a script that prints every number shown on screen next to its FROZEN.json path; any mismatch fails the build.
- Check that no frame contains a hard cut inside scenes 1–10 and that the only font in the bundle is Instrument Sans.
- Watch the render once at 1× and list: scene timings, any text on screen longer than 8 words, any overlap or clipped text.
- Total length 1:45–2:15. Report the final path, duration and the TTS engine used.
