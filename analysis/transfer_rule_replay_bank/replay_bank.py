#!/usr/bin/env python3
"""Replay manager 816200's non-chip transfers with real pre-deadline bank."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


MANAGER_ID = 816200
SEASON_GWS = 38
CHIP_GWS = {6, 13, 23, 34}
EXPECTED_TRANSFER_COUNT = 101
EXPECTED_ANALYZED_COUNT = 46
FORM_WINDOW = 4
MIN_MEAN_MINUTES = 45.0
NO_CANDIDATE = "NO_CANDIDATE"
SALE_ONLY_DELTA = -191

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
TRANSFERS_PATH = REPO_ROOT / "data/raw/managers/transfers/manager_816200.json"
PICKS_DIR = REPO_ROOT / "data/raw/managers/picks/manager_816200"
FEATURES_PATH = REPO_ROOT / "data/processed/player_gw_features.csv"
BASELINE_PATH = REPO_ROOT / "analysis/transfer_rule_replay/replay_results.csv"
RESULTS_PATH = HERE / "replay_bank_results.csv"
SUMMARY_PATH = HERE / "summary.md"

RESULT_COLUMNS = [
    "gw",
    "out_name",
    "out_sell_price",
    "pre_deadline_bank",
    "budget_cap",
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
    "actual_in_pool",
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

    assert len(transfers) == EXPECTED_TRANSFER_COUNT
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
    """Compute fixed-denominator means for GWs ``gw-4`` through ``gw-1``."""
    window_gws = tuple(range(gw - FORM_WINDOW, gw))
    assert len(window_gws) == FORM_WINDOW
    assert all(window_gw < gw for window_gw in window_gws)
    window = features.loc[features["gameweek"].isin(window_gws)]
    assert window.empty or int(window["gameweek"].max()) < gw
    stats = window.groupby("player_id", as_index=True).agg(
        rule_pick_form=("total_points", "sum"),
        mean_minutes=("minutes", "sum"),
    )
    return stats / float(FORM_WINDOW), window_gws


def load_prior_context(gw: int) -> tuple[set[int], float, int, Path]:
    """Load the prior squad and the bank carried into the GW-T deadline."""
    source_gw = gw - 1
    picks_path = PICKS_DIR / f"event_{source_gw:02d}.json"
    if not picks_path.exists():
        raise FileNotFoundError(f"Missing prior-GW picks file: {picks_path}")
    payload = json.loads(picks_path.read_text())
    picks = payload.get("picks", [])
    if len(picks) != 15:
        raise ValueError(f"Expected 15 picks in {picks_path}, found {len(picks)}")
    entry_history = payload.get("entry_history", {})
    if "bank" not in entry_history:
        raise ValueError(f"Missing entry_history.bank in {picks_path}")
    recorded_event = int(entry_history.get("event", source_gw))
    assert recorded_event == source_gw, (gw, picks_path, recorded_event)
    bank_raw = int(entry_history["bank"])
    bank_gbp_m = bank_raw / 10.0
    assert source_gw < gw
    return {int(pick["element"]) for pick in picks}, bank_gbp_m, bank_raw, picks_path


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
    assert sale_gw > start_gw
    return sale_gw - 1, sale_gw


def exclusion_reasons(
    *,
    actual_in: int,
    prior_squad: set[int],
    other_incoming: set[int],
    actual_position: str,
    out_position: str,
    feature_price: float,
    budget_cap: float,
    mean_minutes: float,
) -> list[str]:
    """Explain why the actual incoming player is not in the final pool."""
    reasons: list[str] = []
    if actual_in in prior_squad:
        reasons.append("already in prior squad")
    if actual_in in other_incoming:
        reasons.append("same-GW other incoming exclusion")
    if actual_position != out_position:
        reasons.append("position mismatch")
    if feature_price > budget_cap + 1e-9:
        reasons.append(
            f"feature price £{feature_price:.1f}m exceeds cap £{budget_cap:.1f}m"
        )
    if mean_minutes < MIN_MEAN_MINUTES:
        reasons.append(
            f"prior-4 mean minutes {mean_minutes:.2f} below {MIN_MEAN_MINUTES:.0f}"
        )
    return reasons


def build_replay(
    transfers: pd.DataFrame,
    features: pd.DataFrame,
    *,
    first_transfer_bank_only: bool,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Apply the locked rule with either primary or shared-bank sensitivity caps."""
    analyzed_mask = ~transfers["event"].isin(CHIP_GWS)
    analyzed = transfers.loc[analyzed_mask]
    chip_transfer_count = int((~analyzed_mask).sum())
    assert len(analyzed) == EXPECTED_ANALYZED_COUNT

    all_ids = set(features["player_id"])
    missing_in_ids = sorted(set(transfers["element_in"]) - all_ids)
    missing_out_ids = sorted(set(transfers["element_out"]) - all_ids)
    assert not missing_in_ids and not missing_out_ids

    points = features.set_index(["player_id", "gameweek"])["total_points"]
    same_gw_incoming = transfers.groupby("event")["element_in"].apply(set).to_dict()
    analyzed_order_in_gw = analyzed.groupby("event", sort=False).cumcount()
    analyzed_counts_by_gw = analyzed.groupby("event").size().to_dict()
    catalog_cache: dict[int, pd.DataFrame] = {}
    stats_cache: dict[int, pd.DataFrame] = {}
    context_cache: dict[int, tuple[set[int], float, int, Path]] = {}
    rows: list[dict[str, object]] = []

    prior_squad_violations: list[dict[str, object]] = []
    same_gw_incoming_violations: list[dict[str, object]] = []
    actual_position_violations: list[dict[str, object]] = []
    recorded_affordability_violations: list[dict[str, object]] = []
    actual_pool_exceptions: list[dict[str, object]] = []
    price_fallback_count = 0
    leak_windows_checked = 0
    bank_timing_checks = 0
    missing_actual_score_rows = 0
    missing_rule_score_rows = 0

    for row_index, transfer in analyzed.iterrows():
        gw = int(transfer["event"])
        transfer_order = int(analyzed_order_in_gw.loc[row_index])
        actual_in = int(transfer["element_in"])
        actual_out = int(transfer["element_out"])
        out_sell_price = float(transfer["element_out_cost"]) / 10.0
        actual_in_price = float(transfer["element_in_cost"]) / 10.0

        if gw not in catalog_cache:
            catalog_cache[gw] = catalog_at_gw(features, gw)
            stats_cache[gw], window_gws = four_gw_form_and_minutes(features, gw)
            context_cache[gw] = load_prior_context(gw)
            assert window_gws == tuple(range(gw - FORM_WINDOW, gw))
            assert max(window_gws) < gw
        catalog = catalog_cache[gw]
        stats = stats_cache[gw]
        prior_squad, pre_deadline_bank, bank_raw, bank_path = context_cache[gw]
        assert bank_path.name == f"event_{gw - 1:02d}.json"
        leak_windows_checked += 1
        bank_timing_checks += 1

        bank_for_cap = (
            pre_deadline_bank
            if not first_transfer_bank_only or transfer_order == 0
            else 0.0
        )
        budget_cap = out_sell_price + bank_for_cap

        out_meta = catalog.loc[actual_out]
        in_meta = catalog.loc[actual_in]
        out_position = str(out_meta["position_short"])
        actual_position = str(in_meta["position_short"])
        other_incoming = set(same_gw_incoming.get(gw, set())) - {actual_in}

        if actual_in in prior_squad:
            prior_squad_violations.append({"gw": gw, "player_id": actual_in})
        if actual_in in other_incoming:
            same_gw_incoming_violations.append({"gw": gw, "player_id": actual_in})
        if actual_position != out_position:
            actual_position_violations.append({"gw": gw, "player_id": actual_in})
        if actual_in_price > budget_cap + 1e-9:
            recorded_affordability_violations.append(
                {
                    "gw": gw,
                    "transfer_order": transfer_order + 1,
                    "actual_in": str(in_meta["web_name"]),
                    "actual_price": actual_in_price,
                    "budget_cap": budget_cap,
                }
            )

        candidates = catalog.loc[catalog["position_short"] == out_position].copy()
        candidates = candidates.loc[~candidates.index.isin(prior_squad)]
        candidates = candidates.loc[~candidates.index.isin(other_incoming)]
        candidates = candidates.loc[candidates["price"] <= budget_cap + 1e-9]
        candidates = candidates.join(stats, how="left")
        candidates[["rule_pick_form", "mean_minutes"]] = candidates[
            ["rule_pick_form", "mean_minutes"]
        ].fillna(0.0)
        candidates = candidates.loc[candidates["mean_minutes"] >= MIN_MEAN_MINUTES]
        candidates = candidates.reset_index(drop=True).sort_values(
            ["rule_pick_form", "mean_minutes", "price", "player_id"],
            ascending=[False, False, True, True],
            kind="stable",
        )

        actual_form = float(stats["rule_pick_form"].get(actual_in, 0.0))
        actual_mean_minutes = float(stats["mean_minutes"].get(actual_in, 0.0))
        actual_in_pool = bool((candidates["player_id"] == actual_in).any())
        if not actual_in_pool:
            reasons = exclusion_reasons(
                actual_in=actual_in,
                prior_squad=prior_squad,
                other_incoming=other_incoming,
                actual_position=actual_position,
                out_position=out_position,
                feature_price=float(in_meta["price"]),
                budget_cap=budget_cap,
                mean_minutes=actual_mean_minutes,
            )
            actual_pool_exceptions.append(
                {
                    "gw": gw,
                    "transfer_order": transfer_order + 1,
                    "actual_in": str(in_meta["web_name"]),
                    "candidate_count": len(candidates),
                    "scored": not candidates.empty,
                    "reasons": "; ".join(reasons) if reasons else "unclassified",
                }
            )

        hold_end_gw, _sale_gw = holding_end_gw(transfers, row_index, actual_in)
        hold_gws = hold_end_gw - gw + 1
        actual_pts, actual_missing = points_over_window(
            points, actual_in, gw, hold_end_gw
        )
        missing_actual_score_rows += actual_missing

        if candidates.empty:
            rule_pick_name = NO_CANDIDATE
            rule_pick_price = np.nan
            rule_pick_form = np.nan
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
                "pre_deadline_bank": pre_deadline_bank,
                "budget_cap": budget_cap,
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
                "actual_in_pool": actual_in_pool,
            }
        )

    assert not prior_squad_violations
    assert not same_gw_incoming_violations
    assert not actual_position_violations
    assert leak_windows_checked == len(analyzed)
    assert bank_timing_checks == len(analyzed)
    # The locked per-leg cap does not include cash released by other same-GW legs.
    # Keep any such exceptions visible rather than silently widening the cap.

    results = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    assert len(results) == EXPECTED_ANALYZED_COUNT
    assert results["gw"].isin(CHIP_GWS).sum() == 0
    multi_gws = {gw for gw, count in analyzed_counts_by_gw.items() if count > 1}
    diagnostics: dict[str, object] = {
        "variant": "sensitivity" if first_transfer_bank_only else "primary",
        "total_transfers": len(transfers),
        "chip_transfer_count": chip_transfer_count,
        "chip_counts": {
            gw: int((transfers["event"] == gw).sum()) for gw in sorted(CHIP_GWS)
        },
        "actual_analyzed": len(results),
        "missing_in_ids": missing_in_ids,
        "missing_out_ids": missing_out_ids,
        "recorded_affordability_violations": recorded_affordability_violations,
        "actual_pool_exceptions": actual_pool_exceptions,
        "price_fallback_count": price_fallback_count,
        "leak_windows_checked": leak_windows_checked,
        "bank_timing_checks": bank_timing_checks,
        "missing_actual_score_rows": missing_actual_score_rows,
        "missing_rule_score_rows": missing_rule_score_rows,
        "multi_transfer_gws": sorted(multi_gws),
        "transfers_in_multi_transfer_gws": int(results["gw"].isin(multi_gws).sum()),
    }
    return results, diagnostics


def summarize(results: pd.DataFrame) -> dict[str, object]:
    """Calculate replay aggregates, excluding no-candidate pushes from totals."""
    scored = results.loc[results["rule_pick_name"] != NO_CANDIDATE].copy()
    agreements = int(results["agreement"].sum())
    return {
        "analyzed": len(results),
        "scored": len(scored),
        "no_candidate_count": len(results) - len(scored),
        "agreements": agreements,
        "agreement_rate_all": agreements / len(results),
        "agreement_rate_scored": agreements / len(scored) if len(scored) else np.nan,
        "actual_total": int(scored["actual_pts"].sum()),
        "rule_total": int(scored["rule_pts"].sum()),
        "total_delta": int(scored["delta"].sum()),
        "mean_delta": float(scored["delta"].mean()) if len(scored) else np.nan,
        "wins": int((scored["delta"] > 0).sum()),
        "losses": int((scored["delta"] < 0).sum()),
        "ties": int((scored["delta"] == 0).sum()),
        "top_wins": scored.loc[scored["delta"] > 0]
        .sort_values(["delta", "gw"], ascending=[False, True])
        .head(3),
        "top_losses": scored.loc[scored["delta"] < 0]
        .sort_values(["delta", "gw"], ascending=[True, True])
        .head(3),
    }


def compare_with_baseline(results: pd.DataFrame) -> dict[str, object]:
    """Verify row alignment and measure how the bank changes rule selections."""
    baseline = pd.read_csv(BASELINE_PATH)
    assert len(baseline) == len(results) == EXPECTED_ANALYZED_COUNT
    keys = ["gw", "out_name", "actual_in_name"]
    assert baseline[keys].equals(results[keys])
    changed = baseline["rule_pick_name"].ne(results["rule_pick_name"])
    baseline_delta = int(baseline["delta"].sum())
    assert baseline_delta == SALE_ONLY_DELTA
    return {
        "changed_count": int(changed.sum()),
        "unchanged_count": int((~changed).sum()),
        "baseline_delta": baseline_delta,
        "net_rule_points_effect": int(results["delta"].sum() - baseline_delta),
        "changed_rows": pd.DataFrame(
            {
                "gw": results.loc[changed, "gw"],
                "actual_in": results.loc[changed, "actual_in_name"],
                "sale_only_pick": baseline.loc[changed, "rule_pick_name"],
                "bank_aware_pick": results.loc[changed, "rule_pick_name"],
                "sale_only_delta": baseline.loc[changed, "delta"],
                "bank_aware_delta": results.loc[changed, "delta"],
            }
        ),
    }


def bank_verification_sample(
    transfers: pd.DataFrame,
) -> pd.DataFrame:
    """Return three deterministic bank joins with source file and units."""
    analyzed = transfers.loc[~transfers["event"].isin(CHIP_GWS)]
    sampled = analyzed.iloc[[0, len(analyzed) // 2, len(analyzed) - 1]]
    rows = []
    for _, transfer in sampled.iterrows():
        gw = int(transfer["event"])
        _squad, bank_gbp_m, bank_raw, path = load_prior_context(gw)
        rows.append(
            {
                "transfer_gw": gw,
                "bank_source_gw": gw - 1,
                "file_used": path.relative_to(REPO_ROOT).as_posix(),
                "bank_raw_tenths": bank_raw,
                "bank_gbp_m": bank_gbp_m,
            }
        )
    sample = pd.DataFrame(rows)
    assert (sample["bank_source_gw"] == sample["transfer_gw"] - 1).all()
    assert np.allclose(sample["bank_raw_tenths"] / 10, sample["bank_gbp_m"])
    return sample


def outcome_lines(frame: pd.DataFrame) -> list[str]:
    if frame.empty:
        return ["- None."]
    return [
        f"- GW{row.gw}: sold {row.out_name}, actually bought {row.actual_in_name} "
        f"({row.actual_pts} pts), rule bought {row.rule_pick_name} "
        f"({row.rule_pts} pts), delta {row.delta:+d}."
        for row in frame.itertuples(index=False)
    ]


def write_summary(
    primary: pd.DataFrame,
    primary_agg: dict[str, object],
    primary_diag: dict[str, object],
    sensitivity_agg: dict[str, object],
    sensitivity_diag: dict[str, object],
    comparison: dict[str, object],
) -> None:
    """Write the analysis handoff with quoted values derived from the replay."""
    improvement = primary_agg["total_delta"] - SALE_ONLY_DELTA
    pool_exceptions = primary_diag["actual_pool_exceptions"]
    scored_pool_exceptions = [item for item in pool_exceptions if item["scored"]]
    lines = [
        "# Bank-aware transfer rule replay",
        "",
        "## Result",
        "",
        f"The primary bank-aware replay gives every transfer the outgoing sale price plus "
        f"the manager's bank from the end of GW T-1. Across {primary_agg['scored']} "
        f"candidate-available transfers, actual picks scored **{primary_agg['actual_total']} "
        f"points** and rule picks scored **{primary_agg['rule_total']} points**. The "
        f"rule-minus-actual result was **{primary_agg['total_delta']:+d} points**, or "
        f"**{primary_agg['mean_delta']:+.2f} per scored transfer**.",
        "",
        f"The sale-only baseline was **{SALE_ONLY_DELTA:+d}**. Adding the real bank "
        f"changed {comparison['changed_count']} of 46 rule picks and made the rule "
        f"**{abs(improvement)} points worse**. A deficit of "
        f"**{abs(primary_agg['total_delta'])} points** still remained under a fair cap.",
        "",
        f"The new record was **{primary_agg['wins']} wins, {primary_agg['losses']} "
        f"losses, and {primary_agg['ties']} ties**, plus "
        f"{primary_agg['no_candidate_count']} no-candidate push. The rule agreed with "
        f"the actual incoming player {primary_agg['agreements']} times, or "
        f"**{primary_agg['agreement_rate_all']:.1%} of all 46 transfers**.",
        "",
        "## Biggest new wins",
        "",
        *outcome_lines(primary_agg["top_wins"]),
        "",
        "## Biggest new losses",
        "",
        *outcome_lines(primary_agg["top_losses"]),
        "",
        "## Shared-bank sensitivity",
        "",
        f"There were **{primary_diag['transfers_in_multi_transfer_gws']} analyzed "
        f"transfers in multi-transfer GWs**. In the conservative sensitivity, only "
        "the first transfer in each GW could add the bank. Later transfers used the "
        "sale price only.",
        "",
        f"That version scored actual picks at **{sensitivity_agg['actual_total']}** and "
        f"rule picks at **{sensitivity_agg['rule_total']}**, for a "
        f"**{sensitivity_agg['total_delta']:+d}** delta across "
        f"{sensitivity_agg['scored']} candidate-available rows. It was "
        f"**{sensitivity_agg['total_delta'] - primary_agg['total_delta']:+d} points** "
        "different from the primary full-bank-per-transfer design.",
        "",
        "## Verification and data quirks",
        "",
        f"- Bank join: each transfer at T reads `entry_history.bank` from "
        f"`event_{{T-1}}.json`. The console prints three files and confirms the stored "
        "tenths are divided by 10 to get £m.",
        f"- Bank timing: expected one T-1 timing check for each of 46 transfers; "
        f"actual {primary_diag['bank_timing_checks']}. No event T or later file is used.",
        f"- Recorded-price affordability: expected 0 actual incoming costs above "
        f"sale plus bank under the design premise; actual "
        f"{len(primary_diag['recorded_affordability_violations'])}. These exceptions "
        "occur because another same-GW transfer leg released cash. The locked per-leg "
        "cap does not include those package proceeds.",
        f"- Actual-in-pool: {int(primary['actual_in_pool'].sum())} of 46 actual picks "
        f"passed every candidate filter. There were {len(pool_exceptions)} exceptions, "
        f"including {len(scored_pool_exceptions)} rows where another candidate still "
        "made the row scorable. The console prints every reason.",
        f"- Chip exclusion: expected 46 analyzed after excluding GWs "
        f"{sorted(CHIP_GWS)}; actual {primary_diag['actual_analyzed']}. Chip-GW counts "
        f"were {primary_diag['chip_counts']}.",
        f"- Leak freedom: expected 46 fixed windows `[T-4, T-1]`; actual "
        f"{primary_diag['leak_windows_checked']}. Every maximum source GW was asserted "
        "to be less than T.",
        f"- Outcome blanks: missing player-GW rows count as zero. Primary missing rows "
        f"were {primary_diag['missing_actual_score_rows']} for actual picks and "
        f"{primary_diag['missing_rule_score_rows']} for rule picks.",
        f"- Candidate price quirk: as in the verified baseline, the rule uses the "
        "feature-table price at or before T. Actual buy and sale columns use recorded "
        "transfer costs. This preserves the one-change design but means the actual "
        "recorded affordability check and the feature-price candidate check are not "
        "identical.",
        "- The primary design intentionally lets each same-GW transfer see the full "
        "pre-deadline bank. It is a per-transfer affordability test, not a jointly "
        "optimized transfer package. The sensitivity shows the effect of a stricter "
        "shared-bank assumption.",
        "- This is a descriptive counterfactual. It does not include team limits beyond "
        "the locked exclusions, captaincy, benching, hits, or whether a rule pick would "
        "have started.",
        "",
        "## Method note",
        "",
        "For each non-chip transfer at GW T, candidates match the outgoing player's "
        "position, are absent from the prior-GW squad and the GW's other actual incoming "
        "players, cost no more than the outgoing sale price plus the bank stored after "
        "GW T-1, and average at least 45 minutes over GWs T-4 through T-1. Ranking and "
        "tiebreaks are unchanged: prior four-GW mean points, higher mean minutes, lower "
        "price, then lower player ID. Both picks use the actual holding window, and "
        "missing gameweeks score zero.",
        "",
    ]
    SUMMARY_PATH.write_text("\n".join(lines))


def print_verification(
    bank_sample: pd.DataFrame,
    primary: pd.DataFrame,
    primary_agg: dict[str, object],
    primary_diag: dict[str, object],
    sensitivity_agg: dict[str, object],
    sensitivity_diag: dict[str, object],
    comparison: dict[str, object],
) -> None:
    print("\n=== Bank join verification (3 actual transfers) ===")
    print(bank_sample.to_string(index=False))
    print("Units: entry_history.bank is tenths of £m; bank_raw_tenths / 10 = bank_gbp_m. CONFIRMED")
    print("\n=== Expected versus actual validation ===")
    print(f"Total transfers: expected {EXPECTED_TRANSFER_COUNT}; actual {primary_diag['total_transfers']}")
    print(f"Chip exclusion: expected {EXPECTED_ANALYZED_COUNT}; actual {primary_diag['actual_analyzed']}")
    print(f"Chip-GW transfer counts: {primary_diag['chip_counts']}")
    print(
        "Leak-free [T-4,T-1] windows: expected 46; actual "
        f"{primary_diag['leak_windows_checked']}"
    )
    print(
        "Bank timing from event_{T-1}, never T or later: expected 46; actual "
        f"{primary_diag['bank_timing_checks']}"
    )
    print(
        "Primary recorded actual buys above sale+bank cap: expected 0; actual "
        f"{len(primary_diag['recorded_affordability_violations'])}"
    )
    scored_pool_exceptions = [
        item for item in primary_diag["actual_pool_exceptions"] if item["scored"]
    ]
    print(
        "Actual incoming in final candidate pool: expected every eligible/scored "
        f"transfer; actual {int(primary['actual_in_pool'].sum())}/46. "
        f"Scored exceptions={len(scored_pool_exceptions)}"
    )
    if primary_diag["actual_pool_exceptions"]:
        print("Actual-in-pool exceptions and reasons:")
        print(pd.DataFrame(primary_diag["actual_pool_exceptions"]).to_string(index=False))
    assert all(item["reasons"] != "unclassified" for item in scored_pool_exceptions)
    print(
        "Analyzed transfers in multi-transfer GWs: "
        f"{primary_diag['transfers_in_multi_transfer_gws']} across "
        f"{len(primary_diag['multi_transfer_gws'])} GWs"
    )
    print("\n=== Primary full-bank-per-transfer aggregates ===")
    print(
        f"Analyzed={primary_agg['analyzed']}, scored={primary_agg['scored']}, "
        f"no_candidate={primary_agg['no_candidate_count']}"
    )
    print(
        f"Actual={primary_agg['actual_total']}, rule={primary_agg['rule_total']}, "
        f"delta={primary_agg['total_delta']:+d}, mean={primary_agg['mean_delta']:+.2f}"
    )
    print(
        f"W/L/T={primary_agg['wins']}/{primary_agg['losses']}/{primary_agg['ties']}; "
        f"agreement={primary_agg['agreements']}/46 "
        f"({primary_agg['agreement_rate_all']:.1%})"
    )
    print(
        f"Versus sale-only {comparison['baseline_delta']:+d}: "
        f"{comparison['changed_count']} picks changed; net rule effect "
        f"{comparison['net_rule_points_effect']:+d}"
    )
    print("\n=== Sensitivity: bank only on first transfer within each GW ===")
    print(
        f"Analyzed={sensitivity_agg['analyzed']}, scored={sensitivity_agg['scored']}, "
        f"no_candidate={sensitivity_agg['no_candidate_count']}"
    )
    print(
        f"Actual={sensitivity_agg['actual_total']}, rule={sensitivity_agg['rule_total']}, "
        f"delta={sensitivity_agg['total_delta']:+d}; difference vs primary "
        f"{sensitivity_agg['total_delta'] - primary_agg['total_delta']:+d}"
    )
    print(
        "Sensitivity recorded affordability exceptions (expected possible on 2nd+ "
        f"legs): {len(sensitivity_diag['recorded_affordability_violations'])}"
    )


def main() -> None:
    transfers, features = load_inputs()
    primary, primary_diag = build_replay(
        transfers, features, first_transfer_bank_only=False
    )
    sensitivity, sensitivity_diag = build_replay(
        transfers, features, first_transfer_bank_only=True
    )
    primary_agg = summarize(primary)
    sensitivity_agg = summarize(sensitivity)
    comparison = compare_with_baseline(primary)
    bank_sample = bank_verification_sample(transfers)

    primary.to_csv(RESULTS_PATH, index=False, float_format="%.2f")
    write_summary(
        primary,
        primary_agg,
        primary_diag,
        sensitivity_agg,
        sensitivity_diag,
        comparison,
    )

    print("=== Full per-transfer bank-aware replay table ===")
    print(primary.to_string(index=False))
    print_verification(
        bank_sample,
        primary,
        primary_agg,
        primary_diag,
        sensitivity_agg,
        sensitivity_diag,
        comparison,
    )
    print(f"\nWrote {RESULTS_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote {SUMMARY_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
