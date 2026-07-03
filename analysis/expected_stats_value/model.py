"""Rigorous test: do trailing expected stats add value for shortlisting the next 4-8 GWs?

Metric  = Spearman(trailing predictor, forward mean points) among likely starters (ranking skill).
Uncertainty = gameweek-block bootstrap (resample decision-GW t), paired diffs on the same resample.
Also: incremental standardized OLS coefficients and an out-of-sample walk-forward ranking check.
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel import build


def sp(df, c, y="fwd"):
    return spearmanr(df[c], df[y], nan_policy="omit").correlation


def block_boot(df, fns, B=2000, seed=0):
    rng = np.random.default_rng(seed)
    ts = df["t"].unique()
    gp = {t: s for t, s in df.groupby("t")}
    base = {k: f(df) for k, f in fns.items()}
    acc = {k: [] for k in fns}
    for _ in range(B):
        st = rng.choice(ts, size=len(ts), replace=True)
        bd = pd.concat([gp[t] for t in st], ignore_index=True)
        for k, f in fns.items():
            acc[k].append(f(bd))
    return {k: (base[k], np.percentile(acc[k], 2.5), np.percentile(acc[k], 97.5)) for k in fns}


def std(d, cols):
    X = d[cols].values.astype(float)
    return (X - X.mean(0)) / X.std(0)


def inc_coef(d, cols, tgt):
    d = d.dropna(subset=cols + ["fwd"])
    m = LinearRegression().fit(std(d, cols), d["fwd"].values)
    return dict(zip(cols, m.coef_))[tgt]


def _fit_std(tr, cols):
    X = tr[cols].values.astype(float)
    return (X - X.mean(0)) / X.std(0)


def _apply_std(te, tr, cols):
    a = tr[cols].values.astype(float)
    return (te[cols].values.astype(float) - a.mean(0)) / a.std(0)


def walkforward_sp(df, base_cols, add_cols, start_t=12):
    """Out-of-sample: train on decision-GW < t, predict at t. Per-block Spearman, base vs base+add."""
    df = df.dropna(subset=list(set(base_cols + add_cols)) + ["fwd"]).copy()
    rows_b, rows_f = [], []
    for t in sorted(df.t.unique()):
        if t < start_t:
            continue
        tr, te = df[df.t < t], df[df.t == t]
        if len(tr) < 200 or len(te) < 15:
            continue
        for cols, store in [(base_cols, rows_b), (base_cols + add_cols, rows_f)]:
            m = LinearRegression().fit(_fit_std(tr, cols), tr["fwd"].values)
            pred = m.predict(_apply_std(te, tr, cols))
            store.append((t, spearmanr(pred, te["fwd"].values).correlation))
    return (pd.DataFrame(rows_b, columns=["t", "rho"]),
            pd.DataFrame(rows_f, columns=["t", "rho"]))


if __name__ == "__main__":
    for N in [4, 8]:
        p = build(N)
        a = p[p.pos.isin(["MID", "FWD"])].copy()
        print(f"\n{'='*66}\nN={N}  ATTACKERS (MID+FWD)  n={len(a)}")
        r = block_boot(a, {
            "form5": lambda d: sp(d, "form5"), "xgi": lambda d: sp(d, "xgi"),
            "ict": lambda d: sp(d, "ict"),
            "xgi-form5": lambda d: sp(d, "xgi") - sp(d, "form5"),
            "ict-xgi": lambda d: sp(d, "ict") - sp(d, "xgi")}, B=1500)
        for k in ["form5", "xgi", "ict", "xgi-form5", "ict-xgi"]:
            b, lo, hi = r[k]
            flag = "" if lo <= 0 <= hi else "  *CI excl 0"
            print(f"  Spearman {k:12} {b:+.3f} [{lo:+.3f},{hi:+.3f}]{flag}")
        base, full = walkforward_sp(a, ["form5", "fdr"], ["xgi"])
        d = (full.set_index("t").rho - base.set_index("t").rho).dropna()
        print(f"  OOS baseline{{form5,fdr}} {base.rho.mean():+.3f} -> +xgi {full.rho.mean():+.3f}"
              f"  gain {d.mean():+.3f}  (+ in {(d>0).mean()*100:.0f}% of {len(d)} blocks)")
