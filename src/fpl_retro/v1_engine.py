"""
v1 — realistic decision-value evaluation  (season 2025/26)
==========================================================
Question: does the two-stage predictive layer create PRACTICAL decision value
once FPL realities are included (squad/formation/bench/captaincy/banking/hits/
chips), or does a simple rule do just as well?

Two-stage model (unchanged):
  - availability gate (hard filter p_play>=0.5)
  - conditional ranker among likely starters
Engine scores used by role:
  - TRANSFER score  = E[pts|play] among likely starters only (v0.1 ranker)
  - SELECT/CAPTAIN  = p_play * E[pts|play]  (expected next-period points)

Realistic simulator (walk-forward GW8->34, leak-free):
  transfers (banked free tf cap 2; engine may take -4 hits when predicted gain>4+tau)
  -> formation-legal XI + bench order + captain/vice (pre-GW scores)
  -> actual scoring with auto-subs + captain doubling.
Chips EXCLUDED for all strategies (separate optimisation; chip-free weekly process
is the only fair comparison). Decision value decomposed: transfer / captaincy /
squad-selection / total. Uncertainty via 40 cohort starting squads (paired CIs).

LANGUAGE: predictive/associational only. "predicted", "ranked", "would have scored
in simulation". No causal claims.
CAVEATS: price reconstruction sparse; sell half-profit ignored; 1-GW selection uses
the 4-GW ranker as proxy (dedicated 1-GW model = v1.1); EO from 300-manager sample.
"""
import numpy as np, pandas as pd, glob, json, re
from collections import defaultdict
import src.fpl_retro.v0_engine as v0
import src.fpl_retro.v0_1_engine as v1

START, END = 8, 34
SQUAD = {1: 2, 2: 5, 3: 5, 4: 3}                 # GK,DEF,MID,FWD in a 15
FMIN, FMAX = {2: 3, 3: 2, 4: 1}, {2: 5, 3: 5, 4: 3}  # outfield formation bounds
HIT = 4

# --------------------------------------------------------------- precompute
def cohort_eo(n=300, seed=3):
    dirs = sorted(glob.glob(f"{v0.RAW}/managers/picks/manager_*"))
    rng = np.random.default_rng(seed)
    dirs = list(rng.choice(dirs, min(n, len(dirs)), replace=False))
    eo = {t: defaultdict(int) for t in range(START, END + 1)}
    cnt = {t: 0 for t in range(START, END + 1)}
    for d in dirs:
        for t in range(START, END + 1):
            fp = f"{d}/event_{t:02d}.json"
            try:
                pj = json.load(open(fp))
            except FileNotFoundError:
                continue
            cnt[t] += 1
            for p in pj["picks"]:
                eo[t][p["element"]] += 1
    return {t: {pid: eo[t][pid] / cnt[t] for pid in eo[t]} for t in eo if cnt[t]}

def build_lookup(D):
    panel = v0.build_panel(D)
    P = v1.pooled_predictions(D, panel)           # has e_pts, p_play, features, y4
    SC = {}
    for t in range(START, END + 1):
        rows = P[P["gw"] == t]
        SC[t] = {}
        for r in rows.itertuples():
            SC[t][r.pid] = dict(e_pts=r.e_pts, p_play=r.p_play, pts4=r.pts4,
                                mins4=r.mins4, value=r.value, fdr4=r.fdr4, price=r.price,
                                sel=r.p_play * r.e_pts)
    return SC

# --------------------------------------------------------------- XI / scoring
def pick_xi(squad, pos, score):
    """Formation-legal XI maximising pre-GW score. Returns (xi, bench_order, cap, vice)."""
    by = defaultdict(list)
    for p in squad:
        by[pos[p]].append(p)
    for q in by:
        by[q].sort(key=lambda p: score.get(p, -1), reverse=True)
    gk = by[1][0]; bench_gk = by[1][1] if len(by[1]) > 1 else None
    out = []
    for q in (2, 3, 4):                            # satisfy minimums
        out += [(p, q) for p in by[q][:FMIN[q]]]
    chosen = set(p for p, _ in out)
    rest = sorted([(p, q) for q in (2, 3, 4) for p in by[q] if p not in chosen],
                  key=lambda pq: score.get(pq[0], -1), reverse=True)
    cnt = {2: FMIN[2], 3: FMIN[3], 4: FMIN[4]}
    for p, q in rest:
        if len(out) >= 10: break
        if cnt[q] < FMAX[q]:
            out.append((p, q)); cnt[q] += 1
    xi = [gk] + [p for p, _ in out]
    bench = [p for p in squad if p not in set(xi) and p != bench_gk]
    bench.sort(key=lambda p: score.get(p, -1), reverse=True)
    field = sorted([p for p in xi if p != gk], key=lambda p: score.get(p, -1), reverse=True)
    cap = field[0] if field else gk
    vice = field[1] if len(field) > 1 else gk
    return xi, ([bench_gk] if bench_gk else []) + bench, cap, vice

def score_gw(xi, bench, cap, vice, gk_bench, pos, pts, mins):
    """Actual points with auto-subs + captain doubling."""
    played = lambda p: mins.get(p, 0) > 0
    final = [p for p in xi if played(p)]
    # GK auto-sub
    if xi and not played(xi[0]) and gk_bench and played(gk_bench[0]):
        final = [gk_bench[0]] + [p for p in final if pos[p] != 1]
    # outfield auto-subs from bench order, formation-legal
    cur = defaultdict(int)
    for p in final:
        cur[pos[p]] += 1
    out_bench = [p for p in bench if pos[p] != 1]
    for b in out_bench:
        if len(final) >= 11: break
        if not played(b): continue
        q = pos[b]
        if cur[q] < FMAX[q]:
            final.append(b); cur[q] += 1
    base = sum(pts.get(p, 0) for p in final)
    capt = cap if played(cap) else (vice if played(vice) else None)
    bonus = pts.get(capt, 0) if capt in set(final) or (capt and played(capt)) else 0
    return base + bonus, pts.get(cap, 0) if played(cap) else pts.get(vice, 0)

# --------------------------------------------------------------- simulator
def metric_fn(name, SCt):
    f = {"engine_t": lambda d: d["e_pts"], "engine_s": lambda d: d["sel"],
         "hi_points": lambda d: d["pts4"], "hi_minutes": lambda d: d["mins4"],
         "hi_value": lambda d: d["value"], "fixture": lambda d: -d["fdr4"]}[name]
    return {pid: f(SCt[pid]) for pid in SCt}

def simulate(D, SC, squad0, bank0, transfer, select, captain, eo, allow_hits=False, tau=2.0):
    """Returns dict of season totals: total, captain_pts(extra), transfers, hits."""
    pos, pts, mins = D["pos"], D["pts"], D["mins"]
    squad = list(squad0); bank = bank0; free = 1
    tot = capt_extra = n_tf = n_hit = 0
    for t in range(START, END + 1):
        SCt = SC.get(t, {})
        # ---- transfer step ----
        if transfer != "hold":
            tsc = (metric_fn(transfer, SCt) if transfer.startswith(("hi_", "fixture"))
                   else None)
            if transfer == "engine":
                likely = {p for p in SCt if SCt[p]["p_play"] >= v1.GATE_THRESH}
                tsc = {p: SCt[p]["e_pts"] for p in likely}
            elif transfer == "template":
                tsc = {p: eo.get(t, {}).get(p, 0) for p in SCt
                       if SCt[p]["p_play"] >= v1.GATE_THRESH}
            else:  # naive among likely starters
                likely = {p for p in SCt if SCt[p]["p_play"] >= v1.GATE_THRESH}
                tsc = {p: tsc[p] for p in likely if p in tsc}
            owned = set(squad)
            for _ in range(2):                     # up to 2 transfers/GW
                best = None
                for outp in squad:
                    if outp not in SCt: continue
                    for inn in tsc:
                        if inn in owned or pos[inn] != pos[outp]: continue
                        if SCt[inn]["price"] > SCt[outp]["price"] + bank + 1e-9: continue
                        g = tsc[inn] - tsc.get(outp, -1)
                        if best is None or g > best[2]: best = (inn, outp, g)
                if best is None: break
                inn, outp, g = best
                is_hit = free <= 0
                # engine: gain in points -> compare to hit; naive: take only with free tf
                if transfer == "engine":
                    need = (HIT if is_hit else 0) + tau
                    if g <= need or (is_hit and not allow_hits): break
                else:
                    if g <= 0 or is_hit: break      # naive: free tf only, positive gain
                bank += SCt[outp]["price"] - SCt[inn]["price"]
                squad = [inn if p == outp else p for p in squad]; owned = set(squad)
                if is_hit: tot -= HIT; n_hit += 1
                free -= 1; n_tf += 1
        free = min(2, free + 1)
        # ---- selection + captain ----
        ssc = (metric_fn("engine_s", SCt) if select == "engine" else
               metric_fn({"hi_points": "hi_points", "hi_minutes": "hi_minutes",
                          "hi_value": "hi_value", "fixture": "fixture"}[select], SCt)
               if select in ("hi_points", "hi_minutes", "hi_value", "fixture") else
               metric_fn("engine_s", SCt))
        csc = (metric_fn("engine_s", SCt) if captain == "engine" else
               metric_fn("hi_points", SCt) if captain == "hi_points" else
               metric_fn("engine_s", SCt))
        xi, bench, cap, vice = pick_xi(squad, pos, ssc)
        # captain override by captain metric (among XI field)
        field = [p for p in xi if pos[p] != 1]
        if field:
            cap = max(field, key=lambda p: csc.get(p, -1))
            vice = max([p for p in field if p != cap] or [cap], key=lambda p: csc.get(p, -1))
        gk_bench = [p for p in bench if pos[p] == 1]
        gpts, cpts = score_gw(xi, [p for p in bench if pos[p] != 1], cap, vice, gk_bench,
                              pos, pts.get(t, {}), mins.get(t, {}))
        tot += gpts; capt_extra += cpts            # cpts ~ captain's own pts (doubled portion)
    return dict(total=tot, captain=capt_extra, transfers=n_tf, hits=n_hit)

# --------------------------------------------------------------- multi-start harness
def starts(n=40, seed=1):
    files = sorted(glob.glob(f"{v0.RAW}/managers/picks/manager_*/event_{START:02d}.json"))
    rng = np.random.default_rng(seed)
    out = []
    for fp in rng.choice(files, n, replace=False):
        d = json.load(open(fp))
        out.append(([p["element"] for p in d["picks"]], d["entry_history"]["bank"] / 10.0))
    return out

def ci(a):
    a = np.array(a); return a.mean(), np.percentile(a, 2.5), np.percentile(a, 97.5)

def run():
    D = v0.load(); v0.POS = D["pos"]
    SC = build_lookup(D); eo = cohort_eo()
    S = starts(40)
    print(f"=== v1 realistic decision-value sim — season 2025/26 ===")
    print(f"40 cohort starting squads | walk-forward GW{START}-{END} | chips excluded\n")

    simple = ["hi_points", "hi_minutes", "hi_value", "fixture", "template"]
    # ---------- TOTAL ----------
    def runlayer(transfer_for, select_for, captain_for, label):
        res = {}
        for strat in ["engine"] + simple + (["hold"] if "hold" not in simple else []):
            tr = strat if transfer_for == "strat" else transfer_for
            se = strat if select_for == "strat" else select_for
            ca = strat if captain_for == "strat" else captain_for
            vals = []
            for sq, bk in S:
                r = simulate(D, SC, sq, bk, tr, se, ca, eo, allow_hits=True)
                vals.append(r["total"] if label != "CAPTAIN" else r["captain"])
            res[strat] = vals
        return res

    layers = {
        "TOTAL":   runlayer("strat", "strat", "strat", "TOTAL"),
        "TRANSFER":runlayer("strat", "engine", "engine", "TRANSFER"),
        "SELECT":  runlayer("hold", "strat", "engine", "SELECT"),
        "CAPTAIN": runlayer("hold", "engine", "strat", "CAPTAIN"),
    }
    for name, res in layers.items():
        eng = res["engine"]
        cands = {k: v for k, v in res.items() if k not in ("engine", "hold")}
        best = max(cands, key=lambda k: np.mean(cands[k]))
        em, elo, ehi = ci(eng)
        diff = np.array(eng) - np.array(res[best])
        dm, dlo, dhi = ci(diff)
        vs_hold = ""
        if "hold" in res:
            dh = np.array(eng) - np.array(res["hold"]); vs_hold = f" | vs hold {dh.mean():+.0f}[{np.percentile(dh,2.5):+.0f},{np.percentile(dh,97.5):+.0f}]"
        tag = "WIN" if dlo > 0 else ("LOSE" if dhi < 0 else "tie")
        print(f"[{name:8}] engine {em:6.0f}  best simple = {best} ({np.mean(res[best]):.0f}) | "
              f"engine-best {dm:+.0f} CI[{dlo:+.0f},{dhi:+.0f}] {tag}{vs_hold}")

    # ---------- captaincy vs USER ACTUAL (single path, entry 816200) ----------
    print("\nCaptaincy vs your ACTUAL picks (entry 816200, your real squad each GW, chips excl.):")
    U = v0.load_user(D)
    eng_c = act_c = hip_c = 0; nz = 0
    for t in range(START, END + 1):
        if t in U["chips"] or t not in U["picks"]: continue
        squad = [p for p in U["picks"][t] if p in SC.get(t, {})]
        if not squad: continue
        SCt = SC[t]; csc = {p: SCt[p]["sel"] for p in squad}
        field = [p for p in squad if D["pos"][p] != 1]
        if not field: continue
        eng_cap = max(field, key=lambda p: csc.get(p, -1))
        hip_cap = max(field, key=lambda p: SCt[p]["pts4"])
        # actual captain
        pj = json.load(open(f"{v0.RAW}/managers/picks/manager_{v0.ENTRY}/event_{t:02d}.json"))
        act = next((p["element"] for p in pj["picks"] if p["is_captain"]), None)
        gp = D["pts"].get(t, {})
        eng_c += gp.get(eng_cap, 0); hip_c += gp.get(hip_cap, 0)
        act_c += gp.get(act, 0) if act else 0; nz += 1
    print(f"  over {nz} non-chip GWs — captain points captured (single, not doubled):")
    print(f"    engine-captain {eng_c} | hi_points-captain {hip_c} | YOUR actual {act_c}")

    # ---------- verdict ----------
    tdm = ci(np.array(layers['TOTAL']['engine']) - np.array(layers['TOTAL'][
        max({k:v for k,v in layers['TOTAL'].items() if k not in ('engine','hold')},
            key=lambda k: np.mean(layers['TOTAL'][k]))]))
    comp_wins = [n for n in ("TRANSFER", "SELECT", "CAPTAIN")
                 if ci(np.array(layers[n]['engine']) - np.array(layers[n][
                     max({k:v for k,v in layers[n].items() if k not in ('engine','hold')},
                         key=lambda k: np.mean(layers[n][k]))]))[1] > 0]
    print("\n=== v1 SUCCESS CRITERION ===")
    print(f"engine beats BEST simple rule on TOTAL (CI>0)? {tdm[1] > 0}  "
          f"(engine-best {tdm[0]:+.0f} CI[{tdm[1]:+.0f},{tdm[2]:+.0f}])")
    print(f"component layers where engine beats best simple (CI>0): {comp_wins or 'NONE'}")
    promote = tdm[1] > 0 and len(comp_wins) >= 1
    print(f"\nVERDICT: {'PROMOTE' if promote else 'DO NOT PROMOTE — recommend best simple rule as weekly process'}")
    print("\nCAVEATS: chips excluded; 1-GW selection uses 4-GW ranker as proxy; price/EO "
          "reconstruction sparse; half-profit sells ignored; portfolio realism partial.")

if __name__ == "__main__":
    run()
