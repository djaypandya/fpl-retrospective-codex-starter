"""Walk-forward, leak-free panel for the 'do expected stats add value?' analysis.

For each player-gameweek row t (the moment you decide going INTO gameweek t, knowing
only gameweeks < t), we pair trailing predictors (the *_prior rolling features, which
use only gameweeks strictly before t) with the player's forward mean points over the
next N played gameweeks [t, t+N-1]. Fixture difficulty for the upcoming window is
joined from fixture_difficulty.csv. Nothing from gameweek t or later leaks into a predictor.
"""
import os
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
D = pd.read_csv(os.path.join(REPO, "data/processed/player_gw_features.csv"))
F = pd.read_csv(os.path.join(REPO, "data/processed/fixture_difficulty.csv"))


def build(N=4, gate=45, min_prior=3, min_fwd=2):
    """Return one row per eligible (decision-GW t, player).

    gate      : minutes that count as 'played' (both for eligibility and the forward target)
    min_prior : require this many prior gameweeks so the trailing window is real
    min_fwd   : require at least this many *played* gameweeks in the forward window
    """
    d = D.sort_values(["player_id", "gameweek"]).copy()
    recs = []
    for pid, g in d.groupby("player_id"):
        g = g.set_index("gameweek")
        pts, mins = g["total_points"], g["minutes"]
        for t in g.index:
            row = g.loc[t]
            if row["prior_gameweeks_count"] < min_prior:
                continue
            fwd_gws = [t + k for k in range(N) if (t + k) in g.index]
            played = [w for w in fwd_gws if mins.get(w, 0) >= gate]
            if len(played) < min_fwd:
                continue
            recs.append((
                t, pid, row["position_short"], row["team_short_name"],
                pts.loc[played].mean(), len(played),
                row["total_points_roll3_mean_prior"], row["total_points_roll5_mean_prior"],
                row["expected_goal_involvements_roll3_mean_prior"],
                row["expected_goals_roll3_mean_prior"], row["expected_assists_roll3_mean_prior"],
                row["expected_goals_conceded_roll3_mean_prior"],
                row["ict_index_roll3_mean_prior"], row["threat_roll3_mean_prior"],
                row["creativity_roll3_mean_prior"], row["influence_roll3_mean_prior"],
                row["minutes_roll3_mean_prior"],
            ))
    p = pd.DataFrame(recs, columns=[
        "t", "pid", "pos", "team", "fwd", "nfwd", "form3", "form5", "xgi", "xg", "xa",
        "xgc", "ict", "threat", "creat", "infl", "min3"])
    p = p[p["min3"] >= gate].copy()  # eligibility: likely starter by trailing minutes
    fcol = f"fpl_difficulty_mean_next{3 if N <= 5 else 5}"
    fj = F[["team_short_name", "gameweek", fcol]].rename(
        columns={"team_short_name": "team", "gameweek": "t", fcol: "fdr"})
    p = p.merge(fj, on=["team", "t"], how="left")
    return p
