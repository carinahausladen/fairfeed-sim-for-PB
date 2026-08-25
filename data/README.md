# Data — the frozen MünchenBudget snapshot

This is the public data the paper is calibrated on. The scripts in the repository
root read from here; nothing needs the internet.

```
data/
├── ballot.json          # the 14 anchored MünchenBudget 2025 ballot proposals (calibrates q)
├── onboarding/          # the onboarding figure's source HTML
└── consul_sort_audit/   # feed-ordering audit across live Consul deployments (paper Table 1)
```

## Where it comes from

`ballot.json` is public proposal metadata (title, votes, comments count, status)
from the **Consul Democracy** deployment *MünchenBudget* at
<https://unser.muenchen.de/> — 14 records, the anchored 2025 ballot proposals. It
carries **no author names, no user identifiers and no comment text**, and the
`description` field is empty in every record. Each record does keep the
proposal's public URL, so the snapshot stays verifiable against its source. The
live site changes between cycles, so this is a **frozen snapshot**; re-fetching
it will *not* reproduce the paper. Use this snapshot.

`consul_sort_audit/` records which feed orderings each live Consul deployment
offers (the basis for Table 1); `onboarding/` is the source HTML for Figure 1.

## Licence

The **compilation** under `data/` — the selection, extraction and arrangement of
these records — is CC-BY-4.0; see [`../LICENSE-DATA.txt`](../LICENSE-DATA.txt).

The proposal titles it reproduces were written by MünchenBudget participants and
published by the City of Munich. No rights in that text are claimed or granted
here: it appears as factual metadata about a public participatory-budgeting
round, and any rights in it remain with its authors and with the City of Munich.

## Data statement

The comment-authorship analysis behind the paper's §Data statistics (self-comment
share, zero-comment proposals, single-agency concentration) is derived from public
MünchenBudget comment authorship and is processed under the GDPR scientific-research
basis (Art. 6(1)(f) / Art. 89), reported only in aggregate — where the paper
describes coordinated commenting it characterises an aggregate pattern, not a named
party. That author-derived corpus is **not distributed** with this package;
`paper_numbers.py` §2 prints the documented values quoted in the paper. The
simulation and both figures do not use it.
