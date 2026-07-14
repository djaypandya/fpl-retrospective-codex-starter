#!/usr/bin/env python3
"""Replay manager 816200's non-chip transfers with a fixed, prior-only rule."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


MANAGER_ID = 816200
SEASON_GWS = 38
CHIP_GWS = {6, 13, 23, 34}
EXPECTED_TRANSFER_COUNT = 101
FORM_WINDOW = 4
MIN_MEAN_MINUTES = 45.0
NO_CANDIDATE = "NO_CANDIDATE"

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
TRANSFERS_PATH = (
    REPO_ROOT / "data/raw/managers/transfers/manager_816200.json"
)
PICKS_DIR = REPO_ROOT / "data/raw/managers/picks/manager_816200"
FEATURES_PATH = REPO_ROOT / "data/processed/player_gw_features.csv"
RESULTS_PATH = HERE / "replay_results.csv"
SUMMARY_PATH = HERE / "summary.md"

RESULT_COLUMNS = [
    "gw",
    "out_name",
    "out_sell_price",
    "actual_in_name",
    "actual_in_price",
    "rule_pick_name",
    "rule_pick_price",
    "rule_pick_form",
    "actual_form",
    "hold_gws",
    "hold_end_gw",
    "actual_pts",
    "rule_pts",
    "delta",
    "agreement",
]


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    """Fail with a useful message when an input schema is incomplete."""
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and validate the raw transfer list and player-gameweek table."""
    transfers = pd.DataFrame(json.loads(TRANSFERS_PATH.read_text()))
    require_columns(
        transfers,
        {
            "element_in",
            "element_in_cost",
            "element_out",
            "element_out_cost",
            "entry",
            "event",
            "time",
        },
        "transfers",
    )
    transfers["time"] = pd.to_datetime(transfers["time"], utc=True)
    for column in [
        "element_in",
        "element_in_cost",
        "element_out",
        "element_out_cost",
        "entry",
        "event",
    ]:
        transfers[column] = pd.to_numeric(transfers[column], errors="raise").astype(int)
    transfers = transfers.sort_values(["event", "time"], kind="stable").reset_index(
        drop=True
    )

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
        "player_gw_features",
    )
    for column in ["gameweek", "player_id"]:
        features[column] = pd.to_numeric(features[column], errors="raise").astype(int)
    for column in ["price", "total_points", "minutes"]:
        features[column] = pd.to_numeric(features[column], errors="coerce")
    features[["total_points", "minutes"]] = features[
        ["total_points", "minutes"]
    ].fillna(0.0)
    features = features.sort_values(["player_id", "gameweek"], kind="stable")

    assert len(transfers) == EXPECTED_TRANSFER_COUNT, (
        f"Expected {EXPECTED_TRANSFER_COUNT} transfers, found {len(transfers)}"
    )
    assert set(transfers["entry"]) == {MANAGER_ID}
    assert not features.duplicated(["player_id", "gameweek"]).any()
    assert features["gameweek"].between(1, SEASON_GWS).all()
    assert features["price"].notna().all()
    return transfers, features


def catalog_at_gw(features: pd.DataFrame, gw: int) -> pd.DataFrame:
    """Return each player's latest metadata/price row at or before ``gw``."""
    available = features.loc[features["gameweek"] <= gw]
    catalog = available.groupby("player_id", sort=False, as_index=False).tail(1).copy()
    catalog = catalog.rename(columns={"gameweek": "price_source_gw"})
    return catalog.set_index("player_id", drop=False)


def four_gw_form_and_minutes(
    features: pd.DataFrame, gw: int
) -> tuple[pd.DataFrame, tuple[int, ...]]:
    """Compute fixed-denominator means for GWs ``gw-4`` through ``gw-1``.

    Missing player-GW rows, blanks, and pre-season gameweek numbers are zero. The
    denominator is always four, including for early-season transfers.
    """
    window_gws = tuple(range(gw - FORM_WINDOW, gw))
    assert len(window_gws) == FORM_WINDOW
    assert all(window_gw < gw for window_gw in window_gws)

    window = features.loc[features["gameweek"].isin(window_gws)]
    assert window.empty or int(window["gameweek"].max()) < gw
    stats = window.groupby("player_id", as_index=True).agg(
        rule_pick_form=("total_points", "sum"),
        mean_minutes=("minutes", "sum"),
    )
    stats = stats / float(FORM_WINDOW)
    return stats, window_gws


def load_prior_squad(gw: int) -> set[int]:
    """Load the manager's 15-player squad from the preceding gameweek."""
    picks_path = PICKS_DIR / f"event_{gw - 1:02d}.json"
    if not picks_path.exists():
        raise FileNotFoundError(f"Missing prior-GW picks file: {picks_path}")
    payload = json.loads(picks_path.read_text())
    picks = payload.get("picks", [])
    if len(picks) != 15:
        raise ValueError(f"Expected 15 picks in {picks_path}, found {len(picks)}")
    return {int(pick["element"]) for pick in picks}


def points_over_window(
    points: pd.Series, player_id: int, start_gw: int, end_gw: int
) -> tuple[int, int]:
    """Sum actual points over an inclusive GW window, filling missing rows with 0."""
    if end_gw < start_gw:
        return 0, 0
    expected_index = pd.MultiIndex.from_product(
        [[player_id], range(start_gw, end_gw + 1)],
        names=["player_id", "gameweek"],
    )
    values = points.reindex(expected_index)
    missing_rows = int(values.isna().sum())
    return int(values.fillna(0.0).sum()), missing_rows


def holding_end_gw(
    all_transfers: pd.DataFrame, row_index: int, incoming_player: int
) -> tuple[int, int | None]:
    """Find the first later transaction that sells the actual incoming player."""
    later = all_transfers.iloc[row_index + 1 :]
    sale = later.loc[later["element_out"] == incoming_player]
    if sale.empty:
        return SEASON_GWS, None
    sale_gw = int(sale.iloc[0]["event"])
    start_gw = int(all_transfers.iloc[row_index]["event"])
    assert sale_gw > start_gw, (
        "An incoming player was sold again within the same GW, which would create "
        f"an empty holding window: player={incoming_player}, GW={start_gw}"
    )
    return sale_gw - 1, sale_gw


def build_replay(
    transfers: pd.DataFrame, features: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Apply the locked counterfactual rule to every non-chip transfer."""
    analyzed_mask = ~transfers["event"].isin(CHIP_GWS)
    analyzed = transfers.loc[analyzed_mask]
    chip_transfer_count = int((~analyzed_mask).sum())
    expected_analyzed = len(transfers) - chip_transfer_count
    assert len(analyzed) == expected_analyzed

    all_ids = set(features["player_id"])
    missing_in_ids = sorted(set(transfers["element_in"]) - all_ids)
    missing_out_ids = sorted(set(transfers["element_out"]) - all_ids)
    assert not missing_in_ids and not missing_out_ids

    points = features.set_index(["player_id", "gameweek"])["total_points"]
    same_gw_incoming = transfers.groupby("event")["element_in"].apply(set).to_dict()
    catalog_cache: dict[int, pd.DataFrame] = {}
    stats_cache: dict[int, pd.DataFrame] = {}
    rows: list[dict[str, object]] = []

    prior_squad_violations: list[dict[str, object]] = []
    same_gw_incoming_violations: list[dict[str, object]] = []
    actual_position_violations: list[dict[str, object]] = []
    recorded_price_violations: list[dict[str, object]] = []
    feature_price_violations: list[dict[str, object]] = []
    price_fallback_count = 0
    leak_windows_checked = 0
    missing_actual_score_rows = 0
    missing_rule_score_rows = 0

    for row_index, transfer in analyzed.iterrows():
        gw = int(transfer["event"])
        actual_in = int(transfer["element_in"])
        actual_out = int(transfer["element_out"])
        out_sell_price = float(transfer["element_out_cost"]) / 10.0
        actual_in_price = float(transfer["element_in_cost"]) / 10.0

        if gw not in catalog_cache:
            catalog_cache[gw] = catalog_at_gw(features, gw)
            stats_cache[gw], window_gws = four_gw_form_and_minutes(features, gw)
            assert max(window_gws) < gw
        catalog = catalog_cache[gw]
        stats = stats_cache[gw]
        leak_windows_checked += 1

        if actual_in not in catalog.index or actual_out not in catalog.index:
            raise AssertionError(
                f"Actual transfer IDs lack metadata at or before GW{gw}: "
                f"out={actual_out}, in={actual_in}"
            )
        out_meta = catalog.loc[actual_out]
        in_meta = catalog.loc[actual_in]
        out_position = str(out_meta["position_short"])
        actual_position = str(in_meta["position_short"])

        prior_squad = load_prior_squad(gw)
        other_incoming = set(same_gw_incoming.get(gw, set())) - {actual_in}
        if actual_in in prior_squad:
            prior_squad_violations.append(
                {"gw": gw, "player_id": actual_in, "name": in_meta["web_name"]}
            )
        if actual_in in other_incoming:
            same_gw_incoming_violations.append(
                {"gw": gw, "player_id": actual_in, "name": in_meta["web_name"]}
            )
        if actual_position != out_position:
            actual_position_violations.append(
                {
                    "gw": gw,
                    "out": out_meta["web_name"],
                    "incoming": in_meta["web_name"],
                }
            )
        if actual_in_price > out_sell_price:
            recorded_price_violations.append(
                {
                    "gw": gw,
                    "out": out_meta["web_name"],
                    "out_sell_price": out_sell_price,
                    "incoming": in_meta["web_name"],
                    "actual_in_price": actual_in_price,
                }
            )
        feature_in_price = float(in_meta["price"])
        if feature_in_price > out_sell_price:
            feature_price_violations.append(
                {
                    "gw": gw,
                    "out": out_meta["web_name"],
                    "out_sell_price": out_sell_price,
                    "incoming": in_meta["web_name"],
                    "feature_in_price": feature_in_price,
                }
            )

        candidates = catalog.loc[catalog["position_short"] == out_position].copy()
        candidates = candidates.loc[~candidates.index.isin(prior_squad)]
        candidates = candidates.loc[~candidates.index.isin(other_incoming)]
        candidates = candidates.loc[candidates["price"] <= out_sell_price + 1e-9]
        candidates = candidates.join(stats, how="left")
        candidates[["rule_pick_form", "mean_minutes"]] = candidates[
            ["rule_pick_form", "mean_minutes"]
        ].fillna(0.0)
        candidates = candidates.loc[candidates["mean_minutes"] >= MIN_MEAN_MINUTES]
        candidates = candidates.reset_index(drop=True)
        candidates = candidates.sort_values(
            ["rule_pick_form", "mean_minutes", "price", "player_id"],
            ascending=[False, False, True, True],
            kind="stable",
        )

        actual_form = float(
            stats["rule_pick_form"].get(actual_in, 0.0)
            if not stats.empty
            else 0.0
        )
        hold_end_gw, _sale_gw = holding_end_gw(transfers, row_index, actual_in)
        hold_gws = hold_end_gw - gw + 1
        actual_pts, actual_missing = points_over_window(
            points, actual_in, gw, hold_end_gw
        )
        missing_actual_score_rows += actual_missing

        if candidates.empty:
            rule_pick_id: int | None = None
            rule_pick_name = NO_CANDIDATE
            rule_pick_price = np.nan
            rule_pick_form = np.nan
            # A missing candidate is a push for the row, but aggregate point
            # comparisons explicitly exclude it.
            rule_pts = actual_pts
            delta = 0
            agreement = False
        else:
            pick = candidates.iloc[0]
            rule_pick_id = int(pick["player_id"])
            rule_pick_name = str(pick["web_name"])
            rule_pick_price = float(pick["price"])
            rule_pick_form = float(pick["rule_pick_form"])
            rule_pts, rule_missing = points_over_window(
                points, rule_pick_id, gw, hold_end_gw
            )
            missing_rule_score_rows += rule_missing
            delta = rule_pts - actual_pts
            agreement = rule_pick_id == actual_in
            price_fallback_count += int(pick["price_source_gw"] < gw)

        rows.append(
            {
                "gw": gw,
                "out_name": str(out_meta["web_name"]),
                "out_sell_price": out_sell_price,
                "actual_in_name": str(in_meta["web_name"]),
                "actual_in_price": actual_in_price,
                "rule_pick_name": rule_pick_name,
                "rule_pick_price": rule_pick_price,
                "rule_pick_form": rule_pick_form,
                "actual_form": actual_form,
                "hold_gws": hold_gws,
                "hold_end_gw": hold_end_gw,
                "actual_pts": actual_pts,
                "rule_pts": rule_pts,
                "delta": delta,
                "agreement": agreement,
            }
        )

    assert not prior_squad_violations, prior_squad_violations
    assert not same_gw_incoming_violations, same_gw_incoming_violations
    assert not actual_position_violations, actual_position_violations
    assert leak_windows_checked == len(analyzed)

    results = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    assert len(results) == len(analyzed)
    assert results["gw"].isin(CHIP_GWS).sum() == 0
    diagnostics: dict[str, object] = {
        "total_transfers": len(transfers),
        "chip_transfer_count": chip_transfer_count,
        "chip_counts": {
            gw: int((transfers["event"] == gw).sum()) for gw in sorted(CHIP_GWS)
        },
        "expected_analyzed": expected_analyzed,
        "actual_analyzed": len(results),
        "missing_in_ids": missing_in_ids,
        "missing_out_ids": missing_out_ids,
        "prior_squad_violations": prior_squad_violations,
        "same_gw_incoming_violations": same_gw_incoming_violations,
        "actual_position_violations": actual_position_violations,
        "recorded_price_violations": recorded_price_violations,
        "feature_price_violations": feature_price_violations,
        "price_fallback_count": price_fallback_count,
        "leak_windows_checked": leak_windows_checked,
        "missing_actual_score_rows": missing_actual_score_rows,
        "missing_rule_score_rows": missing_rule_score_rows,
    }
    return results, diagnostics


def price_verification_table(
    transfers: pd.DataFrame, features: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Build a deterministic three-transfer ID/name/unit verification sample."""
    analyzed = transfers.loc[~transfers["event"].isin(CHIP_GWS)]
    sample_positions = [0, len(analyzed) // 2, len(analyzed) - 1]
    sampled = analyzed.iloc[sample_positions]
    records: list[dict[str, object]] = []
    for _, transfer in sampled.iterrows():
        gw = int(transfer["event"])
        catalog = catalog_at_gw(features, gw)
        out_meta = catalog.loc[int(transfer["element_out"])]
        in_meta = catalog.loc[int(transfer["element_in"])]
        records.append(
            {
                "gw": gw,
                "out_id": int(transfer["element_out"]),
                "out_name": out_meta["web_name"],
                "out_cost_raw": int(transfer["element_out_cost"]),
                "out_cost_gbp_m": float(transfer["element_out_cost"]) / 10.0,
                "out_feature_price": float(out_meta["price"]),
                "in_id": int(transfer["element_in"]),
                "in_name": in_meta["web_name"],
                "in_cost_raw": int(transfer["element_in_cost"]),
                "in_cost_gbp_m": float(transfer["element_in_cost"]) / 10.0,
                "in_feature_price": float(in_meta["price"]),
            }
        )

    all_costs = pd.concat(
        [
            transfers[["element_in", "element_in_cost", "event"]].rename(
                columns={"element_in": "player_id", "element_in_cost": "cost"}
            ),
            transfers[["element_out", "element_out_cost", "event"]].rename(
                columns={"element_out": "player_id", "element_out_cost": "cost"}
            ),
        ],
        ignore_index=True,
    )
    comparisons = []
    for row in all_costs.itertuples(index=False):
        catalog = catalog_at_gw(features, int(row.event))
        comparisons.append((float(row.cost), float(catalog.loc[int(row.player_id), "price"])))
    comparison = pd.DataFrame(comparisons, columns=["raw_cost", "feature_price"])
    normalized_median_error = float(
        (comparison["raw_cost"] / 10.0 - comparison["feature_price"]).abs().median()
    )
    unscaled_median_error = float(
        (comparison["raw_cost"] - comparison["feature_price"]).abs().median()
    )
    assert normalized_median_error < 1.0
    assert unscaled_median_error > 20.0
    unit_metrics = {
        "normalized_median_error": normalized_median_error,
        "unscaled_median_error": unscaled_median_error,
    }
    return pd.DataFrame(records), unit_metrics


def summarize(results: pd.DataFrame) -> dict[str, object]:
    """Calculate aggregates, explicitly excluding no-candidate pushes."""
    scored = results.loc[results["rule_pick_name"] != NO_CANDIDATE].copy()
    no_candidate_count = len(results) - len(scored)
    agreements = int(results["agreement"].sum())
    wins = int((scored["delta"] > 0).sum())
    losses = int((scored["delta"] < 0).sum())
    ties = int((scored["delta"] == 0).sum())
    total_delta = int(scored["delta"].sum())
    mean_delta = float(scored["delta"].mean()) if len(scored) else float("nan")
    return {
        "analyzed": len(results),
        "scored": len(scored),
        "no_candidate_count": no_candidate_count,
        "agreements": agreements,
        "agreement_rate_all": agreements / len(results) if len(results) else float("nan"),
        "agreement_rate_scored": agreements / len(scored) if len(scored) else float("nan"),
        "actual_total": int(scored["actual_pts"].sum()),
        "rule_total": int(scored["rule_pts"].sum()),
        "total_delta": total_delta,
        "mean_delta": mean_delta,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "top_wins": scored.loc[scored["delta"] > 0]
        .sort_values(["delta", "gw"], ascending=[False, True])
        .head(3),
        "top_losses": scored.loc[scored["delta"] < 0]
        .sort_values(["delta", "gw"], ascending=[True, True])
        .head(3),
    }


def outcome_lines(frame: pd.DataFrame) -> list[str]:
    """Format notable wins/losses for Markdown."""
    if frame.empty:
        return ["- None."]
    lines = []
    for row in frame.itertuples(index=False):
        lines.append(
            f"- GW{row.gw}: sold {row.out_name}, actually bought {row.actual_in_name} "
            f"({row.actual_pts} pts), rule bought {row.rule_pick_name} "
            f"({row.rule_pts} pts), delta {row.delta:+d}."
        )
    return lines


def write_summary(
    results: pd.DataFrame,
    aggregates: dict[str, object],
    diagnostics: dict[str, object],
    unit_metrics: dict[str, float],
    features: pd.DataFrame,
) -> None:
    """Write the requested plain-English report."""
    varying_price_players = int(
        (features.groupby("player_id")["price"].nunique() > 1).sum()
    )
    recorded_violations = diagnostics["recorded_price_violations"]
    feature_violations = diagnostics["feature_price_violations"]
    lines = [
        "# Counterfactual transfer rule replay",
        "",
        "## Result",
        "",
        f"The replay analyzed **{aggregates['analyzed']} transfers** after excluding "
        f"the {diagnostics['chip_transfer_count']} transfers made in chip GWs "
        f"{sorted(CHIP_GWS)}. A rule candidate was available for "
        f"{aggregates['scored']} transfers; {aggregates['no_candidate_count']} "
        "no-candidate rows were recorded as pushes and excluded from point aggregates.",
        "",
        f"The rule agreed with the actual incoming player {aggregates['agreements']} "
        f"times: **{aggregates['agreement_rate_all']:.1%} of all analyzed transfers** "
        f"and {aggregates['agreement_rate_scored']:.1%} of transfers with a candidate.",
        "",
        f"Across candidate-available transfers, actual picks scored "
        f"**{aggregates['actual_total']} points** and rule picks scored "
        f"**{aggregates['rule_total']} points** over identical actual holding windows. "
        f"The rule-minus-actual delta was **{aggregates['total_delta']:+d} total "
        f"points**, or **{aggregates['mean_delta']:+.2f} points per scored transfer**.",
        "",
        f"Outcome count: **{aggregates['wins']} wins, {aggregates['losses']} losses, "
        f"and {aggregates['ties']} ties**, plus "
        f"{aggregates['no_candidate_count']} separately counted no-candidate pushes.",
        "",
        "## Three biggest rule wins",
        "",
        *outcome_lines(aggregates["top_wins"]),
        "",
        "## Three biggest rule losses",
        "",
        *outcome_lines(aggregates["top_losses"]),
        "",
        "## Verification and data quirks",
        "",
        f"- Element-ID join: expected 0 unmatched incoming/outgoing IDs; actual "
        f"{len(diagnostics['missing_in_ids'])} incoming and "
        f"{len(diagnostics['missing_out_ids'])} outgoing. The three-transfer console "
        "sample prints the joined names and both recorded and feature prices.",
        f"- Price units: dividing transfer cost fields by 10 gives £m values. Across "
        f"all transfer legs, the median absolute gap to the feature price is "
        f"£{unit_metrics['normalized_median_error']:.2f}m after conversion versus "
        f"{unit_metrics['unscaled_median_error']:.1f} without conversion, confirming "
        "the tenths-to-£m conversion.",
        f"- Historical-price limitation: {varying_price_players} players have more "
        "than one distinct `price` across their feature rows. Therefore the feature "
        "table contains a season-end/static price repeated across GWs, not true "
        "deadline prices. The replay nevertheless uses that field at/latest before T "
        "because the rule explicitly requires it. Recorded transfer costs are retained "
        "for actual buy/sell columns and verification.",
        f"- Chip exclusion: expected {diagnostics['total_transfers']} total minus "
        f"{diagnostics['chip_transfer_count']} chip-GW transfers = "
        f"{diagnostics['expected_analyzed']} analyzed; actual "
        f"{diagnostics['actual_analyzed']}. Chip-GW counts were "
        f"{diagnostics['chip_counts']}.",
        f"- Leak freedom: expected one four-GW prior-only window for every analyzed "
        f"transfer; actual {diagnostics['leak_windows_checked']}. Every window was "
        "asserted to be exactly `[T-4, T-1]`, so no form/minutes input touches GW T "
        "or later. Early-season nonexistent GW numbers count as zero.",
        f"- Squad sanity: expected 0 actual incoming players in the GW T-1 squad and "
        f"0 duplicated as a same-GW other incoming player; actual "
        f"{len(diagnostics['prior_squad_violations'])} and "
        f"{len(diagnostics['same_gw_incoming_violations'])}.",
        f"- Actual affordability: {len(recorded_violations)} of "
        f"{aggregates['analyzed']} actual buys had recorded `element_in_cost > "
        "element_out_cost`; this is legal with banked funds but violates this rule's "
        f"outgoing-sale-price-only cap. Using the specified feature price instead, "
        f"{len(feature_violations)} actual incoming players were above the cap.",
        f"- Price fallback: {diagnostics['price_fallback_count']} selected rule picks "
        "needed a latest-prior rather than exact-GW price row.",
        f"- Outcome blanks: missing player-GW rows are scored as zero. There were "
        f"{diagnostics['missing_actual_score_rows']} missing actual-pick rows and "
        f"{diagnostics['missing_rule_score_rows']} missing rule-pick rows inside the "
        "evaluated holding windows.",
        "- `hold_end_gw` is the last included scoring GW (`T_sold - 1`), and "
        "`hold_gws` is the inclusive number of GWs from transfer GW through that end. "
        "If the actual incoming player was never sold later, the end is GW38.",
        "- This is a deterministic retrospective comparison, not an estimate of causal "
        "points gained: it ignores transfer packages, bank allocation across simultaneous "
        "moves, squad/team limits beyond the stated exclusions, captaincy, benching, and "
        "whether the counterfactual player would have been started.",
        "",
        "## Method note",
        "",
        "For each non-chip transfer, candidates match the outgoing player's position, "
        "are absent from the prior-GW squad and the GW's other actual incoming players, "
        "cost no more than the recorded outgoing sale price, and average at least 45 "
        "minutes over the fixed four prior GWs. Ranking is by prior four-GW mean points, "
        "then mean minutes, lower price, and lower player ID. Both picks are scored over "
        "the actual incoming player's holding window with blank/missing rows worth zero.",
        "",
    ]
    SUMMARY_PATH.write_text("\n".join(lines))


def print_verification(
    sample: pd.DataFrame,
    unit_metrics: dict[str, float],
    diagnostics: dict[str, object],
    aggregates: dict[str, object],
) -> None:
    """Print expected-versus-actual checks and aggregates."""
    print("\n=== Element ID and price-unit verification (3 actual transfers) ===")
    print(sample.to_string(index=False))
    print(
        "Unit expectation: raw transfer costs are tenths of £m; actual median "
        f"absolute gap after /10 = £{unit_metrics['normalized_median_error']:.2f}m "
        f"(without /10: {unit_metrics['unscaled_median_error']:.1f}). CONFIRMED"
    )
    print("\n=== Expected versus actual validation ===")
    print(
        f"Total transfers: expected {EXPECTED_TRANSFER_COUNT}; "
        f"actual {diagnostics['total_transfers']}"
    )
    print(
        f"Chip exclusion: expected {diagnostics['total_transfers']} - "
        f"{diagnostics['chip_transfer_count']} = {diagnostics['expected_analyzed']}; "
        f"actual {diagnostics['actual_analyzed']}"
    )
    print(f"Chip-GW transfer counts: {diagnostics['chip_counts']}")
    print(
        "ID joins: expected 0 unmatched in/out; actual "
        f"{len(diagnostics['missing_in_ids'])}/{len(diagnostics['missing_out_ids'])}"
    )
    print(
        "Prior-squad / same-GW-other-in violations: expected 0/0; actual "
        f"{len(diagnostics['prior_squad_violations'])}/"
        f"{len(diagnostics['same_gw_incoming_violations'])}"
    )
    print(
        "Leak-free four-GW windows: expected "
        f"{diagnostics['actual_analyzed']}; actual "
        f"{diagnostics['leak_windows_checked']} (all max GW < T)"
    )
    print(
        "Actual buys with recorded in_cost > out_cost: "
        f"{len(diagnostics['recorded_price_violations'])}"
    )
    print(
        "Actual buys with feature price > recorded out_cost cap: "
        f"{len(diagnostics['feature_price_violations'])}"
    )
    if diagnostics["recorded_price_violations"]:
        print(pd.DataFrame(diagnostics["recorded_price_violations"]).to_string(index=False))
    print(
        "Missing scoring rows filled with zero (actual/rule): "
        f"{diagnostics['missing_actual_score_rows']}/"
        f"{diagnostics['missing_rule_score_rows']}"
    )
    print("\n=== Aggregates (no-candidate pushes excluded) ===")
    print(
        f"Analyzed={aggregates['analyzed']}, scored={aggregates['scored']}, "
        f"no_candidate={aggregates['no_candidate_count']}"
    )
    print(
        f"Agreements={aggregates['agreements']} "
        f"({aggregates['agreement_rate_all']:.1%} of analyzed; "
        f"{aggregates['agreement_rate_scored']:.1%} of scored)"
    )
    print(
        f"Actual points={aggregates['actual_total']}, "
        f"rule points={aggregates['rule_total']}, "
        f"total delta={aggregates['total_delta']:+d}, "
        f"mean delta={aggregates['mean_delta']:+.2f}"
    )
    print(
        f"Wins/losses/ties={aggregates['wins']}/"
        f"{aggregates['losses']}/{aggregates['ties']}"
    )


def main() -> None:
    transfers, features = load_inputs()
    results, diagnostics = build_replay(transfers, features)
    verification_sample, unit_metrics = price_verification_table(transfers, features)
    aggregates = summarize(results)

    results.to_csv(RESULTS_PATH, index=False, float_format="%.2f")
    write_summary(results, aggregates, diagnostics, unit_metrics, features)

    print("=== Full per-transfer replay table ===")
    print(results.to_string(index=False))
    print_verification(verification_sample, unit_metrics, diagnostics, aggregates)
    print(f"\nWrote {RESULTS_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote {SUMMARY_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
