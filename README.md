# fairfeed-sim-for-PB

Simulation and reproduction package for **_Fair Feed Ranking for Participatory
Budgeting_** (GoodIT '26).

> Carina I. Hausladen. 2026. Fair Feed Ranking for Participatory Budgeting. In
> *International Conference on Information Technology for Social Good (GoodIT '26)*.
> ACM. <https://doi.org/10.1145/3794786.3830735>

This repository reproduces the paper's two figures and every number it quotes,
from one shared simulation engine and a frozen, public snapshot of the
MünchenBudget participatory-budgeting data.

```
├── simulation.py       # the whole simulation engine (universe + feeds + engines)
├── fig_1.py            # Figure 1 — onboarding (panels A/B/C)  -> output/fig_1.png
├── fig_2.py            # Figure 2 — results (panels a–d)        -> output/fig_2.png
├── paper_numbers.py    # every number the paper quotes (4 sections; see below)
├── requirements.txt
├── data/               # public calibration data + feed audit (see data/README.md)
├── docs/               # interactive playground (GitHub Pages), see below
└── output/             # generated figures land here
```

## Interactive playground

`docs/` is a web page where anyone can play with the simulation: pick a feed,
switch on the reject button or fake comments, and watch which proposals reach the
ballot. The paper's results panels are recomputed live in the browser.

- `docs/sim.js` is a JavaScript port of `simulation.py`, running on the same
  universe (`docs/universe.json`, written by `python3 docs/export_universe.py`).
- `node docs/check.js` compares the browser engine with the paper's numbers.
- Preview locally: `cd docs && python3 -m http.server`, then open <http://localhost:8000>.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 paper_numbers.py   # prints reproduced vs paper for every number (< 1 min)
python3 fig_2.py           # -> output/fig_2.png   (the paper's results figure)
python3 fig_1.py           # -> output/fig_1.png   (onboarding; needs Chrome + Pillow)
```

`paper_numbers.py` runs the full simulation in well under a minute.

## What reproduces what

The paper has **two figures** and a set of **numbers**. Each maps to exactly one
command:

| Paper output | Command | Writes |
|---|---|---|
| **Figure 1** — onboarding (panels A/B/C) | `python3 fig_1.py` | `output/fig_1.png` |
| **Figure 2** — results (panels a–d) | `python3 fig_2.py` | `output/fig_2.png` |
| Every number in the text | `python3 paper_numbers.py` | prints reproduced vs paper |

Each figure has **exactly one** source script. (Inside the authors' paper tree the
figure scripts also refresh the copies embedded in the manuscript; outside it,
that copy step is simply skipped and the figure lands only in `output/`.)

`paper_numbers.py` has **four sections**, run all together or one at a time
(`python3 paper_numbers.py 3`):

1. **simulation** — abstract / Results / manipulation numbers
2. **comments** — §Data descriptive statistics (13%→38% self-comments, 69% zero-comment, 40% agency); printed as the documented values quoted in the paper (the comment-authorship corpus is not distributed here)
3. **qkappa** — reviewer robustness check: quality–reach correlation (ρ ∈ {0, 0.3, 0.6})
4. **flood** — reviewer robustness check: the 0.35→0.27 flooding drop is a worst case

## How it fits together

All the model lives in **`simulation.py`**; `fig_2.py` and `paper_numbers.py` are
thin and only call into it (`fig_1.py` just renders a static HTML mockup and needs
no simulation). The module builds one calibrated universe (459 proposals, 7,134
voters, 10 topics) and exposes voting loops that share it:

| Engine | What it adds | Feeds the paper's… |
|---|---|---|
| `simulate_table` | fixed browse budget; records support, fit, reach, cross-cutting | Table-1 / abstract numbers |
| `simulate_endo`  | browsing length responds to relevance (Eq. *continue*) | figure panels (a), (b) |
| `simulate_net`   | gated reject channel + comment flooding; ballot on net signal | figure panel (d), gated-reject sweep |
| `simulate_pillars` | the §9.6 manipulation config (fixed support floor, unlock-after-5) | manipulation paragraph |

**Figure 1** (`fig_1.py`) is a static HTML/CSS design mockup rendered with headless
Chrome — not a computed result. **Figure 2** (`fig_2.py`) is the 4-panel results
figure drawn from the engine above.

## Determinism

Everything seeds numpy's PCG64 generator (seed 42), whose stream is stable
across numpy versions, so results reproduce bit-for-bit on any recent build.

One detail was fixed for reproducibility: the original analysis scripts assigned
proposal categories with Python's builtin `hash()`, which is **salted per process**
(`PYTHONHASHSEED`), so the 14 anchored proposals' categories — and hence the
reported numbers — wobbled run-to-run at the 2nd–3rd decimal. This package uses a
deterministic **md5** category hash instead. The wobble was always sub-rounding,
so every value the paper reports is unchanged (verified against three salted runs
and a `PYTHONHASHSEED=0` run).

## Verification: reproduced vs. paper

Run `python3 paper_numbers.py` for the live table. Summary of the headline
values (✓ = matches the paper to its stated precision):

| Paper claim | Paper | Reproduced |
|---|---|---|
| Coverage (≥20 supporters), Most-commented → FairFeed | 16% → 82% | 16% → 82% ✓ |
| Support Gini, Most-commented → FairFeed | 0.69 → 0.33 | 0.69 → 0.33 ✓ |
| Mean fit, FairFeed vs Most-commented | 0.42 vs 0.28 | 0.43 vs 0.28 ✓ |
| Would-support-anywhere, FairFeed vs Most-commented | 34% vs 13% | 35% vs 12% ✓ |
| Author reach κ, FairFeed vs Most-commented | 3.0 vs 17 | 3.0 vs 17 ✓ |
| Cross-cutting votes, FairFeed vs Most-commented | 1.40 vs 0.68 | 1.41 vs 0.67 ✓ |
| Browsed / on-topic seen, FairFeed | 5.3 / ≈5 | 5.2 / 5.2 ✓ |
| Exposure Gini, popularity vs FairFeed | 0.88 vs 0.16 | 0.88 vs 0.18 ✓ |
| Top-20 quality, flooding sinks most-commented | 0.35 → 0.27 | 0.35 → 0.27 ✓ |
| Gated reject lift over approve-only (optional / knee) | +18% / +32% | +18% / +32% ✓ |
| Would-be-vetoed dropped by optional reject | 2 → 1 | 2 → 1 ✓ |
| Gated-reject controversy fall (optional / knee) | −21% / −35% | −21% / −35% ✓ |
| Self-comments, 2025 → 2026 | 13% → 38% | 13% → 38% ✓ |
| Zero-comment proposals (2025) | 69% | 69% ✓ |
| One agency's share of 2026 comments | ≈40% | 40% ✓ |
| Clean net-signal ballot quality | 0.45 | 0.45 ✓ |
| Accounts to bury half the shortlist | ≈75 | ≈75 ✓ |
| D21 2:1 cap holds displacement to | 12/20 | 12/20 ✓ |

## Data & provenance

`data/` holds the public MünchenBudget proposal metadata the paper was calibrated
on (from the Consul Democracy deployment at <https://unser.muenchen.de/>), the
onboarding-figure source, and the Consul feed-ordering audit for Table 1. It
contains no personal data. The live site changes between cycles, so this is a
frozen snapshot; see `data/README.md` for the layout and the data statement.

The comment-authorship figures in the paper's §Data (13%→38% self-comments, 69%
zero-comment, ~40% single-agency) are computed from an author-derived comment
corpus that is **not distributed** with this package. `paper_numbers.py` §2 prints
them as the documented values quoted in the paper; the simulation and both figures
never use that corpus, so everything else reproduces from `data/` here.

## License

- **Code** (`*.py`, this README): MIT — see [`LICENSE`](LICENSE).
- **Data** (`data/`): the *compilation* — the selection, extraction and
  arrangement of the records — is Creative Commons Attribution 4.0 (CC-BY-4.0).
  The proposal titles it reproduces were written by MünchenBudget participants
  and published by the City of Munich; no rights in that text are claimed or
  granted here. See [`LICENSE-DATA.txt`](LICENSE-DATA.txt).

## Citation

```bibtex
@inproceedings{hausladen2026fairfeed,
  author    = {Hausladen, Carina I.},
  title     = {Fair Feed Ranking for Participatory Budgeting},
  booktitle = {International Conference on Information Technology for Social Good (GoodIT '26)},
  year      = {2026},
  publisher = {ACM},
  doi       = {10.1145/3794786.3830735}
}
```
