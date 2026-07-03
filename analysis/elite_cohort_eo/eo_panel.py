"""Q2: Does the CURRENT-RANK elite cohort's effective ownership (known at GW t)
help pick players for t+1..t+N, vs baselines? Walk-forward, leak-free.

Cohort at t = top-DECILE of the 1,000-manager sample by overall_rank AT t (no look-ahead).
Availability gate = >=45 min/GW avg over trailing N GW (project convention; playing players only).
Outcome = mean total_points over t+1..t+N.
"""
import json, glob, os, re, pickle
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(REPO, "data", "raw")
MGR = os.path.join(RAW, "managers")
CACHE = os.path.join(HERE, "eo_cache.pkl")

def build_cache():
    # player per-GW points & minutes
    pts, mins = {}, {}
    for f in glob.glob(f"{RAW}/gw_live/gw_*_live.json"):
        gw = int(re.search(r"gw_(\d+)", f).group(1))
        d = json.load(open(f)); pts[gw], mins[gw] = {}, {}
        for e in d["elements"]:
            pts[gw][e["id"]] = e["stats"]["total_points"]
            mins[gw][e["id"]] = e["stats"]["minutes"]
    # position
    bs = json.load(open(f"{RAW}/bootstrap_static_smoke.json"))
    pos = {e["id"]: e["element_type"] for e in bs["elements"]}
    # manager per-GW rank
    rank = {}
    for f in glob.glob(f"{MGR}/history/manager_*.json"):
        mid = int(os.path.basename(f).split("_")[1].split(".")[0])
        d = json.load(open(f)); rank[mid] = {r["event"]: r["overall_rank"] for r in d["current"]}
    finalrank = {m: rank[m].get(38, np.nan) for m in rank}
    # manager per-GW picks: owns[mid][gw] = set(elements); caps[mid][gw] = captain element
    owns, caps = {}, {}
    for dpath in glob.glob(f"{MGR}/picks/manager_*"):
        mid = int(os.path.basename(dpath).split("_")[1])
        owns[mid], caps[mid] = {}, {}
        for pf in glob.glob(f"{dpath}/event_*.json"):
            gw = int(re.search(r"event_(\d+)", pf).group(1))
            d = json.load(open(pf))
            s = set(); cap = None
            for p in d["picks"]:
                s.add(p["element"])
                if p.get("is_captain"): cap = p["element"]
            owns[mid][gw] = s; caps[mid][gw] = cap
    cache = dict(pts=pts, mins=mins, pos=pos, rank=rank, finalrank=finalrank, owns=owns, caps=caps)
    pickle.dump(cache, open(CACHE, "wb"))
    return cache

if os.path.exists(CACHE):
    C = pickle.load(open(CACHE, "rb"))
    print("loaded cache")
else:
    print("building cache (reads ~38k pick files, ~30-60s)...")
    C = build_cache()

PTS, MINS, POS, RANK, FINAL, OWNS, CAPS = C["pts"], C["mins"], C["pos"], C["rank"], C["finalrank"], C["owns"], C["caps"]
USER = 816200
MIDS = [m for m in RANK if m != USER]   # reference sample excludes user's own entry
print(f"players/gw: {len(PTS)} GWs; managers: {len(MIDS)}")

def cohort_at(t, frac=0.10, use_final=False, topk_abs=None):
    """Managers who are elite as known at GW t (top-frac by overall_rank at t)."""
    if use_final:
        ranked = sorted([m for m in MIDS if not np.isnan(FINAL[m])], key=lambda m: FINAL[m])
    else:
        avail = [m for m in MIDS if t in RANK[m]]
        ranked = sorted(avail, key=lambda m: RANK[m][t])
    if topk_abs is not None:
        return set(ranked[:topk_abs])
    k = max(1, int(round(len(ranked) * frac)))
    return set(ranked[:k])

def ultra_elite_at(t):
    """Managers currently inside top-10K overall at GW t (absolute FPL rank, not sample-relative)."""
    return set(m for m in MIDS if t in RANK[m] and RANK[m][t] <= 10000)

def build_panel(N=4, gate_min_per_gw=45, cohort_frac=0.10, use_final=False,
                ultra=False, cap_weight=False):
    rows = []
    for t in range(N, 38 - N + 1):
        past = range(t - N + 1, t + 1)
        fwd = range(t + 1, t + N + 1)
        if ultra:
            coh = ultra_elite_at(t)
        else:
            coh = cohort_at(t, frac=cohort_frac, use_final=use_final)
        coh = [m for m in coh if t in OWNS.get(m, {})]
        csize = len(coh)
        if csize < 20:
            continue
        allm = [m for m in MIDS if t in OWNS.get(m, {})]
        asize = len(allm)
        # cohort ownership counts
        cnt = {}
        capcnt = {}
        for m in coh:
            for e in OWNS[m][t]:
                cnt[e] = cnt.get(e, 0) + 1
            cp = CAPS[m].get(t)
            if cp is not None:
                capcnt[cp] = capcnt.get(cp, 0) + 1
        acnt = {}
        for m in allm:
            for e in OWNS[m][t]:
                acnt[e] = acnt.get(e, 0) + 1
        # candidate players = those present in all needed GW live files & pass gate
        ids = set(PTS[t])
        for g in list(past) + list(fwd):
            ids &= set(PTS[g])
        for i in ids:
            mins_sum = sum(MINS[g][i] for g in past)
            if mins_sum < gate_min_per_gw * N:
                continue
            eo = cnt.get(i, 0) / csize
            if cap_weight:
                eo = (cnt.get(i, 0) + capcnt.get(i, 0)) / csize
            rows.append(dict(
                t=t, pid=i, pos=POS.get(i, 0),
                cohort_eo=eo,
                sample_own=acnt.get(i, 0) / asize,
                recent_pts=np.mean([PTS[g][i] for g in past]),
                fwd_mean=np.mean([PTS[g][i] for g in fwd]),
                csize=csize,
            ))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    df = build_panel(4)
    print(f"\nN=4 panel: n_rows={len(df)}, n_decision_GW={df.t.nunique()} (t={df.t.min()}..{df.t.max()})")
    print(f"median cohort size: {df.csize.median():.0f}")
    print(df[["cohort_eo", "sample_own", "recent_pts", "fwd_mean"]].describe().round(3))
    print("\ncorr matrix (predictors + outcome):")
    print(df[["cohort_eo", "sample_own", "recent_pts", "fwd_mean"]].corr(method="spearman").round(3))
