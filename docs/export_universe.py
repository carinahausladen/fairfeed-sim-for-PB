"""
export_universe.py — write docs/universe.json, the proposals and voters the web
playground runs on.

It is build_universe(seed=42) from simulation.py, serialised: the same 459
proposals (quality, topic, divisiveness, submission day, author reach) and the
same 7,134 voters (seed proposal, browse budget, support threshold, arrival
order) as every number in the paper. No proposal titles are exported.

    python3 docs/export_universe.py        # from the repository root
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np  # noqa: E402
import simulation as ff  # noqa: E402

U = ff.build_universe()

# numpy's argsort is unstable: on tied comment counts it does NOT keep index
# order. The un-jittered most-commented sort (simulate_table, simulate_endo)
# inherits that tie order, and the funded winners sit at indices 0-9, so index
# order would show them first and flatter the feed. Export numpy's tie order.
tie_rank = np.empty(U.M, int)
tie_rank[np.argsort(-np.zeros(U.M, int))] = np.arange(U.M)


def rounded(a, d):
    return [round(float(x), d) for x in a]


out = {
    "M": U.M, "N": U.N, "C": U.C,
    "nWin": len(U.winners), "nVet": len(U.vetoed),   # indices 0..9 funded, 10..13 vetoed
    "cats": U.cats.tolist(), "q": rounded(U.qs, 5), "xi": rounded(U.contr, 5),
    "tsub": [int(x) for x in U.tsub], "kappa": rounded(U.kappa, 4),
    "seeds": U.seeds.tolist(), "budgets": U.budgets.tolist(),
    "tau": rounded(U.thresholds, 5), "order": U.order.tolist(),
    "tieRank": tie_rank.tolist(),
}
(HERE / "universe.json").write_text(json.dumps(out, separators=(",", ":")))
print(f"wrote {HERE / 'universe.json'}")
