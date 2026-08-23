"""Build an optimised GW1 squad for the 2026/27 FPL season.

Combines the live 2026/27 ``bootstrap-static`` / ``fixtures`` API with the
validated 2025/26 dataset in this repo, then selects the squad with a mixed
integer linear program (PuLP/CBC) rather than a greedy heuristic.

Division of labour between the two data sources:

* **Live API** supplies every player-level input for the new season: price,
  position, club, availability, set-piece orders, ownership, fixtures, and the
  carried-over 2025/26 totals (minutes, points, xGI, starts, clean sheets).
* **Repo dataset** (``player_gw_features.csv``, 29,747 player-gameweek rows)
  supplies the two things the API cannot: a split-half backtest that *earns*
  the blend weights used in the projection, and per-player defensive
  contribution, which the API does not carry across seasons.

Run::

    python3.12 scripts/build_gw1_squad.py
    python3.12 scripts/build_gw1_squad.py --offline   # reuse cached snapshot

Outputs ``outputs/gw1_2026_27/`` : ``squad.csv``, ``pool.csv``,
``results.json``, ``backtest.csv``.
"""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pulp
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
PROCESSED = REPO / "data" / "processed"
OUT = REPO / "outputs" / "gw1_2026_27"

BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"

POS = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

# Reliability shrinkage constant, in minutes. A player with exactly this many
# minutes gets a 50/50 blend of their own rate and the positional mean.
SHRINK_K = 900.0

# Fixture tilt. Rule 6: fixtures break ties, they do not drive picks.
FIXTURE_ALPHA = {"GKP": 0.07, "DEF": 0.07, "MID": 0.05, "FWD": 0.05}
GW1_FIXTURE_WEIGHT = 0.40  # rest of the weight goes on the mean of GW1-5

# Availability and role discounts.
MOVER_DISCOUNT = 0.90  # new club -> minutes are less certain
NO_HISTORY_DISCOUNT = 0.75
HORIZON = 5  # gameweeks of fixtures used for the tilt


# --------------------------------------------------------------------------
# 1. Data loading
# --------------------------------------------------------------------------
def _ssl_context() -> ssl.SSLContext:
    """Python.org builds ship without linked root certificates, so use certifi."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

def _download(url: str, dest: Path) -> dict:
    with urllib.request.urlopen(url, timeout=90, context=_ssl_context()) as resp:
        payload = json.load(resp)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload))
    return payload


def load_live_data(offline: bool = False, stamp: str | None = None) -> tuple[dict, list]:
    """Fetch the new-season API, caching a dated snapshot for reproducibility."""
    stamp = stamp or date.today().isoformat()
    bs_path = RAW / f"bootstrap_static_2026_27_{stamp}.json"
    fx_path = RAW / f"fixtures_2026_27_{stamp}.json"

    if offline or (bs_path.exists() and fx_path.exists()):
        candidates = sorted(RAW.glob("bootstrap_static_2026_27_*.json"))
        if not candidates:
            raise FileNotFoundError("No cached snapshot found; run without --offline.")
        bs_path = candidates[-1]
        fx_path = RAW / bs_path.name.replace("bootstrap_static", "fixtures")
        return json.loads(bs_path.read_text()), json.loads(fx_path.read_text())

    return _download(BOOTSTRAP_URL, bs_path), _download(FIXTURES_URL, fx_path)


def load_last_season() -> pd.DataFrame:
    """Per-gameweek 2025/26 rows from the repo's validated dataset."""
    cols = [
        "gameweek", "player_id", "web_name", "position_short", "team_name", "price",
        "total_points", "minutes", "starts", "expected_goal_involvements",
        "defensive_contribution",
    ]
    return pd.read_csv(PROCESSED / "player_gw_features.csv", usecols=cols)


def load_id_code_bridge() -> dict[int, int]:
    """2025/26 element id -> permanent player code (the cross-season key)."""
    old = json.loads((RAW / "bootstrap_static_smoke.json").read_text())
    return {e["id"]: e["code"] for e in old["elements"]}


# --------------------------------------------------------------------------
# 2. Backtest: earn the blend weights instead of assuming them
# --------------------------------------------------------------------------
@dataclass
class Backtest:
    table: pd.DataFrame
    weights: dict[str, float] = field(default_factory=dict)


def run_backtest(gw: pd.DataFrame, split: int = 19, min_minutes: int = 450) -> Backtest:
    """Split 2025/26 in half; ask which first-half signal predicts second-half scoring.

    Answers the only question that matters for a new-season projection: given a
    body of past minutes, what forecasts future scoring? Returns, per position,
    the weight to place on xGI relative to raw points-per-90.
    """
    def totals(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.groupby("player_id").agg(
            mins=("minutes", "sum"),
            pts=("total_points", "sum"),
            xgi=("expected_goal_involvements", "sum"),
        ).reset_index()

    h1, h2 = totals(gw[gw.gameweek <= split]), totals(gw[gw.gameweek > split])
    meta = gw.sort_values("gameweek").groupby("player_id").agg(
        name=("web_name", "last"), pos=("position_short", "last")).reset_index()

    m = h1.merge(h2, on="player_id", suffixes=("_h1", "_h2")).merge(meta, on="player_id")
    u = m[m.mins_h1 >= min_minutes].copy()
    u["pp90_h1"] = u.pts_h1 / u.mins_h1 * 90
    u["xgi90_h1"] = u.xgi_h1 / u.mins_h1 * 90
    u["mpg_h1"] = u.mins_h1 / split
    played_on = u[u.mins_h2 >= min_minutes].copy()
    played_on["pp90_h2"] = played_on.pts_h2 / played_on.mins_h2 * 90

    rows, weights = [], {}
    for pos in ("GKP", "DEF", "MID", "FWD"):
        a, b = u[u.pos == pos], played_on[played_on.pos == pos]
        if len(a) < 12:
            continue
        r_pp90_rate = spearmanr(b.pp90_h1, b.pp90_h2).statistic if len(b) >= 12 else np.nan
        r_xgi_rate = spearmanr(b.xgi90_h1, b.pp90_h2).statistic if len(b) >= 12 else np.nan
        rows.append({
            "position": pos, "n_rate": len(b), "n_total": len(a),
            "pp90_to_future_rate": r_pp90_rate,
            "xgi90_to_future_rate": r_xgi_rate,
            "minutes_to_future_points": spearmanr(a.mpg_h1, a.pts_h2).statistic,
            "points_to_future_points": spearmanr(a.pts_h1, a.pts_h2).statistic,
        })
        # xGI is meaningless for a goalkeeper; any correlation there is noise.
        if pos == "GKP":
            weights[pos] = 0.0
        else:
            x, p = max(r_xgi_rate, 0.0), max(r_pp90_rate, 0.0)
            weights[pos] = 0.5 if (x + p) == 0 else x / (x + p)

    return Backtest(table=pd.DataFrame(rows), weights=weights)


def validate_projection(gw: pd.DataFrame, backtest: Backtest, split: int = 19,
                        min_minutes: int = 450) -> pd.DataFrame:
    """Does the assembled projection beat the obvious baselines?

    Rebuilds the whole projection using only first-half data, then scores it
    against second-half points. This is the honest test of the method as a
    whole, rather than of its ingredients one at a time.
    """
    h1 = gw[gw.gameweek <= split].groupby("player_id").agg(
        mins=("minutes", "sum"), pts=("total_points", "sum"),
        xgi=("expected_goal_involvements", "sum"), starts=("starts", "sum"),
        dc=("defensive_contribution", "sum")).reset_index()
    h2 = gw[gw.gameweek > split].groupby("player_id")["total_points"].sum().rename("pts_h2")
    meta = gw.sort_values("gameweek").groupby("player_id").agg(
        pos=("position_short", "last"), price=("price", "last")).reset_index()

    d = h1.merge(h2, on="player_id").merge(meta, on="player_id")
    d = d[d.mins >= min_minutes].copy()
    d["pp90"] = d.pts / d.mins * 90
    d["xgi90"] = d.xgi / d.mins * 90
    d["dc90"] = d.dc / d.mins * 90
    dc_threshold = {"DEF": 10.0, "MID": 12.0, "FWD": 12.0, "GKP": np.inf}
    d["dc_pts90"] = [2.0 * min(1.0, v / dc_threshold.get(pos, np.inf))
                     for v, pos in zip(d.dc90, d.pos)]

    pos_rate = d.groupby("pos").pp90.mean().to_dict()
    dc_mean = d.groupby("pos").dc_pts90.mean().to_dict()
    implied = {}
    for pos in ("DEF", "MID", "FWD"):
        s = d[d.pos == pos]
        if len(s) >= 10:
            implied[pos] = np.polyfit(s.xgi90, s.pp90, 1)

    proj = []
    for _, r in d.iterrows():
        base = pos_rate.get(r.pos, 3.0)
        w_xgi = backtest.weights.get(r.pos, 0.5)
        if r.pos in implied:
            slope, intercept = implied[r.pos]
            imp = intercept + slope * r.xgi90
            if r.pos in ("DEF", "MID"):
                imp += r.dc_pts90 - dc_mean.get(r.pos, 0.0)
        else:
            imp = r.pp90
        own = w_xgi * imp + (1 - w_xgi) * r.pp90
        w = r.mins / (r.mins + SHRINK_K)
        rate = w * own + (1 - w) * base
        mps = min(90.0, r.mins / r.starts) if r.starts >= 3 else r.mins / split
        share = w * min(1.0, r.starts / split) + (1 - w) * 0.5
        proj.append(rate * (mps * share if r.starts >= 3 else mps) / 90.0)
    d["projection"] = proj

    methods = {
        "assembled projection": d.projection,
        "baseline: H1 total points": d.pts,
        "baseline: H1 points per 90": d.pp90,
        "baseline: H1 minutes": d.mins,
        "baseline: price": d.price,
    }
    rows = []
    for name, series in methods.items():
        series = pd.Series(np.asarray(series, dtype=float), index=d.index)
        by_pos = {
            f"rho_{pos}": round(spearmanr(series.loc[g.index], g.pts_h2).statistic, 3)
            for pos, g in d.groupby("pos")
        }
        rows.append({
            "method": name,
            "spearman_vs_h2_points": round(spearmanr(series, d.pts_h2).statistic, 3),
            "mean_h2_points_of_top20": round(d.loc[series.nlargest(20).index, "pts_h2"].mean(), 1),
            **by_pos,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 3. Build the player pool
# --------------------------------------------------------------------------
def verified_defensive_rates(gw: pd.DataFrame, bridge: dict[int, int],
                             api_minutes: dict[int, int]) -> tuple[pd.DataFrame, int]:
    """Defensive contribution per 90 from repo data, for codes we can trust.

    The repo's id->code bridge comes from a snapshot that has drifted for a
    handful of players. We keep a player only where repo minutes match the
    API's carried minutes exactly, which filters the bad mappings out.
    """
    agg = gw.groupby("player_id").agg(
        mins=("minutes", "sum"), dc=("defensive_contribution", "sum")).reset_index()
    agg["code"] = agg.player_id.map(bridge)
    agg = agg.dropna(subset=["code"])
    agg["code"] = agg["code"].astype(int)
    agg["api_mins"] = agg.code.map(api_minutes)
    ok = agg[(agg.api_mins.notna()) & (agg.api_mins == agg.mins) & (agg.mins > 0)].copy()
    rejected = int(len(agg[(agg.api_mins.notna()) & (agg.api_mins != agg.mins)]))
    ok["dc_per_90"] = ok.dc / ok.mins * 90
    return ok[["code", "dc_per_90"]], rejected


def fixture_difficulty(fixtures: list, horizon: int = HORIZON) -> pd.DataFrame:
    """Per team: GW1 difficulty and the mean over the opening `horizon` gameweeks."""
    rows = []
    for f in fixtures:
        if f["event"] is None or f["event"] > horizon:
            continue
        rows.append({"team": f["team_h"], "gw": f["event"], "fdr": f["team_h_difficulty"],
                     "opp": f["team_a"], "home": True})
        rows.append({"team": f["team_a"], "gw": f["event"], "fdr": f["team_a_difficulty"],
                     "opp": f["team_h"], "home": False})
    df = pd.DataFrame(rows)
    gw1 = df[df.gw == 1].set_index("team")
    out = df.groupby("team").agg(fdr_next5=("fdr", "mean"), games_next5=("gw", "count"))
    out["fdr_gw1"] = gw1["fdr"]
    out["gw1_opp"] = gw1["opp"]
    out["gw1_home"] = gw1["home"]
    return out.reset_index()


def build_pool(bootstrap: dict, fixtures: list, gw: pd.DataFrame,
               bridge: dict[int, int], backtest: Backtest) -> tuple[pd.DataFrame, dict]:
    teams = {t["id"]: t for t in bootstrap["teams"]}
    old = json.loads((RAW / "bootstrap_static_smoke.json").read_text())
    old_team = {t["id"]: t["name"] for t in old["teams"]}
    last_club = {e["code"]: old_team[e["team"]] for e in old["elements"]}

    api_minutes = {e["code"]: e["minutes"] for e in bootstrap["elements"]}
    dc_rates, dc_rejected = verified_defensive_rates(gw, bridge, api_minutes)
    dc_map = dict(zip(dc_rates.code, dc_rates.dc_per_90))
    fdr = fixture_difficulty(fixtures).set_index("team")

    rows = []
    for e in bootstrap["elements"]:
        pos, code, tid = POS[e["element_type"]], e["code"], e["team"]
        mins = float(e["minutes"])
        prior_club = last_club.get(code)
        if prior_club is None:
            history = "none"
        elif prior_club != teams[tid]["name"]:
            history = "mover"
        else:
            history = "full"
        # Players with a stale/absent carried record are treated as no-history.
        if mins == 0:
            history = "none"

        rows.append({
            "code": code, "player_id": e["id"], "name": e["web_name"],
            "full_name": f"{e['first_name']} {e['second_name']}".strip(),
            "position": pos, "club": teams[tid]["name"], "club_id": tid,
            "price": e["now_cost"] / 10.0,
            "status": e["status"],
            "chance": e["chance_of_playing_next_round"],
            "news": (e["news"] or "").strip(),
            "ownership": float(e["selected_by_percent"] or 0),
            "ep_next": float(e["ep_next"] or 0),
            "penalties_order": e["penalties_order"],
            "set_piece_order": e["corners_and_indirect_freekicks_order"],
            "prior_club": prior_club, "history": history,
            "ls_minutes": mins, "ls_points": float(e["total_points"]),
            "ls_starts": float(e["starts"]),
            "ls_xgi": float(e["expected_goal_involvements"] or 0),
            "ls_clean_sheets": float(e["clean_sheets"]),
            "dc_per_90": dc_map.get(code, np.nan),
            "team_strength": (teams[tid]["strength_overall_home"]
                              + teams[tid]["strength_overall_away"]) / 2.0,
            "fdr_gw1": fdr.at[tid, "fdr_gw1"], "fdr_next5": fdr.at[tid, "fdr_next5"],
            "gw1_opp": teams[fdr.at[tid, "gw1_opp"]]["short_name"],
            "gw1_home": bool(fdr.at[tid, "gw1_home"]),
        })

    pool = pd.DataFrame(rows)
    diagnostics = {
        "n_players": len(pool),
        "history_counts": pool.history.value_counts().to_dict(),
        "dc_codes_matched": len(dc_rates),
        "dc_codes_rejected_stale_mapping": dc_rejected,
    }
    return pool, diagnostics


# --------------------------------------------------------------------------
# 4. Project expected points per gameweek
# --------------------------------------------------------------------------
def project(pool: pd.DataFrame, backtest: Backtest) -> pd.DataFrame:
    p = pool.copy()
    p["pp90"] = np.where(p.ls_minutes > 0, p.ls_points / p.ls_minutes.replace(0, np.nan) * 90, np.nan)
    p["xgi90"] = np.where(p.ls_minutes > 0, p.ls_xgi / p.ls_minutes.replace(0, np.nan) * 90, np.nan)

    # Within each position, learn how xGI per 90 converts into points per 90,
    # fitted on players with a full season's worth of evidence.
    p["xgi_implied_pp90"] = np.nan
    fits = {}
    for pos in ("DEF", "MID", "FWD"):
        s = p[(p.position == pos) & (p.ls_minutes >= 900)]
        if len(s) < 10:
            continue
        slope, intercept = np.polyfit(s.xgi90, s.pp90, 1)
        fits[pos] = {"slope": float(slope), "intercept": float(intercept), "n": int(len(s))}
        idx = p.position == pos
        p.loc[idx, "xgi_implied_pp90"] = intercept + slope * p.loc[idx, "xgi90"]

    # Defensive contribution is a real points source the API does not carry.
    # Convert it into points per 90 using the live scoring thresholds.
    dc_threshold = {"DEF": 10.0, "MID": 12.0, "FWD": 12.0, "GKP": np.inf}
    p["dc_points_per_90"] = [
        0.0 if np.isnan(d) else 2.0 * min(1.0, d / dc_threshold.get(pos, np.inf))
        for d, pos in zip(p.dc_per_90, p.position)
    ]
    # Only the deviation from the positional average is new information. A
    # player's own points-per-90 already contains the defensive points he
    # earned, so adding the raw figure back would count it twice.
    dc_pos_mean = (p[(p.ls_minutes >= 900) & p.dc_per_90.notna()]
                   .groupby("position").dc_points_per_90.mean().to_dict())

    pos_mean_rate = (p[p.ls_minutes >= 900].groupby("position").pp90.mean().to_dict())
    reliability = p.ls_minutes / (p.ls_minutes + SHRINK_K)

    blended = []
    for _, r in p.iterrows():
        pos = r.position
        base = pos_mean_rate.get(pos, 3.0)
        if r.ls_minutes <= 0 or np.isnan(r.pp90):
            blended.append(base * NO_HISTORY_DISCOUNT)
            continue
        w_xgi = backtest.weights.get(pos, 0.5)
        implied = r.xgi_implied_pp90 if not np.isnan(r.xgi_implied_pp90) else r.pp90
        if pos in ("DEF", "MID") and not np.isnan(r.dc_per_90):
            # The xGI model is blind to defensive work, so correct only that
            # component, and only by how far the player sits from average.
            implied = implied + (r.dc_points_per_90 - dc_pos_mean.get(pos, 0.0))
        own = w_xgi * implied + (1 - w_xgi) * r.pp90
        w = r.ls_minutes / (r.ls_minutes + SHRINK_K)
        blended.append(w * own + (1 - w) * base)
    p["rate_per_90"] = blended
    p["reliability"] = reliability
    p.attrs["dc_pos_mean"] = dc_pos_mean

    # A goalkeeper's scoring rate proved unpredictable in the backtest, so the
    # only honest differentiator is the quality of the defence in front of him.
    gk = p.position == "GKP"
    strength_mult = 0.85 + 0.10 * (p.team_strength - p.team_strength.min())
    p.loc[gk, "rate_per_90"] = pos_mean_rate.get("GKP", 3.0) * strength_mult[gk]

    # Minutes answer two separate questions, and the data speaks to each one
    # on its own: when a player starts, how long does he stay on (his role),
    # and how often does he start (fitness and selection). A season lost to
    # injury damages the second without saying anything about the first, so
    # projecting straight from total minutes buries a fit player forever.
    starts = p.ls_starts.fillna(0)
    minutes_per_start = np.where(
        starts >= 3, np.clip(p.ls_minutes / starts.replace(0, np.nan), 0, 90), np.nan)
    own_start_share = np.clip(starts / 38.0, 0, 1)
    # Price is the market's own forecast of a player's role, and before a ball
    # is kicked it is the only forward-looking minutes signal we have.
    price_pct = p.groupby("position").price.rank(pct=True)
    prior_start_share = 0.20 + 0.60 * price_pct
    w_s = p.ls_minutes / (p.ls_minutes + SHRINK_K)
    start_share = w_s * own_start_share + (1 - w_s) * prior_start_share
    fallback = np.clip(p.ls_minutes / 38.0, 0, 90)

    p["minutes_per_start"] = minutes_per_start
    p["start_share"] = start_share
    p["proj_minutes"] = np.where(
        np.isnan(minutes_per_start), fallback, minutes_per_start * start_share)

    role_mult = np.where(p.history == "mover", MOVER_DISCOUNT, 1.0)
    avail = np.where(p.status == "a", 1.0,
                     np.where(p.status == "d", (p.chance.fillna(75) / 100.0), 0.0))
    p["available"] = p.status.isin(["a", "d"])
    p["proj_minutes"] = p.proj_minutes * role_mult * avail

    # No-history players: price is the market's forecast of their role.
    no_hist = p.history == "none"
    price_rank = p.groupby("position").price.rank(pct=True)
    p.loc[no_hist, "proj_minutes"] = (
        90.0 * (0.35 + 0.45 * price_rank[no_hist]) * NO_HISTORY_DISCOUNT
        * avail[no_hist.to_numpy()]
    )

    alpha = p.position.map(FIXTURE_ALPHA).astype(float)
    fdr_blend = GW1_FIXTURE_WEIGHT * p.fdr_gw1 + (1 - GW1_FIXTURE_WEIGHT) * p.fdr_next5
    p["fixture_mult"] = 1 + alpha * (3.0 - fdr_blend)
    p["fdr_blend"] = fdr_blend

    p["xp"] = p.rate_per_90 * p.proj_minutes / 90.0 * p.fixture_mult
    p["xp_per_million"] = p.xp / p.price
    p.attrs["xgi_fits"] = fits
    p.attrs["pos_mean_rate"] = pos_mean_rate
    return p


# --------------------------------------------------------------------------
# 5. Optimise with a mixed integer linear program
# --------------------------------------------------------------------------
@dataclass
class Solution:
    squad: pd.DataFrame
    objective: float
    status: str
    label: str


def optimise(pool: pd.DataFrame, bootstrap: dict, *, objective_col: str = "xp",
             bench_weight: float = 0.12, allow_unknown_starters: bool = False,
             label: str = "primary", forced_out: list[int] | None = None,
             forced_in: list[int] | None = None,
             bench_plan: list[dict] | None = None) -> Solution:
    """Select 15 players, a starting XI, and a captain by maximising expected points.

    Formation, budget, club limits and squad size all come from the API's own
    game settings, so the program stays correct if the rules ever change.
    """
    gs = bootstrap["game_settings"]
    budget = gs["squad_total_spend"] / 10.0
    club_limit = gs["squad_team_limit"]
    types = {t["id"]: t for t in bootstrap["element_types"]}
    squad_need = {POS[t["id"]]: t["squad_select"] for t in types.values()}
    play_min = {POS[t["id"]]: t["squad_min_play"] for t in types.values()}
    play_max = {POS[t["id"]]: t["squad_max_play"] for t in types.values()}

    p = pool[pool.available].copy()
    if forced_out:
        p = p[~p.code.isin(forced_out)]
    p = p.reset_index(drop=True)
    idx = list(p.index)

    prob = pulp.LpProblem("fpl_gw1_squad", pulp.LpMaximize)
    squad = pulp.LpVariable.dicts("squad", idx, cat="Binary")
    start = pulp.LpVariable.dicts("start", idx, cat="Binary")
    capt = pulp.LpVariable.dicts("capt", idx, cat="Binary")

    ep = p[objective_col].fillna(0).to_dict()
    prob += pulp.lpSum(
        ep[i] * start[i] + ep[i] * capt[i] + bench_weight * ep[i] * (squad[i] - start[i])
        for i in idx
    )

    prob += pulp.lpSum(squad[i] for i in idx) == sum(squad_need.values())
    prob += pulp.lpSum(p.at[i, "price"] * squad[i] for i in idx) <= budget
    prob += pulp.lpSum(start[i] for i in idx) == 11
    prob += pulp.lpSum(capt[i] for i in idx) == 1

    for pos, need in squad_need.items():
        members = [i for i in idx if p.at[i, "position"] == pos]
        prob += pulp.lpSum(squad[i] for i in members) == need
        prob += pulp.lpSum(start[i] for i in members) >= play_min[pos]
        prob += pulp.lpSum(start[i] for i in members) <= play_max[pos]

    for club in p.club_id.unique():
        members = [i for i in idx if p.at[i, "club_id"] == club]
        prob += pulp.lpSum(squad[i] for i in members) <= club_limit

    for code in forced_in or []:
        members = [i for i in idx if p.at[i, "code"] == code]
        if not members:
            raise ValueError(f"forced_in player {code} is not in the available pool")
        prob += pulp.lpSum(squad[i] for i in members) == 1

    # Optional bench-fodder strategy: pin some bench slots to a price, so the
    # money saved there can be spent on the eleven players who actually score.
    # Each rule is {"price": 4.0, "count": 2, "min_ownership": 10.0, "exact": True}.
    for rule in bench_plan or []:
        members = [
            i for i in idx
            if abs(p.at[i, "price"] - rule["price"]) < 1e-6
            and p.at[i, "ownership"] >= rule.get("min_ownership", 0.0)
            and (rule.get("position") is None or p.at[i, "position"] == rule["position"])
        ]
        if not members:
            raise ValueError(f"no players satisfy bench rule {rule}")
        on_bench = pulp.lpSum(squad[i] - start[i] for i in members)
        if rule.get("exact", True):
            prob += on_bench == rule["count"]
        else:
            prob += on_bench >= rule["count"]

    for i in idx:
        prob += start[i] <= squad[i]
        prob += capt[i] <= start[i]
        # Rule 8: a player with no Premier League record is bench cover only.
        if not allow_unknown_starters and p.at[i, "history"] == "none":
            prob += start[i] == 0
            prob += squad[i] * p.at[i, "price"] <= 5.0

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    chosen = p.loc[[i for i in idx if squad[i].value() > 0.5]].copy()
    chosen["is_starter"] = [start[i].value() > 0.5 for i in chosen.index]
    chosen["is_captain"] = [capt[i].value() > 0.5 for i in chosen.index]
    chosen = chosen.sort_values(
        ["is_starter", "position", "xp"],
        ascending=[False, True, False],
        key=lambda s: s.map({"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}) if s.name == "position" else s,
    )
    return Solution(squad=chosen, objective=float(pulp.value(prob.objective)),
                    status=pulp.LpStatus[status], label=label)


def bench_order(squad: pd.DataFrame) -> pd.DataFrame:
    bench = squad[~squad.is_starter].copy()
    gk = bench[bench.position == "GKP"]
    outfield = bench[bench.position != "GKP"].sort_values("xp", ascending=False)
    return pd.concat([outfield, gk])


# --------------------------------------------------------------------------
# 6. Sensitivity analyses
# --------------------------------------------------------------------------
def run_sensitivities(pool: pd.DataFrame, bootstrap: dict, primary: Solution) -> pd.DataFrame:
    variants = [
        ("no_new_player_rule", dict(allow_unknown_starters=True)),
        ("fpl_own_ep_next", dict(objective_col="ep_next")),
        ("ignore_fixtures", dict(objective_col="xp_no_fixture")),
        ("bench_weight_zero", dict(bench_weight=0.0)),
    ]
    base = set(primary.squad.code)
    rows = []
    for name, kwargs in variants:
        work = pool.copy()
        if kwargs.get("objective_col") == "xp_no_fixture":
            work["xp_no_fixture"] = work.rate_per_90 * work.proj_minutes / 90.0
        sol = optimise(work, bootstrap, label=name, **kwargs)
        overlap = len(base & set(sol.squad.code))
        cap = sol.squad[sol.squad.is_captain]
        rows.append({
            "variant": name, "status": sol.status,
            "squad_overlap_with_primary": overlap,
            "changed": 15 - overlap,
            "captain": cap.name.iloc[0] if len(cap) else "-",
            "spend": round(float(sol.squad.price.sum()), 1),
            "objective": round(sol.objective, 2),
        })
    return pd.DataFrame(rows)


def cheaper_rival_test(pool: pd.DataFrame, solution: Solution) -> pd.DataFrame:
    """For each starter, the best cheaper same-position player left on the board."""
    picked = set(solution.squad.code)
    rows = []
    for _, r in solution.squad[solution.squad.is_starter].iterrows():
        rivals = pool[(pool.position == r.position) & (pool.price < r.price)
                      & (~pool.code.isin(picked)) & (pool.available)
                      & (pool.history != "none")]
        if rivals.empty:
            continue
        best = rivals.loc[rivals.xp.idxmax()]
        rows.append({
            "starter": r["name"], "position": r.position, "price": r.price, "xp": round(r.xp, 2),
            "best_cheaper": best["name"], "rival_price": best.price, "rival_xp": round(best.xp, 2),
            "xp_given_up": round(r.xp - best.xp, 2), "saving": round(r.price - best.price, 1),
        })
    return pd.DataFrame(rows).sort_values("xp_given_up")


# --------------------------------------------------------------------------
# 7. Entry point
# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true", help="reuse the cached snapshot")
    ap.add_argument("--budget-check", action="store_true", help="print the LP status only")
    args = ap.parse_args()

    bootstrap, fixtures = load_live_data(offline=args.offline)
    gw = load_last_season()
    bridge = load_id_code_bridge()

    backtest = run_backtest(gw)
    validation = validate_projection(gw, backtest)
    # Weights learned on GW1-12 against GW13-24, then scored on GW25-38, so the
    # tuning never sees the window it is judged on.
    oos_weights = run_backtest(gw[gw.gameweek <= 24], split=12, min_minutes=300)
    validation_oos = validate_projection(gw, oos_weights, split=24)

    pool, diagnostics = build_pool(bootstrap, fixtures, gw, bridge, backtest)
    pool = project(pool, backtest)

    primary = optimise(pool, bootstrap)
    sens = run_sensitivities(pool, bootstrap, primary)
    rivals = cheaper_rival_test(pool, primary)

    OUT.mkdir(parents=True, exist_ok=True)
    primary.squad.to_csv(OUT / "squad.csv", index=False)
    pool.to_csv(OUT / "pool.csv", index=False)
    backtest.table.to_csv(OUT / "backtest.csv", index=False)
    validation.to_csv(OUT / "validation.csv", index=False)
    validation_oos.to_csv(OUT / "validation_out_of_sample.csv", index=False)
    sens.to_csv(OUT / "sensitivity.csv", index=False)
    rivals.to_csv(OUT / "cheaper_rival_test.csv", index=False)

    results = {
        "generated": date.today().isoformat(),
        "diagnostics": diagnostics,
        "backtest_weights": backtest.weights,
        "backtest": backtest.table.to_dict("records"),
        "validation": validation.to_dict("records"),
        "validation_out_of_sample": validation_oos.to_dict("records"),
        "cheaper_rival_test": rivals.to_dict("records"),
        "xgi_fits": pool.attrs.get("xgi_fits", {}),
        "pos_mean_rate": pool.attrs.get("pos_mean_rate", {}),
        "solver_status": primary.status,
        "objective": primary.objective,
        "spend": float(primary.squad.price.sum()),
        "squad": primary.squad.to_dict("records"),
        "sensitivity": sens.to_dict("records"),
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))

    xi = primary.squad[primary.squad.is_starter]
    bench = bench_order(primary.squad)
    print(f"solver: {primary.status} | spend £{primary.squad.price.sum():.1f}m "
          f"| XI xP {xi.xp.sum():.1f}")
    for _, r in primary.squad.iterrows():
        tag = "C" if r.is_captain else ("XI" if r.is_starter else "b")
        print(f"  {tag:>2} {r.position} {r['name']:<16} {r.club:<15} "
              f"£{r.price:>4.1f}m  xP {r.xp:5.2f}  {r.history}")
    print("\nbench order:", " > ".join(bench["name"].tolist()))
    print("\nvalidation (in-sample split):\n",
          validation[["method", "spearman_vs_h2_points", "mean_h2_points_of_top20"]].to_string(index=False))
    print("\nvalidation (out-of-sample):\n",
          validation_oos[["method", "spearman_vs_h2_points", "mean_h2_points_of_top20"]].to_string(index=False))
    print("\nsensitivity:\n", sens.to_string(index=False))


if __name__ == "__main__":
    main()
