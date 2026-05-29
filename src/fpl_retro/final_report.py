"""Final retrospective summary helpers."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


MY_TEAM_ID = 816200

LEAK_SUMMARY_COLUMNS = [
    "rank",
    "area",
    "decision_type",
    "basis",
    "signed_points_impact",
    "leak_points",
    "gain_points",
    "confidence",
    "additive_to_total",
    "evidence_count",
    "evidence_summary",
    "caveat",
    "recommended_focus",
]


def _numeric(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def _bool_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    return df[column].fillna(False).astype(bool)


def _confidence_from_count(count: int, *, direct_points: bool = True) -> str:
    if not direct_points:
        return "Low"
    if count >= 20:
        return "High"
    if count >= 8:
        return "Medium"
    return "Low"


def _row(
    *,
    area: str,
    decision_type: str,
    basis: str,
    signed_points_impact: float,
    confidence: str,
    additive_to_total: bool,
    evidence_count: int,
    evidence_summary: str,
    caveat: str,
    recommended_focus: str,
) -> dict[str, object]:
    return {
        "area": area,
        "decision_type": decision_type,
        "basis": basis,
        "signed_points_impact": float(signed_points_impact),
        "leak_points": float(max(-signed_points_impact, 0)),
        "gain_points": float(max(signed_points_impact, 0)),
        "confidence": confidence,
        "additive_to_total": bool(additive_to_total),
        "evidence_count": int(evidence_count),
        "evidence_summary": evidence_summary,
        "caveat": caveat,
        "recommended_focus": recommended_focus,
    }


def _transfer_rows(
    transfer_groups: pd.DataFrame,
    transfer_decisions: pd.DataFrame,
    manager_behaviour: pd.DataFrame,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not transfer_groups.empty:
        groups = transfer_groups.copy()
        if "manager_id" in groups.columns:
            groups = groups[groups["manager_id"].astype(int).eq(MY_TEAM_ID)]
        net = _numeric(groups, "group_net_points_after_hit_5gw")
        losses = net[net < 0]
        gains = net[net > 0]
        hit_cost = _numeric(groups, "group_hit_cost_allocated").sum()
        funding_groups = int(groups["transfer_group_type"].astype(str).str.contains("released_budget|spent_budget|restructure", na=False).sum())
        rows.append(
            _row(
                area="Transfers: package outcomes",
                decision_type="transfer_package",
                basis="package_level_5gw_net_after_hit",
                signed_points_impact=float(net.sum()),
                confidence=_confidence_from_count(len(groups)),
                additive_to_total=True,
                evidence_count=len(groups),
                evidence_summary=(
                    f"{len(groups)} transfer packages; {len(gains)} positive, {len(losses)} negative; "
                    f"{hit_cost:.1f} hit points included; {funding_groups} structural packages."
                ),
                caveat=(
                    "Strategic transfer impact uses package-level 5GW net after hits. Individual transfer legs are "
                    "not added separately to avoid double-counting bundled decisions."
                ),
                recommended_focus="Review the negative packages first, especially multi-transfer and hit weeks.",
            )
        )
        if len(losses):
            rows.append(
                _row(
                    area="Transfers: negative packages",
                    decision_type="transfer_package",
                    basis="package_level_negative_5gw_net_after_hit",
                    signed_points_impact=float(losses.sum()),
                    confidence=_confidence_from_count(len(losses)),
                    additive_to_total=False,
                    evidence_count=len(losses),
                    evidence_summary=f"{len(losses)} packages lost {abs(losses.sum()):.1f} points over 5GW after hits.",
                    caveat="Diagnostic subset of transfer package outcomes; not additive with total package impact.",
                    recommended_focus="Identify recurring process errors inside the losing packages.",
                )
            )
    if not transfer_decisions.empty:
        decisions = transfer_decisions.copy()
        if "manager_id" in decisions.columns:
            decisions = decisions[decisions["manager_id"].astype(int).eq(MY_TEAM_ID)]
        possible_funding = int(_bool_series(decisions, "possible_funding_leg").sum())
        individual_losses = _numeric(decisions, "net_points_after_hit_5gw")
        individual_losses = individual_losses[individual_losses < 0]
        rows.append(
            _row(
                area="Transfers: individual-leg diagnostics",
                decision_type="individual_transfer_leg",
                basis="individual_leg_5gw_net_after_hit_diagnostic",
                signed_points_impact=float(individual_losses.sum()),
                confidence="Medium",
                additive_to_total=False,
                evidence_count=len(individual_losses),
                evidence_summary=(
                    f"{len(individual_losses)} individual transfer legs were negative; "
                    f"{possible_funding} possible funding legs were flagged."
                ),
                caveat="Diagnostic only. Individual legs can be part of a profitable package and are not summed into the headline leak total.",
                recommended_focus="Use individual rows to inspect why a package worked or failed, not to score package strategy twice.",
            )
        )
    if not manager_behaviour.empty:
        me = manager_behaviour[manager_behaviour["manager_id"].astype(int).eq(MY_TEAM_ID)]
        if not me.empty and "transfer_hit_cost_total" in me.columns:
            hit_cost = float(pd.to_numeric(me.iloc[0]["transfer_hit_cost_total"], errors="coerce"))
            rows.append(
                _row(
                    area="Transfer hits",
                    decision_type="hit_management",
                    basis="official_hit_cost_diagnostic",
                    signed_points_impact=-hit_cost,
                    confidence="High",
                    additive_to_total=False,
                    evidence_count=int(pd.to_numeric(me.iloc[0].get("hit_weeks", 0), errors="coerce")),
                    evidence_summary=f"{hit_cost:.1f} official transfer-hit points across {int(me.iloc[0].get('hit_weeks', 0))} hit weeks.",
                    caveat="Diagnostic only because hit cost is already included in transfer package net outcomes.",
                    recommended_focus="Demand a clear package-level upside before taking hits.",
                )
            )
    return rows


def _captaincy_rows(captaincy: pd.DataFrame) -> list[dict[str, object]]:
    if captaincy.empty:
        return []
    delta_best = _numeric(captaincy, "delta_vs_best_starter_extra")
    delta_candidate = _numeric(captaincy, "delta_vs_recommended_candidate_extra")
    missed_best = delta_best[delta_best < 0]
    return [
        _row(
            area="Captaincy: hindsight ceiling",
            decision_type="captaincy",
            basis="delta_vs_best_actual_starter_extra",
            signed_points_impact=float(delta_best.sum()),
            confidence="Medium",
            additive_to_total=True,
            evidence_count=len(captaincy),
            evidence_summary=f"{len(missed_best)} gameweeks below the best actual starter; total delta {delta_best.sum():.1f} points.",
            caveat="Hindsight benchmark. Useful for leak sizing, not a claim that the best actual captain was knowable.",
            recommended_focus="Reduce obvious captaincy misses, but judge process separately from perfect-hindsight ceiling.",
        ),
        _row(
            area="Captaincy: pre-GW process benchmark",
            decision_type="captaincy",
            basis="delta_vs_pre_gw_recommended_candidate_extra",
            signed_points_impact=float(delta_candidate.sum()),
            confidence="Medium",
            additive_to_total=False,
            evidence_count=len(captaincy),
            evidence_summary=f"Actual captains were {delta_candidate.sum():.1f} points versus the pre-GW candidate score benchmark.",
            caveat="Process comparator only; not additive with hindsight captaincy leak.",
            recommended_focus="Use the candidate benchmark to review process rather than chasing last week's haul.",
        ),
    ]


def _benching_rows(benching: pd.DataFrame) -> list[dict[str, object]]:
    if benching.empty:
        return []
    regret = _numeric(benching, "bench_regret_points")
    questionable = int(_numeric(benching, "questionable_benchings").sum())
    high_regret = int(_numeric(benching, "high_regret_benchings").sum())
    return [
        _row(
            area="Benching and starting XI",
            decision_type="benching",
            basis="formation_valid_bench_regret",
            signed_points_impact=-float(regret.sum()),
            confidence="Medium",
            additive_to_total=True,
            evidence_count=int((regret > 0).sum()),
            evidence_summary=(
                f"{regret.sum():.1f} formation-valid bench regret points; "
                f"{questionable} questionable benchings; {high_regret} high-regret benchings."
            ),
            caveat="Bench regret is partly hindsight; questionable benching adds a process filter.",
            recommended_focus="Prioritise starting XI decisions where the benched player also had stronger pre-GW evidence.",
        )
    ]


def _adoption_rows(adoption: pd.DataFrame) -> list[dict[str, object]]:
    if adoption.empty:
        return []
    late_mask = adoption["adoption_timing_category"].isin(["late", "never_owned"])
    missed = _numeric(adoption[late_mask], "estimated_points_after_sample_median_before_my_adoption")
    top_names = ", ".join(adoption.loc[late_mask].head(3)["player_name"].astype(str).tolist())
    return [
        _row(
            area="Late adoption of key players",
            decision_type="player_adoption",
            basis="points_after_sample_median_before_my_adoption",
            signed_points_impact=-float(missed.sum()),
            confidence="Low",
            additive_to_total=True,
            evidence_count=int(late_mask.sum()),
            evidence_summary=f"{int(late_mask.sum())} late/never-owned key players; largest examples include {top_names}.",
            caveat="Hindsight-selected key-player benchmark. It sizes opportunity cost but can overstate what was knowable.",
            recommended_focus="React faster when strong-manager adoption aligns with minutes, role, and position-specific route evidence.",
        )
    ]


def _squad_structure_rows(squad_structure: pd.DataFrame) -> list[dict[str, object]]:
    if squad_structure.empty:
        return []
    me = squad_structure[squad_structure["manager_id"].astype(int).eq(MY_TEAM_ID)]
    if me.empty:
        return []
    row = me.iloc[0]
    bench_percentile = float(pd.to_numeric(row.get("avg_bench_value_share_proxy_sample_percentile", 0), errors="coerce"))
    fixture_percentile = float(pd.to_numeric(row.get("avg_starter_good_next3_fixture_players_sample_percentile", 0), errors="coerce"))
    return [
        _row(
            area="Squad structure",
            decision_type="squad_structure",
            basis="sample_percentile_diagnostic",
            signed_points_impact=0.0,
            confidence="Low",
            additive_to_total=False,
            evidence_count=38,
            evidence_summary=(
                f"Bench value share percentile {bench_percentile:.2f}; starter good-fixture exposure percentile {fixture_percentile:.2f}; "
                f"{int(row.get('my_transfer_group_structure_event_count', 0))} structural transfer events."
            ),
            caveat="No direct point estimate. Value fields are price proxies, not exact purchase prices.",
            recommended_focus="Use as context for final report rather than as a standalone points leak.",
        )
    ]


def _chip_rows(manager_behaviour: pd.DataFrame) -> list[dict[str, object]]:
    if manager_behaviour.empty:
        return []
    me = manager_behaviour[manager_behaviour["manager_id"].astype(int).eq(MY_TEAM_ID)]
    if me.empty:
        return []
    row = me.iloc[0]
    return [
        _row(
            area="Chip timing",
            decision_type="chips",
            basis="availability_only_no_counterfactual",
            signed_points_impact=0.0,
            confidence="Low",
            additive_to_total=False,
            evidence_count=int(row.get("chip_count", 0)),
            evidence_summary=f"Recorded chips: {row.get('chip_names', '')}. No chip counterfactual table exists yet.",
            caveat="Chip timing cannot be scored robustly from current outputs without a counterfactual.",
            recommended_focus="Mention chip timing only qualitatively unless a later sprint adds chip-specific counterfactuals.",
        )
    ]


def build_season_gap_leak_summary(
    *,
    transfer_groups_df: pd.DataFrame,
    transfer_decisions_df: pd.DataFrame,
    captaincy_review_df: pd.DataFrame,
    benching_summary_df: pd.DataFrame,
    adoption_timing_df: pd.DataFrame,
    squad_structure_benchmark_df: pd.DataFrame,
    manager_behaviour_summary_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build a ranked leak/gain summary without double-counting transfer legs."""

    rows: list[dict[str, object]] = []
    rows.extend(_transfer_rows(transfer_groups_df, transfer_decisions_df, manager_behaviour_summary_df))
    rows.extend(_captaincy_rows(captaincy_review_df))
    rows.extend(_benching_rows(benching_summary_df))
    rows.extend(_adoption_rows(adoption_timing_df))
    rows.extend(_squad_structure_rows(squad_structure_benchmark_df))
    rows.extend(_chip_rows(manager_behaviour_summary_df))

    summary = pd.DataFrame(rows)
    if summary.empty:
        return pd.DataFrame(columns=LEAK_SUMMARY_COLUMNS)
    summary = summary.sort_values(
        ["leak_points", "gain_points", "additive_to_total"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    summary.insert(0, "rank", range(1, len(summary) + 1))
    return summary[LEAK_SUMMARY_COLUMNS]


def plot_season_gap_waterfall(leak_summary_df: pd.DataFrame, output_path: str | Path) -> Path:
    """Save a cumulative signed-impact waterfall chart for additive leak rows."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    additive = leak_summary_df[leak_summary_df["additive_to_total"].astype(bool)].copy()
    additive = additive[additive["signed_points_impact"].ne(0)]
    if additive.empty:
        additive = leak_summary_df.head(1).copy()
    additive = additive.sort_values("signed_points_impact")

    labels = additive["area"].astype(str).tolist()
    values = additive["signed_points_impact"].astype(float).tolist()
    starts: list[float] = []
    running_total = 0.0
    for value in values:
        starts.append(running_total)
        running_total += value

    labels_with_total = labels + ["Net estimated gap"]
    starts_with_total = starts + [0.0]
    values_with_total = values + [running_total]
    colours = ["#b23b3b" if value < 0 else "#2f7d32" for value in values] + ["#333333"]

    fig_width = max(10, 1.15 * len(labels_with_total))
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    x_positions = range(len(labels_with_total))
    ax.bar(x_positions, values_with_total, bottom=starts_with_total, color=colours)
    ax.axhline(0, color="#333333", linewidth=0.8)
    ax.set_ylabel("Signed points impact")
    ax.set_title("Season Gap and Leak Summary")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(labels_with_total, rotation=35, ha="right")
    for index, (start, value) in enumerate(zip(starts_with_total, values_with_total)):
        end = start + value
        label_y = end + (8 if value >= 0 else -8)
        va = "bottom" if value >= 0 else "top"
        ax.text(index, label_y, f"{value:+.0f}", ha="center", va=va, fontsize=9)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def validate_season_gap_leak_summary(leak_summary_df: pd.DataFrame, chart_path: str | Path) -> dict[str, object]:
    """Run lightweight validation checks for the leak summary story."""

    missing_columns = sorted(set(LEAK_SUMMARY_COLUMNS) - set(leak_summary_df.columns))
    basis_values = set(leak_summary_df.get("basis", pd.Series(dtype=str)).astype(str))
    has_package_basis = any("package" in value for value in basis_values)
    has_individual_diagnostic = any("individual" in value for value in basis_values)
    evidence_missing = int(leak_summary_df["evidence_summary"].fillna("").eq("").sum()) if "evidence_summary" in leak_summary_df else 0
    decision_types = set(leak_summary_df.get("decision_type", pd.Series(dtype=str)).astype(str))
    return {
        "rows": int(len(leak_summary_df)),
        "missing_columns": missing_columns,
        "areas": sorted(leak_summary_df["area"].dropna().unique()) if "area" in leak_summary_df else [],
        "decision_types": sorted(decision_types),
        "has_package_basis": has_package_basis,
        "has_individual_diagnostic": has_individual_diagnostic,
        "evidence_missing_rows": evidence_missing,
        "chart_exists": Path(chart_path).exists(),
        "output_csv_ready": len(leak_summary_df) > 0 and not missing_columns,
    }
