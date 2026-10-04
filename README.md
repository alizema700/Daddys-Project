# Verifier-Gated Discovery Lab (Hack-Nation, Challenge #3)

**Agenten schlagen vor, Code prüft.** Ein agentisches Forschungslabor für jede Domäne, in der sich Aussagen durch Rechnung,
Simulation oder Messung prüfen lassen. Vollständige Anleitung: **[docs/FRAMEWORK.md](docs/FRAMEWORK.md)**. In Claude Code lädt der
Skill `verifier-gated-lab` (`.claude/skills/`) die Anleitung automatisch.

```bash
python -m asd.new_domain meinthema                    # neue Domäne anlegen
python -m asd.selftest meinthema                      # Prüfer muss bestehen
python -m asd.lab_loop --domain meinthema --recherche --runden 0   # große Recherche
python -m asd.phases meinthema                        # welche Phase fehlt noch? (Labor startet erst bei 1-4 OK)
python -m asd.lab_loop --domain meinthema --fragen projects/meinthema/fragen.json --runden 6
python -m asd.novelty meinthema
python -m asd.paper --domain meinthema --autoren "..." --affiliation "ETH Zürich"
```
Experimentelle Fächer (Nasslabor): Domäne von `ExperimentalDomain` erben (Vorlage `asd/domains/assay_demo_domain.py`); das Labor
erzeugt präregistrierte, randomisierte, verblindete Versuchsaufträge, wartet auf die Messdaten und wertet sie mit fester Statistik aus.

Präregistrierte Ergebnisse (`prereg.md`, Rohdaten in `results/`):
| Bedingung (12 Fragen aus Suleman 2026, je 3 Läufe) | richtig | falsch |
|---|---|---|
| Claude pur | 50 % | 36 % |
| Claude mit eigenem Python | 72 % | 22 % |
| Framework (4 Forscher + Code-Prüfer) | 100 % | 0 % |
| Framework, Kaskade (Haiku zuerst) | 97 % | 3 % |

Weitere Befunde: KI- und Literatur-Vorwissen als GP-Prior helfen der Bayes'schen Optimierung nicht (H1, H5, beide präregistriert);
fünf geprüfte numerische Befunde zu offenen Fragen aus Suleman 2026 (`results/explore/`).





## Theoretical physics domain and hypothesis-driven direction (this branch)

- **Domain `theophys`** (`asd/domains/theophys_domain.py`): 23 claim types across spin chains (exact spectra by characteristic polynomial and
  rigorous root isolation), Ising lattices, general relativity, SU(N) gauge theory (β-function, anomalies), Bell inequalities, 1D quantum mechanics
  and symbolic analysis (interval branch-and-bound bounds). Self-test 55/55. Lean 4 proofs (`"beweis": "lean"`, level `proved_lean`) for the
  integer/finite claim types; confirmed claims are upgraded to Lean automatically when Lean is installed.
- **Hypotheses with a provisional status** (`asd/hypothesen.py`): every experiment is evaluated in code against the predictions of the hypotheses
  you (or agents) postulate; the status (testen → beweisen / entscheiden / verfeinern) decides what the lab does next. Only the verifier makes a
  hypothesis final.
- **Consistency** (`asd/konsistenz.py`): contradicting confirmed claims are contested automatically.
- **No budget limits**; the scout keeps 300 sources. Existing domains send byte-identical prompts (caches and frozen benchmarks stay valid).
- Details: `docs/FRAMEWORK.md` §2e–2g and `docs/THEORETICAL_PHYSICS_TUNING.md`.

```bash
python -m asd.selftest theophys
python -m asd.lab_loop --domain theophys --hypothesen my_hypotheses.json --ohne-gates   # quick start without phases 1-4 (logged as deviation)
python -m asd.hypothesen list --projekt theophys
python -m asd.konsistenz theophys --recheck
```

## Measured acceleration (preregistered replay, H7/H8)

Task: rediscover a known result without access to it (domain `lattice`, limit aspect ratio y_∞ ≈ 1.249621 of the optimal 2D lattice for
ν → ∞). Leak guard: Suleman 2026 and derived knowledge files blocked; canary test of the whole agent context green before every run.
Hit = a claim of type `grenzwert`/`y_inf` accepted by the unchanged verifier (numerical verifier, fixed tolerance 2·10⁻⁴ — not a proof).
Same models and budget in every condition
(`python -m benchmarks.replay_lattice`, raw data `results/replay_lattice/`, summary `results/replay_lattice.json`, figure `results/replay_lattice.png`).

<!-- replay:start -->
Paired design: every condition ran on the same 25 seeds (1000–1024).
Metric N = verifier calls to the first hit (31 = failed within budget 30). Source: `results/FROZEN.json` (frozen 2026-10-04T07:28:40, commit 69b42bc).

| Condition | mean N | median N | hits |
|---|---|---|---|
| LAB (integrator, code planner, verifier feedback, learning) | **2.0** | 2.0 | 25/25 |
| HEURISTIC (hand-written: simplest open question first) | 7.92 | 8.0 | 25/25 |
| NO FEEDBACK (same researchers, independent attempts) | 2.48 | 2.0 | 25/25 |
| RANDOM (random sub-questions, no integrator/learning) | 10.52 | 8.0 | 22/25 |
| ORACLE (knows the answer; analytic bound, not run) | 1.0 | 1.0 | – |

| Test (preregistered H8, Benjamini-Hochberg over m = 3, q = 0.1) | speedup | paired bootstrap 95 % CI | one-sided paired permutation p | BH-adjusted | verdict |
|---|---|---|---|---|---|
| **H8b, LAB vs. HEURISTIC** | 3.96× | 3.34–4.8 | 5e-06 | 1.5e-05 | supported |
| **H8a, LAB vs. RANDOM** | 5.26× | 3.5–7.5 | 1e-05 | 1.5e-05 | supported |
| H8c, LAB vs. NO FEEDBACK | 1.24× | 0.96–1.63 | 0.087 | 0.087 | not supported |

- The strongest comparison is H8b: a hand-written heuristic that reaches the target in every seed still needs about 3.96× as many verifier calls as the lab.
- Without verifier feedback the same agents are almost as fast on this easy task (H8c not supported): the gain comes from choosing the right question.
- No human baseline was measured; nothing here compares the lab with a human or a real laboratory.
- Independent scorer (`benchmarks/score_independent.py`, calls the verifier directly, not the benchmark's counting code): 68 of 68 hits with a logged claim re-verified, 0 disagreements; 29 hits from the earlier H7 runs (seeds 1000–1009) predate claim logging and are counted by the benchmark only.
<!-- replay:end -->

## Probatum Lab (web frontend)

`frontend/` is a static site that replays the logged runs and lets anyone re-check them in the browser. Nothing on it is typed by hand: `frontend/build_data.py` turns `runs/omnigent/*/` (record, trace, hash chain, sessions), `results/*.json` and the exported certificates into `frontend/data/`.

```bash
python frontend/build_data.py               # logs -> frontend/data/
python -m http.server -d frontend 8000      # open http://localhost:8000
python frontend/screenshots.py              # Playwright: start, pipeline, results; light, dark, mobile -> frontend/screenshots/
scripts/build_pages.sh --push               # publishes the same site on the gh-pages branch
```

- **Start page:** an excerpt of a real run plays back: a claim is rejected with the verifier's reason, the next one is confirmed, and ∎ appears. Below it are three key figures with their source files, then the list of runs.
- **Run page** (`run.html?run=<id>`) has three columns:
  - rounds in order;
  - the event stream, with one lane per agent (harness calls, handoffs, policy DENY/ASK, verdicts);
  - evidence and the claim register.
- **Re-verify:** for certificates, the unmodified standalone `check.py` runs in Pyodide, which loads only on click. For the run, the hash chain is recomputed with WebCrypto, exactly like `asd/chain.py`.
- **Tamper and re-verify** changes one rate by a factor of 1.001, or one character of a record line, and shows FAIL or the broken link.
- **Results page:** replay benchmark, wrong-answer rates with and without the gate, stress tests, the certified classification, and run metrics. Each section names its source file and the command that regenerates it.

## Databricks (Delta tables, MLflow, Model Serving)

The lab's logs go into Databricks as the single source for dashboards: the hash-chained ledger, the claims with their effective red-team votes, the policy decisions, the replay benchmark per seed, and the frozen numbers that README, paper and video use.

```bash
pip install -e ".[databricks]"
python -m asd.databricks_export                 # without credentials: delta/<table>/ (Delta Lake) + mlflow.db (MLflow)
export DATABRICKS_HOST=https://<workspace> DATABRICKS_TOKEN=<pat> DATABRICKS_WAREHOUSE_ID=<sql-warehouse-id>
python -m asd.databricks_export --catalog main --schema probatum   # Unity Catalog tables + MLflow experiment /Shared/probatum
```

| Table | Rows | Content |
|---|---|---|
| `ledger` | one per `record.jsonl` line | agent, command, input/output ids, result, duration, hash-chain link |
| `claims` | one per Omnigent claim | evidence level, status, effective red-team votes, contradictions |
| `gates` | one per policy event | DENY / ASK / human approval with reason |
| `experiments` | one per condition and seed | `run_id, seed, policy, dataset, step, x_index, y, mlflow_run_id, ts` (N = `step`) |
| `frozen` | one per value in `results/FROZEN.json` | the numbers used in every text |

- **MLflow:**
  - one run per Omnigent session, with its metrics and the record, chain and trace files as artifacts;
  - one run per benchmark condition, with N per seed and the H8 tests.
- **Dashboard:** queries are in `databricks/dashboard.sql`.
- **Model Serving:** with `ASD_LLM=databricks ASD_DBX_ENDPOINT=<endpoint>`, all agents call a Databricks serving endpoint. A different endpoint per role is possible via `ASD_DBX_ENDPOINT_SONNET`, `..._OPUS` and `..._HAIKU`. Caching and replay work unchanged.
- **Status:** the local export (Delta + MLflow) is tested end to end. The Unity Catalog SQL and the serving call are tested against stand-ins in `tests/test_databricks_export.py`; they have not yet been run against a live workspace.

## Use it in your own Claude (MCP server `probatum`)

**Your Claude is the researcher; probatum is the only one that accepts claims.** `probatum` exposes the lab as a local stdio MCP server:
your Claude proposes experiments and typed claims, probatum runs the experiments and decides every claim with the domain's code verifier
(exact rational certificates, symbolic proofs, fixed tolerances). No API key, no LLM calls, no shell, no network inside the server.

Requires [uv](https://docs.astral.sh/uv/) (`uvx`). The repository must be reachable for your git (public, or your GitHub credentials).

**Claude Desktop** — edit `claude_desktop_config.json` (macOS `~/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`):
```json
{
  "mcpServers": {
    "probatum": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/alizema700/Daddys-Project", "probatum-mcp"]
    }
  }
}
```
Restart Claude Desktop, then pick the prompt **research_round** (or **verify_my_result**) from the attachment/prompt menu.

**Claude Code** — one command (the `--` separates the server command):
```bash
claude mcp add --scope user probatum -- uvx --from git+https://github.com/alizema700/Daddys-Project probatum-mcp
```

**Claude Code plugin** (MCP server + the `verifier-gated-lab` skill):
```
/plugin marketplace add alizema700/Daddys-Project
/plugin install probatum@probatum
```
(`claude plugin validate --strict` passes for `plugin/` and `.claude-plugin/marketplace.json`.)

| Tool | What it does |
|---|---|
| `list_domains` | domains (`lattice`, `proofreading`) with experiment and claim types |
| `selftest(domain)` | verifier self-test (known true/false statements); **all other tools refuse a domain until it passed in this session** |
| `describe(domain)` | context, experiment primitives and claim types with field schemas, rules |
| `run_experiment(domain, spec)` | `{"op", "args"}` → experiment id + compact result (errors as `{"fehler": ...}`) |
| `submit_claim(domain, claim)` | the only way to confirm a result: `bestanden`, `level`, `grund`, `claim_id`; tolerance fields are removed and reported, unknown fields rejected |
| `challenge_claim(domain, claim_id, counter_claim)` | red-team by your Claude; a passing, contradicting counter-claim marks the claim contested |
| `list_claims`, `research_record` | confirmed / contested / rejected claims; every call is logged |
| `build_paper(domain, title, authors)` | confirmed claims + rejected attempts + writing rules (your Claude writes; every number must come from a claim) |

Resources: `probatum://domains/{domain}/claims`, `probatum://domains/{domain}/record`, `probatum://guide`. Prompts: `research_round`, `verify_my_result`.
Data: `PROBATUM_HOME` (default `~/.probatum/<domain>/state.json`, `record.jsonl`). Limits: `PROBATUM_TIMEOUT` (default 120 s per computation,
hard-killed subprocess), `PROBATUM_SELFTEST_TIMEOUT` (900 s). Tests: `pytest tests/test_mcp_server.py` (9 tests: self-test gate, valid claim
confirmed, claim shifted by 1e-6 rejected, own tolerance ignored, unknown field rejected, timeout), `python tests/mcp_protocol_check.py --voll`
(real stdio session: lists tools/resources/prompts, self-test, one confirmed and one rejected claim). Example session: [`docs/probatum_example_session.md`](docs/probatum_example_session.md).

## Evidence standards and deliverables

<!-- rubric:start -->
### Evidence standards

Every result is accepted only by a code verifier (`Domain.check`); agents only propose. Levels: `proved_lean`, `computed_rigorous` (exact rational / symbolic / interval certificates), `statistical` (preregistered test with CI), `observed` (numerical), `hypothesis`. Every claim and question carries an `origin` derived from the record (`AGENT:<role>` or `HUMAN-PROPOSED`). The run logs are sealed with a hash chain (`asd/chain.py`). The table below is generated and checked by `python -m asd.rubric`; it fails loudly on any ✗.

### Challenge deliverables map

| Requirement (challenge brief) | Met | Evidence (checked by `python -m asd.rubric`) |
|---|---|---|
| Omnigent orchestrates the live discovery workflow | ✓ | runs/omnigent/2026-10-04/sessions/ (17 dispatches by Omnigent lead `verifier-gated-lab`) |
| ≥2 specialist agents exchange structured results (handoffs with ids) | ✓ | runs/omnigent/2026-10-04/record.jsonl: agents ['learner', 'planner', 'redteam', 'researcher', 'scout']; planner option ids reused by researcher in 9 calls |
| Planner with budget chooses between ≥2 tests | ✓ | runs/omnigent/2026-10-04/state.json: 3 decisions with ≥2 options (cost in verifier calls, budget 40) |
| A result changes the next decision | ✓ | runs/omnigent/2026-10-04/record.jsonl: 3 decisions that cite a verified claim id (reopen / follow-up questions) |
| A surprising result reopens an assumption | ✓ | runs/omnigent/2026-10-04/record.jsonl: surprise at 2026-10-04T02:25:45 -> reopen {'annahme': 'A1', 'claim': 'proofreading-O14'} |
| Parallel sub-sessions | ✓ | runs/omnigent/2026-10-04/HIGHLIGHTS.md: 4 turns with ≥2 parallel sub-sessions |
| Parallel experiments | ✓ | 1 turns with ≥2 parallel experiment sessions |
| Human approval via Omnigent policies (ASK) and a policy DENY | ✓ | runs/omnigent/2026-10-04/HIGHLIGHTS.md: ASK raised+approved=True, DENY present=True; omni/config.yaml publish_gate |
| Shared research record; every decision reconstructable | ✓ | runs/omnigent/2026-10-04/record.jsonl (64 entries with input/output ids); hash chain intact (82 links, head 1fcb11696c9a) |
| Citations for facts | ✓ | projects/omni_proofreading/references.bib: 18 entries, 18 with DOI/arXiv/URL, 0 unverified |
| Run logs attached | ✓ | runs/omnigent/2026-10-04/sessions/: 15 session exports |
| Agent-generated hypotheses/claims marked (origin) | ✓ | runs/omnigent/2026-10-04/origin.json: origin derived from the record for 39/39 claims+questions |
| Uncertainty preserved (levels, confidence intervals) | ✓ | every claim has an evidence level; results/replay_lattice.json: speedups with bootstrap CI, hit rates with Clopper-Pearson CI |
| Controls documented (self-test, blind claims, red team, canary) | ✓ | verifier self-test 7 true / 11 false cases; benchmarks/blind_claims.py (random claims, 0/20 accepted); projects/proofreading/verifier_redteam.json; replay canary test |
| Approval gates documented | ✓ | README.md, section Omnigent orchestration: policy table |
| Needed validation named | ✓ | projects/omni_proofreading/paper.md: numbered open questions / needed validation; projects/omni_proofreading/referee_report.md |
| Measured improvement | ✓ | results/replay_lattice.json H8b: lab vs heuristic 3.96x (95% CI 3.34 to 4.80, p = 5e-06, 25 paired seeds); results/metrics_proofreading.json |
| Next experiment justified | ✓ | runs/omnigent/2026-10-04/sessions/lead: 7 lead decisions naming the next step with a reason |
| Agent specifications and policies in the repo | ✓ | omni/config.yaml + 6 agent specs; README agent table |

All requirements met.
<!-- rubric:end -->

## Omnigent orchestration

**Agents propose, Omnigent orchestrates, only the code verifier accepts.** The lab (`asd/`) stays the source of truth (verifier
`Domain.check`, self-test, `state.json`, `prereg.md`); Omnigent (`omni/`, tested with omnigent 0.16.0) orchestrates the live discovery
workflow. Agents act only through the frozen harness `python -m asd.cli <command>`; every call is appended to
`projects/<project>/record.jsonl` (time, agent, command, input ids, output ids, result), so every decision can be reconstructed.

| Agent | Decision it owns | Tools (asd.cli) | Input | Output |
|---|---|---|---|---|
| `verifier-gated-lab` (lead, PI) | what runs next; when to stop or switch thread; reacts to surprises | `status`, `plan`, `fragen`; `sys_session_send`, `sys_read_inbox` | research goal | round decisions, final summary |
| `scout` (haiku, read-only) | which evidence is relevant | `wissen`, `fragen` | domain, project | evidence / claim ids, open question ids |
| `planner` (sonnet, read-only + `waehle`) | which of ≥2 code-generated rival experiments to run (cost in verifier calls vs. expected gain, direction from the provisional hypothesis status); re-planning after a surprise | `options`, `waehle`, `reopen`, `plan`, `status` | question id / reopen request | chosen option id + rejected ids |
| `researcher` (sonnet) | experiments and the claim; **only agent allowed to call the verifier** | `doku`, `fragen`, `experiment`, `pruefe` | question id + option id | experiment ids, claim id (+ surprise flag) |
| `redteam` (**opus**, different model, read-only) | counter-checks that would pass if the claim were false | `status`, `doku`, `redteam` | claim id | counter-check ids, claim status |
| `learner` (haiku) | follow-up questions (generalisation > edge case > counterexample) | `wissen`, `folgefragen` | claim / round id | new question ids |
| `scribe` (sonnet) | building the paper — only after human approval | `python -m asd.paper` | domain, project | paper path |

Code-generated options: `asd/planner.py` (broad scan vs. deep certified computation, plus generalisation / edge case once a thread has a
confirmed claim). Surprises: `asd.cli pruefe` reports `ueberraschung: true` when a verified result contradicts a preregistered assumption
(`state.json: annahmen`); the planner then runs `asd.cli reopen` and re-plans.

**Policies** (`omni/config.yaml`, under `guardrails: policies:`; the lead's policies apply to every sub-agent):

| Policy | Type | Purpose |
|---|---|---|
| `spawn_bounds` | built-in `orchestration.spawn_bounds` | at most 3 `sys_session_send` dispatches per turn |
| `verifier_only` | CEL | DENY any direct write to `state.json` / `record.jsonl` / `projects/` (redirect, `tee`, `cp`, `mv`, `sed -i`, file write tools) — claims are stored only by `asd.cli pruefe` |
| `leak_guard` | CEL | DENY reading blocked sources (hold-out results, answer keys, pre-cutoff literature; paths/terms configurable, same list as `omni/leak_guard.json`) |
| `harness_only` | CEL | DENY shell commands other than the frozen harness (`python -m asd.cli`, `python -m asd.paper`) |
| `publish_gate` | CEL | ASK (human approval) before `asd.paper` or `git push` |
| `read_only` | built-in `orchestration.read_only_os` | scout, planner, redteam cannot write files |
| `no_pruefe` | CEL (per agent) | every agent except the researcher is denied `asd.cli pruefe` |
| `loop_guard` | Python (`asd.omni_policies`) | own loop guard that ignores `sys_read_inbox` (the built-in `detect_loop` blocks headless runs on the third empty inbox read); DENY after 5 identical calls |
| `allowlist` (per agent) | Python | each role may call only its own `asd.cli` commands (scout: wissen/fragen/status; planner: options/waehle/reopen/plan/status/hypothese; researcher: doku/fragen/experiment/pruefe; red team: status/doku/wissen/redteam; learner: wissen/folgefragen; scribe: paper only). The PI has **no shell at all** (no compute tools by construction) |
| `publish_requires_votes` | Python, reads `projects/<P>/state.json` | DENY `asd.paper` until every new confirmed claim has a red-team vote |
| `no_resubmission` | Python, reads the project state | DENY re-submitting a claim whose canonical hash the verifier already rejected (also enforced inside `asd.cli pruefe`) |
| `claim_phrases_ask` | Python | ASK on wording with a scope claim ("proved for all", "novel", "first") in texts the lab writes; the paper gate removes such phrases unless a claim carries them |

Offline check of all policy verdicts: `/root/omni-venv/bin/python benchmarks/omni_policy_check.py` (20/20). The Python policies need the
package in Omnigent's environment: `uv pip install -e . --no-deps` (inside the Omnigent venv), then restart the server (`omnigent stop`).

**Ledger and traces.** The first entry of every `record.jsonl` is the sha256 of the preregistration. The planner registers a falsifiable
hypothesis with a machine-checkable criterion before each experiment (`asd.cli hypothese`); the verifier result marks it `bestätigt` or
`widerlegt` ("the lab refutes itself", logged in `decisions.md`). `python scripts/export_trace.py runs/omnigent/<run>` writes `trace.json`
(Omnigent session id, every handoff with sha256 of message and inbox entry, every verifier receipt with certificate hash, policy events,
"later round rests on an earlier decision", hash chain) and `verification.passed`; the guided tour shows this seal.
Static replay page for GitHub Pages: `scripts/build_pages.sh --push` (branch `gh-pages`).

**Run it** (Python ≥ 3.12 venv outside the repo: `pip install "omnigent>=0.16"`; the claude-sdk harness uses the local Claude login):
```bash
python -m asd.omni_setup --quelle proofreading --projekt omni_proofreading     # fresh project: copied state + assumption A1 + start question
omnigent run omni -p "Domain proofreading, project omni_proofreading, start question F20, 3 rounds."
python benchmarks/omni_watch.py <session_id>                                   # status, pending approvals, record.jsonl
```
Recorded run: [`runs/omnigent/2026-10-04/`](runs/omnigent/2026-10-04/README.md) — session logs of the lead and all 14 sub-sessions,
`record.jsonl`, `decisions.md`, and [`HIGHLIGHTS.md`](runs/omnigent/2026-10-04/HIGHLIGHTS.md) with timestamps: 12 policy DENYs (leak_guard,
verifier_only, harness_only), 4 parallel dispatches, 3 option choices, 1 verifier rejection, 3 confirmed claims, a surprise that reopened
assumption A1 and changed the plan, opus red team, and a `publish_gate` ASK approved by a human. Result of the run: 8 new exactly
certified violations of η ≥ e^(−2Δ); classification of the two-bound-state family now 50 proved / 11 violations / 27 open.

## Dauerbetrieb

`run_forever.py` lässt das Labor unbeaufsichtigt laufen: Zyklus = `asd.lab_loop --runden 5` → `asd.paper` (inkl. Referee-Durchgang)
→ Qualitätskriterium `asd/quality.py:publikationsreif`. Es stoppt erst, wenn ein bestätigtes, rigoros geprüftes Hauptresultat
existiert, das laut Literatur neu ist (offen_laut_literatur / nicht_gefunden), das Paper 0 Verstöße hat und der Referee keine schwere,
mit vorhandenen Claims behebbare Schwäche meldet; dann baut es `paper_final.pdf` und beendet sich. Ein Zyklenlimit gibt es nur mit `--max-runden N` (Standard 0 = unbegrenzt).
Abstürze werden mit Traceback nach `logs/<domain>/supervisor.log` geschrieben und neu gestartet (Zustand in `projects/<domain>/state.json`);
Rate-Limits/Quota werden exponentiell abgewartet (1, 2, 4 … 30 min), nie abgebrochen. Bleibt ein Faden 3 Runden ohne neuen Claim,
erzwingt das Labor einen Themenwechsel (`--themenwechsel`).

```bash
tmux new -s lab 'caffeinate -dims python run_forever.py --domain <name> --autoren "A, B" --affiliation "ETH Zürich"'
# Linux statt caffeinate:  systemd-inhibit python run_forever.py --domain <name>
tail -f logs/<name>/status.md      # eine Zeile pro Zyklus: Zeit, Zyklus, Laborrunden, bestätigte Claims, Hauptresultate, Neuheit, Referee, Kriterium
less logs/<name>/supervisor.log    # Abstürze, Neustarts, Wartezeiten
tmux attach -t lab                 # live zusehen (Ctrl-b d: wieder lösen)
```
Test der Robustheit: `python run_forever.py --domain lattice --max-runden 2 --runden-pro-zyklus 1 --ohne-gates --test-fehler`
(künstlicher Absturz, Rate-Limit im Kindprozess und 2 Rate-Limits im LLM-Aufruf; alle drei werden abgefangen).

---

## Teil 1: Buchwald-Hartwig-Validierung (ursprüngliche Pipeline)

Agenten schlagen Hypothesen und Experimente vor. Akzeptiert wird nur, was Gates, Statistik oder Lean bestätigen. Projektregeln: `CLAUDE.md`. Präregistrierung: `prereg.md`. Entscheidungen: `decisions.md`.

## Schnellstart
```bash
git clone --depth 1 https://github.com/doylelab/rxnpredict.git
pip install numpy pandas scipy scikit-learn
python run.py                 # 4 Policies × 20 Seeds × 3 Datensätze, Gates, Claims, Tabellen (~3 min auf 4 Kernen)
python dashboard.py           # dashboard/index.html, liest nur tables/*.csv
python paper.py               # paper/results.md, jeder Satz mit claim_id
lean lean/ENRandom.lean       # kombinatorischer Kern von E[N_random] = (n+1)/(k+1) in Lean bewiesen (Log: lean/ENRandom.log)
```
Probelauf: `python run.py --seeds 3`. Ohne KI: `python run.py --policies random,gp_ei`.

## Aufbau
| Datei | Inhalt |
|---|---|
| `asd/data.py` | Datensatz, Treffer (Top-1 %), Sichten für die KI: `named` (Namen + SMILES) und `neutral` (Codes + Deskriptoren) |
| `asd/lab.py` | `Lab.run(i)`: einziger Zugang zu den Ausbeuten, jeder Aufruf geht in `experiments` |
| `asd/policies.py` | `random`, `gp_ei` (identisch zu `lab.py`), `hybrid`, `hybrid_neutral`; Schnittstelle `propose(history, rng)` |
| `asd/hypotheses.py` | Hypothesen-Agent: Prompt bauen, Antwort prüfen, `Hypothesis`, Vorwissen m(x) |
| `asd/hyptest.py` | eigener Test jeder KI-Hypothese auf 200 Zufallsexperimenten |
| `asd/stats.py` | gepaarter Permutationstest, Bootstrap-KI, Benjamini-Hochberg, exakte Momente von N |
| `asd/gates.py` | Gates G0–G7 inkl. H1, H2, Negativkontrollen, Lean |
| `asd/claims.py`, `asd/tables.py` | Claims aus Gate-Ergebnissen; die Tabellen `experiments`, `claims`, `gates` samt Validierung |
| `hypotheses/` | KI-Hypothesen mit Prompt, Rohantwort und Generator (Provenienz) |
| `lean/` | Lean 4 (Core, ohne Mathlib): kombinatorischer Kern von E[N_random] = (n+1)/(k+1) bewiesen; der Schritt E[N] = Σ P(N ≥ t) ist Standard und nicht formalisiert. Log: `lean/ENRandom.log`. Diskrete Claims (z. B. klassische Bell-Schranke) über `python -m asd.lean_check` -> Stufe `proved_lean` |
| `lab.py`, `results_selftest.json` | ursprünglicher Selbsttest (Referenz für Gate G2) |
