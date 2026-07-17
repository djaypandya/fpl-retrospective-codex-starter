#!/usr/bin/env python3
"""Reconcile the FPL strategy simulation with the transfer replay.

This script recomputes the common replay yardstick and the notebook's
availability/form collapse. It also records, but does not mix, the separately
defined season-simulation results reported by ``fpl_decision_story.ipynb``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

REPLAY_PATH = REPO_ROOT / "analysis/transfer_rule_replay_bank/replay_bank_results.csv"
TRANSFERS_PATH = REPO_ROOT / "data/raw/managers/transfers/manager_816200.json"
FEATURES_PATH = REPO_ROOT / "data/processed/player_gw_features.csv"
TIMELINE_PATH = REPO_ROOT / "data/processed/my_gameweek_timeline.csv"
SQUAD_PATH = REPO_ROOT / "data/processed/my_squad_gameweek.csv"
OUTPUT_PATH = HERE / "reconciliation_results.csv"
REPLAY_DETAIL_OUTPUT = HERE / "replay_reconciliation_detail.csv"

CHIP_GWS = {6, 13, 23, 34}
SEASON_END_GW = 38
NO_CANDIDATE = "NO_CANDIDATE"

EXPECTED_REPLAY_ROWS = 46
EXPECTED_SCORED_ROWS = 45
EXPECTED_HUMAN_TOTAL = 784
EXPECTED_RULE_TOTAL = 587
EXPECTED_ALL_FORM_RHO = 0.79
EXPECTED_SCREENED_FORM_RHO = 0.20
EXPECTED_ALL_BIN_MEANS = [0.46, 0.58, 2.15, 8.02, 11.93]
EXPECTED_SCREENED_BIN_MEANS = [9.21, 10.41, 11.30, 12.10, 13.54]


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    """Raise a useful error when a source table has changed."""
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def load_transfers() -> pd.DataFrame:
    """Load manager transfers in the same stable order as the bank replay."""
    transfers = pd.DataFrame(json.loads(TRANSFERS_PATH.read_text()))
    require_columns(
        transfers,
        {"element_in", "element_out", "entry", "event", "time"},
        "manager transfers",
    )
    transfers["time"] = pd.to_datetime(transfers["time"], utc=True)
    transfers = transfers.sort_values(["event", "time"], kind="stable").reset_index(
        drop=True
    )
    return transfers


def hold_end_gw(
    transfers: pd.DataFrame, row_index: int, incoming_player_id: int
) -> int:
    """Return the last GW of the actual incoming player's holding window."""
    later_sales = transfers.iloc[row_index + 1 :]
    later_sales = later_sales.loc[
        later_sales["element_out"].astype(int).eq(incoming_player_id)
    ]
    if later_sales.empty:
        return SEASON_END_GW
    return int(later_sales.iloc[0]["event"]) - 1


def points_over_window(
    points: pd.Series, player_id: int, start_gw: int, end_gw: int
) -> int:
    """Sum player points on an inclusive GW window, filling absent rows with zero."""
    index = pd.MultiIndex.from_product(
        [[player_id], range(start_gw, end_gw + 1)],
        names=["player_id", "gameweek"],
    )
    return int(points.reindex(index).fillna(0).sum())


def reconstruct_replay_yardstick(
    features: pd.DataFrame,
    transfers: pd.DataFrame,
    timeline: pd.DataFrame,
    squad: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Rebuild the locked replay and add an outgoing-player hold baseline.

    This is deliberately independent of the prior replay results CSV. It uses
    the same locked rule: same position, affordable at outgoing sale value plus
    the bank entering the deadline, at least 180 minutes over the prior four
    GWs, then highest prior-four-GW points. Ties use minutes, lower price, then
    player ID. Players already in the pre-transfer squad are excluded.
    """
    require_columns(
        features,
        {
            "gameweek",
            "player_id",
            "web_name",
            "position_short",
            "price",
            "total_points",
            "minutes",
        },
        "player GW features",
    )
    require_columns(timeline, {"event", "bank_value"}, "manager timeline")
    require_columns(squad, {"event", "element"}, "manager squad")
    assert not features.duplicated(["player_id", "gameweek"]).any()

    points = features.set_index(["player_id", "gameweek"])["total_points"]
    player_names = features.groupby("player_id")["web_name"].last().to_dict()
    player_positions = (
        features.groupby("player_id")["position_short"].last().to_dict()
    )
    bank_by_gw = timeline.set_index("event")["bank_value"]
    analyzed = transfers.loc[~transfers["event"].isin(CHIP_GWS)]
    assert len(analyzed) == EXPECTED_REPLAY_ROWS

    rows: list[dict[str, object]] = []
    for transfer_index, transfer in analyzed.iterrows():
        transfer_gw = int(transfer["event"])
        outgoing_id = int(transfer["element_out"])
        incoming_id = int(transfer["element_in"])
        end_gw = hold_end_gw(transfers, transfer_index, incoming_id)

        event_moves = analyzed.loc[analyzed["event"].eq(transfer_gw)]
        pre_squad = set(
            squad.loc[squad["event"].eq(transfer_gw), "element"].astype(int)
        )
        pre_squad.difference_update(event_moves["element_in"].astype(int))
        pre_squad.update(event_moves["element_out"].astype(int))

        prior_bank = float(bank_by_gw.loc[transfer_gw - 1])
        budget = float(transfer["element_out_cost"]) / 10.0 + prior_bank
        current = features.loc[features["gameweek"].eq(transfer_gw)].copy()
        history = (
            features.loc[
                features["gameweek"].between(transfer_gw - 4, transfer_gw - 1)
            ]
            .groupby("player_id", as_index=False)
            .agg(form_points_4gw=("total_points", "sum"), minutes_4gw=("minutes", "sum"))
        )
        candidates = current.merge(history, on="player_id", how="left")
        candidates[["form_points_4gw", "minutes_4gw"]] = candidates[
            ["form_points_4gw", "minutes_4gw"]
        ].fillna(0)
        candidates = candidates.loc[
            candidates["position_short"].eq(player_positions[outgoing_id])
            & candidates["price"].le(budget)
            & candidates["minutes_4gw"].ge(180)
            & ~candidates["player_id"].isin(pre_squad)
        ].sort_values(
            ["form_points_4gw", "minutes_4gw", "price", "player_id"],
            ascending=[False, False, True, True],
        )

        incoming_current = current.loc[current["player_id"].eq(incoming_id)].iloc[0]
        incoming_history = history.loc[history["player_id"].eq(incoming_id)]
        incoming_minutes = (
            0.0
            if incoming_history.empty
            else float(incoming_history.iloc[0]["minutes_4gw"])
        )
        actual_in_pool = bool(
            float(incoming_current["price"]) <= budget and incoming_minutes >= 180
        )

        if candidates.empty:
            rule_pick_id: int | None = None
            rule_pick_name = NO_CANDIDATE
            rule_points = np.nan
            rule_form = np.nan
            rule_minutes = np.nan
            rule_price = np.nan
        else:
            rule_pick = candidates.iloc[0]
            rule_pick_id = int(rule_pick["player_id"])
            rule_pick_name = str(rule_pick["web_name"])
            rule_points = points_over_window(
                points, rule_pick_id, transfer_gw, end_gw
            )
            rule_form = float(rule_pick["form_points_4gw"])
            rule_minutes = float(rule_pick["minutes_4gw"])
            rule_price = float(rule_pick["price"])

        rows.append(
            {
                "gw": transfer_gw,
                "out_player_id": outgoing_id,
                "out_name": str(player_names[outgoing_id]),
                "actual_in_player_id": incoming_id,
                "actual_in_name": str(player_names[incoming_id]),
                "hold_end_gw": end_gw,
                "bank_before": prior_bank,
                "out_sale_price": float(transfer["element_out_cost"]) / 10.0,
                "budget_cap": budget,
                "actual_in_pool": actual_in_pool,
                "rule_pick_player_id": rule_pick_id,
                "rule_pick_name": rule_pick_name,
                "rule_form_points_4gw": rule_form,
                "rule_minutes_4gw": rule_minutes,
                "rule_price": rule_price,
                "actual_pts": points_over_window(
                    points, incoming_id, transfer_gw, end_gw
                ),
                "rule_pts": rule_points,
                "nothing_pts": points_over_window(
                    points, outgoing_id, transfer_gw, end_gw
                ),
            }
        )

    detail = pd.DataFrame(rows)
    scored = detail.loc[detail["rule_pick_name"].ne(NO_CANDIDATE)].copy()

    assert len(detail) == EXPECTED_REPLAY_ROWS
    assert len(scored) == EXPECTED_SCORED_ROWS
    assert int(scored["actual_pts"].sum()) == EXPECTED_HUMAN_TOTAL
    assert int(scored["rule_pts"].sum()) == EXPECTED_RULE_TOTAL
    assert int(scored["nothing_pts"].sum()) == 534
    assert int((~detail["actual_in_pool"]).sum()) == 11

    if REPLAY_PATH.exists():
        locked = pd.read_csv(REPLAY_PATH)
        require_columns(
            locked,
            {"actual_pts", "rule_pts", "rule_pick_name", "actual_in_pool"},
            "prior bank replay",
        )
        locked_scored = locked.loc[locked["rule_pick_name"].ne(NO_CANDIDATE)]
        assert len(locked) == len(detail)
        assert int(locked_scored["actual_pts"].sum()) == int(
            scored["actual_pts"].sum()
        )
        assert int(locked_scored["rule_pts"].sum()) == int(
            scored["rule_pts"].sum()
        )

    totals = {
        "sample_n": float(len(scored)),
        "human_total": float(scored["actual_pts"].sum()),
        "human_mean": float(scored["actual_pts"].mean()),
        "rule_total": float(scored["rule_pts"].sum()),
        "rule_mean": float(scored["rule_pts"].mean()),
        "nothing_total": float(scored["nothing_pts"].sum()),
        "nothing_mean": float(scored["nothing_pts"].mean()),
    }
    totals["human_minus_rule"] = totals["human_total"] - totals["rule_total"]
    totals["rule_minus_nothing"] = totals["rule_total"] - totals["nothing_total"]
    totals["human_minus_nothing"] = totals["human_total"] - totals["nothing_total"]
    return detail, totals


def build_form_panel(features: pd.DataFrame) -> pd.DataFrame:
    """Recreate the engine's complete next-four-GW player-decision panel.

    For decision GW t, recent form is points in t-3 through t, while the target
    is points in t+1 through t+4. Rows must exist in all eight GWs. The decision
    range is t=4..34, matching ``v0_engine.build_panel``.
    """
    points = features.pivot(
        index="player_id", columns="gameweek", values="total_points"
    )
    minutes = features.pivot(
        index="player_id", columns="gameweek", values="minutes"
    )
    rows: list[pd.DataFrame] = []

    for decision_gw in range(4, 35):
        player_ids = features.loc[
            features["gameweek"].eq(decision_gw), "player_id"
        ]
        history_gws = range(decision_gw - 3, decision_gw + 1)
        target_gws = range(decision_gw + 1, decision_gw + 5)
        history_points = points.reindex(index=player_ids, columns=history_gws)
        history_minutes = minutes.reindex(index=player_ids, columns=history_gws)
        target_points = points.reindex(index=player_ids, columns=target_gws)
        complete = history_points.notna().all(axis=1) & target_points.notna().all(
            axis=1
        )
        rows.append(
            pd.DataFrame(
                {
                    "decision_gw": decision_gw,
                    "player_id": complete.index[complete].to_numpy(),
                    "recent_points_4gw": history_points.loc[complete].sum(
                        axis=1
                    ).to_numpy(),
                    "recent_minutes_4gw": history_minutes.loc[complete].sum(
                        axis=1
                    ).to_numpy(),
                    "next_points_4gw": target_points.loc[complete].sum(
                        axis=1
                    ).to_numpy(),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def equal_count_form_means(panel: pd.DataFrame) -> list[float]:
    """Return five equal-count form-bin means using the engine's stable tie rule."""
    ranked = panel["recent_points_4gw"].rank(method="first")
    bins = pd.qcut(ranked, 5, labels=False)
    return panel.assign(form_bin=bins).groupby("form_bin")["next_points_4gw"].mean().tolist()


def recompute_form_collapse(features: pd.DataFrame) -> dict[str, object]:
    """Recompute the 0.79 to 0.20 availability collapse from processed data."""
    panel = build_form_panel(features)
    screened = panel.loc[panel["recent_minutes_4gw"].ge(180)].copy()
    all_rho = float(
        spearmanr(panel["recent_points_4gw"], panel["next_points_4gw"]).statistic
    )
    screened_rho = float(
        spearmanr(
            screened["recent_points_4gw"], screened["next_points_4gw"]
        ).statistic
    )
    all_means = equal_count_form_means(panel)
    screened_means = equal_count_form_means(screened)

    assert round(all_rho, 2) == EXPECTED_ALL_FORM_RHO
    assert round(screened_rho, 2) == EXPECTED_SCREENED_FORM_RHO
    assert np.allclose(all_means, EXPECTED_ALL_BIN_MEANS, atol=0.01)
    assert np.allclose(screened_means, EXPECTED_SCREENED_BIN_MEANS, atol=0.02)

    return {
        "all_n": len(panel),
        "all_rho": all_rho,
        "all_bin_means": all_means,
        "screened_n": len(screened),
        "screened_rho": screened_rho,
        "screened_bin_means": screened_means,
        "screen": "recent_minutes_4gw >= 180",
    }


def result_row(
    section: str,
    metric: str,
    value: object,
    unit: str,
    sample_n: object,
    source: str,
    status: str,
    definition: str,
) -> dict[str, object]:
    return {
        "section": section,
        "metric": metric,
        "value": value,
        "unit": unit,
        "sample_n": sample_n,
        "source": source,
        "status": status,
        "definition": definition,
    }


def build_results(
    replay: pd.DataFrame,
    replay_totals: dict[str, float],
    form: dict[str, object],
) -> pd.DataFrame:
    """Build a long, traceable results table for charts and writeups."""
    replay_source = "independently reconstructed from raw transfers + timeline + squad + player_gw_features.csv"
    replay_definition = (
        "45 candidate-available non-chip transfers; inclusive actual incoming holding window [T, hold_end]"
    )
    rows = [
        result_row("replay", "human_total", int(replay_totals["human_total"]), "points", 45, replay_source, "recomputed", replay_definition),
        result_row("replay", "human_mean", replay_totals["human_mean"], "points per transfer window", 45, replay_source, "recomputed", replay_definition),
        result_row("replay", "simple_rule_total", int(replay_totals["rule_total"]), "points", 45, replay_source, "recomputed", replay_definition),
        result_row("replay", "simple_rule_mean", replay_totals["rule_mean"], "points per transfer window", 45, replay_source, "recomputed", replay_definition),
        result_row("replay", "do_nothing_total", int(replay_totals["nothing_total"]), "points", 45, replay_source, "recomputed", replay_definition + "; outgoing player's points over the same window"),
        result_row("replay", "do_nothing_mean", replay_totals["nothing_mean"], "points per transfer window", 45, replay_source, "recomputed", replay_definition + "; outgoing player's points over the same window"),
        result_row("replay", "human_minus_rule", int(replay_totals["human_minus_rule"]), "points", 45, replay_source, "recomputed", "human total minus simple-rule total on the replay metric"),
        result_row("replay", "rule_minus_nothing", int(replay_totals["rule_minus_nothing"]), "points", 45, replay_source, "recomputed", "simple-rule total minus outgoing-player hold total on the replay metric"),
        result_row("replay", "human_minus_nothing", int(replay_totals["human_minus_nothing"]), "points", 45, replay_source, "recomputed", "human total minus outgoing-player hold total on the replay metric"),
        result_row("replay", "actual_buys_outside_rule_pool", int((~replay["actual_in_pool"].astype(bool)).sum()), "transfers", 46, replay_source, "recomputed", "actual incoming player failed at least one locked candidate filter"),
    ]

    form_source = "recomputed from data/processed/player_gw_features.csv"
    form_definition = "Spearman(recent 4-GW points, realized next-4-GW points), decision GWs 4..34"
    rows.extend(
        [
            result_row("form_collapse", "all_players_spearman", form["all_rho"], "Spearman rho", form["all_n"], form_source, "recomputed", form_definition),
            result_row("form_collapse", "minutes_screened_spearman", form["screened_rho"], "Spearman rho", form["screened_n"], form_source, "recomputed", form_definition + "; require recent 4-GW minutes >= 180"),
            result_row("form_collapse", "all_players_bin_means", json.dumps([round(value, 6) for value in form["all_bin_means"]]), "next-4-GW points", form["all_n"], form_source, "recomputed", "five equal-count recent-points groups, stable first-rank ties"),
            result_row("form_collapse", "minutes_screened_bin_means", json.dumps([round(value, 6) for value in form["screened_bin_means"]]), "next-4-GW points", form["screened_n"], form_source, "recomputed", "same five-bin method after recent 4-GW minutes >= 180"),
        ]
    )

    simulation_source = "notebooks/fpl_decision_story.ipynb constants from src/fpl_retro/v1_engine.py; independently rerun during reconciliation"
    simulation_definition = "mean GW8..34 full-strategy season total across 40 sampled starting squads"
    rows.extend(
        [
            result_row("notebook_simulation", "hold_total", 1481, "points per simulated season", 40, simulation_source, "reported and rerun matched", simulation_definition),
            result_row("notebook_simulation", "engine_total", 1680, "points per simulated season", 40, simulation_source, "reported and rerun matched", simulation_definition),
            result_row("notebook_simulation", "simple_rule_total", 1839, "points per simulated season", 40, simulation_source, "reported and rerun matched", simulation_definition),
            result_row("notebook_simulation", "engine_minus_hold", 199, "points per simulated season", 40, simulation_source, "reported and rerun matched", "paired mean difference; 95% empirical range +31 to +406"),
            result_row("notebook_simulation", "engine_minus_simple_rule", -159, "points per simulated season", 40, simulation_source, "reported and rerun matched", "paired mean difference; 95% empirical range -271 to -62"),
            result_row("notebook_simulation", "transfer_engine_minus_simple", -33, "points per simulated season", 40, simulation_source, "reported and rerun matched", "transfer layer only; 95% empirical range -155 to +53, classified as tie"),
            result_row("notebook_simulation", "selection_engine_minus_simple", -28, "points per simulated season", 40, simulation_source, "reported and rerun matched", "selection layer only; 95% empirical range -56 to -5"),
            result_row("notebook_simulation", "captaincy_engine_minus_simple", -23, "captain points per simulated season", 40, simulation_source, "reported and rerun matched", "captaincy layer only; 95% empirical range -49 to -1"),
        ]
    )

    rows.extend(
        [
            result_row("convergence", "replay_form_to_goals_spearman", 0.19, "Spearman rho", "prior study", "analysis/transfer_rule_replay_bank/transfer_rule_bank_story.md", "reported prior finding", "trailing form versus next-4-GW goals; a different target from notebook next-4-GW points"),
            result_row("convergence", "currency_guard", "do not compare 159 with 197", "text", "two experiments", "v1_engine.py + independent locked replay rebuild", "verified", "159 is a paired mean full-strategy simulated-season gap across 40 starts; 197 is a summed incoming-player holding-window gap across 45 replay rows"),
            result_row("model_replay_placement", "status", "not scored", "text", "not applicable", "src/fpl_retro/v0_1_engine.py and v1_engine.py", "skipped", "published prediction window cannot provide a clean pre-deadline model score for every one of the 46 replay transfers; model stays qualitative on the hierarchy"),
        ]
    )
    return pd.DataFrame(rows)


def print_verification(
    replay_totals: dict[str, float], form: dict[str, object], results: pd.DataFrame
) -> None:
    """Print expected-versus-actual checks and the complete result table."""
    print("EXPECTED VS ACTUAL")
    checks = [
        ("replay rows scored", EXPECTED_SCORED_ROWS, int(replay_totals["sample_n"])),
        ("human replay total", EXPECTED_HUMAN_TOTAL, int(replay_totals["human_total"])),
        ("rule replay total", EXPECTED_RULE_TOTAL, int(replay_totals["rule_total"])),
        ("all-player form rho", EXPECTED_ALL_FORM_RHO, round(float(form["all_rho"]), 2)),
        ("minutes-screened form rho", EXPECTED_SCREENED_FORM_RHO, round(float(form["screened_rho"]), 2)),
    ]
    for label, expected, actual in checks:
        print(f"- {label}: expected={expected} | actual={actual} | match={expected == actual}")
    print(f"- do-nothing replay total: expected=new computation | actual={int(replay_totals['nothing_total'])}")
    print(
        "- all-player bin means: "
        f"expected={EXPECTED_ALL_BIN_MEANS} | actual={[round(x, 2) for x in form['all_bin_means']]}"
    )
    print(
        "- screened bin means: "
        f"expected={EXPECTED_SCREENED_BIN_MEANS} | actual={[round(x, 2) for x in form['screened_bin_means']]}"
    )
    print("- model replay placement: skipped; no complete clean score for all 46 transfers")
    print("- currency guard: 159 is a 40-start simulated season gap; 197 is a 45-window replay gap")
    print(
        "- prior replay CSV cross-check: "
        + ("available and matched" if REPLAY_PATH.exists() else "source absent; independent locked-rule rebuild used")
    )
    print("\nFULL RESULTS")
    print(results.to_string(index=False))
    print(f"\nWrote: {REPLAY_DETAIL_OUTPUT}")
    print(f"\nWrote: {OUTPUT_PATH}")


def main() -> None:
    features = pd.read_csv(
        FEATURES_PATH,
        usecols=[
            "gameweek",
            "player_id",
            "web_name",
            "position_short",
            "price",
            "total_points",
            "minutes",
        ],
    )
    transfers = load_transfers()
    timeline = pd.read_csv(TIMELINE_PATH, usecols=["event", "bank_value"])
    squad = pd.read_csv(SQUAD_PATH, usecols=["event", "element"])
    replay_detail, replay_totals = reconstruct_replay_yardstick(
        features, transfers, timeline, squad
    )
    form = recompute_form_collapse(features)
    results = build_results(replay_detail, replay_totals, form)
    replay_detail.to_csv(REPLAY_DETAIL_OUTPUT, index=False)
    results.to_csv(OUTPUT_PATH, index=False)
    print_verification(replay_totals, form, results)


if __name__ == "__main__":
    main()
