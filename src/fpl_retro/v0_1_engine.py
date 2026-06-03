"""
v0.1 — separate the two decisions  (season 2025/26)
====================================================
v0 mixed "will they play?" with "who's the better asset?" into one score, so a
one-line minutes rule won the availability-dominated sim. v0.1 fixes the FRAMING:

  STAGE 1 (hard filter): availability gate -> keep only LIKELY STARTERS
                         (predicted P(play >=60' next GW) >= 0.5, walk-forward).
  STAGE 2 (rank):        among likely starters only, engine score = conditional
                         points model E[pts | play]. This is the pure asset-quality
                         decision the manager actually agonises over.

Objective: does the engine's starter-vs-starter edge convert into decision value?
SUCCESS (pre-registered): among likely starters, engine must beat BOTH hi_minutes
AND hi_value on out-of-sample ranking, AND show a plausible positive decision-value
signal over the 4-GW horizon. If it only beats weak baselines -> call it failed.

All language predictive/associational. Walk-forward only; purge s+4<=t. No causal claims.
Primary horizon y4; y3/y6 secondary report only.
"""
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.preprocessing import StandardScaler
import src.fpl_retro.v0_engine as v0

GATE_THRESH = 0.5
BLOCKS = [(8, 16), (17, 25), (26, 34)]
POSN = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

def fit_stage(train, test):
    """Return (p_play, e_pts) for test rows. Gate=logistic; conditional=Ridge on starters."""
    gs = StandardScaler().fit(train[v0.GATE_F])
    gate = LogisticRegression(max_iter=1000).fit(gs.transform(train[v0.GATE_F]), train["play_next"])
    p_play = gate.predict_proba(gs.transform(test[v0.GATE_F]))[:, 1]
    tr = train[train["played_fwd"] == 1]
    sc = StandardScaler().fit(tr[v0.PT_F])
    Xtr = np.hstack([sc.transform(tr[v0.PT_F]), v0.posdum(tr).values.astype(float)])
    pm = Ridge(alpha=1.0).fit(Xtr, tr["y4"])
    Xte = np.hstack([sc.transform(test[v0.PT_F]), v0.posdum(test).values.astype(float)])
    return p_play, np.clip(pm.predict(Xte), 0, None)

SCORES = {"engine": "e_pts", "hi_minutes": "mins4", "hi_value": "value",
          "hi_points": "pts4", "fixture_only": "neg_fdr"}

def pooled_predictions(D, panel):
    out = []
    for t in range(v0.TEST_START, v0.TEST_END + 1):
        train = panel[panel["gw"] <= t - v0.KP]
        test = panel[panel["gw"] == t].copy()
        if len(train) < 200 or test.empty:
            continue
        p_play, e_pts = fit_stage(train, test)
        test["p_play"] = p_play
        test["e_pts"] = e_pts
        test["neg_fdr"] = -test["fdr4"]
        out.append(test)
    P = pd.concat(out).dropna(subset=["y4"])
    return P

# ----------------------------------------------------------------- ranking evaluation
def block_boot_spearman(df, col, target="y4", B=4000, seed=0):
    rng = np.random.default_rng(seed)
    gws = df["gw"].unique()
    vals = []
    for _ in range(B):
        samp = rng.choice(gws, len(gws), replace=True)
        d = pd.concat([df[df["gw"] == g] for g in samp])
        vals.append(spearmanr(d[col], d[target]).statistic)
    pt = spearmanr(df[col], df[target]).statistic
    return pt, np.percentile(vals, 2.5), np.percentile(vals, 97.5)

def block_boot_diff(df, col_a, col_b, target="y4", B=4000, seed=0):
    """Bootstrap CI of Spearman(a)-Spearman(b) over GW blocks (paired)."""
    rng = np.random.default_rng(seed)
    gws = df["gw"].unique()
    diffs = []
    for _ in range(B):
        samp = rng.choice(gws, len(gws), replace=True)
        d = pd.concat([df[df["gw"] == g] for g in samp])
        diffs.append(spearmanr(d[col_a], d[target]).statistic - spearmanr(d[col_b], d[target]).statistic)
    pt = spearmanr(df[col_a], df[target]).statistic - spearmanr(df[col_b], df[target]).statistic
    return pt, np.percentile(diffs, 2.5), np.percentile(diffs, 97.5)

def topk_lift(df, col, target="y4", frac=0.1):
    d = df.sort_values(col, ascending=False)
    k = max(1, int(len(d) * frac))
    return d[target].iloc[:k].mean() - df[target].mean()

# ----------------------------------------------------------------- portfolio sim
def portfolio_sim(D, P, strategy_col, tau=0.0, start_gw=8):
    """Cumulative top-11 points from a 15-man squad, 1 free transfer/GW, like-for-like,
    buy restricted to LIKELY STARTERS. Proxy: each GW score top-11 of the 15 (no formation
    legality, no captain) — applied identically to all strategies so comparisons are fair."""
    U = v0.load_user(D)
    squad = [p for p in U["picks"].get(start_gw, [])]
    bank = U["banks"].get(start_gw, 0.0)
    total, n_tf = 0.0, 0
    for t in range(start_gw, v0.TEST_END + 1):
        rows = P[P["gw"] == t]
        sc = {r.pid: r for r in rows.itertuples()}
        likely = {pid for pid in sc if sc[pid].p_play >= GATE_THRESH}
        price = {pid: sc[pid].price for pid in sc}
        # transfer decision (buy must be a likely starter)
        owned = set(squad)
        best = None
        for out in squad:
            if out not in sc: continue
            for inn in likely:
                if inn in owned or inn not in sc: continue
                if D["pos"][inn] != D["pos"][out]: continue
                if price[inn] > price[out] + bank + 1e-9: continue
                gain = getattr(sc[inn], strategy_col) - getattr(sc[out], strategy_col)
                if gain <= tau: continue
                if best is None or gain > best[2]:
                    best = (inn, out, gain)
        if best:
            inn, out, _ = best
            bank += price[out] - price[inn]
            squad = [inn if p == out else p for p in squad]
            n_tf += 1
        # score this GW: top-11 actual points among the 15 owned
        gpts = sorted((D["pts"].get(t, {}).get(p, 0) for p in squad), reverse=True)[:11]
        total += sum(gpts)
    return total, n_tf

# ----------------------------------------------------------------- run
def run():
    D = v0.load(); v0.POS = D["pos"]
    panel = v0.build_panel(D)
    P = pooled_predictions(D, panel)
    starters = P[P["p_play"] >= GATE_THRESH].copy()
    print(f"=== v0.1 — season 2025/26 ===")
    print(f"pooled OOS rows: {len(P):,} | LIKELY STARTERS (p_play>={GATE_THRESH}): {len(starters):,}")
    print(f"walk-forward test GW{v0.TEST_START}..{v0.TEST_END}, primary horizon next {v0.KP} GW\n")

    # gate sanity
    prec = starters["play_next"].mean()
    rec = starters["play_next"].sum() / max(1, P["play_next"].sum())
    print(f"[gate] of flagged likely-starters, {prec:.1%} actually played>=60' next GW (precision); "
          f"captured {rec:.1%} of all who did (recall)\n")

    # ---- A. pooled ranking among likely starters ----
    print("A) OUT-OF-SAMPLE RANKING vs realized next-4-GW points  (likely starters only)")
    print(f"   {'rule':13} {'Spearman':>9} {'95% CI':>20} {'top-decile lift (pts/4GW)':>26}")
    ranks = {}
    for name, col in SCORES.items():
        pt, lo, hi = block_boot_spearman(starters, col)
        ranks[name] = pt
        lift = topk_lift(starters, col)
        print(f"   {name:13} {pt:>9.3f} {('[%.3f, %.3f]'%(lo,hi)):>20} {lift:>26.2f}")

    print("\n   Engine-minus-baseline Spearman (paired block-bootstrap; CI>0 => engine wins):")
    verdict_rank = {}
    for b in ["hi_minutes", "hi_value", "hi_points", "fixture_only"]:
        d, lo, hi = block_boot_diff(starters, "e_pts", SCORES[b])
        win = lo > 0
        verdict_rank[b] = win
        print(f"     engine - {b:13} = {d:+.3f}  CI[{lo:+.3f}, {hi:+.3f}]  {'WIN' if win else 'not sig'}")

    # ---- B. position-specific ----
    print("\nB) POSITION-SPECIFIC Spearman (likely starters):")
    print(f"   {'pos':4} {'n':>5} {'engine':>7} {'hi_min':>7} {'hi_val':>7} {'hi_pts':>7}  engine best?")
    for p in (1, 2, 3, 4):
        sub = starters[starters["pos"] == p]
        if len(sub) < 40: continue
        sr = {n: spearmanr(sub[c], sub["y4"]).statistic for n, c in SCORES.items()}
        best = max(("engine", "hi_minutes", "hi_value", "hi_points"), key=lambda n: sr[n])
        print(f"   {POSN[p]:4} {len(sub):>5} {sr['engine']:>7.3f} {sr['hi_minutes']:>7.3f} "
              f"{sr['hi_value']:>7.3f} {sr['hi_points']:>7.3f}  {'YES' if best=='engine' else 'no ('+best+')'}")

    # ---- C. GW-block consistency ----
    print("\nC) GW-BLOCK CONSISTENCY (Spearman, likely starters):")
    print(f"   {'block':10} {'n':>5} {'engine':>7} {'hi_min':>7} {'hi_val':>7}  engine>=both?")
    block_ok = 0
    for a, b in BLOCKS:
        sub = starters[(starters["gw"] >= a) & (starters["gw"] <= b)]
        sr = {n: spearmanr(sub[c], sub["y4"]).statistic for n, c in SCORES.items()}
        ok = sr["engine"] >= sr["hi_minutes"] and sr["engine"] >= sr["hi_value"]
        block_ok += ok
        print(f"   GW{a:02d}-{b:02d}   {len(sub):>5} {sr['engine']:>7.3f} {sr['hi_minutes']:>7.3f} "
              f"{sr['hi_value']:>7.3f}  {'yes' if ok else 'NO'}")

    # ---- D. secondary horizons ----
    print("\nD) SECONDARY HORIZONS (engine Spearman among likely starters):")
    for tgt in ["y3", "y6"]:
        s = starters.dropna(subset=[tgt])
        print(f"   {tgt}: engine {spearmanr(s['e_pts'], s[tgt]).statistic:.3f} | "
              f"hi_minutes {spearmanr(s['mins4'], s[tgt]).statistic:.3f} | "
              f"hi_value {spearmanr(s['value'], s[tgt]).statistic:.3f}")

    # ---- E. portfolio decision value ----
    print("\nE) SEASON-LONG PORTFOLIO SIM (cumulative top-11 pts from GW8; 1 free tf/GW;")
    print("   buys restricted to likely starters; proxy = top-11 of 15, no captain/formation):")
    base = None
    for name, col in [("hold", None), ("engine", "e_pts"), ("hi_minutes", "mins4"),
                      ("hi_value", "value"), ("hi_points", "pts4")]:
        if name == "hold":
            tot, ntf = portfolio_sim(D, P, "e_pts", tau=1e9)  # tau huge => never transfer
        else:
            tot, ntf = portfolio_sim(D, P, col, tau=(2.0 if name == "engine" else 0.0))
        if name == "hold": base = tot
        print(f"   {name:12} cumulative pts {tot:7.0f}  ({tot-base:+.0f} vs hold)  transfers={ntf}")

    # ---- VERDICT ----
    print("\n=== v0.1 SUCCESS CRITERION ===")
    beats_min = verdict_rank["hi_minutes"]
    beats_val = verdict_rank["hi_value"]
    print(f"Among likely starters, engine beats hi_minutes (CI of diff >0)? {beats_min}")
    print(f"Among likely starters, engine beats hi_value   (CI of diff >0)? {beats_val}")
    print(f"Block consistency: engine >= both in {block_ok}/{len(BLOCKS)} GW blocks")
    overall = beats_min and beats_val
    print(f"\nVERDICT: {'PASS — promote to v1' if overall else 'NOT MET'}")
    if not overall:
        better = [b for b in ('hi_minutes','hi_value') if not verdict_rank[b]]
        print(f"  Engine does NOT reliably beat: {better}.  Per the pre-registered rule, do "
              f"not dress it up — recommend the simpler rule unless decision-value (E) is clearly positive.")
    print("\nCAVEATS: portfolio proxy ignores formation legality, captaincy, bench order, chips, "
          "and FPL half-profit selling; 1 free transfer/GW (no hits/banking); price reconstruction "
          "sparse; rows temporally dependent (block-bootstrap mitigates, not eliminates). v1 TODO.")

if __name__ == "__main__":
    run()
