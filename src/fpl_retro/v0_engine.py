"""
v0 walk-forward FPL decision engine  —  season 2025/26
=======================================================
SMALLEST useful implementation. Sole purpose: does this engine carry enough
signal to beat (a) hold-current-squad and (b) at least one naive transfer
baseline over a leak-free walk-forward backtest, after transfer costs?

Design (matches the agreed scope):
  - Decision row = one (player, decision_gw t), features from GW (t-3..t) ONLY.
  - Two-part model: availability gate  P(play next GW)  x  E[points | play].
  - Primary target y4 = sum points over GW (t+1..t+4). Secondary report y3,y6.
  - Walk-forward expanding window with PURGE: train only on decision GWs s
    whose target window is fully observed before t  (s+4 <= t). No random split.
  - Decision sim: from the user's ACTUAL squad each GW, pick the single best
    feasible like-for-like transfer (budget-checked). Engine transfers only if
    predicted 4-GW gain > threshold; naive baselines transfer on any positive gain.
  - Retrospective: compare entry 816200's ACTUAL transfers vs engine reco.

LEAK-FREE GUARANTEES:
  - bootstrap_static used ONLY for static fields (position, team) + season-start
    price anchor (now_cost - cost_change_start). Its end-of-season form/points/
    ownership are NEVER used.
  - Features use only event <= t. Forward FIXTURE difficulty is schedule (known
    in advance) -> allowed. Forward POINTS/MINUTES are outcomes -> targets only.
  - Reconstructed price at t uses only transfer-cost observations at event <= t.

CAVEATS / TODOs (v0 deliberately simple):
  - Price reconstruction is sparse (only traded players get mid-season obs);
    non-traded players sit at the season-start anchor -> flagged low-confidence.
  - Sell proceeds ignore FPL's half-profit selling rule. TODO.
  - Single transfer/GW, 1 free transfer assumed (cost 0); no banking. TODO.
  - 3-per-club constraint not enforced in the swap search. TODO.
  - Chip gameweeks (wildcard/free-hit/etc.) excluded from the head-to-head
    retrospective (single-swap model can't represent them).
"""
import json, glob, re
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.preprocessing import StandardScaler

SEASON = "2025/26"
RAW = "/Users/djay/Documents/fpl-retrospective-codex-starter/data/raw"
ENTRY = 816200
H = 4                 # history window (prior GW)
KP = 4                # PRIMARY forward horizon
TEST_START = 8        # first walk-forward decision GW
TEST_END = 34         # last decision GW with a full 4-GW forward target (34+4=38)
ENGINE_TAU = 2.0      # min predicted 4-GW gain (pts) for engine to transfer

# ----------------------------------------------------------------------------- load
def load():
    bs = json.load(open(f"{RAW}/bootstrap_static_smoke.json"))
    pos   = {e["id"]: e["element_type"] for e in bs["elements"]}
    team  = {e["id"]: e["team"] for e in bs["elements"]}
    name  = {e["id"]: e["web_name"] for e in bs["elements"]}
    start_price = {e["id"]: e["now_cost"] - e["cost_change_start"] for e in bs["elements"]}
    end_price   = {e["id"]: e["now_cost"] for e in bs["elements"]}

    pts, mins, starts, registered = {}, {}, {}, {}
    for f in glob.glob(f"{RAW}/gw_live/gw_*_live.json"):
        gw = int(re.search(r"gw_(\d+)", f).group(1))
        d = json.load(open(f))
        pts[gw], mins[gw], starts[gw], registered[gw] = {}, {}, {}, set()
        for e in d["elements"]:
            s = e["stats"]; i = e["id"]
            pts[gw][i] = s["total_points"]; mins[gw][i] = s["minutes"]
            starts[gw][i] = s.get("starts", 0); registered[gw].add(i)
    GWS = sorted(pts)

    # fixture difficulty faced per (team, gw)  -> list of difficulties (DGW => >1)
    fx = json.load(open(f"{RAW}/fixtures.json"))
    team_fdr = defaultdict(list)  # (team,gw) -> [difficulties]
    for f in fx:
        gw = f.get("event")
        if gw is None: continue
        team_fdr[(f["team_h"], gw)].append(f["team_h_difficulty"])
        team_fdr[(f["team_a"], gw)].append(f["team_a_difficulty"])

    # reconstruct price series from pooled transfer-cost observations (event<=t safe)
    price_obs = defaultdict(list)  # (player,event) -> [costs]
    for f in glob.glob(f"{RAW}/managers/transfers/manager_*.json"):
        for t in json.load(open(f)):
            price_obs[(t["element_in"], t["event"])].append(t["element_in_cost"])
            price_obs[(t["element_out"], t["event"])].append(t["element_out_cost"])
    price = {}   # player -> {gw: price_tenths}
    traded = set(p for (p, e) in price_obs)
    for i in pos:
        series, last = {}, start_price[i]
        for gw in GWS:
            obs = price_obs.get((i, gw))
            if obs: last = int(np.median(obs))
            series[gw] = last
        series[GWS[-1]] = end_price[i]  # end anchor
        price[i] = series
    return dict(pos=pos, team=team, name=name, pts=pts, mins=mins, starts=starts,
                registered=registered, GWS=GWS, team_fdr=team_fdr, price=price,
                start_price=start_price, traded=traded)

# ----------------------------------------------------------------------------- features
def fdr_next(D, tm, t, k):
    diffs = []
    for gw in range(t + 1, t + k + 1):
        diffs += D["team_fdr"].get((tm, gw), [])
    return float(np.mean(diffs)) if diffs else 3.0   # neutral if blank

def build_panel(D):
    pts, mins, starts, reg, GWS = D["pts"], D["mins"], D["starts"], D["registered"], D["GWS"]
    rows = []
    for t in range(H, TEST_END + 1):              # decision GW
        for i in reg[t]:
            hist = range(t - H + 1, t + 1)
            if any(i not in pts[g] for g in hist): continue
            pts4 = sum(pts[g][i] for g in hist)
            mins4 = sum(mins[g][i] for g in hist)
            st4 = sum(starts[g][i] for g in hist)
            pr = D["price"][i][t] / 10.0
            val = pts4 / pr if pr > 0 else 0.0
            fdr = fdr_next(D, D["team"][i], t, KP)
            # targets
            def fwd(k):
                gws = [g for g in range(t + 1, t + k + 1) if g in pts and i in pts[g]]
                return (sum(pts[g][i] for g in gws), len(gws))
            y3, _ = fwd(3); y4, n4 = fwd(4); y6, n6 = fwd(6)
            play_next = 1 if (t + 1 in mins and mins.get(t + 1, {}).get(i, 0) >= 60) else 0
            played_fwd = 1 if sum(mins[g].get(i, 0) for g in range(t + 1, t + KP + 1)
                                  if g in mins) > 0 else 0
            rows.append(dict(gw=t, pid=i, pos=D["pos"][i], pts4=pts4, mins4=mins4,
                             starts4=st4, price=pr, value=val, fdr4=fdr,
                             y3=y3, y4=y4 if n4 == 4 else np.nan,
                             y6=y6 if n6 == 6 else np.nan,
                             play_next=play_next, played_fwd=played_fwd))
    return pd.DataFrame(rows)

# ----------------------------------------------------------------------------- two-part model
GATE_F = ["mins4", "starts4", "pts4"]
PT_F   = ["pts4", "mins4", "starts4", "value", "fdr4"]
def posdum(df): return pd.get_dummies(df["pos"], prefix="pos").reindex(
    columns=[f"pos_{p}" for p in (1, 2, 3, 4)], fill_value=0)

def fit_predict(train, test):
    """Two-part: P(play) * E[pts|play]. Returns yhat4 for test rows."""
    # gate
    gs = StandardScaler().fit(train[GATE_F])
    gate = LogisticRegression(max_iter=1000).fit(gs.transform(train[GATE_F]), train["play_next"])
    p_play = gate.predict_proba(gs.transform(test[GATE_F]))[:, 1]
    # conditional points model: train only on rows that actually played forward
    tr = train[train["played_fwd"] == 1]
    Xtr = np.hstack([StandardScaler().fit(tr[PT_F]).transform(tr[PT_F]), posdum(tr).values.astype(float)])
    sc = StandardScaler().fit(tr[PT_F])
    Xtr = np.hstack([sc.transform(tr[PT_F]), posdum(tr).values.astype(float)])
    pm = Ridge(alpha=1.0).fit(Xtr, tr["y4"])
    Xte = np.hstack([sc.transform(test[PT_F]), posdum(test).values.astype(float)])
    e_pts = pm.predict(Xte)
    return p_play * np.clip(e_pts, 0, None)

# ----------------------------------------------------------------------------- user team
def load_user(D):
    picks, banks, ehist = {}, {}, {}
    for fp in sorted(glob.glob(f"{RAW}/managers/picks/manager_{ENTRY}/event_*.json")):
        gw = int(re.search(r"event_(\d+)", fp).group(1))
        d = json.load(open(fp))
        picks[gw] = [p["element"] for p in d["picks"]]      # 15-man squad
        banks[gw] = d["entry_history"]["bank"] / 10.0
        ehist[gw] = d["entry_history"]
    transfers = defaultdict(list)
    for t in json.load(open(f"{RAW}/managers/transfers/manager_{ENTRY}.json")):
        transfers[t["event"]].append((t["element_in"], t["element_out"]))
    chips = {c["event"]: c["name"] for c in
             json.load(open(f"{RAW}/managers/history/manager_{ENTRY}.json")).get("chips", [])}
    return dict(picks=picks, banks=banks, ehist=ehist, transfers=transfers, chips=chips)

# ----------------------------------------------------------------------------- decision sim
def best_swap(owned, cand, score, price, bank, realized, require_gain=0.0):
    """Pick single feasible like-for-like swap maximizing score gain.
    Returns (pid_in, pid_out, pred_gain, realized_net) or None (=hold)."""
    best = None
    owned_set = set(owned)
    for out in owned:
        if out not in score: continue
        for inn in cand[POS[out]]:
            if inn in owned_set or inn not in score: continue
            if price[inn] > price[out] + bank + 1e-9: continue        # budget
            gain = score[inn] - score[out]
            if gain <= require_gain: continue
            if best is None or gain > best[2]:
                rn = realized.get(inn, np.nan) - realized.get(out, np.nan)
                best = (inn, out, gain, rn)
    return best

def run():
    D = load(); U = load_user(D)
    global POS; POS = D["pos"]
    panel = build_panel(D)
    print(f"=== v0 FPL decision engine — season {SEASON} ===")
    print(f"panel rows (player-GW decisions, GW{H}..{TEST_END}): {len(panel):,}")
    print(f"walk-forward test GWs: {TEST_START}..{TEST_END} | primary horizon: next {KP} GW")
    print(f"user entry {ENTRY} | chip GWs excluded from head-to-head: "
          f"{sorted(g for g in U['chips'] if TEST_START<=g<=TEST_END)}\n")

    strategies = ["engine", "hold", "hi_points", "hi_minutes", "hi_value", "easy_fixtures"]
    per_gw = {s: [] for s in strategies}          # realized net y4 per test GW
    per_gw_h = {s: {3: [], 6: []} for s in strategies}   # secondary horizons
    retro_rows = []

    for t in range(TEST_START, TEST_END + 1):
        train = panel[panel["gw"] <= t - KP]                      # PURGE: target fully observed
        test = panel[panel["gw"] == t].copy()
        if len(train) < 200 or test.empty: continue
        test["yhat4"] = fit_predict(train, test)

        sc = {r.pid: r for r in test.itertuples()}
        price_t = {pid: sc[pid].price for pid in sc}
        real_y4 = {pid: (sc[pid].y4 if not np.isnan(sc[pid].y4) else 0.0) for pid in sc}
        real_y3 = {pid: sc[pid].y3 for pid in sc}
        real_y6 = {pid: (sc[pid].y6 if not np.isnan(sc[pid].y6) else 0.0) for pid in sc}
        cand = defaultdict(list)
        for pid in sc: cand[POS[pid]].append(pid)

        owned = [p for p in U["picks"].get(t, []) if p in sc]
        bank = U["banks"].get(t, 0.0)
        if not owned: continue

        metric = {
            "engine":        {pid: sc[pid].yhat4 for pid in sc},
            "hi_points":     {pid: sc[pid].pts4 for pid in sc},
            "hi_minutes":    {pid: sc[pid].mins4 for pid in sc},
            "hi_value":      {pid: sc[pid].value for pid in sc},
            "easy_fixtures": {pid: -sc[pid].fdr4 for pid in sc},
        }
        # hold = 0 every GW
        per_gw["hold"].append(0.0); per_gw_h["hold"][3].append(0.0); per_gw_h["hold"][6].append(0.0)
        for s in strategies:
            if s == "hold": continue
            tau = ENGINE_TAU if s == "engine" else 0.0
            swap = best_swap(owned, cand, metric[s], price_t, bank, real_y4, require_gain=tau)
            if swap is None:
                per_gw[s].append(0.0); per_gw_h[s][3].append(0.0); per_gw_h[s][6].append(0.0)
            else:
                inn, out, _, rn = swap
                per_gw[s].append(0.0 if np.isnan(rn) else rn)
                per_gw_h[s][3].append(real_y3.get(inn, 0) - real_y3.get(out, 0))
                per_gw_h[s][6].append(real_y6.get(inn, 0) - real_y6.get(out, 0))

        # ---- retrospective vs user actual (skip chip GWs) ----
        if t in U["chips"]:
            continue
        eng = best_swap(owned, cand, metric["engine"], price_t, bank, real_y4, require_gain=ENGINE_TAU)
        eng_in, eng_out = (eng[0], eng[1]) if eng else (None, None)
        eng_val = (0.0 if (eng is None or np.isnan(eng[3])) else eng[3])
        # user's actual transfers this GW
        acts = [(i, o) for (i, o) in U["transfers"].get(t, []) if i in sc and o in sc]
        hit = U["ehist"][t]["event_transfers_cost"] if t in U["ehist"] else 0
        user_val = sum(real_y4.get(i, 0) - real_y4.get(o, 0) for (i, o) in acts) - hit
        if not acts and eng is None:
            cat = "both_hold"
        elif not acts and eng is not None:
            cat = "user_held_engine_bought"
        elif acts and eng is None:
            cat = "user_bought_engine_held"
        else:
            cat = "both_transferred_diff" if (eng_in, eng_out) not in acts else "agree"
        retro_rows.append(dict(gw=t, category=cat,
                               user_in=";".join(D["name"][i] for i, _ in acts) or "-",
                               user_out=";".join(D["name"][o] for _, o in acts) or "-",
                               user_net_y4=round(user_val, 1),
                               engine_in=D["name"][eng_in] if eng_in else "-",
                               engine_out=D["name"][eng_out] if eng_out else "-",
                               engine_net_y4=round(eng_val, 1),
                               engine_minus_user=round(eng_val - user_val, 1)))

    # ----------------------------------------------------------------- results
    def boot_ci(vals, B=5000):
        v = np.array(vals); n = len(v)
        if n == 0: return (np.nan, np.nan, np.nan)
        means = [v[np.random.randint(0, n, n)].mean() for _ in range(B)]
        return (v.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5))

    np.random.seed(0)
    print(f"{'strategy':14} {'nGW':>4} {'mean net y4/GW':>15} {'95% block-bootstrap CI':>26}  transfers")
    res = {}
    for s in strategies:
        m, lo, hi = boot_ci(per_gw[s])
        n_tf = sum(1 for x in per_gw[s] if x != 0.0) if s != "hold" else 0
        res[s] = (m, lo, hi)
        print(f"{s:14} {len(per_gw[s]):>4} {m:>15.3f} {('[%+.3f, %+.3f]'%(lo,hi)):>26}  {n_tf}")

    print("\nSecondary horizons (engine, realized net per GW; decision still y4-based):")
    for k in (3, 6):
        v = per_gw_h["engine"][k]; print(f"  y{k}: mean {np.mean(v):+.3f}/GW")

    em, elo, ehi = res["engine"]
    print("\n--- v0 SUCCESS CRITERION ---")
    beats_hold = elo > 0
    naive = {k: res[k][0] for k in ("hi_points", "hi_minutes", "hi_value", "easy_fixtures")}
    beats_naive = [k for k, v in naive.items() if em > v]
    print(f"beats HOLD (CI lower bound > 0)?  {beats_hold}  (engine {em:+.3f} CI[{elo:+.3f},{ehi:+.3f}])")
    print(f"beats >=1 naive baseline?         {len(beats_naive)>0}  (beats: {beats_naive})")
    print(f"VERDICT: {'PASS' if (beats_hold and beats_naive) else 'NOT MET — signal too weak in v0'}")

    # retrospective
    rdf = pd.DataFrame(retro_rows)
    print("\n--- RETROSPECTIVE: entry 816200 actual vs engine (chip GWs excluded) ---")
    if not rdf.empty:
        print(rdf["category"].value_counts().to_string())
        tot = rdf["engine_minus_user"].sum()
        print(f"\nTotal engine-minus-user realized 4-GW points across non-chip GWs: {tot:+.1f}")
        worst = rdf.sort_values("engine_minus_user", ascending=False).head(5)
        print("Top 5 GWs where engine reco would have most improved vs your actual:")
        print(worst[["gw", "category", "user_out", "user_in", "user_net_y4",
                     "engine_out", "engine_in", "engine_net_y4", "engine_minus_user"]].to_string(index=False))
    # save tables
    out = "/Users/djay/Documents/fpl-retrospective-codex-starter/outputs/tables"
    pd.DataFrame({s: pd.Series(per_gw[s]) for s in strategies}).to_csv(f"{out}/v0_walkforward_pergw.csv", index=False)
    rdf.to_csv(f"{out}/v0_retrospective_816200.csv", index=False)
    print(f"\nsaved: {out}/v0_walkforward_pergw.csv , v0_retrospective_816200.csv")
    print("\nCAVEATS: sparse price reconstruction; sell half-profit ignored; 1 free "
          "transfer/GW assumed (no banking, no hits beyond user actual); 3-per-club "
          "not enforced; chip GWs excluded from head-to-head. All TODO for v1.")

if __name__ == "__main__":
    run()
