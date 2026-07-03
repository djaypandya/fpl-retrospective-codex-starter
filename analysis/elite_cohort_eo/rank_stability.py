"""Q1: When does current overall rank start tracking end-of-season skill?
Data: managers/history/manager_X.json -> current[t].overall_rank (leak-free, per-GW).
Sample = 1,001 top-~1% finishers (survivorship-selected -> range-restricted -> conservative)."""
import json, glob, os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
MGR = os.path.join(REPO, "data", "raw", "managers")

# rank[manager][gw] = overall_rank
rank = {}
for f in glob.glob(f"{MGR}/history/manager_*.json"):
    mid = int(os.path.basename(f).split("_")[1].split(".")[0])
    d = json.load(open(f))
    rank[mid] = {r["event"]: r["overall_rank"] for r in d["current"]}

mids = sorted(rank)
print(f"n managers = {len(mids)}")

USER = 816200  # user's own entry (final ~457k) excluded from reference-cohort stats
cohort = [m for m in mids if m != USER]
print(f"reference cohort (excl user {USER}) = {len(cohort)}")

def col(gw, ids):
    return np.array([rank[m].get(gw, np.nan) for m in ids])

FINAL = 38
print("\n=== Spearman(current rank at t, FINAL rank) and rank persistence (t->t+4, t->t+8) ===")
print(f"{'GW':>3} {'n':>5} {'rho_vs_final':>13} {'rho_t+4':>9} {'rho_t+8':>9}")
rows = []
for t in range(1, 39):
    rt = col(t, cohort); rf = col(FINAL, cohort)
    mask = ~np.isnan(rt) & ~np.isnan(rf)
    rho_f = spearmanr(rt[mask], rf[mask]).correlation if mask.sum() > 10 else np.nan
    outs = {}
    for k in (4, 8):
        if t + k <= 38:
            rk = col(t + k, cohort); m2 = ~np.isnan(rt) & ~np.isnan(rk)
            outs[k] = spearmanr(rt[m2], rk[m2]).correlation
        else:
            outs[k] = np.nan
    rows.append((t, mask.sum(), rho_f, outs[4], outs[8]))
    print(f"{t:>3} {mask.sum():>5} {rho_f:>13.3f} {outs[4]:>9.3f} {outs[8]:>9.3f}")

df = pd.DataFrame(rows, columns=["gw", "n", "rho_final", "rho_t4", "rho_t8"])
for b in (0.5, 0.6, 0.7):
    e4 = next((t for t in range(1, 34) if (df[(df.gw >= t) & (df.gw <= 34)].rho_t4 >= b).all()), None)
    print(f"persistence(t->t+4) stays >= {b} from GW {e4} onward")
df.to_csv(os.path.join(HERE, "rank_stability.csv"), index=False)
print("saved rank_stability.csv")
