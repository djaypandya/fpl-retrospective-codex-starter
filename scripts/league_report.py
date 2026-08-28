"""Mini-league intelligence report for a live gameweek.

Pulls a classic league's standings, every manager's picks for one gameweek, and
each manager's past-season history, then answers four questions:

1. What is the template team in this league?
2. How does each manager split the budget across the starting eleven?
3. What do the historically strongest managers do differently?
4. Which players can hurt me most from here?

Run::

    python3.12 scripts/league_report.py --league 14074 --entry 46116 --gw 1

Writes ``outputs/league_<id>_gw<n>/`` and prints a summary.
"""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

API = "https://fantasy.premierleague.com/api"
POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}
TEMPLATE_SLOTS = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
REPO = Path(__file__).resolve().parents[1]


def _ssl_context() -> ssl.SSLContext:
    """Python.org builds ship without linked root certificates, so use certifi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

def get(url: str, cache: Path) -> dict:
    """Fetch JSON, caching to disk so a re-run costs nothing."""
    if cache.exists() and cache.stat().st_size > 0:
        return json.loads(cache.read_text())
    with urllib.request.urlopen(url, timeout=60, context=_ssl_context()) as r:
        payload = json.load(r)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload))
    return payload


def load(league: int, gw: int, cache_dir: Path) -> dict:
    bootstrap = get(f"{API}/bootstrap-static/", cache_dir / "bootstrap.json")
    fixtures = get(f"{API}/fixtures/?event={gw}", cache_dir / f"fixtures_gw{gw}.json")
    standings = get(f"{API}/leagues-classic/{league}/standings/",
                    cache_dir / f"standings_{league}.json")
    entries = [r["entry"] for r in standings["standings"]["results"]]
    picks = {e: get(f"{API}/entry/{e}/event/{gw}/picks/", cache_dir / "picks" / f"{e}.json")
             for e in entries}
    history = {e: get(f"{API}/entry/{e}/history/", cache_dir / "history" / f"{e}.json")
               for e in entries}
    transfers = {e: get(f"{API}/entry/{e}/transfers/", cache_dir / "transfers" / f"{e}.json")
                 for e in entries}
    return dict(bootstrap=bootstrap, fixtures=fixtures, standings=standings,
                picks=picks, history=history, transfers=transfers)


def build_picks(data: dict) -> pd.DataFrame:
    """One row per manager-player, with live points and whether the club has played."""
    bs = data["bootstrap"]
    el = {e["id"]: e for e in bs["elements"]}
    club = {t["id"]: t["short_name"] for t in bs["teams"]}
    played = set()
    for f in data["fixtures"]:
        if f["started"]:
            played |= {f["team_h"], f["team_a"]}
    meta = {r["entry"]: r for r in data["standings"]["standings"]["results"]}

    rows = []
    for eid, pk in data["picks"].items():
        chip = pk.get("active_chip")
        for p in pk["picks"]:
            e = el[p["element"]]
            rows.append(dict(
                entry=eid, manager=meta[eid]["player_name"], team_name=meta[eid]["entry_name"],
                rank=meta[eid]["rank"], live_pts=meta[eid]["total"], chip=chip,
                element=p["element"], name=e["web_name"], pos=POS[e["element_type"]],
                club=club[e["team"]], team_id=e["team"],
                # Price at season start: what the squad was actually built with.
                price=(e["now_cost"] - e["cost_change_start"]) / 10,
                slot=p["position"], multiplier=p["multiplier"],
                is_captain=p["is_captain"], gw_points=e["event_points"],
                played=e["team"] in played))
    # Deterministic order: these CSVs are committed, so a re-run should only
    # diff where the data actually changed, not where dict order happened to.
    return (pd.DataFrame(rows)
            .sort_values(["rank", "entry", "slot"])
            .reset_index(drop=True))


def league_template(df: pd.DataFrame) -> pd.DataFrame:
    """Most-owned players by position, with effective ownership."""
    n = df.entry.nunique()
    own = df.groupby(["element", "name", "pos", "club"], as_index=False).agg(
        owners=("entry", "nunique"), mult=("multiplier", "sum"),
        gw_points=("gw_points", "first"), price=("price", "first"),
        played=("played", "first"))
    own["own_pct"] = 100 * own.owners / n
    # Effective ownership counts a captain twice, which is what actually hurts.
    own["eo_pct"] = 100 * own.mult / n
    picks = [own[own.pos == p].nlargest(k, "own_pct") for p, k in TEMPLATE_SLOTS.items()]
    return pd.concat(picks).assign(
        slot_order=lambda d: d.pos.map({"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3})
    ).sort_values(["slot_order", "own_pct"], ascending=[True, False]).drop(columns="slot_order")


def budget_split(df: pd.DataFrame) -> pd.DataFrame:
    """Spend per position for the nominal starting eleven, comparable across chips.

    Managers who played a chip still get scored on slots 1-11 so the split means
    the same thing for everyone. Keep `chip` out of the pivot index: it is null
    for most managers, and pivot_table silently drops null index groups.
    """
    xi = df[df.slot <= 11]
    b = (xi.pivot_table(index="entry", columns="pos", values="price", aggfunc="sum")
           .reindex(columns=list(TEMPLATE_SLOTS)).fillna(0).reset_index())
    b["XI_spend"] = b[list(TEMPLATE_SLOTS)].sum(axis=1)
    meta = df.groupby("entry", as_index=False).agg(
        manager=("manager", "first"), rank=("rank", "first"),
        live_pts=("live_pts", "first"), chip=("chip", "first"),
        squad_value=("price", "sum"))
    b = b.merge(meta, on="entry")
    b["bench"] = b.squad_value - b.XI_spend
    return b.sort_values("rank")


def rank_managers(data: dict, df: pd.DataFrame, min_seasons: int = 4) -> pd.DataFrame:
    """Rank managers by median overall finish, which rewards consistency over one spike."""
    rows = []
    for eid, h in data["history"].items():
        past = h.get("past", [])
        ranks = [p["rank"] for p in past][-5:]
        rows.append(dict(
            entry=eid, manager=df[df.entry == eid].manager.iloc[0], seasons=len(ranks),
            median_rank=int(np.median(ranks)) if ranks else np.nan,
            best_rank=min(ranks) if ranks else np.nan,
            detail="; ".join(f"{p['season_name'][2:]}:{p['rank'] // 1000}k" for p in past[-5:])))
    out = pd.DataFrame(rows)
    out["qualified"] = out.seasons >= min_seasons
    return out.sort_values(["qualified", "median_rank"], ascending=[False, True])


def exposure(df: pd.DataFrame, me: int) -> pd.DataFrame:
    """Per point a player scores, how much ground do I gain or lose on the average rival?"""
    n = df.entry.nunique()
    rivals = df[df.entry != me]
    r = rivals.groupby(["element", "name", "pos", "club", "gw_points", "played", "price"],
                       as_index=False).multiplier.sum()
    r["rival_avg_mult"] = r.multiplier / (n - 1)
    r["my_mult"] = r.element.map(df[df.entry == me].set_index("element").multiplier).fillna(0)
    r["net"] = r.my_mult - r.rival_avg_mult
    return r.sort_values("net")


def transfer_activity(data: dict, gw: int, me: int) -> dict:
    """Who the league bought and sold for this gameweek, and at what cost.

    A transfer is a manager spending their one free move, or paying 4 points for
    an extra one. Both say something about conviction, so hits are tracked apart
    from free moves.
    """
    bs = data["bootstrap"]
    el = {e["id"]: e for e in bs["elements"]}
    club = {t["id"]: t["short_name"] for t in bs["teams"]}
    meta = {r["entry"]: r for r in data["standings"]["standings"]["results"]}

    moves, per_manager = [], []
    for eid, log in data["transfers"].items():
        this_gw = [t for t in log if t["event"] == gw]
        hist = data["picks"][eid]["entry_history"]
        chip = data["picks"][eid].get("active_chip")
        # Count from the transfer log, not entry_history: FPL reports
        # event_transfers as 0 for a wildcard or free hit even when the manager
        # rebuilt the whole squad, so the header field undercounts activity.
        per_manager.append({
            "entry": eid, "manager": meta[eid]["player_name"],
            "transfers": len(this_gw),
            "free_transfers_used": hist["event_transfers"],
            "hit_cost": hist["event_transfers_cost"],
            "chip": chip or "",
            "in": ", ".join(el[t["element_in"]]["web_name"] for t in this_gw) or "-",
            "out": ", ".join(el[t["element_out"]]["web_name"] for t in this_gw) or "-",
        })
        for t in this_gw:
            for direction, key in [("in", "element_in"), ("out", "element_out")]:
                e = el[t[key]]
                moves.append({
                    "entry": eid, "manager": meta[eid]["player_name"],
                    "direction": direction, "element": e["id"], "name": e["web_name"],
                    "pos": POS[e["element_type"]], "club": club[e["team"]],
                    "price": t[f"{key}_cost"] / 10, "gw_points": e["event_points"],
                })

    mv = pd.DataFrame(moves)
    flow = pd.DataFrame(columns=["name", "pos", "club", "in", "out", "net"])
    if not mv.empty:
        counts = (mv.groupby(["name", "pos", "club", "direction"]).entry.nunique()
                  .unstack(fill_value=0).reset_index())
        for c in ("in", "out"):
            if c not in counts:
                counts[c] = 0
        counts["net"] = counts["in"] - counts["out"]
        flow = counts.sort_values("net", ascending=False)

    pm = pd.DataFrame(per_manager).sort_values(["transfers", "hit_cost"], ascending=False)
    return {"moves": mv, "flow": flow, "per_manager": pm,
            "active": int((pm.transfers > 0).sum()), "total": int(pm.transfers.sum()),
            "hits": int((pm.hit_cost > 0).sum()), "hit_points": int(pm.hit_cost.sum()),
            "chips": pm[pm.chip != ""][["manager", "chip", "transfers"]].to_dict("records"),
            "quiet": int((pm.transfers == 0).sum()),
            "i_moved": bool(pm[pm.entry == me].transfers.iloc[0])}


def head_to_head(df: pd.DataFrame, me: int, rival: int) -> dict:
    """What is left to play that only one of us owns."""
    mine = set(df[(df.entry == me) & (df.multiplier > 0)].element)
    theirs = set(df[(df.entry == rival) & (df.multiplier > 0)].element)
    left = df[~df.played & (df.multiplier > 0)]
    return {
        "rival": df[df.entry == rival].manager.iloc[0],
        "only_mine": sorted(left[(left.entry == me) & left.element.isin(mine - theirs)].name),
        "only_theirs": sorted(left[(left.entry == rival) & left.element.isin(theirs - mine)].name),
        "my_units_left": int(left[left.entry == me].multiplier.sum()),
        "their_units_left": int(left[left.entry == rival].multiplier.sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--league", type=int, required=True)
    ap.add_argument("--entry", type=int, required=True)
    ap.add_argument("--gw", type=int, required=True)
    ap.add_argument("--top", type=int, default=5, help="how many historic managers to profile")
    args = ap.parse_args()

    out = REPO / "outputs" / f"league_{args.league}_gw{args.gw}"
    cache = out / "raw"
    data = load(args.league, args.gw, cache)
    df = build_picks(data)
    n = df.entry.nunique()

    tmpl = league_template(df)
    budget = budget_split(df)
    hist = rank_managers(data, df)
    risk = exposure(df, args.entry)
    tx = transfer_activity(data, args.gw, args.entry)

    top5 = hist[hist.qualified].nsmallest(args.top, "median_rank")
    cols = list(TEMPLATE_SLOTS) + ["XI_spend", "bench"]
    compare = pd.DataFrame({
        "me": budget[budget.entry == args.entry][cols].iloc[0],
        "top_managers": budget[budget.entry.isin(top5.entry)][cols].mean(),
        "league": budget[cols].mean()}).round(2)
    compare["me_vs_top"] = (compare.me - compare.top_managers).round(2)

    left = df[~df.played & (df.multiplier > 0)].groupby("entry").multiplier.sum()
    total = df[df.multiplier > 0].groupby("entry").multiplier.sum()
    remaining = (100 * left / total).round(0).rename("pct_left")

    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "picks_long.csv", index=False)
    tmpl.to_csv(out / "template.csv", index=False)
    budget.to_csv(out / "budget.csv", index=False)
    hist.to_csv(out / "history.csv", index=False)
    risk.to_csv(out / "exposure.csv", index=False)
    tx["flow"].to_csv(out / "transfer_flow.csv", index=False)
    tx["per_manager"].to_csv(out / "transfers_by_manager.csv", index=False)
    tx["moves"].to_csv(out / "transfer_moves.csv", index=False)
    compare.to_csv(out / "budget_vs_top.csv")

    fx = data["fixtures"]
    print(f"league {args.league} GW{args.gw}: {n} managers | "
          f"{sum(f['started'] for f in fx)}/{len(fx)} matches started, "
          f"{sum(f['finished'] for f in fx)} finished")
    print("\nTEMPLATE\n", tmpl[["name", "pos", "club", "own_pct", "eo_pct", "gw_points"]]
          .round(1).to_string(index=False))
    print("\nBUDGET vs TOP MANAGERS\n", compare.to_string())
    print("\nTOP MANAGERS BY MEDIAN FINISH\n",
          top5[["manager", "seasons", "median_rank", "detail"]].to_string(index=False))
    print("\nBIGGEST RISKS STILL TO PLAY\n",
          risk[~risk.played].head(8)[["name", "club", "my_mult", "rival_avg_mult", "net"]]
          .round(2).to_string(index=False))
    print(f"\nTRANSFERS: {tx['active']} of {n} managers made {tx['total']} moves "
          f"({tx['quiet']} stood still); {tx['hits']} took hits costing "
          f"{tx['hit_points']} points; you moved: {tx['i_moved']}")
    for c in tx["chips"]:
        print(f"  chip: {c['manager']} played {c['chip']} ({c['transfers']} moves)")
    if not tx["flow"].empty:
        print(tx["flow"].head(8).to_string(index=False))
    print(f"\nshare of my score still to play: {remaining.get(args.entry, 0):.0f}%")
    for rival in budget[budget.entry != args.entry].head(2).entry:
        print(" ", head_to_head(df, args.entry, rival))


if __name__ == "__main__":
    main()
