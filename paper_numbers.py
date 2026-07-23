"""
numbers.py — reproduce every number the paper quotes, in one file.

Four sections, run top to bottom. Each prints the reproduced value next to the
value as it appears in the paper.

  1. simulation  — abstract / Results / manipulation numbers (from simulation.py)
  2. comments    — §Data descriptive statistics (from the scraped CSVs in data/)
  3. qkappa      — reviewer robustness check: does a quality-reach correlation
                   break the "exposure correction is costless" claim?
  4. flood       — reviewer robustness check: the 0.35 -> 0.27 comment-flooding
                   drop is a worst case (an upper bound on the damage)

    python3 numbers.py            # run all four sections
    python3 numbers.py 1 3        # run only sections 1 and 3

Sections 1, 3, 4 seed-average over the QUALITY_SEEDS voter realizations, exactly
as the paper figure does; section 2 is pure descriptive stats off the corpus.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import simulation as ff


# ═══════════════════════════════════════════════════════════════════════════
# 1. Simulation numbers (abstract / Results / manipulation)
# ═══════════════════════════════════════════════════════════════════════════
def section_simulation():
    U = ff.build_universe()
    FLOOR, WSA_BAR = 20, 0.5

    def line(label, got, paper):
        print(f"  {label:<34} reproduced = {got:<10} paper: {paper}")

    print("=" * 78)
    print("1. Simulation — every simulation number in the paper")
    print(f"  universe: {U.M} proposals, {U.N} voters, {U.C} topics  (seed 42, md5 categories)")
    print("=" * 78)

    # ── Table-1 / abstract numbers: fixed-budget browse ──────────────────────
    R = {n: ff.simulate_table(U, n, 42) for n in ff.FEEDS}

    cov = {n: (R[n]["supports"] >= FLOOR).mean() * 100 for n in ff.FEEDS}
    gv = {n: ff.gini(R[n]["supports"]) for n in ff.FEEDS}
    fitm = {n: R[n]["fit"].mean() for n in ff.FEEDS}
    wsa = {n: (R[n]["fit"] >= WSA_BAR).mean() * 100 for n in ff.FEEDS}
    reach = {n: R[n]["kappa"].mean() for n in ff.FEEDS}
    cc = {n: R[n]["crosscut"].mean() for n in ff.FEEDS}

    print("\n[Abstract / Results: coverage of the eligible pool, ≥20 supporters]")
    line("coverage FairFeed", f"{cov['FairFeed']:.0f}%", "82%")
    line("coverage Most-commented", f"{cov['Most-commented']:.0f}%", "16% (16–18% popularity sorts)")
    line("coverage Newest", f"{cov['Newest']:.0f}%", "18% (16–18%)")
    line("coverage Random", f"{cov['Random']:.0f}%", "53%")

    print("\n[Abstract / Results: support concentration, Gini]")
    line("support Gini Most-commented", f"{gv['Most-commented']:.2f}", "0.69")
    line("support Gini FairFeed", f"{gv['FairFeed']:.2f}", "0.33")

    print("\n[Results: vote legitimacy — rank-independent fit of non-seed supports]")
    line("mean fit FairFeed", f"{fitm['FairFeed']:.2f}", "0.42")
    line("mean fit Most-commented", f"{fitm['Most-commented']:.2f}", "0.28")
    line("would-support-anywhere FairFeed", f"{wsa['FairFeed']:.0f}%", "35% (fit ≥ 0.5)")
    line("would-support-anywhere Most-comm.", f"{wsa['Most-commented']:.0f}%", "12%")

    print("\n[Results: author reach κ of supported proposals]")
    line("reach FairFeed", f"{reach['FairFeed']:.1f}", "≈3.0 (near-unknown authors)")
    line("reach Most-commented", f"{reach['Most-commented']:.0f}", "≈17 (prominent authors)")

    print("\n[Results: cross-cutting (non-seed) votes per citizen — figure panel (c)]")
    line("cross-cutting FairFeed", f"{cc['FairFeed']:.2f}", "1.40")
    line("cross-cutting Most-commented", f"{cc['Most-commented']:.2f}", "0.68")
    # share casting ANY non-seed vote — the dashed reference lines drawn on panel (c)
    any_ff = (R["FairFeed"]["crosscut"] >= 1).mean() * 100
    any_oth = np.mean([(R[n]["crosscut"] >= 1).mean() * 100 for n in ff.FEEDS if n != "FairFeed"])
    line("cast ≥1 cross-cutting vote, FairFeed", f"{any_ff:.0f}%", "67%")
    line("cast ≥1 cross-cutting vote, other feeds", f"{any_oth:.0f}%", "≈44%")

    # ── Discovery panels: endogenous browsing ────────────────────────────────
    ENDO = {n: ff.simulate_endo(U, n, 42 + 7) for n in ff.FEEDS}
    pop = ["Random", "Newest", "Most-commented"]
    browsed_ff = ENDO["FairFeed"]["browsed"].mean()
    # The paper says current designs sustain "at most about 3.8" viewed proposals — that is a
    # MAX over the non-FairFeed feeds, not their mean. They differ (≈3.5 / 3.6 / 3.8), so the
    # mean (≈3.7) would check a claim the paper does not make. Report the max, and name it.
    browsed_by_feed = {n: ENDO[n]["browsed"].mean() for n in pop}
    browsed_pop_best = max(browsed_by_feed, key=browsed_by_feed.get)
    browsed_pop = browsed_by_feed[browsed_pop_best]
    rel_ff = ENDO["FairFeed"]["rel_seen"].mean()
    rel_pop = np.mean([ENDO[n]["rel_seen"].mean() for n in pop])
    exp_gini = {n: ff.gini(ENDO[n]["votes"]) for n in ff.FEEDS}
    med = {n: np.median(ENDO[n]["votes"]) for n in ff.FEEDS}

    print("\n[Results panel (a): what each citizen sees, and how far they look]")
    line("on-topic seen FairFeed", f"{rel_ff:.1f}", "≈5 on-topic proposals")
    line("on-topic seen popularity", f"{rel_pop:.1f}", "≈0.3 (1-in-10 chance rate)")
    line("browsed FairFeed", f"{browsed_ff:.1f}", "5.2 (≈40% further)")
    line(f"browsed, best other feed ({browsed_pop_best})", f"{browsed_pop:.1f}", "3.8 ('at most about 3.8')")

    print("\n[Results panel (b): exposure coverage / concentration]")
    line("exposure Gini Most-commented", f"{exp_gini['Most-commented']:.2f}", "0.88 (popularity sorts)")
    line("exposure Gini Newest", f"{exp_gini['Newest']:.2f}", "0.88")
    line("exposure Gini FairFeed", f"{exp_gini['FairFeed']:.2f}", "≈0.16")
    line("exposure Gini Random", f"{exp_gini['Random']:.2f}", "≈0.16 (fair but blind)")
    line("median exposure Most-comm.", f"{med['Most-commented']:.0f}", "≈9 views")
    line("median exposure Newest", f"{med['Newest']:.0f}", "≈9 views ('seen only nine times')")
    # shares clearing the visibility floor (ē/2) and reaching perfect equality (ē) — the
    # y-tick labels and the dashed benchmark on panel (b).
    _mu = ENDO["FairFeed"]["votes"].mean()
    _floor = max(3.0, 0.5 * _mu)
    clears = {n: (ENDO[n]["votes"] >= _floor).mean() * 100 for n in ff.FEEDS}
    reaches = {n: (ENDO[n]["votes"] >= _mu).mean() * 100 for n in ff.FEEDS}
    line("clears floor, FairFeed", f"{clears['FairFeed']:.0f}%", "100% ('all of them')")
    line("clears floor, Random", f"{clears['Random']:.0f}%", "98%")
    line("clears floor, popularity sorts",
         f"{min(clears['Newest'], clears['Most-commented']):.0f}–{max(clears['Newest'], clears['Most-commented']):.0f}%", "7–8%")
    line("reaches ≈97 (perfect equality), FairFeed", f"{reaches['FairFeed']:.0f}%", "39%")
    line("reaches ≈97 (perfect equality), Random", f"{reaches['Random']:.0f}%", "5%")
    # even-attention benchmark = FairFeed's realized total exposures spread evenly over
    # the M proposals: N voters × (realized browse depth + 1 seed) / M. The floor (panel b)
    # is half of this. NB: it uses the *realized* depth (~5.2), not the geometric budget
    # mean of 10 — voters stop early under the continue-rule (Eq. continue).
    even_views = ENDO["FairFeed"]["votes"].mean()
    print(f"  (perfectly even exposure would show each proposal {even_views:.0f}× — paper: ≈97)")
    print(f"      check: {U.N} voters × {browsed_ff + 1:.1f} cards / {U.M} proposals = {U.N * (browsed_ff + 1) / U.M:.0f}; floor = half = {even_views/2:.0f}")

    # ── Top-20 quality (panel d) + comment flooding ──────────────────────────
    variants = {"Random": dict(kind="random"), "Newest": dict(kind="newest"),
                "Most-commented": dict(kind="mc"), "MC flooded": dict(kind="mc", flood=True),
                "FairFeed": dict(kind="fair"), "FairFeed + reject": dict(kind="fair", reject_rate=0.10)}
    QF = {n: float(np.mean([ff.simulate_net(U, run_seed=rs, **kw)["q"].mean()
                            for rs in ff.QUALITY_SEEDS])) for n, kw in variants.items()}

    print("\n[Results panel (d): top-20 quality across feeds, 12-seed average]")
    line("Most-commented (clean)", f"{QF['Most-commented']:.2f}", "0.35")
    line("Most-commented (≈25% flooded)", f"{QF['MC flooded']:.2f}", "0.27 (flooding costs ≈1/5)")
    line("FairFeed (approve-only)", f"{QF['FairFeed']:.3f}", "0.41 (near random-pick floor)")
    line("FairFeed + gated reject", f"{QF['FairFeed + reject']:.3f}", "0.48")
    line("gated reject lift vs approve-only",
         f"+{100*(QF['FairFeed + reject']/QF['FairFeed']-1):.0f}%", "+18%")

    # ── Gated-reject cast-rate sweep ─────────────────────────────────────────
    sw = ff.gated_reject_sweep(U)
    b = sw["approve_only"]
    opt = sw["rates"][ff.RATE_OPTIONAL]
    knee = sw["rates"][ff.RATE_KNEE]

    print("\n[Results: FairFeed's gated reject cleans the ballot]")
    line("approve-only quality", f"{b['q']:.2f}", "baseline")
    line("approve-only would-be-vetoed", f"{b['highxi']:.0f}", "2 (ξ>0.6 on ballot)")
    line("optional r̄≈0.10: Δquality", f"+{opt['dq_pct']:.0f}%", "+18%")
    line("optional r̄≈0.10: Δcontroversy", f"{opt['dcontr_pct']:.0f}%", "−21%")
    line("optional r̄≈0.10: would-be-vetoed", f"{opt['highxi']:.0f}", "1 (2→1 drops off)")
    line("knee r̄≈0.30: Δquality", f"+{knee['dq_pct']:.0f}%", "+32%")
    line("knee r̄≈0.30: Δcontroversy", f"{knee['dcontr_pct']:.0f}%", "−35%")

    # ── Manipulation: gaming the reject channel (main-results config, see README) ─
    Ks = [1, 2, 5, 10, 20, 30, 50, 75, 100, 150, 200, 500, 1000]
    bury_open = ff.attacker_bury(U, Ks, two_for_one=False)
    bury_d21 = ff.attacker_bury(U, Ks, two_for_one=True)
    half_open = next((k for k in Ks if bury_open[k][0] >= 10), None)
    d21_max = max(d for d, _ in bury_d21.values())
    q_clean = ff.organic_clean_quality(U)
    smart = ff.attacker_smart(U, Ks, two_for_one=False)        # worst case: no defence
    q_floor = min(smart.values())
    sp = ff.attacker_selfpromote(U)                            # D21 coupling: self-promotion attack

    print("\n[Results: negative feedback inverts the incentive and costs verified identities]")
    print("  -- D21 coupling: weaponising the reject is no cheaper than ballot-stuffing --")
    line("seat junk via honest ballot-stuffing", f"{sp['honest_median']} ids (≈{sp['honest_median']/U.N*100:.2f}%)", "≈36 (0.5%)")
    line("seat junk via weaponised reject", f"{sp['weaponise_median']} ids (≈{sp['weaponise_median']/U.N*100:.2f}%)", "≈25 (0.35%)")
    line("identity discount from weaponising", f"{sp['honest_median']/sp['weaponise_median']:.2f}x", "≈1.4x (bounded)")
    line("forced approvals taxed per reject acct", f"{sp['forced_tax']}", "19 (D21 P>=2M)")
    print("  -- burying (pure vandalism, indifferent to own gain) --")
    line("accounts to bury half the ballot", f"{half_open} (≈{half_open/U.N*100:.1f}% voters)", "≈75 (≈1.1%)")
    line("ballot displaced by 100 accounts", f"{bury_open[100][0]}/20", "13/20 (≈1.4%)")
    line("displacement cap, proposal backstop", f"{d21_max}/20", "12/20")
    line("clean net-signal top-20 quality", f"{q_clean:.2f}", "0.45")
    line("smart-attack top-20 quality (min)", f"{q_floor:.2f}", "≈0.45 (barely moves)")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Comment statistics (§Data) — straight from the scraped corpus
# ═══════════════════════════════════════════════════════════════════════════
def section_comments():
    SCRAPE = Path(__file__).resolve().parent / "data" / "scrape"
    ROUNDS = {
        2025: dict(projects="muenchen_budget_2025_all_projects.csv", projects_sep=",",
                   comments="muenchen_budget_2025_comments.csv"),
        2026: dict(projects="muenchen_budget_2026_all_projects.csv", projects_sep=";",
                   comments="muenchen_budget_2026_comments.csv"),
    }

    def line(label, got, paper):
        print(f"  {label:<40} reproduced = {got:<10} paper: {paper}")

    print("=" * 78)
    print("2. Comments — descriptive comment statistics (paper §Data)")
    print("=" * 78)

    # The comment-authorship corpus is author-derived and is NOT distributed with
    # this package; the simulation never needs it. When it is absent, report the
    # documented §Data values (as quoted in the paper) instead of recomputing.
    if not all((SCRAPE / cfg[k]).exists()
               for cfg in ROUNDS.values() for k in ("projects", "comments")):
        print("\n  (comment-authorship corpus not distributed with this package.)")
        print("  Documented §Data values, as quoted in the paper:")
        line("2025 self-comments (author on own)", "13% (84/640)", "13%")
        line("2025 proposals with zero comments", "69%", "69%")
        line("2026 self-comments (author on own)", "38% (183/476)", "38%")
        line("2026 largest single commenter (agency)", "40% (190/476)", "≈40%")
        return

    for year, cfg in ROUNDS.items():
        sub = pd.read_csv(SCRAPE / cfg["projects"], sep=cfg["projects_sep"])
        com = pd.read_csv(SCRAPE / cfg["comments"])

        proj_author = sub.set_index("project_id")["user"].to_dict()
        com = com.copy()
        com["proj_author"] = com["project_id"].map(proj_author)

        n_comments = len(com)
        self_n = int((com["comment_author"] == com["proj_author"]).sum())
        self_share = self_n / n_comments if n_comments else 0.0

        n_props = len(sub)
        with_comment = sub["project_id"].isin(com["project_id"].unique()).sum()
        zero_share = (1 - with_comment / n_props) * 100

        print(f"\n[{year} round]  {n_props} proposals, {n_comments} comments")
        paper_self = "13%" if year == 2025 else "38%"
        line("self-comments (author on own proposal)",
             f"{self_share*100:.0f}% ({self_n}/{n_comments})", paper_self)
        if year == 2025:
            line("proposals with zero comments", f"{zero_share:.0f}%", "69%")
        if year == 2026:
            top_author, top_n = com["comment_author"].value_counts().head(1).items().__next__()
            line("largest single commenter (agency)",
                 f"{top_n}/{n_comments} = {top_n/n_comments*100:.0f}%",
                 "≈40% (one advertising agency)")
            print(f"      (largest commenter is '{top_author}')")


# ═══════════════════════════════════════════════════════════════════════════
# 3. q–κ robustness (reviewers A & C): does a positive quality–reach correlation
#    break the "exposure correction is costless in surfaced quality" claim?
# ═══════════════════════════════════════════════════════════════════════════
def section_qkappa():
    N_ANCHORED = 14          # indices 0..13 are the field-calibrated ballot proposals
    CORRELATIONS = [0.0, 0.3, 0.6]
    SEEDS = ff.QUALITY_SEEDS

    def spearman(a, b):
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        ra -= ra.mean(); rb -= rb.mean()
        return float((ra @ rb) / np.sqrt((ra @ ra) * (rb @ rb)))

    def correlated_universe(rho, pair_seed=42):
        """Return a copy of the base universe in which reach κ has been permuted
        among the synthetic proposals so that Spearman(q, κ) ≈ rho, and seeds are
        re-drawn from the new reach vector. q, category, controversy are untouched."""
        U = ff.build_universe()
        rng = np.random.default_rng(pair_seed)
        syn = np.arange(N_ANCHORED, U.M)
        q_syn = U.qs[syn]
        k_sorted = np.sort(U.kappa[syn])

        rq = np.argsort(np.argsort(q_syn)).astype(float)
        rq = (rq - rq.mean()) / rq.std()
        t = rho * rq + np.sqrt(max(1.0 - rho * rho, 0.0)) * rng.standard_normal(len(syn))
        k_new = np.empty(len(syn))
        k_new[np.argsort(t)] = k_sorted
        U.kappa = U.kappa.copy()
        U.kappa[syn] = k_new

        srng = np.random.default_rng(pair_seed + 1)
        U.seeds = srng.choice(U.M, size=U.N, p=U.kappa / U.kappa.sum())
        return U

    def underseen_quality(U, run_seed):
        """Mean latent quality of the least-seen quartile of proposals under FairFeed
        — the low-reach items the under-exposure boost keeps trying to lift."""
        R = ff.simulate_table(U, "FairFeed", run_seed)
        votes = R["votes"]
        cut = np.quantile(votes, 0.25)
        underseen = votes <= cut
        return float(U.qs[underseen].mean())

    print("=" * 74)
    print("3. q–κ robustness: does a positive quality–reach correlation break the")
    print("   'exposure correction is costless in surfaced quality' claim?")
    print("=" * 74)
    print(f"  synthetic proposals re-paired: {ff.M_PROPOSALS - N_ANCHORED}; "
          f"{N_ANCHORED} anchored kept; seeds ∝ reach re-drawn")
    print(f"  field-mean quality (random-pick floor): {ff.build_universe().qs.mean():.3f}\n")

    hdr = f"  {'target ρ':>9} {'actual ρ':>9} {'FF q':>8} {'FF+rej q':>9} {'underseen q':>12}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    rows = []
    for rho in CORRELATIONS:
        U = correlated_universe(rho)
        actual = spearman(U.qs[N_ANCHORED:], U.kappa[N_ANCHORED:])
        ff_q = float(np.mean([ff.simulate_net(U, "fair", rs)["q"].mean() for rs in SEEDS]))
        ffr_q = float(np.mean([ff.simulate_net(U, "fair", rs, reject_rate=0.10)["q"].mean()
                               for rs in SEEDS]))
        uq = float(np.mean([underseen_quality(U, rs) for rs in SEEDS]))
        rows.append((rho, actual, ff_q, ffr_q, uq))
        print(f"  {rho:>9.2f} {actual:>9.2f} {ff_q:>8.3f} {ffr_q:>9.3f} {uq:>12.3f}")

    base = rows[0]
    print("\n  change in FairFeed approve-only top-20 quality vs ρ=0 baseline:")
    for rho, _, ff_q, ffr_q, _ in rows:
        print(f"    ρ={rho:.1f}:  {ff_q:.3f}  ({100*(ff_q/base[2]-1):+.1f}%)")
    print("\n  change in FairFeed + gated-reject top-20 quality vs ρ=0 baseline:")
    for rho, _, ff_q, ffr_q, _ in rows:
        print(f"    ρ={rho:.1f}:  {ffr_q:.3f}  ({100*(ffr_q/base[3]-1):+.1f}%)")


# ═══════════════════════════════════════════════════════════════════════════
# 4. Flood robustness: the 0.35 -> 0.27 comment-flooding drop is a worst case
# ═══════════════════════════════════════════════════════════════════════════
def section_flood():
    U = ff.build_universe()
    M = U.M
    SEEDS = list(ff.QUALITY_SEEDS)[:4]   # voter realizations (kept small; pure-Python)
    DRAWS = 6                            # random target draws per (arm, K)
    ORDER_LOW = np.argsort(U.qs)         # proposal indices, worst quality first

    def mc_top20_quality(flood_idx, run_seed):
        """Most-commented ballot quality with `flood_idx` proposals comment-flooded.
        Faithful to simulate_net(kind='mc', flood=...), reject channel off."""
        rng = np.random.default_rng(run_seed)
        sup = np.zeros(M, int)
        com = np.zeros(M, int)
        if flood_idx is not None:
            com[flood_idx] = ff.FLOOD_AMT
        for i in U.order:
            s = int(U.seeds[i]); V = int(U.budgets[i]); tau = U.thresholds[i]
            sup[s] += 1
            if rng.random() < ff.COMMENT_PROB_BASE * (1 + 3 * U.contr[s]):
                com[s] += 1
            if V == 0:
                continue
            for r, j in enumerate(np.argsort(-com + rng.uniform(0, 1e-6, M))[:V]):
                if j == s:
                    continue
                m = 1.0 if U.cats[j] == U.cats[s] else ff.OFFTOPIC_MATCH
                fit = U.qs[j] * m; dec = 1 / (1 + ff.K_DECAY * r)
                if rng.random() < ff.sigmoid(ff.BETA * (fit - tau)) * (1 - ff.LAMBDA * U.contr[j]) * dec:
                    sup[j] += 1
                if rng.random() < ff.COMMENT_PROB_BASE * (1 + 3 * U.contr[j]) * dec:
                    com[j] += 1
        return float(U.qs[np.argsort(-sup)[:20]].mean())

    def avg_over_seeds(flood_idx):
        return float(np.mean([mc_top20_quality(flood_idx, rs) for rs in SEEDS]))

    def avg_over_draws(pool, K, salt):
        vals = []
        for t in range(DRAWS):
            idx = np.random.default_rng(salt + t).choice(pool, size=K, replace=False)
            vals.append(avg_over_seeds(idx))
        return float(np.mean(vals))

    clean = avg_over_seeds(None)
    print("=" * 70)
    print("4. Flood robustness — most-commented top-20 quality")
    print(f"  universe: {U.M} proposals, {U.N} voters  (seed 42, md5 categories)")
    print(f"  clean (no flood): {clean:.3f}   [paper: 0.35]")
    print("=" * 70)
    print(f"\n{'attacker targeting':<34}{'top-20 q':>10}{'rel. drop':>12}")
    bottom_half = ORDER_LOW[:M // 2]
    for K in (ff.N_FLOOD,):
        q = avg_over_seeds(ORDER_LOW[:K])
        print(f"{'weakest-%d (PAPER, worst case)' % K:<34}{q:>10.3f}{100*(q/clean-1):>11.0f}%   [paper: 0.27]")
    for K in (3, 5):
        q = avg_over_seeds(ORDER_LOW[:K])
        print(f"{'weakest-%d' % K:<34}{q:>10.3f}{100*(q/clean-1):>11.0f}%")
    for K in (3, 5):
        q = avg_over_draws(np.arange(M), K, 100)
        print(f"{'random-%d, anywhere' % K:<34}{q:>10.3f}{100*(q/clean-1):>11.0f}%")
    for K in (3, 5):
        q = avg_over_draws(bottom_half, K, 200)
        print(f"{'random-%d, from weakest half' % K:<34}{q:>10.3f}{100*(q/clean-1):>11.0f}%")

    print(
        "\nReading: the weakest-proposal target (the paper's model) is the strongest"
        "\nattack; flooding random or stronger proposals moves quality less. The"
        "\n0.35 -> 0.27 figure is therefore an upper bound on the damage."
    )


SECTIONS = {
    "1": section_simulation,
    "2": section_comments,
    "3": section_qkappa,
    "4": section_flood,
}

if __name__ == "__main__":
    picks = [a for a in sys.argv[1:] if a in SECTIONS] or list(SECTIONS)
    for i, k in enumerate(picks):
        if i:
            print()
        SECTIONS[k]()
