"""
simulation — the FairFeed participatory-budgeting simulation engine, in one module.

This is the shared engine behind every simulation number and the results figure
in the paper "Fair Feed Ranking for Participatory Budgeting" (GoodIT 2026). The
thin `reproduce_*.py` scripts import from here; nothing about the model lives in
those scripts.

The model has three parts (paper Section "A Model of Exposure-Driven
Shortlisting"):

  * the proposals  — M = 459, calibrated on MünchenBudget 2025 (build_universe)
  * the voters     — N = 7,134, arriving sequentially through a seed proposal
  * the feeds      — Random, Newest, Most-commented (Consul defaults) and FairFeed

Three voting loops read the same universe:

  * simulate_table  — fixed browse budget; records support, fit, reach,
                      cross-cutting votes  (Table-1 / discovery numbers)
  * simulate_endo   — endogenous browsing length (Eq. "continue past rank r");
                      records how far each voter explores  (figure panels a, b)
  * simulate_net    — fixed budget + a gated reject channel and optional comment
                      flooding; ranks the ballot on net = supports - capped
                      rejects  (figure panel d, gated-reject sweep, manipulation)

Determinism
-----------
Everything is seeded off numpy's PCG64 generator (seed 42), which is stable
across numpy versions. The one historical non-determinism in the original
scripts was the proposal-category hash: `1_results_figures.py`/`1c` used Python's
builtin `hash()`, which is salted per process (PYTHONHASHSEED), so the 14 anchored
proposals' categories wobbled run-to-run. We adopt the deterministic md5 category
hash already used by `1f_gated_reject.py` ("matches notebook"). The wobble was
always sub-rounding, so every value the paper reports is unchanged; see
README.md for the verification table.

Run the scripts from this folder:  python3 paper_numbers.py
"""

import json
import hashlib
from pathlib import Path

import numpy as np

# ─────────────────────────── fixed model constants ──────────────────────────
M_PROPOSALS, N_AGENTS, N_CATEGORIES, PROPOSAL_DAYS = 459, 7134, 10, 60

# voter decision (paper Eq. "support")
BETA, LAMBDA, K_DECAY = 5, 0.5, 0.15          # fit slope, controversy discount, position decay
COMMENT_PROB_BASE = 0.04                        # base per-card commenting rate
OFFTOPIC_MATCH = 0.3                            # m_ij for an off-topic card

# endogenous browsing (paper Eq. "continue past rank r")
ENG_ALPHA, ENDO_B0, ENDO_BR, ENDO_BF, MAX_SCROLL = 0.6, 0.5, 4.0, 0.05, 80

# comment flooding (a manipulator preloads comments on the lowest-quality proposals)
N_FLOOD, FLOOD_AMT = 5, 120

# gated reject channel (paper Eq. "reject")
REJECT_W, UNLOCK = 1.5, 2                        # reject weight in the feed score; D21 unlock gate

DATA_DIR = Path(__file__).resolve().parent / "data"


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def gini(x):
    a = np.sort(np.asarray(x, float))
    n = len(a)
    return 0.0 if a.sum() == 0 else float(np.sum((2 * np.arange(1, n + 1) - n - 1) * a) / (n * a.sum()))


def _cat_of(title):
    """Deterministic proposal category in [0, N_CATEGORIES). md5, not builtin hash()."""
    return int(hashlib.md5(title.encode()).hexdigest(), 16) % N_CATEGORIES


# ─────────────────────────────── the universe ───────────────────────────────
class Universe:
    """The calibrated pool of proposals and voters, drawn once from seed `seed`.

    Attributes (all numpy arrays unless noted):
      M, N, C            sizes (proposals, agents, categories)
      winners, vetoed    the 14 anchored ballot proposals (list of dicts)
      cats, qs, contr    per-proposal category, latent quality q, controversy xi
      tsub, kappa        per-proposal submission day, author reach kappa
      seeds              per-agent seed proposal index (drawn proportional to reach)
      budgets            per-agent browse budget V (geometric, mean 10, capped 50)
      thresholds         per-agent support threshold tau (~N(0.5, 0.15))
      order              per-agent arrival order
    """

    def __init__(self, data_dir=DATA_DIR, seed=42):
        rng0 = np.random.default_rng(seed)
        ballot = json.loads((Path(data_dir) / "ballot.json").read_text())
        winners = sorted([b for b in ballot if b["status"] == "winner"], key=lambda b: -b["votes"])
        vetoed = sorted([b for b in ballot if b["status"] == "vetoed"], key=lambda b: -b["comments"])

        proposals = []
        # 10 funded winners: q linearly maps the real vote count onto [0.70, 1.0]
        for b in winners:
            proposals.append({
                "q": 0.70 + 0.30 * (b["votes"] - 966) / max(1329 - 966, 1),
                "t_submit": rng0.integers(0, PROPOSAL_DAYS),
                "category": _cat_of(b["title"]),
                "social_capital": rng0.pareto(1.5) + 1.0,
                "controversy": float(rng0.beta(1.5, 8)),
            })
        # 4 vetoed: pinned just above threshold (q=0.55) but high-controversy, high-reach
        for b in vetoed:
            proposals.append({
                "q": 0.55,
                "t_submit": rng0.integers(0, PROPOSAL_DAYS),
                "category": _cat_of(b["title"]),
                "social_capital": (rng0.pareto(1.5) + 1.0) * 1.5,
                "controversy": float(0.6 + rng0.uniform(0, 0.3)),
            })
        # the remaining 445 synthetic proposals: q ~ Beta(2,5), reach independent of q
        for _ in range(M_PROPOSALS - len(proposals)):
            proposals.append({
                "q": float(rng0.beta(2, 5)),
                "t_submit": int(rng0.integers(0, PROPOSAL_DAYS)),
                "category": int(rng0.integers(N_CATEGORIES)),
                "social_capital": float(rng0.pareto(1.5) + 1.0),
                "controversy": float(rng0.beta(1.5, 4)),
            })

        self.M, self.N, self.C = M_PROPOSALS, N_AGENTS, N_CATEGORIES
        self.winners, self.vetoed = winners, vetoed
        self.cats = np.array([p["category"] for p in proposals])
        self.qs = np.array([p["q"] for p in proposals])
        self.contr = np.array([p["controversy"] for p in proposals])
        self.tsub = np.array([p["t_submit"] for p in proposals])
        self.kappa = np.array([p["social_capital"] for p in proposals])

        # voters (drawn off the same generator, after the proposals)
        self.seeds = rng0.choice(self.M, size=N_AGENTS, p=self.kappa / self.kappa.sum())
        self.budgets = np.minimum(rng0.geometric(0.1, size=N_AGENTS), 50)
        self.thresholds = np.clip(rng0.normal(0.5, 0.15, size=N_AGENTS), 0.1, 0.95)
        self.order = np.argsort(rng0.integers(0, 14, size=N_AGENTS))


def build_universe(data_dir=DATA_DIR, seed=42):
    return Universe(data_dir=data_dir, seed=seed)


# ─────────────────────────────── the feeds ──────────────────────────────────
# A feed orders the proposals a voter sees. The three Consul rules read submission
# date / comment count / nothing; FairFeed reads only declared signals (topical
# match + an under-exposure boost + an optional reject subtraction).

def _feed_indices(name, U, s, V, S, rng, reject_on=False):
    if name == "Random":
        return rng.permutation(U.M)[:V]
    if name == "Newest":
        return np.argsort(-U.tsub + rng.uniform(0, 1e-6, U.M))[:V]
    if name == "Most-commented":
        # NB: no tie-break jitter here — the Consul default is a pure comment-count
        # sort. Early on every count is zero, so the stable argsort keeps hammering
        # the same first proposals (the concentration the paper reports). Adding
        # jitter would randomise those ties and wrongly spread exposure.
        return np.argsort(-S["comments"])[:V]
    # FairFeed
    match = np.where(U.cats == U.cats[s], 1.0, OFFTOPIC_MATCH)
    # dynamic under-exposure floor: half the average exposure so far (a neutral or
    # reject still counts as "seen"), so only the genuinely under-viewed are boosted
    boost = np.where(S["votes"] < max(3.0, 0.5 * S["votes"].sum() / U.M), 0.5, 0.0)
    score = match + boost
    if reject_on:
        score = score - REJECT_W * (S["down"] / (S["down"].max() + 1))
    return np.argsort(-(score + rng.uniform(0, 1e-6, U.M)))[:V]


FEEDS = ["Random", "Newest", "Most-commented", "FairFeed"]


# ──────────────────────── engine 1: fixed-budget browse ──────────────────────
def simulate_table(U, feed_name, run_seed, flood=False):
    """Fixed browse budget. Records, per run: accumulated support x_j, the
    rank-independent FIT of every non-seed support, the author REACH of every
    non-seed support, exposure votes e_j, and the per-citizen cross-cutting count.
    Source of the Table-1 / abstract numbers (coverage, Gini, fit, WSA, reach,
    cross-cutting)."""
    rng = np.random.default_rng(run_seed)
    supports = np.zeros(U.M, int)
    comments = np.zeros(U.M, int)
    votes = np.zeros(U.M, int)             # any-rating exposure (support/neutral/reject)
    if flood:
        comments[np.argsort(U.qs)[:N_FLOOD]] = FLOOD_AMT
    S = {"supports": supports, "votes": votes, "comments": comments}
    fit_votes, kappa_votes = [], []
    crosscut = np.zeros(U.N, int)
    for i in U.order:
        s = int(U.seeds[i]); V = int(U.budgets[i]); tau = U.thresholds[i]
        supports[s] += 1; votes[s] += 1
        if rng.random() < COMMENT_PROB_BASE * (1 + 3 * U.contr[s]):
            comments[s] += 1
        if V > 0:
            for r, j in enumerate(_feed_indices(feed_name, U, s, V, S, rng)):
                if j == s:
                    continue
                votes[j] += 1
                m = 1.0 if U.cats[j] == U.cats[s] else OFFTOPIC_MATCH
                fit = sigmoid(BETA * (U.qs[j] * m - tau))           # rank-independent
                decay = 1.0 / (1.0 + K_DECAY * r)
                if rng.random() < fit * (1 - LAMBDA * U.contr[j]) * decay:
                    supports[j] += 1; crosscut[i] += 1
                    fit_votes.append(fit); kappa_votes.append(U.kappa[j])
                if rng.random() < COMMENT_PROB_BASE * (1 + 3 * U.contr[j]) * decay:
                    comments[j] += 1
    return {"supports": supports.copy(), "votes": votes.copy(),
            "fit": np.array(fit_votes), "kappa": np.array(kappa_votes),
            "crosscut": crosscut}


# ──────────────────── engine 2: endogenous browsing length ───────────────────
def simulate_endo(U, feed_name, run_seed):
    """Browsing length responds to recent relevance (paper Eq. "continue past
    rank r"): a relevance-matched feed holds attention longer. Records how far
    each voter explores (browsed), how many on-topic cards she saw (rel_seen),
    and exposure votes e_j. Source of figure panels (a) and (b)."""
    rng = np.random.default_rng(run_seed)
    supports = np.zeros(U.M, int)
    comments = np.zeros(U.M, int)
    votes = np.zeros(U.M, int)
    S = {"supports": supports, "votes": votes, "comments": comments}
    browsed, rel_seen, int_seen = [], [], []
    for i in U.order:
        s = int(U.seeds[i]); tau = U.thresholds[i]
        supports[s] += 1; votes[s] += 1
        eng = float(U.qs[s]); nb = nrel = nint = 0
        for r, j in enumerate(_feed_indices(feed_name, U, s, MAX_SCROLL, S, rng)):
            if j == s:
                continue
            votes[j] += 1; nb += 1
            m = 1.0 if U.cats[j] == U.cats[s] else OFFTOPIC_MATCH
            fit = U.qs[j] * m
            nrel += (m == 1.0); nint += (fit >= 0.5)
            decay = 1.0 / (1.0 + K_DECAY * r)
            if rng.random() < sigmoid(BETA * (U.qs[j] * m - tau)) * (1 - LAMBDA * U.contr[j]) * decay:
                supports[j] += 1
            eng = ENG_ALPHA * fit + (1 - ENG_ALPHA) * eng
            if rng.random() >= sigmoid(ENDO_B0 + ENDO_BR * eng - ENDO_BF * r):
                break
        browsed.append(nb); rel_seen.append(nrel); int_seen.append(nint)
    return {"supports": supports, "votes": votes, "browsed": np.array(browsed),
            "rel_seen": np.array(rel_seen), "int_seen": np.array(int_seen)}


# ───────────── engine 3: fixed budget + gated reject + flooding ──────────────
def simulate_net(U, kind, run_seed, flood=False, reject_rate=0.0):
    """Fixed-budget browse with a gated reject channel. The reject option unlocks
    only after UNLOCK ratings (D21-Janecek gate); the ballot is ranked on
    net = supports - min(rejects, half supports) (the 2:1 cap). `kind` is one of
    'random' | 'newest' | 'mc' | 'fair'. Returns the quality of the 20 ballot
    proposals plus their controversy. Source of figure panel (d), the gated-reject
    sweep, and the approve-only baseline."""
    rng = np.random.default_rng(run_seed)
    sup = np.zeros(U.M, int); com = np.zeros(U.M, int)
    vot = np.zeros(U.M, int); dn = np.zeros(U.M, int)
    if flood:
        com[np.argsort(U.qs)[:N_FLOOD]] = FLOOD_AMT
    S = {"votes": vot, "comments": com, "down": dn}
    ron = reject_rate > 0
    for i in U.order:
        s = int(U.seeds[i]); V = int(U.budgets[i]); tau = U.thresholds[i]
        sup[s] += 1; vot[s] += 1; rated = 1
        if rng.random() < COMMENT_PROB_BASE * (1 + 3 * U.contr[s]):
            com[s] += 1
        if V == 0:
            continue
        if kind == "random":
            feed = rng.permutation(U.M)[:V]
        elif kind == "newest":
            feed = np.argsort(-U.tsub + rng.uniform(0, 1e-6, U.M))[:V]
        elif kind == "mc":
            feed = np.argsort(-com + rng.uniform(0, 1e-6, U.M))[:V]
        else:  # fair
            match = np.where(U.cats == U.cats[s], 1.0, OFFTOPIC_MATCH)
            boost = np.where(vot < max(3.0, 0.5 * vot.sum() / U.M), 0.5, 0.0)
            score = match + boost
            if ron:
                score = score - REJECT_W * (dn / (dn.max() + 1))
            feed = np.argsort(-(score + rng.uniform(0, 1e-6, U.M)))[:V]
        for r, j in enumerate(feed):
            if j == s:
                continue
            rated += 1; vot[j] += 1
            m = 1.0 if U.cats[j] == U.cats[s] else OFFTOPIC_MATCH
            fit = U.qs[j] * m; dec = 1 / (1 + K_DECAY * r)
            if rng.random() < sigmoid(BETA * (fit - tau)) * (1 - LAMBDA * U.contr[j]) * dec:
                sup[j] += 1
            elif ron and rated >= UNLOCK:
                if rng.random() < reject_rate * (U.contr[j] * (1 - fit)) * dec:
                    dn[j] += 1
            if rng.random() < COMMENT_PROB_BASE * (1 + 3 * U.contr[j]) * dec:
                com[j] += 1
    score = sup - np.minimum(dn, 0.5 * sup) if ron else sup   # 2:1 cap
    top20 = np.argsort(-score)[:20]
    return {"top20": top20, "q": U.qs[top20], "contr": U.contr[top20],
            "supports": sup, "down": dn}


# ─────────────────── analysis: gated-reject cast-rate sweep ──────────────────
RATE_OPTIONAL, RATE_KNEE, RATE_FORCED = 0.10, 0.30, 0.53
HIGH_CONTR = 0.6
QUALITY_SEEDS = range(300, 312)   # 12 voter realizations, seed-averaged (as in 1f / panel d)


def gated_reject_sweep(U, rates=(RATE_OPTIONAL, RATE_KNEE, RATE_FORCED), seeds=QUALITY_SEEDS):
    """Sweep the reject cast-rate r-bar across its empirical range and, for each,
    report seed-averaged top-20 quality, controversy, and the count of would-be-
    vetoed (xi > 0.6) survivors on the ballot. The cast-rate is set by the
    interface, so we sweep rather than assume one value."""
    def agg(rr):
        runs = [simulate_net(U, "fair", rs, reject_rate=rr) for rs in seeds]
        q = float(np.mean([r["q"].mean() for r in runs]))
        contr = float(np.mean([r["contr"].mean() for r in runs]))
        highxi = float(np.mean([(r["contr"] > HIGH_CONTR).sum() for r in runs]))
        return {"q": q, "contr": contr, "highxi": highxi}

    base = agg(0.0)                       # approve-only baseline (no reject)
    sweep = {rr: agg(rr) for rr in rates}
    out = {"approve_only": base, "rates": {}}
    for rr, s in sweep.items():
        out["rates"][rr] = {**s,
                            "dq_pct": 100 * (s["q"] / base["q"] - 1),
                            "dcontr_pct": 100 * (s["contr"] / base["contr"] - 1)}
    return out


# ───────── engine 4: the §9.6 "transparency / manipulation" lineage ──────────
# The manipulation analysis uses a slightly different FairFeed configuration than
# the main results: the reject unlocks only after UNLOCK_PILLARS ratings and the
# under-exposure boost reads a FIXED support floor (supports < 10) rather than the
# dynamic vote floor. We keep it separate so the main-results numbers are untouched.
UNLOCK_PILLARS = 5


def simulate_pillars(U, reject_rate, run_seed):
    """FairFeed with the §9.6 manipulation-lineage config (fixed support floor of
    10, reject unlock after 5 ratings), ranked on net = supports - downvotes.
    Returns the accumulated supports and downvotes."""
    rng = np.random.default_rng(run_seed)
    supports = np.zeros(U.M, int)
    comments = np.zeros(U.M, int)
    downvotes = np.zeros(U.M, int)
    S = {"supports": supports, "comments": comments, "downvotes": downvotes}
    allow_negative = reject_rate > 0
    for i in U.order:
        s = int(U.seeds[i]); V = int(U.budgets[i]); tau = U.thresholds[i]
        supports[s] += 1; rated = 1
        if rng.random() < COMMENT_PROB_BASE * (1 + 3 * U.contr[s]):
            comments[s] += 1
        if V == 0:
            continue
        score = np.where(U.cats == U.cats[s], 1.0, OFFTOPIC_MATCH)
        score = score + np.where(supports < 10, 0.5, 0.0)        # fixed support floor
        if allow_negative:
            score = score - REJECT_W * (downvotes / (downvotes.max() + 1))
        shown = np.argsort(-(score + rng.uniform(0, 1e-6, U.M)))[:V]
        for r, j in enumerate(shown):
            if j == s:
                continue
            rated += 1
            m = 1.0 if U.cats[j] == U.cats[s] else OFFTOPIC_MATCH
            decay = 1.0 / (1.0 + K_DECAY * r)
            if rng.random() < sigmoid(BETA * (U.qs[j] * m - tau)) * (1 - LAMBDA * U.contr[j]) * decay:
                supports[j] += 1
            elif allow_negative and rated >= UNLOCK_PILLARS:
                if rng.random() < reject_rate * (U.contr[j] * (1 - U.qs[j] * m)) * decay:
                    downvotes[j] += 1
            if rng.random() < COMMENT_PROB_BASE * (1 + 3 * U.contr[j]) * decay:
                comments[j] += 1
    return {"supports": supports, "downvotes": downvotes}


# ──────────── analysis: top-20 quality across feeds (figure panel d) ─────────
QUALITY_VARIANTS = {
    "Random": dict(kind="random"), "Newest": dict(kind="newest"),
    "Most-commented": dict(kind="mc"), "MC flooded": dict(kind="mc", flood=True),
    "FairFeed": dict(kind="fair"), "FairFeed + reject": dict(kind="fair", reject_rate=0.10),
}


def quality_bars(U, seeds=QUALITY_SEEDS, vis_seed=300):
    """Top-20 quality per feed variant: QF = mean over `seeds` voter realizations,
    Q20 = the 20 ballot-proposal quality values for one representative run
    (vis_seed). FIELD_Q is the field-mean quality (the random-pick floor)."""
    QF = {n: float(np.mean([simulate_net(U, run_seed=rs, **kw)["q"].mean() for rs in seeds]))
          for n, kw in QUALITY_VARIANTS.items()}
    Q20 = {n: simulate_net(U, run_seed=vis_seed, **kw)["q"] for n, kw in QUALITY_VARIANTS.items()}
    return QF, Q20, float(U.qs.mean())


# ─────────────── analysis: gaming the reject channel (burying) ───────────────
N_REPS = 8                                # voter realizations averaged for the organic ballot


def _organic_ballot(U, reject_rate=RATE_OPTIONAL, n_reps=N_REPS):
    """The honest FairFeed ballot with the reject channel on (net = supports -
    downvotes), averaged over n_reps voter realizations. This is the ground truth
    the attacker tries to bury.

    Uses `simulate_net` — the SAME FairFeed configuration as the main results
    (dynamic exposure floor, reject unlock after 2). The paper's manipulation
    paragraph was originally built on the older `simulate_pillars` config (fixed
    support floor, unlock after 5); it was switched to this config for
    consistency with the rest of the paper (clean ballot quality 0.45, ~75
    accounts to bury half, D21 2:1 cap holds to 12/20)."""
    runs = [simulate_net(U, "fair", 2000 + k, reject_rate=reject_rate) for k in range(n_reps)]
    sup = np.mean([r["supports"] for r in runs], axis=0)
    dn = np.mean([r["down"] for r in runs], axis=0)
    return sup, dn


def attacker_bury(U, Ks, two_for_one=False):
    """An attacker with an identity budget K casts one reject on each genuine
    top-20 proposal (one reject per account, worst case). Returns, for each K,
    (displaced, top-20 quality). With two_for_one=True the D21-Janecek 2:1 cap
    (counted rejects <= half a proposal's supports) is applied. This is the
    cost-asymmetry argument: comments scale with effort (one account), rejects
    with distinct verified identities."""
    sup, dn0 = _organic_ballot(U)
    genuine = np.argsort(-(sup - dn0))[:20]          # the honest net-signal shortlist
    gset = set(genuine.tolist())

    def displaced(K):
        dn = dn0.copy(); dn[genuine] += K
        if two_for_one:
            dn = np.minimum(dn, sup / 2.0)
        top20 = np.argsort(-(sup - dn))[:20]
        return 20 - len(gset & set(top20.tolist())), float(U.qs[top20].mean())

    return {int(K): displaced(int(K)) for K in Ks}


def attacker_smart(U, Ks, two_for_one=True):
    """A smart attacker downvotes ONLY the high-quality genuine winners (spares the
    low-merit ones) to poison ballot quality. Returns top-20 quality vs K."""
    sup, dn0 = _organic_ballot(U)
    genuine = np.argsort(-(sup - dn0))[:20]
    hi = genuine[np.argsort(-U.qs[genuine])[:10]]    # the 10 highest-quality winners

    def quality(K):
        dn = dn0.copy(); dn[hi] += K
        if two_for_one:
            dn = np.minimum(dn, sup / 2.0)
        top20 = np.argsort(-(sup - dn))[:20]
        return float(U.qs[top20].mean())

    return {int(K): quality(int(K)) for K in Ks}


def organic_clean_quality(U):
    """Mean quality of the honest net-signal top-20 (the attacker's 'clean' baseline)."""
    sup, dn0 = _organic_ballot(U)
    return float(U.qs[np.argsort(-(sup - dn0))[:20]].mean())


# ───── analysis: the D21 coupling — a reject is bundled with two approvals ─────
# The D21-Janecek rule is voter-level, NOT one-person-one-vote: each voter may
# cast P plus-votes and M minus-votes with P >= 2M, and a minus-vote unlocks only
# behind two plus-votes. So the negative channel cannot be wielded in isolation:
# every reject an attacker casts is *taxed* two approvals it must spend elsewhere,
# and (one vote per proposal) it can aim at most one of them at its own proposal.
# This function tests the self-promotion attack the coupling is meant to deter:
# seat a low-quality proposal P* on the ballot, comparing plain ballot-stuffing
# (honest approvals on P*) against weaponising the reject (downvote the rivals
# blocking P*, paying the D21 two-approval tax that scatters across the field).
SELFPROMOTE_RIVALS = 10        # a smart attacker downvotes the weakest genuine winners
SELFPROMOTE_NCAND  = 8         # candidate junk proposals, results reported as the median


def _seat_identities(U, net0, order, pstar, strategy, n_rivals):
    """Minimum identity budget K to lift proposal `pstar` into the net-support
    top-20. `strategy`: 'honest' = K approvals on pstar only; 'weaponise' = also
    one reject per account on each of `n_rivals` weakest winners, with the D21
    two-approval tax (K*(2*n_rivals-1) forced approvals) scattered uniformly over
    the rest of the field (the realistic case: forced votes the attacker cannot
    aim at itself, so they lift competitors)."""
    rivals = order[20 - n_rivals:20]
    busy = set([int(pstar)] + rivals.tolist())
    others = np.array([j for j in range(U.M) if j not in busy])
    for K in range(0, 3000):
        net = net0.copy()
        net[pstar] += K
        if strategy == "weaponise":
            net[rivals] -= K
            forced = K * (2 * n_rivals - 1)               # D21: P >= 2M, two approvals per reject
            net[others] += forced / len(others)           # scattered, cannot land on pstar
        if int(np.sum(net > net[pstar])) < 20:
            return K
    return None


def attacker_selfpromote(U, n_rivals=SELFPROMOTE_RIVALS, n_cand=SELFPROMOTE_NCAND):
    """Tests whether the D21-coupled reject opens a cheaper capture than plain
    ballot-stuffing. For the `n_cand` lowest-quality proposals ranked just outside
    the genuine top-20, returns the MEDIAN identity budget to seat one via honest
    approvals vs via weaponised rejects, plus the forced-approval tax multiplier
    and the field-mean quality (the junk an attacker tries to seat is far below it).
    The finding: weaponising buys only a bounded ~1.5x identity discount and still
    costs tens of verified identities, because each reject is taxed two approvals
    that scatter onto competitors. The binding resource stays verified identities,
    not effort -- the same conclusion as the burying analysis below."""
    sup, dn0 = _organic_ballot(U)
    net0 = sup - dn0
    order = np.argsort(-net0)
    cand = sorted([int(j) for j in order[20:60]], key=lambda j: U.qs[j])[:n_cand]
    honest = [_seat_identities(U, net0, order, p, "honest", n_rivals) for p in cand]
    weap   = [_seat_identities(U, net0, order, p, "weaponise", n_rivals) for p in cand]
    return {
        "honest_median": int(np.median(honest)),
        "weaponise_median": int(np.median(weap)),
        "forced_tax": 2 * n_rivals - 1,            # approvals forced per account at n_rivals rejects
        "junk_q": float(np.median([U.qs[p] for p in cand])),
        "field_q": float(U.qs.mean()),
        "n_voters": U.N,
    }
