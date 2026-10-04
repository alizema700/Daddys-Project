# Theoretical physics: what can be tuned in the framework

Working document for the theoretical-physics specialisation (branch `claude/intelligent-hopper-h89lhw`, not merged into the
default branch). It lists every setting that can be specified, tuned or optimised, in two parts:
A = knobs that already exist in the generic code, B = the design space of a theoretical-physics domain (`asd/domains/<name>_domain.py`).

**Hard rule that no tuning may break:** verifier tolerances, precisions and acceptance criteria are fixed *before* a run
(preregistration) and are never loosened to make a claim pass. Everything below that touches the verifier is a design decision
taken once per domain and covered by the self-test, not a knob to turn during a run.

---

## A. Knobs that already exist in the generic code

| # | Knob | Where | Current value | What it trades off |
|---|---|---|---|---|
| A1 | Researcher cascade (persona, model per stage) | `asd/discovery.py` `KASKADE` | sparsam/haiku → numeriker/haiku → skeptiker/sonnet → theoretiker/sonnet | cost vs. hit rate; the order decides who answers first |
| A2 | Researcher personas (prompt text) | `discovery.STRATEGIEN` | 4 generic personas | diversity of approaches (see B10) |
| A3 | Experiments per researcher | `forscher(max_ops=8)`, round 2: 6 | 8 + 6 | exploration depth vs. tokens/compute |
| A4 | Strength maximisation | `solve_cascade(staerkung=2)` | 2 attempts | stronger/more general theorems vs. cost |
| A5 | CEGIS refinements | `discovery.py` `len(cegis) < 3` | 3 | how often a counterexample is fed back |
| A6 | Stop without progress | `lab_loop --stopp-ohne-fortschritt` | 3 rounds | persistence vs. waste |
| A7 | Thread rule (stay in thread) | `lab_loop.faden_fortschritt(fenster=2)` | 2 rounds | depth vs. breadth |
| A8 | Integrator: questions per batch, share of literature-open questions, max. 1 anchor | `integrator_fragen(k=5)` prompt | 5, ≥ 50 %, ≤ 1 | novelty vs. feasibility |
| A9 | Learner preference order | `lernen()` prompt | generalisation > edge case > counterexample | which follow-ups get explored |
| A10 | Red team: counter-checks per claim | `lab_loop.red_team` (2), `cli redteam` (≤ 6, `--auto`) | 2 / 6 | robustness vs. verifier calls |
| A11 | Planner option types, cost and gain heuristics | `asd/planner.py` or `Domain.optionen()` | scan (3), deep (1), generalisation (2), edge case (2) | which experiment the planner prefers |
| A12 | Verifier budget per Omnigent run | `state.json budget_verifier`, `omni_setup --budget-verifier` | 40 | run length |
| A13 | Omnigent limits | `omni/config.yaml` | 40 USD, ASK at 10/20, 3 dispatches/turn, 300 tool calls, researcher 30 | cost vs. autonomy |
| A14 | Models per Omnigent role | `omni/agents/*/config.yaml` | lead opus, red team opus, scout/learner haiku, rest sonnet | independence of red team vs. cost |
| A15 | Scout size | `research.run(n_queries=40, per_query=30, keep=300, kette=15)` | keep doubled 150 → 300 | coverage vs. time |
| A16 | Phase-1 thresholds | `asd/phases.py SCHWELLEN` | 1000 / 100 / 60 / 8 classics | literature depth required before the lab starts |
| A17 | Literature sources | `research.py` | arXiv, Europe PMC, Crossref, `literature/` | **INSPIRE-HEP is missing** (central for hep-th/hep-ph/gr-qc) |
| A18 | Leak guard | `Domain.recherche_sperre`, `omni/leak_guard.json`, CEL `leak_guard` | Suleman terms + paths | contamination control |
| A19 | Novelty search | `novelty.check_claim` | 3–5 queries, 8 hits/source, 30 abstracts | false "new" vs. cost |
| A20 | Paper gate | `writer.write(rounds=2)`, `QUANT`, `SCHWELLE`, `ENV_RANK` | 2 correction rounds | strictness of text checks |
| A21 | Paper form | `paper.SULEMAN_FORM`, `--fachgebiet`, `Domain.fachgebiet` | Suleman 2026 | journal style (e.g. PRD/JHEP/CMP variants) |
| A22 | Publishability criterion | `asd/quality.py` | ≥ 1 rigorous, novel main result, 0 violations, no major fixable referee point | when `run_forever` stops |
| A23 | LLM backend, cache, replay, seed salt | `ASD_LLM`, `ASD_MODEL`, `ASD_SEED_SALT`, `cache/llm/` | `claude -p`, sonnet | reproducibility |
| A24 | MCP timeouts | `PROBATUM_TIMEOUT`, `PROBATUM_SELFTEST_TIMEOUT` | 120 s / 900 s | heavy computations need more |
| A25 | Self-test minimum | `asd/selftest.py` | ≥ 3 true, ≥ 3 false | verifier trust |
| A26 | Statistics (only for Monte-Carlo-type claims) | `experimental.py`, `stats.py` | α 0.05, 20 000 permutations, seed 12345, BH, FPR ≤ 0.08 | statistical claims |

---

## B. Design space of a theoretical-physics domain

### B1. Choice of subfield / problem class (first decision, determines everything else)
Good candidates are fields where a statement can be **decided by computation**:
- **Mathematical physics / variational problems:** lattice energies, packing, optimal configurations (existing `lattice` domain).
- **Statistical mechanics:** exactly solvable and finite models (Ising/Potts/vertex models), transfer matrices, high/low-temperature
  series, bounds on free energies, critical points by duality.
- **Quantum many-body / spin chains:** exact diagonalisation, Bethe ansatz, spectral gaps, ground-state energy bounds,
  symmetry sectors, integrability tests (commuting charges).
- **Quantum mechanics:** spectra of potentials, perturbation series, WKB, bound-state existence, rigorous eigenvalue enclosures.
- **QFT / particle physics (perturbative):** tree and loop amplitudes, Feynman integrals (master integrals, differential
  equations), beta functions, anomaly cancellation, Ward identities, group-theory factors.
- **General relativity:** exact solutions (Einstein equations satisfied symbolically), curvature invariants, horizons, geodesics,
  stability of orbits, energy conditions.
- **Classical mechanics / dynamical systems:** integrals of motion, stability, periodic orbits, bifurcations, KAM-type numerics.
- **Quantum information / foundations:** Bell/CHSH bounds, entanglement measures, SDP bounds (NPA hierarchy), channel capacities.
- **Non-equilibrium / biophysics (existing `proofreading` domain):** Markov networks, thermodynamic bounds.

### B2. Experiment primitives (`run_op`)
Each one is an experiment that agents may call. Choose per subfield, make each fail softly (`{"fehler": ...}`), bounded in time
and size:
- symbolic algebra (simplify, series, limit, solve, integrate, tensor algebra: curvature, Christoffels) — SymPy, optionally FORM/Cadabra
- exact linear algebra (rational / algebraic number fields) — python-flint, SymPy
- exact diagonalisation (dense/sparse, by symmetry sector) and Lanczos
- transfer matrices, partition functions on finite lattices (exact polynomials)
- Monte Carlo (Metropolis/cluster), with seeds and autocorrelation estimates
- ODE/PDE integration (adaptive, with error estimates), shooting methods for eigenvalues
- series/perturbation expansions to order N, Padé/Borel resummation
- Feynman integrals: IBP reduction, sector decomposition, numerical integration at high precision
- RG flows, fixed-point search, stability matrix
- optimisation: global minimisation (multi-start, basin hopping), SDP solvers
- group theory: Casimirs, tensor products, branching rules, anomaly coefficients
- dimensional analysis / units check of an expression

Tunable per primitive: allowed parameter ranges, maximum system size / truncation order, working precision, time limit,
caching, which outputs are shown to the agent (leak control).

### B3. Claim types (`check`) — the core of the domain
Narrow, typed, unambiguous checks. Proposed catalogue for theoretical physics:

| Claim type | Statement | Typical verification | Best level |
|---|---|---|---|
| `identitaet` | expression A ≡ B (on a domain) | symbolic simplification to 0; fallback: random rational points + Schwartz–Zippel | computed_rigorous |
| `wert` | quantity Q(params) = x | exact or interval arithmetic enclosure contains x within verifier tolerance | computed_rigorous / observed |
| `schranke` | Q(p) ≥ f(p) for all p in a region | symbolic positivity, SOS certificate with rational rounding, interval branch-and-bound | computed_rigorous |
| `grenzwert` / `asymptotik` | lim Q = L, Q ~ c·p^α | symbolic limit; or Richardson extrapolation at two resolutions | computed_rigorous / observed |
| `vorzeichenwechsel` / `phasenuebergang` | Q changes sign in [a, b] | interval evaluation at both ends + width ≤ fixed limit | computed_rigorous |
| `optimum` | configuration X minimises E | verifier's own global search (other seed, more starts, finer grid) + local Hessian | observed |
| `stabilitaet` | Hessian/linearisation positive definite at X | exact or interval eigenvalue bounds | computed_rigorous |
| `spektrum` / `gap` | eigenvalue λ_k in [lo, hi], gap > Δ | Temple/Kato bounds, interval Lanczos, exact characteristic polynomial | computed_rigorous |
| `loesung` | metric / field configuration solves the field equations | residual of the equations simplifies symbolically to 0 | computed_rigorous |
| `erhaltung` / `symmetrie` | Q is conserved / H commutes with S | commutator / Poisson bracket = 0 exactly | computed_rigorous |
| `integrabilitaet` | family of charges in involution | pairwise commutators = 0 for N ≤ N_max | computed_rigorous (finite N) |
| `koeffizient` | series coefficient c_n = r | exact computation to order n | computed_rigorous |
| `konsistenz` | Ward identity, sum rule, gauge independence, anomaly-free | explicit check of the identity | computed_rigorous |
| `exponent` (Monte Carlo) | critical exponent ν ∈ [lo, hi] | finite-size scaling fit, bootstrap CI, preregistered | statistical |
| `lean` | discrete/algebraic lemma | `asd/lean_check.py` | proved_lean |

For each claim type, decide: required fields (schema, `asd/mcp_schemas.py`), forbidden fields (tolerances), canonical
`describe()` sentence, `widerspricht()` partners, `angriffe()` generator, `gegenbeispiel()` format, `relevanz()`, `staerke()`.

### B4. Verification method and evidence level
Ladder (never skip a rung): `observed` (floating point, "numerical") → `statistical` (preregistered test) → `computed_rigorous`
(exact rational/algebraic, interval arithmetic with arb/mpmath `iv`, symbolic proof, rational SOS certificate) → `proved_lean`.
Tunable:
- which back end certifies which claim type (SymPy vs. python-flint `arb`, `fmpq`, `acb`; Lean for discrete lemmas)
- **independence**: verifier uses a different method/resolution/seed than the experiment (e.g. experiment = floating ED,
  verifier = exact characteristic polynomial)
- integer-relation finds (PSLQ) of closed forms stay `observed` unless a proof is attached
- standalone certificates (`certificate.json` + `check.py` with the standard library only), currently only for proofreading
  (`asd/certificates.py` needs to become generic)

### B5. Tolerances and precision policy (all owned by the verifier)
- absolute/relative tolerance per claim type (e.g. 1e-12 relative for exact-vs-float comparison, 2e-4 for the lattice limit)
- working precision (mpmath digits, arb bits), interval widths for sign changes
- convergence rule: result must agree at two resolutions / truncation orders / lattice sizes / step sizes
- extrapolation rule (which fit, how many points)
- maximum sizes (N spins, loop order, series order) for verifier runtime
- time limits per check (and what a time-out means: "not executable", never "passed")

### B6. Physics consistency gates (generic sub-checks every claim can be routed through)
dimensional analysis/units; known limiting cases (free theory, classical limit ħ→0, weak coupling, large N, flat space);
symmetry (Lorentz, gauge, discrete C/P/T, lattice symmetries); hermiticity/reality; unitarity, positivity, causality;
conservation laws; sum rules; regulator/scheme/gauge independence of physical results; Ward identities; anomaly cancellation.
Tunable: which gates are mandatory for which claim type.

### B7. Conventions and model parameters (`parameter()`, appears in the paper as `C-modell`)
units (natural ħ = c = k_B = 1 or SI), metric signature (+−−− vs −+++), Fourier and normalisation conventions, coupling
definitions, renormalisation scheme (MS-bar, on-shell), gauge choice, boundary conditions (periodic/open), thermodynamic-limit
convention. Fixed once and stated; convention mismatch is a classic false-claim source and belongs in the self-test.

### B8. Self-test design
- true anchors with known exact results (examples: 2D Ising critical temperature, harmonic oscillator and hydrogen spectra,
  Schwarzschild solves vacuum Einstein equations, one-loop QED/QCD beta-function coefficients, CHSH ≤ 2 classical / 2√2 quantum)
- near misses (value off by 1 %, sign change just outside the interval, bound violated at one point)
- convention errors (wrong metric sign, wrong normalisation), dimensionally inconsistent expressions
- tolerance-loosening attempt (`toleranz` field must be ignored), malformed input, out-of-range parameters
- every bug found later becomes a new self-test case (`selftest_extra.json` via `asd.verifier_redteam`)

### B9. Red team, contradictions, counterexamples
`widerspricht`: e.g. two different values for the same quantity, bound vs. a point below it, "stable" vs. a negative eigenvalue,
"solution" vs. non-zero residual. `angriffe`: opposite limit, other gauge/regulator, larger system size, parameter search for
violations of a bound. `gegenbeispiel` (CEGIS): parameter point where a bound fails, residual of an equation, eigenvalue
below a claimed gap.

### B10. Agent prompts and personas
Physics personas instead of the generic four, e.g. perturbative (expand and compute orders), numerical (scan, extrapolate),
symmetry/group theory, scaling/dimensional analysis, exact-solution seeker, skeptic (limits and counterexamples).
Tunable: personas, cascade order, model per stage, number of stages, `kontext` text (model, quantities, units, rules, anchors
without answers), `primitive_doc`/`claim_doc` wording.

### B11. Planner options specific to physics (`Domain.optionen`)
scan in parameter space; deep certified computation at few points; raise perturbative order / system size; take a limit;
symmetry/consistency check; generalisation (family, all N); edge case / counterexample search; finite-size scaling.
Each with cost in verifier calls and an expected-gain heuristic.

### B12. Literature and leak control
arXiv categories (hep-th, hep-ph, hep-lat, gr-qc, cond-mat.*, math-ph, quant-ph, nlin), INSPIRE-HEP API (to be added),
classics per subfield (≥ 8), blocked sources (answer keys, papers after a chosen cut-off for replay benchmarks),
novelty search queries by subfield.

### B13. Paper settings
`fachgebiet` (e.g. "Mathematical Physics", "High Energy Physics – Theory"), notation table, which environments are allowed
per level (Theorem only for `computed_rigorous`/`proved_lean`), figures (`figures()`: phase diagrams, RG flows, spectra, bounds
vs. parameters), "Status of the computer-assisted parts" remark, appendix on numerical methods and error control.

### B14. Compute
dependencies (SymPy, python-flint, mpmath, NumPy/SciPy, optional cvxpy for SDP, optional Lean 4 + Mathlib), time limits per
experiment and per check, parallelism, caching of expensive results, hardware limits for ED/Monte Carlo sizes.

---

## C. What can be optimised (metrics)

| Metric | Direction | Source |
|---|---|---|
| False-accept rate of the verifier (self-test, verifier red team, blind random claims) | must be 0 | `asd.selftest`, `asd.verifier_redteam`, `benchmarks/blind_claims.py` |
| Verifier calls / experiments until the first confirmed hit (N) | minimise | replay benchmark (H7/H8 design) |
| Share of confirmed claims at `computed_rigorous`/`proved_lean` vs. `observed` | maximise | `state.json` |
| Claim strength (`Domain.staerke`: main result, all-statements, family size) | maximise | `solve_cascade` |
| CEGIS success (refined conjecture passes after a counterexample) | maximise | `python -m asd.cegis` |
| Contested claims after red team | minimise (but report) | `state.json` |
| Novel main results (`offen_laut_literatur` / `nicht_gefunden`) | maximise | `asd.novelty` |
| Paper violations after gate | 0 | `pruefprotokoll.json` |
| Cost (USD, tokens) and wall time per confirmed claim | minimise | `cache/llm/`, Omnigent cost policy |

Speed metrics may only be optimised over agent-side knobs (A1–A15, B2, B10, B11). The verifier side (B3–B8) is optimised only
for correctness and rigour, never for pass rate.

---

## D. Implemented on this branch

| Item | Where | Setting now |
|---|---|---|
| Budget limits removed | `omni/config.yaml` (no `cost_budget`, no `max_tool_calls`), researcher (no `tool_call_cap`, no "at most 6 experiments"), `asd.cli status`, `asd.omni_setup --budget-verifier 0`, `lab_loop --runden 0`, `run_forever --max-runden 0` | unlimited by default; runs end on the content criteria (no progress, publishable, no open questions). Loop guard and the 3-dispatch concurrency bound stay (safety, not budget) |
| Papers kept by the scout | `lab_loop.scout`, `docs/WORKFLOW_PROMPT.md` | 300 (was 150) |
| Experiment weight (A3, B10, B11) | `Domain.max_ops / max_ops_folge / experiment_runden / experiment_gewicht` | theophys: 16 first-plan experiments, 12 per follow-up, 2 extra experiment rounds, ×1.5 gain for experiment-heavy planner options. Other domains unchanged |
| Hypotheses with provisional status → direction | `asd/hypothesen.py`, `lab_loop`, `asd.cli hypothese/hypothesen/experiment`, `planner.hypothesen_optionen` | see FRAMEWORK.md §2e |
| Consistency | `asd/konsistenz.py` (automatic after every new claim; CLI with `--recheck`) | contradicting confirmed claims are contested |
| Lean | `asd/domains/theophys/lean.py`; `Domain.auto_verstaerkung` | Lean 4 core, `decide`, axioms audited; auto-upgrade to `proved_lean` after confirmation |
| INSPIRE-HEP (A17) | `research.search_inspire`, novelty check | on for theophys |
| Physics personas (B10) | `TheoPhys.strategien/kaskade` | numeriker/haiku → symmetriker/haiku → exakt/sonnet → skeptiker/sonnet → stoerungstheoretiker/sonnet → skalierer/opus |

### Claim types of `theophys` (B3) and how they are verified (B4)

| Type | Verifier | Level |
|---|---|---|
| `identitaet`, `grenzwert`, `reihenkoeffizient` | SymPy, falsification at rational points | computed_rigorous |
| `schranke` | random sampling + best-first interval branch-and-bound (arb, 128 bit, endpoint arithmetic), certified counterexample | computed_rigorous |
| `dimension` | exact dimension algebra (M, L, T, I, Θ) | computed_rigorous |
| `spektrum`, `gap`, `entartung` | exact Pauli algebra → integer matrix → FLINT charpoly → rigorous root isolation (dim ≤ 400); exact values via minimal-polynomial divisibility; above 400: dense + Lanczos | computed_rigorous / observed |
| `kommutator` | exact Pauli algebra with Gaussian rationals | computed_rigorous |
| `ising_zustandsdichte`, `ising_grundzustand` [lean], `ising_freie_energie` | integer transfer matrix (Σg = 2^N checked), arb | computed_rigorous / proved_lean |
| `feldgleichung`, `kruemmungsinvariante` | symbolic Christoffel/Riemann/Ricci/Einstein/Kretschmann | computed_rigorous |
| `darstellung`, `beta_koeffizient` [lean], `asymptotische_freiheit` [lean], `banks_zaks` [lean], `anomaliefrei` [lean] | exact SU(N) group theory, Machacek–Vaughn two-loop (no Yukawa/quartic) | computed_rigorous / proved_lean |
| `klassische_schranke` [lean], `quantenwert` | enumeration of deterministic strategies; exact singlet value | computed_rigorous / proved_lean |
| `qm_eigenwert` | finite differences at 4000 and 8000 points + Richardson, rel. tol. 1e-6 | observed |

Fixed verifier constants (B5): eigenvalue interval width ≤ 1e-6 relative, ln Z/N width ≤ 1e-10 relative, 20 000 B&B boxes, exact spectra up to
dimension 400, Lean Ising enumeration up to 12 spins, time limit 300 s per check/experiment (`THEOPHYS_ZEIT`, `THEOPHYS_ZEIT_EXPERIMENT`).

### Verified so far
- Self-test 55/55 (23 true anchors such as Majumdar–Ghosh E0 = −3 (twofold), Schwarzschild vacuum and Kretschmann 48M²/r⁶, QCD b0 = 7, b1 = 26
  at nf = 6, SM anomaly freedom, CHSH = 2 and −2√2; 26 false statements; 6 Lean cases).
- The LLM prompts for the existing domains (lattice, proofreading) are byte-identical to the pre-change code (42 calls compared), so caches,
  replays and the frozen H7/H8 benchmark stay valid.
- End-to-end lab round with a scripted LLM: a human hypothesis becomes provisionally supported from three experiments, the lab switches to
  "beweisen", the verifier confirms the target claim, the hypothesis is final "bestätigt" (`tests/test_theophys.py`).

### Not done yet (suggestions)
- Physics-specific figures (`figures()`: spectra vs N, phase diagrams) — needs matplotlib in the environment.
- MCP server (`probatum`) does not list `theophys` yet (needs schemas in `asd/mcp_schemas.py`).
- Novelty check is still not run by `asd.cli pruefe` (Omnigent path), only by the lab loop.
- Mathlib-based Lean templates (real analysis, inequalities over ℝ) — current Lean templates are integer/finite only.
- Lanczos/DMRG with rigorous error bounds (Temple/Kato) for dimensions above 400.
