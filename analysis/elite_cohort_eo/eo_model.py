"""Q2 rigorous test: does cohort-EO improve player shortlisting vs baselines?
Metric = Spearman(predictor, forward mean points) among playing players (ranking skill).
Uncertainty = GW-block bootstrap (resample decision-GW t), 2000 iters. Paired diffs on same resample.
"""
import os
from eo_panel import build_panel
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression

HERE = os.path.dirname(os.path.abspath(__file__))

def sp(df, col, y="fwd_mean"):
    return spearmanr(df[col], df[y]).correlation

def block_boot(df, fns, B=2000, seed=0):
    """fns: dict name-> function(df)->scalar. Returns base + CI per name, computed on SAME resamples."""
    rng = np.random.default_rng(seed)
    ts = df["t"].unique()
    grouped = {t: sub for t, sub in df.groupby("t")}
    base = {k: f(df) for k, f in fns.items()}
    acc = {k: [] for k in fns}
    for _ in range(B):
        st = rng.choice(ts, size=len(ts), replace=True)
        bd = pd.concat([grouped[t] for t in st], ignore_index=True)
        for k, f in fns.items():
            acc[k].append(f(bd))
    out = {}
    for k in fns:
        a = np.array(acc[k]); out[k] = (base[k], np.percentile(a, 2.5), np.percentile(a, 97.5))
    return out

if __name__ == "__main__":
    df = build_panel(4)
    print(f"PRIMARY: N=4, current-rank top-decile cohort, playing players. n={len(df)}\n")

    fns = {
        "EO_cohort":      lambda d: sp(d, "cohort_eo"),
        "own_sample":     lambda d: sp(d, "sample_own"),
        "recent_pts":     lambda d: sp(d, "recent_pts"),
        "EO - recent":    lambda d: sp(d, "cohort_eo") - sp(d, "recent_pts"),
        "EO - own_sample":lambda d: sp(d, "cohort_eo") - sp(d, "sample_own"),
    }
    res = block_boot(df, fns)
    print("Spearman(predictor, forward points), 95% GW-block-bootstrap CI:")
    for k in ["EO_cohort", "own_sample", "recent_pts"]:
        b, lo, hi = res[k]; print(f"  {k:12} {b:+.3f}  CI[{lo:+.3f},{hi:+.3f}]")
    print("\nPaired differences (does EO BEAT the baseline?):")
    for k in ["EO - recent", "EO - own_sample"]:
        b, lo, hi = res[k]; sig = "" if (lo<=0<=hi) else "  <-- CI excludes 0"
        print(f"  {k:16} {b:+.3f}  CI[{lo:+.3f},{hi:+.3f}]{sig}")

    def std(d, cols):
        X = d[cols].values.astype(float); return (X - X.mean(0)) / X.std(0)
    def ols_coef(d, cols, target):
        X = std(d, cols); y = d["fwd_mean"].values
        m = LinearRegression().fit(X, y); return dict(zip(cols, m.coef_))[target]
    print("\nIncremental OLS (standardized; coef = pts/GW per 1 SD):")
    for cols, tgt, label in [
        (["recent_pts", "cohort_eo"], "cohort_eo", "EO added on top of recent_pts"),
        (["sample_own", "cohort_eo"], "cohort_eo", "EO added on top of generic ownership"),
        (["recent_pts", "sample_own", "cohort_eo"], "cohort_eo", "EO added on top of recent_pts + generic own"),
    ]:
        r = block_boot(df, {"c": lambda d, c=cols, t=tgt: ols_coef(d, c, t)})
        b, lo, hi = r["c"]; sig = "" if (lo<=0<=hi) else "  <-- CI excludes 0"
        print(f"  {label:48} {b:+.3f}  CI[{lo:+.3f},{hi:+.3f}]{sig}")

    print("\nBy decision-GW block (Spearman vs forward points):")
    print(f"  {'block':10} {'n':>5} {'EO_cohort':>10} {'own_sample':>11} {'recent_pts':>11}")
    for lo_t, hi_t, name in [(4,8,"GW4-8"),(9,14,"GW9-14"),(15,20,"GW15-20"),(21,27,"GW21-27"),(28,34,"GW28-34")]:
        d = df[(df.t>=lo_t)&(df.t<=hi_t)]
        print(f"  {name:10} {len(d):>5} {sp(d,'cohort_eo'):>10.3f} {sp(d,'sample_own'):>11.3f} {sp(d,'recent_pts'):>11.3f}")

    per_t = [(t, len(sub), sp(sub,"cohort_eo"), sp(sub,"sample_own"), sp(sub,"recent_pts"))
             for t, sub in df.groupby("t")]
    pd.DataFrame(per_t, columns=["t","n","eo","own","recent"]).to_csv(os.path.join(HERE, "eo_per_gw.csv"), index=False)
    print("\nsaved eo_per_gw.csv")
