"""Weekly Fantasy Premier League decision-system orchestration."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Any

import pandas as pd


MY_TEAM_ID = 816200

DECISION_PACK_KEYS = [
    "current_squad_context",
    "transfer_candidate_shortlist",
    "sell_candidate_review",
    "transfer_package_review",
    "captaincy_decision",
    "weekly_summary",
]

SUPPORTED_INPUTS = {
    "candidate_rule_features": ("gameweek", "player_id"),
    "current_squad": ("manager_id", "event", "element", "squad_position", "is_captain", "is_vice_captain"),
    "transfer_candidates": (),
    "sell_candidates": (),
    "transfer_packages": (),
    "captaincy_candidates": (),
}

DEFAULT_CURRENT_SQUAD_PATH = Path("data/processed/my_squad_gameweek.csv")
DEFAULT_CANDIDATE_RULE_FEATURES_PATH = Path("outputs/tables/candidate_rule_features.csv")
DEFAULT_PLAYER_SELECTION_RULES_PATH = Path("outputs/tables/player_selection_rule_candidates.csv")
DEFAULT_MANAGER_TRANSFERS_PATH = Path("data/processed/manager_transfers.csv")
DEFAULT_MANAGER_PICKS_PATH = Path("data/processed/manager_picks.csv")
DEFAULT_TOP_N_SAMPLE_MANAGERS_PATH = Path("data/processed/top_n_sample_managers.csv")
DEFAULT_LEARNED_CANDIDATE_RULES_PATH = Path("outputs/tables/learned_candidate_shortlist_rules.csv")
DEFAULT_LEARNED_SELL_HOLD_RULES_PATH = Path("outputs/tables/learned_sell_hold_rules.csv")
DEFAULT_TRANSFER_RULE_CANDIDATES_PATH = Path("outputs/tables/transfer_rule_candidates.csv")
DEFAULT_OUTPUT_TABLES_DIR = Path("outputs/tables")

LEARNED_RULE_COLUMNS = [
    "rule_id",
    "decision_area",
    "plain_english_rule",
    "sample_size",
    "sample_manager_count",
    "rank_band_coverage",
    "evidence_window",
    "mean_outcome",
    "median_outcome",
    "baseline_outcome",
    "uplift_vs_baseline",
    "confidence",
    "when_to_use",
    "when_to_ignore",
    "risk_of_overfitting",
]

SELL_HOLD_RULE_DEFINITIONS = [
    ("rule_sell_low_minutes", "Low minutes security", "availability"),
    ("rule_sell_weak_position_route", "Weak position-specific route to points", "position_route"),
    ("rule_sell_bad_fixtures", "Weak next-3 fixture outlook", "fixtures"),
    ("rule_sell_weak_team", "Weak team context", "team_strength"),
    ("rule_sell_poor_value", "Poor value within position", "price_value"),
    ("rule_sell_low_sample_ownership", "Low prior ownership among sampled managers", "ownership"),
]


def _require_columns(df: pd.DataFrame, required_columns: list[str] | tuple[str, ...], *, name: str = "dataframe") -> None:
    """Raise a clear error if a dataframe is missing required columns."""

    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"{name} is missing required columns: {missing_columns}")


def _safe_numeric(value: Any, *, default: float = 0.0) -> float:
    """Convert a scalar value to float, returning `default` for null or invalid values."""

    converted = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(converted):
        return float(default)
    return float(converted)


def _load_dataframe(value: Any, *, name: str) -> pd.DataFrame:
    """Load a dataframe from an in-memory dataframe or CSV path."""

    if isinstance(value, pd.DataFrame):
        return value.copy()
    path = Path(value)
    if not path.exists():
        raise FileNotFoundError(f"{name} path does not exist: {path}")
    return pd.read_csv(path)


def _normalise_series(series: pd.Series, *, inverse: bool = False) -> pd.Series:
    """Return a 0-1 min/max score, preserving missing values as neutral."""

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() == 0:
        result = pd.Series(0.5, index=series.index, dtype="float64")
    else:
        numeric = numeric.fillna(numeric.median())
        spread = numeric.max() - numeric.min()
        if spread == 0:
            result = pd.Series(0.5, index=series.index, dtype="float64")
        else:
            result = (numeric - numeric.min()) / spread
    if inverse:
        result = 1 - result
    return result.clip(0, 1)


def _optional_numeric(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    """Return a numeric column or a default-valued series aligned to `df`."""

    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def _price_slot(row: pd.Series) -> str:
    """Classify a player's broad FPL price slot by position."""

    position = str(row.get("player_position_short", row.get("position_short", ""))).upper()
    price = _safe_numeric(row.get("player_price", row.get("price", 0)), default=0.0)
    thresholds = {
        "GKP": (4.5, 5.5),
        "DEF": (4.5, 6.0),
        "MID": (5.5, 8.0),
        "FWD": (6.0, 8.0),
    }
    budget_cutoff, premium_cutoff = thresholds.get(position, (5.0, 8.0))
    if price <= budget_cutoff:
        return "budget"
    if price >= premium_cutoff:
        return "premium"
    return "mid_price"


def _squad_role(row: pd.Series) -> str:
    """Classify a player by their selected squad role for the target gameweek."""

    if bool(row.get("is_captain", False)):
        return "captain"
    if bool(row.get("is_vice_captain", False)):
        return "vice_captain"
    squad_position = int(_safe_numeric(row.get("squad_position", 0), default=0))
    if squad_position <= 11:
        return "starter"
    if squad_position == 12:
        return "first_bench"
    if str(row.get("player_position_short", "")).upper() == "GKP":
        return "bench_goalkeeper"
    return "bench_depth"


def _position_route_score(squad: pd.DataFrame) -> pd.Series:
    """Build a position-aware prior scoring-route score for current squad players."""

    position = squad.get("player_position_short", pd.Series("", index=squad.index)).astype(str).str.upper()
    xgi = _normalise_series(_optional_numeric(squad, "player_xgi_per_90_prior"))
    bps = _normalise_series(_optional_numeric(squad, "player_bps_per_90_prior"))
    defensive = _normalise_series(_optional_numeric(squad, "player_defensive_contribution_per_90_prior"))
    saves = _normalise_series(_optional_numeric(squad, "player_saves_per_90_prior"))
    goals_conceded = _normalise_series(_optional_numeric(squad, "player_goals_conceded_per_90_prior"), inverse=True)
    clean_sheet = _normalise_series(_optional_numeric(squad, "team_clean_sheet_rate_prior"))
    points_per_90 = _normalise_series(_optional_numeric(squad, "player_points_per_90_prior"))

    route = pd.Series(0.0, index=squad.index, dtype="float64")
    gkp = position.eq("GKP")
    defender = position.eq("DEF")
    midfielder = position.eq("MID")
    forward = position.eq("FWD")

    route.loc[gkp] = 0.35 * saves.loc[gkp] + 0.30 * clean_sheet.loc[gkp] + 0.20 * goals_conceded.loc[gkp] + 0.15 * bps.loc[gkp]
    route.loc[defender] = (
        0.35 * clean_sheet.loc[defender]
        + 0.30 * defensive.loc[defender]
        + 0.20 * bps.loc[defender]
        + 0.15 * xgi.loc[defender]
    )
    route.loc[midfielder] = (
        0.35 * xgi.loc[midfielder]
        + 0.25 * defensive.loc[midfielder]
        + 0.20 * points_per_90.loc[midfielder]
        + 0.20 * bps.loc[midfielder]
    )
    route.loc[forward] = 0.55 * xgi.loc[forward] + 0.25 * points_per_90.loc[forward] + 0.20 * bps.loc[forward]
    route.loc[~(gkp | defender | midfielder | forward)] = points_per_90.loc[~(gkp | defender | midfielder | forward)]
    return route.clip(0, 1)


def _candidate_tier(score: float, role_security: float) -> str:
    """Classify a transfer candidate into a practical review tier."""

    if role_security < 0.45:
        return "punt"
    if score >= 0.75:
        return "strong"
    if score >= 0.55:
        return "viable"
    return "avoid"


def _candidate_reason(row: pd.Series) -> str:
    reasons: list[str] = []
    if row["role_security_score"] >= 0.7:
        reasons.append("secure role")
    if row["route_to_points_score"] >= 0.7:
        reasons.append("strong position route")
    if row["fixture_score"] >= 0.65:
        reasons.append("good next-3 fixtures")
    if row["team_strength_score"] >= 0.65:
        reasons.append("strong team context")
    if row["ownership_or_adoption_score"] >= 0.65:
        reasons.append("top-sample ownership signal")
    if row["price_value_score"] >= 0.65:
        reasons.append("good value profile")
    if not reasons:
        reasons.append("borderline profile")
    return "; ".join(reasons)


def _candidate_risk(row: pd.Series) -> str:
    risks: list[str] = []
    if row["role_security_score"] < 0.45:
        risks.append("minutes risk")
    if row["fixture_score"] < 0.35:
        risks.append("fixture risk")
    if row["route_to_points_score"] < 0.35:
        risks.append("weak position route")
    if bool(row.get("is_blank_next3", False)):
        risks.append("blank risk")
    if not risks:
        risks.append("no major pre-GW risk flagged")
    return "; ".join(risks)


def _rank_band_coverage(df: pd.DataFrame) -> str:
    if "rank_band" not in df.columns:
        return "unavailable"
    bands = sorted(str(value) for value in df["rank_band"].dropna().unique())
    return ", ".join(bands) if bands else "unavailable"


def _calibration_confidence(sample_size: int, sample_manager_count: int, uplift: float) -> str:
    if sample_size >= 500 and sample_manager_count >= 100 and abs(uplift) >= 1.0:
        return "High"
    if sample_size >= 150 and sample_manager_count >= 50 and abs(uplift) >= 0.3:
        return "Medium"
    return "Low"


def _overfitting_risk(confidence: str, sample_size: int, rank_band_coverage: str) -> str:
    if confidence == "High" and sample_size >= 500 and "," in rank_band_coverage:
        return "Low: broad sample and consistent uplift, but still historical evidence."
    if confidence == "Medium":
        return "Medium: useful sample-backed signal, but threshold should be applied conservatively."
    return "High: small, narrow, or weak signal; use only as supporting evidence."


def _candidate_rule_text(row: pd.Series) -> str:
    position = row.get("position_short", "all positions")
    rule_name = row.get("rule_name", row.get("rule_id", "this profile"))
    return f"For {position}, shortlist players matching '{rule_name}' when the squad needs that scoring route."


def _candidate_when_to_use(row: pd.Series) -> str:
    family = str(row.get("route_family", "")).lower()
    if family == "ownership":
        return "Use as confirmation that strong managers were already moving toward the player before the deadline."
    if family == "fixtures":
        return "Use when fixture quality is a meaningful reason to spend a transfer, especially over a 3-5 GW horizon."
    if family in {"attacking", "clean_sheet", "defensive_contribution", "goalkeeper_save", "bps_bonus", "position_route"}:
        return "Use when the player's scoring route matches their FPL position and your squad need."
    if family == "availability":
        return "Use as a minimum minutes-security filter before considering upside."
    return "Use as one evidence-backed shortlist signal, not as a standalone transfer reason."


def _candidate_when_to_ignore(row: pd.Series) -> str:
    family = str(row.get("route_family", "")).lower()
    if family == "ownership":
        return "Ignore when ownership is stale, bandwagon-driven, or conflicts with role, fixtures, and squad structure."
    if family == "fixtures":
        return "Ignore when minutes security or scoring route is weak despite the fixture run."
    if family == "attacking":
        return "Ignore for players whose role or position does not actually support attacking returns."
    return "Ignore when team news, rotation risk, price structure, or upcoming blanks make the profile misleading."


def build_learned_candidate_shortlist_rules(
    player_selection_rule_results_df: pd.DataFrame,
    top_n_sample_managers_df: pd.DataFrame,
) -> pd.DataFrame:
    """Convert historical player-selection evidence into next-season shortlist rules."""

    _require_columns(
        player_selection_rule_results_df,
        (
            "rule_id",
            "rule_name",
            "route_family",
            "position_short",
            "sample_size",
            "confidence",
        ),
        name="player_selection_rule_results",
    )
    _require_columns(top_n_sample_managers_df, ("manager_id", "rank_band"), name="top_n_sample_managers")

    sample_manager_count = int(top_n_sample_managers_df["manager_id"].nunique())
    rank_band_coverage = _rank_band_coverage(top_n_sample_managers_df)
    rows: list[dict[str, Any]] = []
    for _, row in player_selection_rule_results_df.iterrows():
        for window in (1, 3, 5):
            mean_column = f"mean_points_next{window}"
            median_column = f"median_points_next{window}"
            baseline_column = f"position_baseline_mean_points_next{window}"
            uplift_column = f"mean_uplift_vs_position_baseline_next{window}"
            if mean_column not in row.index or uplift_column not in row.index:
                continue
            sample_size = int(_safe_numeric(row.get("sample_size"), default=0))
            uplift = _safe_numeric(row.get(uplift_column), default=0.0)
            confidence = str(row.get("confidence", _calibration_confidence(sample_size, sample_manager_count, uplift)))
            rows.append(
                {
                    "rule_id": f"candidate_{row['rule_id']}_{row['position_short']}_next{window}",
                    "decision_area": "candidate_shortlist",
                    "plain_english_rule": _candidate_rule_text(row),
                    "sample_size": sample_size,
                    "sample_manager_count": sample_manager_count,
                    "rank_band_coverage": rank_band_coverage,
                    "evidence_window": f"{window}GW",
                    "mean_outcome": _safe_numeric(row.get(mean_column), default=0.0),
                    "median_outcome": _safe_numeric(row.get(median_column), default=0.0),
                    "baseline_outcome": _safe_numeric(row.get(baseline_column), default=0.0),
                    "uplift_vs_baseline": uplift,
                    "confidence": confidence,
                    "when_to_use": _candidate_when_to_use(row),
                    "when_to_ignore": _candidate_when_to_ignore(row),
                    "risk_of_overfitting": _overfitting_risk(confidence, sample_size, rank_band_coverage),
                }
            )

    output = pd.DataFrame(rows, columns=LEARNED_RULE_COLUMNS)
    if output.empty:
        return output
    return output.sort_values(
        ["confidence", "uplift_vs_baseline", "sample_size"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def _sell_recommendation(score: float, priority_score: float, opportunity_score: float) -> str:
    """Classify a current squad player into a sell, monitor, or hold bucket."""

    if score >= 0.65 and (priority_score < 0.55 or opportunity_score >= 0.15):
        return "sell"
    if score >= 0.45:
        return "monitor"
    return "hold"


def _sell_confidence(score: float, opportunity_score: float) -> str:
    """Assign a simple confidence label to the sell recommendation."""

    if score >= 0.70 or score <= 0.30:
        return "High"
    if score >= 0.55 or opportunity_score >= 0.20:
        return "Medium"
    return "Low"


def _sell_explanation(row: pd.Series) -> str:
    reasons: list[str] = []
    if row["role_security_risk_score"] >= 0.55:
        reasons.append("role security risk")
    if row["position_route_risk_score"] >= 0.55:
        reasons.append("weak position route")
    if row["fixture_risk_score"] >= 0.55:
        reasons.append("weak upcoming fixtures")
    if row["team_context_risk_score"] >= 0.55:
        reasons.append("weak team context")
    if row["price_value_risk_score"] >= 0.55:
        reasons.append("poor value for price slot")
    if row["opportunity_cost_score"] >= 0.15:
        reasons.append(f"same-position alternative gap: {row['best_alternative_name']}")
    if row["squad_role_risk_score"] >= 0.45:
        reasons.append("replaceable squad role")
    if not reasons:
        reasons.append("profile still worth holding")
    return "; ".join(reasons)


def _hold_explanation(row: pd.Series) -> str:
    positives: list[str] = []
    if row["role_security_score"] >= 0.70:
        positives.append("secure role")
    if row["position_route_score"] >= 0.60:
        positives.append("good position route")
    if row["fixture_outlook_score"] >= 0.60:
        positives.append("usable fixtures")
    if row["team_context_score"] >= 0.60:
        positives.append("good team context")
    if row["current_squad_priority_score"] >= 0.70:
        positives.append("high squad priority")
    if not positives:
        positives.append("no single severe sell trigger")
    return "; ".join(positives)


def build_sell_candidate_review(
    current_squad_context_df: pd.DataFrame,
    *,
    transfer_candidate_shortlist_df: pd.DataFrame | None = None,
    target_gw: int | None = None,
    bank: float = 0.0,
) -> pd.DataFrame:
    """Score current squad players as hold, monitor, or sell candidates."""

    _require_columns(
        current_squad_context_df,
        (
            "element",
            "player_web_name",
            "player_position_short",
            "player_price",
            "squad_role",
            "role_security_score",
            "position_route_score",
            "fixture_outlook_score",
            "team_context_score",
            "current_squad_priority_score",
        ),
        name="current_squad_context",
    )
    squad = current_squad_context_df.copy()
    if squad.empty:
        raise ValueError("current_squad_context is empty")

    target_gw_value = int(target_gw) if target_gw is not None else int(_safe_numeric(squad.get("event", pd.Series([0])).iloc[0]))
    bank_float = _safe_numeric(bank, default=0.0)

    price = _optional_numeric(squad, "player_price", default=0.0).replace(0, pd.NA)
    value_proxy = _optional_numeric(squad, "current_squad_priority_score", default=0.0) / price
    squad["price_value_risk_score"] = value_proxy.groupby(squad["player_position_short"]).transform(
        lambda series: _normalise_series(series.fillna(0), inverse=True)
    )

    opportunity = pd.DataFrame(
        {
            "player_position_short": squad["player_position_short"],
            "best_alternative_name": "No clear same-position alternative",
            "best_alternative_score": 0.0,
            "best_alternative_price": pd.NA,
        },
        index=squad.index,
    )
    if transfer_candidate_shortlist_df is not None and not transfer_candidate_shortlist_df.empty:
        _require_columns(
            transfer_candidate_shortlist_df,
            ("web_name", "position_short", "price", "transfer_candidate_score"),
            name="transfer_candidate_shortlist",
        )
        candidates = transfer_candidate_shortlist_df.copy()
        candidates["position_short"] = candidates["position_short"].astype(str).str.upper()
        candidates["price"] = pd.to_numeric(candidates["price"], errors="coerce")
        candidates["transfer_candidate_score"] = pd.to_numeric(
            candidates["transfer_candidate_score"],
            errors="coerce",
        ).fillna(0.0)
        for idx, player in squad.iterrows():
            position = str(player["player_position_short"]).upper()
            affordable_price = _safe_numeric(player["player_price"], default=0.0) + bank_float
            eligible = candidates[
                candidates["position_short"].eq(position)
                & (candidates["price"].isna() | candidates["price"].le(affordable_price))
            ].sort_values("transfer_candidate_score", ascending=False)
            if not eligible.empty:
                best = eligible.iloc[0]
                opportunity.loc[idx, "best_alternative_name"] = str(best["web_name"])
                opportunity.loc[idx, "best_alternative_score"] = float(best["transfer_candidate_score"])
                opportunity.loc[idx, "best_alternative_price"] = best["price"]

    squad["best_alternative_name"] = opportunity["best_alternative_name"]
    squad["best_alternative_score"] = pd.to_numeric(opportunity["best_alternative_score"], errors="coerce").fillna(0.0)
    squad["best_alternative_price"] = pd.to_numeric(opportunity["best_alternative_price"], errors="coerce")
    squad["opportunity_cost_score"] = (
        squad["best_alternative_score"] - _optional_numeric(squad, "current_squad_priority_score", default=0.0)
    ).clip(lower=0, upper=1)

    role_risk_map = {
        "captain": 0.00,
        "vice_captain": 0.05,
        "starter": 0.20,
        "first_bench": 0.45,
        "bench_goalkeeper": 0.35,
        "bench_depth": 0.55,
    }
    squad["squad_role_risk_score"] = squad["squad_role"].map(role_risk_map).fillna(0.30).astype(float)
    squad["role_security_risk_score"] = (1 - _optional_numeric(squad, "role_security_score", default=0.5)).clip(0, 1)
    squad["position_route_risk_score"] = (1 - _optional_numeric(squad, "position_route_score", default=0.5)).clip(0, 1)
    squad["fixture_risk_score"] = (1 - _optional_numeric(squad, "fixture_outlook_score", default=0.5)).clip(0, 1)
    squad["team_context_risk_score"] = (1 - _optional_numeric(squad, "team_context_score", default=0.5)).clip(0, 1)
    squad["sell_risk_score"] = (
        0.22 * squad["role_security_risk_score"]
        + 0.20 * squad["position_route_risk_score"]
        + 0.18 * squad["fixture_risk_score"]
        + 0.15 * squad["team_context_risk_score"]
        + 0.12 * squad["price_value_risk_score"]
        + 0.08 * squad["opportunity_cost_score"]
        + 0.05 * squad["squad_role_risk_score"]
    ).clip(0, 1)

    protected_core = squad["squad_role"].isin(["captain", "vice_captain"]) & squad["current_squad_priority_score"].ge(0.60)
    squad.loc[protected_core, "sell_risk_score"] = (squad.loc[protected_core, "sell_risk_score"] - 0.10).clip(0, 1)

    squad["sell_recommendation"] = [
        _sell_recommendation(score, priority, opportunity_score)
        for score, priority, opportunity_score in zip(
            squad["sell_risk_score"],
            squad["current_squad_priority_score"],
            squad["opportunity_cost_score"],
        )
    ]
    squad["confidence"] = [
        _sell_confidence(score, opportunity_score)
        for score, opportunity_score in zip(squad["sell_risk_score"], squad["opportunity_cost_score"])
    ]
    squad["sell_explanation"] = squad.apply(_sell_explanation, axis=1)
    squad["hold_explanation"] = squad.apply(_hold_explanation, axis=1)
    squad["target_gw"] = target_gw_value

    output_columns = [
        "target_gw",
        "element",
        "player_web_name",
        "player_team_name",
        "player_position_short",
        "player_price",
        "squad_position",
        "squad_role",
        "role_security_score",
        "position_route_score",
        "fixture_outlook_score",
        "team_context_score",
        "current_squad_priority_score",
        "role_security_risk_score",
        "position_route_risk_score",
        "fixture_risk_score",
        "team_context_risk_score",
        "price_value_risk_score",
        "squad_role_risk_score",
        "opportunity_cost_score",
        "best_alternative_name",
        "best_alternative_score",
        "best_alternative_price",
        "sell_risk_score",
        "sell_recommendation",
        "confidence",
        "sell_explanation",
        "hold_explanation",
    ]
    review = squad[[column for column in output_columns if column in squad.columns]].sort_values(
        ["sell_risk_score", "opportunity_cost_score", "squad_position"],
        ascending=[False, False, True],
    )
    return review.reset_index(drop=True)


def _learned_position_evidence(
    learned_rules_df: pd.DataFrame | None,
    *,
    decision_area: str,
) -> pd.DataFrame:
    """Summarise learned-rule evidence by position for weekly application scoring."""

    if learned_rules_df is None or learned_rules_df.empty:
        return pd.DataFrame(
            columns=[
                "position_short",
                f"{decision_area}_learned_uplift",
                f"{decision_area}_learned_sample_size",
                f"{decision_area}_learned_confidence",
            ]
        )
    _require_columns(
        learned_rules_df,
        ("decision_area", "plain_english_rule", "sample_size", "uplift_vs_baseline", "confidence"),
        name=f"{decision_area}_learned_rules",
    )
    rules = learned_rules_df[learned_rules_df["decision_area"].eq(decision_area)].copy()
    if rules.empty:
        return pd.DataFrame()
    extracted = rules["plain_english_rule"].astype(str).str.extract(r"For\s+([A-Z]{3}),", expand=False)
    rules["position_short"] = extracted.fillna("ALL")
    rules["positive_uplift"] = pd.to_numeric(rules["uplift_vs_baseline"], errors="coerce").clip(lower=0)
    confidence_rank = {"Low": 1, "Medium": 2, "High": 3}
    rules["confidence_rank"] = rules["confidence"].map(confidence_rank).fillna(1)
    grouped = (
        rules.groupby("position_short", as_index=False)
        .agg(
            learned_uplift=("positive_uplift", "mean"),
            learned_sample_size=("sample_size", "sum"),
            confidence_rank=("confidence_rank", "max"),
        )
        .rename(
            columns={
                "learned_uplift": f"{decision_area}_learned_uplift",
                "learned_sample_size": f"{decision_area}_learned_sample_size",
            }
        )
    )
    inverse_confidence = {value: key for key, value in confidence_rank.items()}
    grouped[f"{decision_area}_learned_confidence"] = grouped["confidence_rank"].map(inverse_confidence).fillna("Low")
    return grouped.drop(columns=["confidence_rank"])


def _pair_recommendation(is_affordable: bool, score: float, sell_label: str) -> str:
    if not is_affordable:
        return "unaffordable"
    if score >= 0.70 and sell_label in {"sell", "monitor"}:
        return "strong_upgrade"
    if score >= 0.55:
        return "viable_upgrade"
    return "avoid"


def _pair_reason(row: pd.Series) -> str:
    if not bool(row["is_affordable"]):
        return "Unaffordable as a single transfer with current bank"
    reasons: list[str] = []
    if row["buy_score_delta"] > 0.10:
        reasons.append("buy profile is stronger than sell profile")
    if row["fixture_swing_score"] > 0.55:
        reasons.append("fixture swing is positive")
    if row["route_swing_score"] > 0.55:
        reasons.append("route-to-points swing is positive")
    if row["role_security_swing_score"] > 0.55:
        reasons.append("role security improves")
    if row["learned_evidence_score"] > 0.55:
        reasons.append("sampled-cohort rules support the direction")
    if not reasons:
        reasons.append("upgrade case is marginal")
    return "; ".join(reasons)


def build_transfer_pair_review(
    transfer_candidate_shortlist_df: pd.DataFrame,
    sell_candidate_review_df: pd.DataFrame,
    *,
    bank: float = 0.0,
    learned_candidate_rules_df: pd.DataFrame | None = None,
    learned_sell_hold_rules_df: pd.DataFrame | None = None,
    max_pairs: int = 120,
) -> pd.DataFrame:
    """Build affordable same-position buy/sell pairs for single-transfer review."""

    _require_columns(
        transfer_candidate_shortlist_df,
        (
            "target_gw",
            "player_id",
            "web_name",
            "team_name",
            "position_short",
            "price",
            "role_security_score",
            "route_to_points_score",
            "fixture_score",
            "team_strength_score",
            "price_value_score",
            "transfer_candidate_score",
        ),
        name="transfer_candidate_shortlist",
    )
    _require_columns(
        sell_candidate_review_df,
        (
            "target_gw",
            "element",
            "player_web_name",
            "player_position_short",
            "player_price",
            "role_security_score",
            "position_route_score",
            "fixture_outlook_score",
            "team_context_score",
            "current_squad_priority_score",
            "sell_risk_score",
            "sell_recommendation",
        ),
        name="sell_candidate_review",
    )

    bank_float = _safe_numeric(bank, default=0.0)
    buys = transfer_candidate_shortlist_df.copy()
    sells = sell_candidate_review_df.copy()
    buys["position_short"] = buys["position_short"].astype(str).str.upper()
    sells["player_position_short"] = sells["player_position_short"].astype(str).str.upper()

    candidate_evidence = _learned_position_evidence(
        learned_candidate_rules_df,
        decision_area="candidate_shortlist",
    ).rename(columns={"position_short": "position_short"})
    sell_evidence = _learned_position_evidence(
        learned_sell_hold_rules_df,
        decision_area="sell_hold",
    ).rename(columns={"position_short": "player_position_short"})

    if not candidate_evidence.empty:
        buys = buys.merge(candidate_evidence, on="position_short", how="left", validate="many_to_one")
    if not sell_evidence.empty:
        sells = sells.merge(sell_evidence, on="player_position_short", how="left", validate="many_to_one")

    pairs = buys.merge(
        sells,
        left_on=["target_gw", "position_short"],
        right_on=["target_gw", "player_position_short"],
        how="inner",
        suffixes=("_buy", "_sell"),
    )
    if pairs.empty:
        raise ValueError("No same-position buy/sell transfer pairs could be built")

    pairs["available_budget"] = pd.to_numeric(pairs["player_price"], errors="coerce").fillna(0.0) + bank_float
    pairs["is_affordable"] = pd.to_numeric(pairs["price"], errors="coerce").le(pairs["available_budget"])
    pairs["buy_score_delta"] = (
        pd.to_numeric(pairs["transfer_candidate_score"], errors="coerce").fillna(0.0)
        - pd.to_numeric(pairs["current_squad_priority_score"], errors="coerce").fillna(0.0)
    )
    pairs["fixture_swing_raw"] = (
        pd.to_numeric(pairs["fixture_score"], errors="coerce").fillna(0.0)
        - pd.to_numeric(pairs["fixture_outlook_score"], errors="coerce").fillna(0.0)
    )
    pairs["route_swing_raw"] = (
        pd.to_numeric(pairs["route_to_points_score"], errors="coerce").fillna(0.0)
        - pd.to_numeric(pairs["position_route_score"], errors="coerce").fillna(0.0)
    )
    pairs["role_security_swing_raw"] = (
        pd.to_numeric(pairs["role_security_score_buy"], errors="coerce").fillna(0.0)
        - pd.to_numeric(pairs["role_security_score_sell"], errors="coerce").fillna(0.0)
    )
    pairs["team_strength_swing_raw"] = (
        pd.to_numeric(pairs["team_strength_score"], errors="coerce").fillna(0.0)
        - pd.to_numeric(pairs["team_context_score"], errors="coerce").fillna(0.0)
    )
    pairs["value_swing_raw"] = (
        pd.to_numeric(pairs["price_value_score"], errors="coerce").fillna(0.0)
        - (pd.to_numeric(pairs["current_squad_priority_score"], errors="coerce").fillna(0.0) / pd.to_numeric(pairs["player_price"], errors="coerce").replace(0, pd.NA)).fillna(0.0)
    )

    pairs["buy_score_component"] = pairs["buy_score_delta"].add(1).div(2).clip(0, 1)
    pairs["fixture_swing_score"] = pairs["fixture_swing_raw"].add(1).div(2).clip(0, 1)
    pairs["route_swing_score"] = pairs["route_swing_raw"].add(1).div(2).clip(0, 1)
    pairs["role_security_swing_score"] = pairs["role_security_swing_raw"].add(1).div(2).clip(0, 1)
    pairs["team_strength_swing_score"] = pairs["team_strength_swing_raw"].add(1).div(2).clip(0, 1)
    pairs["value_swing_score"] = _normalise_series(pairs["value_swing_raw"])

    candidate_uplift = pd.to_numeric(
        pairs.get("candidate_shortlist_learned_uplift", pd.Series(0.0, index=pairs.index)),
        errors="coerce",
    ).fillna(0.0)
    sell_uplift = pd.to_numeric(
        pairs.get("sell_hold_learned_uplift", pd.Series(0.0, index=pairs.index)),
        errors="coerce",
    ).fillna(0.0)
    pairs["learned_candidate_uplift"] = candidate_uplift
    pairs["learned_sell_hold_uplift"] = sell_uplift
    pairs["learned_evidence_score"] = _normalise_series(candidate_uplift + sell_uplift)
    pairs["upgrade_score"] = (
        0.22 * pairs["buy_score_component"]
        + 0.18 * pairs["fixture_swing_score"]
        + 0.18 * pairs["route_swing_score"]
        + 0.14 * pairs["role_security_swing_score"]
        + 0.10 * pairs["team_strength_swing_score"]
        + 0.08 * pairs["value_swing_score"]
        + 0.10 * pairs["learned_evidence_score"]
    ).clip(0, 1)
    pairs.loc[~pairs["is_affordable"], "upgrade_score"] = 0.0
    pairs["recommendation"] = [
        _pair_recommendation(affordable, score, sell_label)
        for affordable, score, sell_label in zip(
            pairs["is_affordable"],
            pairs["upgrade_score"],
            pairs["sell_recommendation"],
        )
    ]
    pairs["reason_summary"] = pairs.apply(_pair_reason, axis=1)

    output = pd.DataFrame(
        {
            "target_gw": pairs["target_gw"],
            "sell_player_id": pairs["element"],
            "sell_player_name": pairs["player_web_name"],
            "sell_position": pairs["player_position_short"],
            "sell_price": pairs["player_price"],
            "sell_recommendation": pairs["sell_recommendation"],
            "sell_risk_score": pairs["sell_risk_score"],
            "buy_player_id": pairs["player_id"],
            "buy_player_name": pairs["web_name"],
            "buy_team_name": pairs["team_name"],
            "buy_position": pairs["position_short"],
            "buy_price": pairs["price"],
            "available_budget": pairs["available_budget"],
            "is_affordable": pairs["is_affordable"],
            "buy_score_delta": pairs["buy_score_delta"],
            "fixture_swing_score": pairs["fixture_swing_score"],
            "route_swing_score": pairs["route_swing_score"],
            "role_security_swing_score": pairs["role_security_swing_score"],
            "team_strength_swing_score": pairs["team_strength_swing_score"],
            "value_swing_score": pairs["value_swing_score"],
            "learned_candidate_uplift": pairs["learned_candidate_uplift"],
            "learned_sell_hold_uplift": pairs["learned_sell_hold_uplift"],
            "learned_evidence_score": pairs["learned_evidence_score"],
            "upgrade_score": pairs["upgrade_score"],
            "recommendation": pairs["recommendation"],
            "reason_summary": pairs["reason_summary"],
        }
    )
    output = output.sort_values(
        ["upgrade_score", "is_affordable", "sell_risk_score", "buy_score_delta"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    if max_pairs > 0:
        output = output.head(int(max_pairs)).copy()
    return output


def _historical_package_modifier(
    transfer_rule_candidates_df: pd.DataFrame | None,
    *,
    transfer_count: int,
    hit_cost: int,
    spent_budget: bool,
    released_budget: bool,
    fixture_improvement_majority: bool,
    window: int,
) -> float:
    """Return a conservative historical uplift modifier for a package profile."""

    if transfer_rule_candidates_df is None or transfer_rule_candidates_df.empty:
        return 0.0
    required = ("rule_level", "rule_id", f"mean_uplift_vs_baseline_next{window}")
    if any(column not in transfer_rule_candidates_df.columns for column in required):
        return 0.0
    rules = transfer_rule_candidates_df[transfer_rule_candidates_df["rule_level"].eq("transfer_package")].copy()
    if rules.empty:
        return 0.0

    matched_rule_ids: list[str] = []
    if transfer_count > 1:
        matched_rule_ids.append("package_is_multi_transfer")
    if hit_cost > 0:
        matched_rule_ids.append("package_is_hit")
    if spent_budget:
        matched_rule_ids.append("package_spent_budget")
    if released_budget:
        matched_rule_ids.append("package_released_budget")
    if fixture_improvement_majority:
        matched_rule_ids.append("package_fixture_improvement_majority")

    if not matched_rule_ids:
        return 0.0
    matched = rules[rules["rule_id"].isin(matched_rule_ids)]
    if matched.empty:
        return 0.0
    uplift = pd.to_numeric(matched[f"mean_uplift_vs_baseline_next{window}"], errors="coerce").dropna()
    if uplift.empty:
        return 0.0
    return float(uplift.mean())


def _hit_recommendation(transfer_count: int, hit_cost: int, net_next1: float, net_next3: float, net_next5: float) -> str:
    if transfer_count == 0:
        return "roll_transfer"
    if hit_cost == 0:
        return "use_free_transfer" if net_next5 > 0 else "hold"
    if hit_cost == 4 and net_next1 >= -1 and net_next3 > 0 and net_next5 >= 4:
        return "consider_minus_4"
    if hit_cost == 8 and net_next1 >= 0 and net_next3 >= 4 and net_next5 >= 12:
        return "consider_minus_8"
    if hit_cost == 12 and net_next1 >= 0 and net_next3 >= 8 and net_next5 >= 20:
        return "consider_minus_12"
    return "avoid_hit"


def _package_confidence(row: dict[str, Any]) -> str:
    if row["hit_cost"] == 0 and row["net_package_value_next5"] > 2:
        return "Medium"
    if row["hit_cost"] == 4 and row["net_package_value_next5"] >= 4 and row["net_package_value_next3"] > 1:
        return "Medium"
    if row["hit_cost"] >= 8 and row["net_package_value_next5"] >= row["hit_cost"]:
        return "Low"
    if row["recommendation"] in {"roll_transfer", "avoid_hit"}:
        return "Medium"
    return "Low"


def _package_reason(row: dict[str, Any]) -> str:
    if row["transfer_count"] == 0:
        return "No-transfer baseline keeps flexibility and avoids unnecessary hit cost"
    reasons: list[str] = []
    if row["hit_cost"] > 0:
        reasons.append(f"package carries a -{row['hit_cost']} hit")
    else:
        reasons.append("covered by available free transfers")
    if row["net_package_value_next5"] > 0:
        reasons.append("5GW net payoff proxy is positive")
    else:
        reasons.append("5GW net payoff proxy does not clear cost")
    if row["historical_modifier_next5"] < 0:
        reasons.append("historical package evidence applies a conservative penalty")
    elif row["historical_modifier_next5"] > 0:
        reasons.append("historical package evidence supports this package type")
    if row["duplicate_check_passed"]:
        reasons.append("no duplicate sold or bought players")
    return "; ".join(reasons)


def build_transfer_package_review(
    transfer_pair_review_df: pd.DataFrame,
    *,
    free_transfers: int = 1,
    transfer_rule_candidates_df: pd.DataFrame | None = None,
    max_pairs_considered: int = 24,
    max_packages_per_size: int = 20,
) -> pd.DataFrame:
    """Build package-level transfer and hit justification scenarios."""

    _require_columns(
        transfer_pair_review_df,
        (
            "target_gw",
            "sell_player_id",
            "sell_player_name",
            "buy_player_id",
            "buy_player_name",
            "buy_price",
            "sell_price",
            "is_affordable",
            "fixture_swing_score",
            "route_swing_score",
            "learned_evidence_score",
            "upgrade_score",
        ),
        name="transfer_pair_review",
    )
    free_transfer_count = int(_safe_numeric(free_transfers, default=1))
    if free_transfer_count < 0:
        raise ValueError("free_transfers must be zero or greater")

    pairs = transfer_pair_review_df.copy()
    pairs = pairs[pairs["is_affordable"].astype(bool)].copy()
    pairs = pairs[~pairs["recommendation"].eq("unaffordable")].copy() if "recommendation" in pairs.columns else pairs
    if pairs.empty:
        raise ValueError("No affordable transfer pairs available for package review")
    pairs = pairs.sort_values("upgrade_score", ascending=False).head(int(max_pairs_considered)).reset_index(drop=True)
    target_gw = int(_safe_numeric(pairs["target_gw"].iloc[0], default=0))

    rows: list[dict[str, Any]] = [
        {
            "target_gw": target_gw,
            "package_id": f"gw{target_gw:02d}_no_transfer",
            "transfer_count": 0,
            "sold_player_ids": "",
            "sold_player_names": "",
            "bought_player_ids": "",
            "bought_player_names": "",
            "gross_package_score": 0.0,
            "package_upgrade_score": 0.0,
            "gross_expected_gain_next1": 0.0,
            "gross_expected_gain_next3": 0.0,
            "gross_expected_gain_next5": 0.0,
            "hit_cost": 0,
            "hit_scenario": "0",
            "net_package_value_next1": 0.0,
            "net_package_value_next3": 0.0,
            "net_package_value_next5": 0.0,
            "historical_modifier_next1": 0.0,
            "historical_modifier_next3": 0.0,
            "historical_modifier_next5": 0.0,
            "recommendation": "roll_transfer",
            "confidence": "Medium",
            "duplicate_check_passed": True,
            "reason_summary": "No-transfer baseline keeps flexibility and avoids unnecessary hit cost",
        }
    ]

    for transfer_count in range(1, 5):
        package_rows: list[dict[str, Any]] = []
        for combo in combinations(pairs.index, transfer_count):
            package = pairs.loc[list(combo)].copy()
            if package["sell_player_id"].nunique() != transfer_count:
                continue
            if package["buy_player_id"].nunique() != transfer_count:
                continue

            hit_cost = max(0, transfer_count - free_transfer_count) * 4
            spent_budget = float(package["buy_price"].sum()) > float(package["sell_price"].sum())
            released_budget = float(package["buy_price"].sum()) < float(package["sell_price"].sum())
            fixture_improvement_majority = pd.to_numeric(
                package["fixture_swing_score"],
                errors="coerce",
            ).fillna(0.5).gt(0.55).mean() >= 0.5

            gross_score = float(package["upgrade_score"].sum())
            average_score = float(package["upgrade_score"].mean())
            package_upgrade_score = min(1.0, 0.70 * average_score + 0.30 * min(gross_score / max(transfer_count, 1), 1.0))

            base_next1 = float((package["upgrade_score"] * 3.0 + package["learned_evidence_score"]).sum())
            base_next3 = float((package["upgrade_score"] * 7.0 + package["learned_evidence_score"] * 2.0).sum())
            base_next5 = float((package["upgrade_score"] * 11.0 + package["learned_evidence_score"] * 3.0).sum())
            historical_next1 = _historical_package_modifier(
                transfer_rule_candidates_df,
                transfer_count=transfer_count,
                hit_cost=hit_cost,
                spent_budget=spent_budget,
                released_budget=released_budget,
                fixture_improvement_majority=fixture_improvement_majority,
                window=1,
            )
            historical_next3 = _historical_package_modifier(
                transfer_rule_candidates_df,
                transfer_count=transfer_count,
                hit_cost=hit_cost,
                spent_budget=spent_budget,
                released_budget=released_budget,
                fixture_improvement_majority=fixture_improvement_majority,
                window=3,
            )
            historical_next5 = _historical_package_modifier(
                transfer_rule_candidates_df,
                transfer_count=transfer_count,
                hit_cost=hit_cost,
                spent_budget=spent_budget,
                released_budget=released_budget,
                fixture_improvement_majority=fixture_improvement_majority,
                window=5,
            )
            gross_next1 = base_next1 + 0.25 * historical_next1
            gross_next3 = base_next3 + 0.25 * historical_next3
            gross_next5 = base_next5 + 0.25 * historical_next5
            row = {
                "target_gw": target_gw,
                "package_id": f"gw{target_gw:02d}_{transfer_count}t_{'_'.join(package['buy_player_id'].astype(int).astype(str))}",
                "transfer_count": transfer_count,
                "sold_player_ids": ",".join(package["sell_player_id"].astype(int).astype(str)),
                "sold_player_names": "; ".join(package["sell_player_name"].astype(str)),
                "bought_player_ids": ",".join(package["buy_player_id"].astype(int).astype(str)),
                "bought_player_names": "; ".join(package["buy_player_name"].astype(str)),
                "gross_package_score": gross_score,
                "package_upgrade_score": package_upgrade_score,
                "gross_expected_gain_next1": gross_next1,
                "gross_expected_gain_next3": gross_next3,
                "gross_expected_gain_next5": gross_next5,
                "hit_cost": hit_cost,
                "hit_scenario": f"-{hit_cost}" if hit_cost > 0 else "0",
                "net_package_value_next1": gross_next1 - hit_cost,
                "net_package_value_next3": gross_next3 - hit_cost,
                "net_package_value_next5": gross_next5 - hit_cost,
                "historical_modifier_next1": historical_next1,
                "historical_modifier_next3": historical_next3,
                "historical_modifier_next5": historical_next5,
                "duplicate_check_passed": True,
            }
            row["recommendation"] = _hit_recommendation(
                transfer_count,
                hit_cost,
                row["net_package_value_next1"],
                row["net_package_value_next3"],
                row["net_package_value_next5"],
            )
            row["confidence"] = _package_confidence(row)
            row["reason_summary"] = _package_reason(row)
            package_rows.append(row)

        package_rows = sorted(
            package_rows,
            key=lambda item: (item["net_package_value_next5"], item["net_package_value_next3"], item["package_upgrade_score"]),
            reverse=True,
        )[: int(max_packages_per_size)]
        rows.extend(package_rows)

    output = pd.DataFrame(rows)
    if output.empty:
        return output
    return output.sort_values(
        ["net_package_value_next5", "net_package_value_next3", "transfer_count"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def save_weekly_hit_payoff_curve(
    transfer_package_review_df: pd.DataFrame,
    chart_path: str | Path,
) -> Path:
    """Save a simple best-package payoff curve by hit cost."""

    _require_columns(
        transfer_package_review_df,
        ("hit_cost", "net_package_value_next1", "net_package_value_next3", "net_package_value_next5"),
        name="transfer_package_review",
    )
    from PIL import Image, ImageDraw

    chart_path = Path(chart_path)
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    best = (
        transfer_package_review_df.groupby("hit_cost", as_index=False)[
            ["net_package_value_next1", "net_package_value_next3", "net_package_value_next5"]
        ]
        .max()
        .sort_values("hit_cost")
    )
    width, height = 900, 520
    margin_left, margin_right, margin_top, margin_bottom = 80, 40, 50, 80
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    x_values = best["hit_cost"].astype(float).tolist()
    y_columns = [
        ("net_package_value_next1", "1GW", (32, 99, 155)),
        ("net_package_value_next3", "3GW", (50, 140, 90)),
        ("net_package_value_next5", "5GW", (190, 95, 40)),
    ]
    y_values = []
    for column, _, _ in y_columns:
        y_values.extend(pd.to_numeric(best[column], errors="coerce").fillna(0).tolist())
    y_values.append(0.0)
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    if x_min == x_max:
        x_max = x_min + 1
    if y_min == y_max:
        y_max = y_min + 1
    y_pad = (y_max - y_min) * 0.12
    y_min -= y_pad
    y_max += y_pad

    plot_left = margin_left
    plot_right = width - margin_right
    plot_top = margin_top
    plot_bottom = height - margin_bottom

    def x_to_px(value: float) -> int:
        return int(plot_left + (value - x_min) / (x_max - x_min) * (plot_right - plot_left))

    def y_to_px(value: float) -> int:
        return int(plot_bottom - (value - y_min) / (y_max - y_min) * (plot_bottom - plot_top))

    draw.text((margin_left, 18), "Weekly hit payoff curve", fill=(0, 0, 0))
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill=(0, 0, 0), width=2)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=(0, 0, 0), width=2)
    zero_y = y_to_px(0.0)
    draw.line((plot_left, zero_y, plot_right, zero_y), fill=(160, 160, 160), width=1)
    for hit_cost in x_values:
        x = x_to_px(hit_cost)
        draw.line((x, plot_bottom, x, plot_bottom + 6), fill=(0, 0, 0), width=1)
        draw.text((x - 8, plot_bottom + 12), str(int(hit_cost)), fill=(0, 0, 0))
    draw.text((plot_left + 280, height - 35), "Hit cost", fill=(0, 0, 0))
    draw.text((10, 240), "Best net payoff proxy", fill=(0, 0, 0))

    legend_x = width - 170
    legend_y = 20
    for idx, (column, label, color) in enumerate(y_columns):
        values = pd.to_numeric(best[column], errors="coerce").fillna(0).tolist()
        points = [(x_to_px(x), y_to_px(y)) for x, y in zip(x_values, values)]
        if len(points) > 1:
            draw.line(points, fill=color, width=3)
        for point in points:
            x, y = point
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
        draw.rectangle((legend_x, legend_y + idx * 22, legend_x + 14, legend_y + 14 + idx * 22), fill=color)
        draw.text((legend_x + 20, legend_y + idx * 22), label, fill=(0, 0, 0))

    image.save(chart_path)
    return chart_path


def _add_sell_hold_rule_flags(features: pd.DataFrame) -> pd.DataFrame:
    output = features.copy()
    output["position_short"] = output["position_short"].astype(str).str.upper()
    group_keys = ["gameweek", "position_short"]

    output["value_per_price_prior"] = (
        _optional_numeric(output, "feature_player_points_per_90_prior", default=0.0)
        / _optional_numeric(output, "feature_player_price", default=0.0).replace(0, pd.NA)
    )
    threshold_columns = {
        "q25_route": ("feature_position_relevant_route_score", 0.25),
        "q25_team": ("feature_team_points_per_fixture_prior", 0.25),
        "q25_value": ("value_per_price_prior", 0.25),
        "q25_ownership": ("feature_ownership_percent_prior", 0.25),
        "q75_fixture": ("feature_fixture_fpl_difficulty_mean_next3", 0.75),
    }
    for output_column, (source_column, quantile) in threshold_columns.items():
        if source_column not in output.columns:
            output[output_column] = pd.NA
            continue
        output[output_column] = output.groupby(group_keys)[source_column].transform(lambda series: series.quantile(quantile))

    output["rule_sell_low_minutes"] = (
        _optional_numeric(output, "feature_player_minutes_roll5_mean_prior", default=0.0).lt(45)
        | _optional_numeric(output, "feature_player_start_rate_prior", default=0.0).lt(0.50)
    )
    output["rule_sell_weak_position_route"] = _optional_numeric(
        output,
        "feature_position_relevant_route_score",
        default=0.0,
    ).le(pd.to_numeric(output["q25_route"], errors="coerce").fillna(-1))
    output["rule_sell_bad_fixtures"] = (
        _optional_numeric(output, "feature_fixture_blank_next3", default=0.0).gt(0)
        | _optional_numeric(output, "feature_fixture_fpl_difficulty_mean_next3", default=3.0).ge(
            pd.to_numeric(output["q75_fixture"], errors="coerce").fillna(4.0)
        )
    )
    output["rule_sell_weak_team"] = _optional_numeric(
        output,
        "feature_team_points_per_fixture_prior",
        default=0.0,
    ).le(pd.to_numeric(output["q25_team"], errors="coerce").fillna(-1))
    output["rule_sell_poor_value"] = pd.to_numeric(output["value_per_price_prior"], errors="coerce").fillna(0.0).le(
        pd.to_numeric(output["q25_value"], errors="coerce").fillna(-1)
    )
    output["rule_sell_low_sample_ownership"] = (
        output.get("feature_ownership_available", pd.Series(False, index=output.index)).fillna(False).astype(bool)
        & _optional_numeric(output, "feature_ownership_percent_prior", default=0.0).le(
            pd.to_numeric(output["q25_ownership"], errors="coerce").fillna(-1)
        )
    )

    for rule_id, _, _ in SELL_HOLD_RULE_DEFINITIONS:
        output[rule_id] = output[rule_id].fillna(False).astype(bool)
    return output


def _sell_rule_text(rule_name: str, position: str) -> str:
    return f"For {position}, treat '{rule_name}' as a sell/replaceability warning only when a credible replacement exists."


def _sell_when_to_use(route_family: str) -> str:
    if route_family == "availability":
        return "Use when the player is losing starts or cannot reliably reach appearance/minutes points."
    if route_family == "fixtures":
        return "Use when the next 3 GWs materially reduce the player's expected scoring route."
    if route_family == "ownership":
        return "Use as a weak confirmation that sampled managers were not broadly holding the player."
    if route_family == "price_value":
        return "Use when the player's price slot can be redeployed into a stronger role or route."
    return "Use when the player's weakness matches their FPL position and there is an evidence-backed replacement path."


def _sell_when_to_ignore(route_family: str) -> str:
    if route_family == "availability":
        return "Ignore if reliable team news suggests the minutes issue has already reversed."
    if route_family == "fixtures":
        return "Ignore if the player has a durable scoring route that is less fixture-sensitive."
    if route_family == "ownership":
        return "Ignore when low ownership reflects differential value rather than weak process."
    return "Ignore when selling would break squad structure, waste transfers, or fund only a marginal upgrade."


def build_learned_sell_hold_rules(
    candidate_rule_features_df: pd.DataFrame,
    manager_transfers_df: pd.DataFrame,
    manager_picks_df: pd.DataFrame,
    top_n_sample_managers_df: pd.DataFrame,
) -> pd.DataFrame:
    """Learn sell/hold evidence from sampled-manager transfer-out behaviour."""

    _require_columns(
        candidate_rule_features_df,
        ("gameweek", "player_id", "position_short", "outcome_points_next1", "outcome_points_next3", "outcome_points_next5"),
        name="candidate_rule_features",
    )
    _require_columns(manager_transfers_df, ("manager_id", "event", "element_out"), name="manager_transfers")
    _require_columns(manager_picks_df, ("manager_id", "event", "element"), name="manager_picks")
    _require_columns(top_n_sample_managers_df, ("manager_id", "rank_band"), name="top_n_sample_managers")

    sample = top_n_sample_managers_df[["manager_id", "rank_band"]].dropna(subset=["manager_id"]).copy()
    sample["manager_id"] = sample["manager_id"].astype(int)
    sample_ids = set(sample["manager_id"])
    rank_band_by_manager = sample.set_index("manager_id")["rank_band"].to_dict()

    features = candidate_rule_features_df.copy()
    features["gameweek"] = pd.to_numeric(features["gameweek"], errors="coerce").astype("Int64")
    features["player_id"] = pd.to_numeric(features["player_id"], errors="coerce").astype("Int64")
    features = _add_sell_hold_rule_flags(features)
    feature_columns = [
        column
        for column in features.columns
        if column.startswith("feature_")
        or column.startswith("outcome_")
        or column.startswith("rule_sell_")
        or column in {"gameweek", "player_id", "position_short"}
    ]
    features = features[feature_columns].dropna(subset=["gameweek", "player_id"]).copy()

    transfers = manager_transfers_df[manager_transfers_df["manager_id"].astype(int).isin(sample_ids)].copy()
    transfers["manager_id"] = transfers["manager_id"].astype(int)
    transfers["event"] = pd.to_numeric(transfers["event"], errors="coerce").astype("Int64")
    transfers["element_out"] = pd.to_numeric(transfers["element_out"], errors="coerce").astype("Int64")
    transfers = transfers.dropna(subset=["event", "element_out"]).copy()
    transfers = transfers.merge(
        features,
        left_on=["event", "element_out"],
        right_on=["gameweek", "player_id"],
        how="inner",
        validate="many_to_one",
    )
    transfers["rank_band"] = transfers["manager_id"].map(rank_band_by_manager)
    transfers["decision"] = "sold"

    sold_keys = transfers[["manager_id", "event", "element_out"]].rename(columns={"element_out": "element"})
    sold_keys["was_sold"] = True
    holds = manager_picks_df[manager_picks_df["manager_id"].astype(int).isin(sample_ids)].copy()
    holds["manager_id"] = holds["manager_id"].astype(int)
    holds["event"] = pd.to_numeric(holds["event"], errors="coerce").astype("Int64")
    holds["element"] = pd.to_numeric(holds["element"], errors="coerce").astype("Int64")
    holds = holds.dropna(subset=["event", "element"]).copy()
    holds = holds.merge(sold_keys, on=["manager_id", "event", "element"], how="left")
    holds = holds[~holds["was_sold"].eq(True)].copy()
    holds = holds.merge(
        features,
        left_on=["event", "element"],
        right_on=["gameweek", "player_id"],
        how="inner",
        validate="many_to_one",
    )
    holds["rank_band"] = holds["manager_id"].map(rank_band_by_manager)
    holds["decision"] = "held"

    rows: list[dict[str, Any]] = []
    for rule_id, rule_name, route_family in SELL_HOLD_RULE_DEFINITIONS:
        if rule_id not in transfers.columns or rule_id not in holds.columns:
            continue
        for position in sorted(features["position_short"].dropna().unique()):
            sold_position = transfers[transfers["position_short"].eq(position)]
            hold_position = holds[holds["position_short"].eq(position)]
            sold_rule = sold_position[sold_position[rule_id]]
            hold_rule = hold_position[hold_position[rule_id]]
            sample_size = int(len(sold_rule))
            if sample_size < 30:
                continue
            sample_manager_count = int(sold_rule["manager_id"].nunique())
            rank_band_coverage = _rank_band_coverage(sold_rule)
            for window in (1, 3, 5):
                outcome_column = f"outcome_points_next{window}"
                if outcome_column not in sold_rule.columns:
                    continue
                baseline_rows = hold_rule if len(hold_rule) >= 30 else hold_position
                mean_outcome = pd.to_numeric(sold_rule[outcome_column], errors="coerce").mean()
                median_outcome = pd.to_numeric(sold_rule[outcome_column], errors="coerce").median()
                baseline_outcome = pd.to_numeric(baseline_rows[outcome_column], errors="coerce").mean()
                uplift = baseline_outcome - mean_outcome
                confidence = _calibration_confidence(sample_size, sample_manager_count, uplift)
                rows.append(
                    {
                        "rule_id": f"sell_hold_{rule_id}_{position}_next{window}",
                        "decision_area": "sell_hold",
                        "plain_english_rule": _sell_rule_text(rule_name, position),
                        "sample_size": sample_size,
                        "sample_manager_count": sample_manager_count,
                        "rank_band_coverage": rank_band_coverage,
                        "evidence_window": f"{window}GW",
                        "mean_outcome": float(mean_outcome),
                        "median_outcome": float(median_outcome),
                        "baseline_outcome": float(baseline_outcome),
                        "uplift_vs_baseline": float(uplift),
                        "confidence": confidence,
                        "when_to_use": _sell_when_to_use(route_family),
                        "when_to_ignore": _sell_when_to_ignore(route_family),
                        "risk_of_overfitting": _overfitting_risk(confidence, sample_size, rank_band_coverage),
                    }
                )

    output = pd.DataFrame(rows, columns=LEARNED_RULE_COLUMNS)
    if output.empty:
        return output
    return output.sort_values(
        ["confidence", "uplift_vs_baseline", "sample_size"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def build_transfer_candidate_shortlist(
    candidate_rule_features_df: pd.DataFrame,
    *,
    target_gw: int,
    current_squad_context_df: pd.DataFrame | None = None,
    include_owned: bool = False,
    max_candidates: int = 80,
) -> pd.DataFrame:
    """Build a leakage-safe transfer candidate shortlist for one target gameweek."""

    _require_columns(
        candidate_rule_features_df,
        ("gameweek", "player_id", "web_name", "team_name", "position_short", "feature_player_price"),
        name="candidate_rule_features",
    )
    candidates = candidate_rule_features_df.copy()
    candidates["gameweek"] = pd.to_numeric(candidates["gameweek"], errors="coerce").astype("Int64")
    candidates = candidates[candidates["gameweek"].eq(int(target_gw))].copy()
    if candidates.empty:
        raise ValueError(f"No candidate feature rows found for target_gw={target_gw}")

    if not include_owned and current_squad_context_df is not None and not current_squad_context_df.empty:
        _require_columns(current_squad_context_df, ("element",), name="current_squad_context")
        owned_ids = set(pd.to_numeric(current_squad_context_df["element"], errors="coerce").dropna().astype(int))
        candidates = candidates[~pd.to_numeric(candidates["player_id"], errors="coerce").astype("Int64").isin(owned_ids)].copy()

    if candidates.empty:
        raise ValueError("No transfer candidates remain after owned-player exclusion")

    role_security = (
        _optional_numeric(candidates, "feature_player_start_rate_prior")
        + _optional_numeric(candidates, "feature_player_appearance_rate_prior")
        + _optional_numeric(candidates, "feature_player_sixty_plus_rate_prior")
    ) / 3
    candidates["role_security_score"] = role_security.clip(0, 1)
    candidates["route_to_points_score"] = _optional_numeric(
        candidates,
        "feature_position_relevant_route_score",
        default=0.0,
    ).clip(0, 1)
    fixture_base = _normalise_series(
        _optional_numeric(candidates, "feature_fixture_fpl_difficulty_mean_next3", default=3.0),
        inverse=True,
    )
    blank_penalty = _optional_numeric(candidates, "feature_fixture_blank_next3", default=0.0).clip(0, 1) * 0.25
    double_bonus = _optional_numeric(candidates, "feature_fixture_double_next3", default=0.0).clip(0, 1) * 0.15
    candidates["fixture_score"] = (fixture_base - blank_penalty + double_bonus).clip(0, 1)
    candidates["team_strength_score"] = (
        _normalise_series(_optional_numeric(candidates, "feature_team_points_per_fixture_prior"))
        + _normalise_series(_optional_numeric(candidates, "feature_team_goals_for_per_fixture_prior"))
        + _normalise_series(_optional_numeric(candidates, "feature_team_clean_sheet_rate_prior"))
    ) / 3
    price = _optional_numeric(candidates, "feature_player_price", default=0.0).replace(0, pd.NA)
    value_proxy = _optional_numeric(candidates, "feature_player_points_per_90_prior", default=0.0) / price
    candidates["price_value_score"] = value_proxy.groupby(candidates["position_short"]).transform(
        lambda series: _normalise_series(series.fillna(0))
    )
    candidates["ownership_or_adoption_score"] = _optional_numeric(
        candidates,
        "feature_ownership_percent_prior",
        default=0.0,
    ).clip(0, 100) / 100
    candidates["transfer_candidate_score"] = (
        0.25 * candidates["role_security_score"]
        + 0.25 * candidates["route_to_points_score"]
        + 0.20 * candidates["fixture_score"]
        + 0.15 * candidates["team_strength_score"]
        + 0.10 * candidates["price_value_score"]
        + 0.05 * candidates["ownership_or_adoption_score"]
    ).clip(0, 1)
    candidates["is_blank_next3"] = _optional_numeric(candidates, "feature_fixture_blank_next3", default=0.0).gt(0)
    candidates["candidate_tier"] = [
        _candidate_tier(score, role)
        for score, role in zip(candidates["transfer_candidate_score"], candidates["role_security_score"])
    ]

    punt_keep = candidates["role_security_score"].lt(0.45) & candidates["route_to_points_score"].ge(0.75)
    candidates = candidates[candidates["role_security_score"].ge(0.45) | punt_keep].copy()
    if candidates.empty:
        raise ValueError("No transfer candidates passed role-security or punt filters")

    candidates["reason_summary"] = candidates.apply(_candidate_reason, axis=1)
    candidates["risk_summary"] = candidates.apply(_candidate_risk, axis=1)
    candidates["target_gw"] = int(target_gw)
    candidates["price"] = _optional_numeric(candidates, "feature_player_price")

    output_columns = [
        "target_gw",
        "player_id",
        "web_name",
        "team_name",
        "position_short",
        "price",
        "role_security_score",
        "route_to_points_score",
        "fixture_score",
        "team_strength_score",
        "price_value_score",
        "ownership_or_adoption_score",
        "transfer_candidate_score",
        "candidate_tier",
        "reason_summary",
        "risk_summary",
    ]
    shortlist = candidates[output_columns].sort_values(
        ["transfer_candidate_score", "role_security_score", "route_to_points_score"],
        ascending=[False, False, False],
    )
    if max_candidates > 0:
        shortlist = shortlist.head(int(max_candidates))
    return shortlist.reset_index(drop=True)


def build_current_squad_context(
    current_squad_df: pd.DataFrame,
    *,
    target_gw: int,
    manager_id: int = MY_TEAM_ID,
) -> pd.DataFrame:
    """Build the leakage-safe current-squad context for one manager and gameweek."""

    _require_columns(current_squad_df, SUPPORTED_INPUTS["current_squad"], name="current_squad")
    squad = current_squad_df.copy()
    squad["manager_id"] = pd.to_numeric(squad["manager_id"], errors="coerce").astype("Int64")
    squad["event"] = pd.to_numeric(squad["event"], errors="coerce").astype("Int64")
    squad = squad[squad["manager_id"].eq(int(manager_id)) & squad["event"].eq(int(target_gw))].copy()
    if squad.empty:
        raise ValueError(f"No current squad rows found for manager_id={manager_id}, target_gw={target_gw}")

    squad["squad_position"] = pd.to_numeric(squad["squad_position"], errors="coerce").astype("Int64")
    squad["is_starter"] = squad.get("is_starter", squad["squad_position"].le(11)).fillna(False).astype(bool)
    squad["is_bench"] = squad.get("is_bench", ~squad["is_starter"]).fillna(False).astype(bool)
    squad["is_captain"] = squad["is_captain"].fillna(False).astype(bool)
    squad["is_vice_captain"] = squad["is_vice_captain"].fillna(False).astype(bool)

    role_security = (
        _optional_numeric(squad, "player_start_rate_prior", 0.0)
        + _optional_numeric(squad, "player_appearance_rate_prior", 0.0)
        + _optional_numeric(squad, "player_sixty_plus_rate_prior", 0.0)
    ) / 3
    role_security = role_security.clip(0, 1)
    route_score = _position_route_score(squad)
    fixture_score = _normalise_series(_optional_numeric(squad, "fixture_fpl_difficulty_mean_next3", 3.0), inverse=True)
    team_context_score = (
        _normalise_series(_optional_numeric(squad, "team_points_per_fixture_prior", 0.0))
        + _normalise_series(_optional_numeric(squad, "team_goals_for_per_fixture_prior", 0.0))
        + _normalise_series(_optional_numeric(squad, "team_clean_sheet_rate_prior", 0.0))
    ) / 3

    squad["is_likely_starter"] = (squad["is_starter"] | role_security.ge(0.7)).astype(bool)
    squad["squad_role"] = squad.apply(_squad_role, axis=1)
    squad["price_slot"] = squad.apply(_price_slot, axis=1)
    squad["role_security_score"] = role_security
    squad["position_route_score"] = route_score
    squad["fixture_outlook_score"] = fixture_score
    squad["team_context_score"] = team_context_score
    squad["current_squad_priority_score"] = (
        0.35 * squad["role_security_score"]
        + 0.30 * squad["position_route_score"]
        + 0.20 * squad["fixture_outlook_score"]
        + 0.15 * squad["team_context_score"]
    ).clip(0, 1)
    squad["context_note"] = (
        "Current-squad context uses selected squad state, prior player/team features, "
        "and upcoming fixture outlook only; current gameweek outcomes are excluded."
    )

    outcome_columns = [
        "actual_points",
        "points_after_multiplier",
        "player_total_points",
        "player_minutes",
        "player_starts",
        "player_goals_scored",
        "player_assists",
        "player_clean_sheets",
        "player_goals_conceded",
        "player_saves",
        "player_bonus",
        "player_bps",
        "player_defensive_contribution",
        "player_expected_goals",
        "player_expected_assists",
        "player_expected_goal_involvements",
        "player_expected_goals_conceded",
    ]
    squad = squad.drop(columns=[column for column in outcome_columns if column in squad.columns])

    front_columns = [
        "manager_id",
        "event",
        "element",
        "player_web_name",
        "player_team_name",
        "player_team_short_name",
        "team_id",
        "player_position",
        "player_position_short",
        "player_price",
        "squad_position",
        "is_starter",
        "is_bench",
        "is_likely_starter",
        "squad_role",
        "price_slot",
        "is_captain",
        "is_vice_captain",
        "multiplier",
        "role_security_score",
        "position_route_score",
        "fixture_outlook_score",
        "team_context_score",
        "current_squad_priority_score",
        "context_note",
    ]
    ordered = [column for column in front_columns if column in squad.columns]
    ordered.extend([column for column in squad.columns if column not in ordered])
    return squad[ordered].sort_values("squad_position").reset_index(drop=True)


def _metadata_row(
    *,
    target_gw: int,
    manager_id: int,
    free_transfers: int,
    bank: float,
    table_name: str,
    source_rows: int = 0,
) -> dict[str, Any]:
    return {
        "target_gw": target_gw,
        "manager_id": manager_id,
        "free_transfers": free_transfers,
        "bank": bank,
        "table_name": table_name,
        "status": "placeholder",
        "source_rows": source_rows,
        "note": "Story 11.1 creates orchestration only; scoring logic is added in later stories.",
    }


def build_weekly_decision_pack(
    target_gw: int,
    manager_id: int = MY_TEAM_ID,
    free_transfers: int = 1,
    bank: float = 0.0,
    include_owned: bool = False,
    output_tables_dir: str | Path | None = DEFAULT_OUTPUT_TABLES_DIR,
    **dataframes_or_paths: Any,
) -> dict[str, pd.DataFrame]:
    """Return the skeleton weekly decision pack for a target gameweek.

    Parameters
    ----------
    target_gw:
        Gameweek being reviewed. Must be a positive integer.
    manager_id:
        FPL manager/team ID. Defaults to manager `816200`.
    free_transfers:
        Available free transfers before hits. Must be zero or greater.
    bank:
        Money in the bank, expressed in FPL price units.
    **dataframes_or_paths:
        Optional input dataframes or CSV paths. Supported keys are listed in
        `SUPPORTED_INPUTS`. Story 11.1 validates supplied inputs but does not
        consume them for scoring yet.

    Returns
    -------
    dict[str, pandas.DataFrame]
        Placeholder DataFrames keyed by the weekly decision-pack output names.
    """

    target_gw_int = int(_safe_numeric(target_gw, default=0))
    manager_id_int = int(_safe_numeric(manager_id, default=MY_TEAM_ID))
    free_transfers_int = int(_safe_numeric(free_transfers, default=1))
    bank_float = _safe_numeric(bank, default=0.0)

    if target_gw_int <= 0:
        raise ValueError("target_gw must be a positive integer")
    if manager_id_int <= 0:
        raise ValueError("manager_id must be a positive integer")
    if free_transfers_int < 0:
        raise ValueError("free_transfers must be zero or greater")
    if bank_float < 0:
        raise ValueError("bank must be zero or greater")

    unknown_inputs = sorted(set(dataframes_or_paths) - set(SUPPORTED_INPUTS))
    if unknown_inputs:
        raise ValueError(f"Unsupported weekly decision-system inputs: {unknown_inputs}")

    if "current_squad" not in dataframes_or_paths and DEFAULT_CURRENT_SQUAD_PATH.exists():
        dataframes_or_paths["current_squad"] = DEFAULT_CURRENT_SQUAD_PATH
    if "candidate_rule_features" not in dataframes_or_paths and DEFAULT_CANDIDATE_RULE_FEATURES_PATH.exists():
        dataframes_or_paths["candidate_rule_features"] = DEFAULT_CANDIDATE_RULE_FEATURES_PATH

    loaded_inputs: dict[str, pd.DataFrame] = {}
    for name, value in dataframes_or_paths.items():
        df = _load_dataframe(value, name=name)
        _require_columns(df, SUPPORTED_INPUTS[name], name=name)
        loaded_inputs[name] = df

    source_rows = sum(len(df) for df in loaded_inputs.values())
    pack = {
        key: pd.DataFrame(
            [
                _metadata_row(
                    target_gw=target_gw_int,
                    manager_id=manager_id_int,
                    free_transfers=free_transfers_int,
                    bank=bank_float,
                    table_name=key,
                    source_rows=source_rows,
                )
            ]
        )
        for key in DECISION_PACK_KEYS
    }
    if "current_squad" in loaded_inputs:
        pack["current_squad_context"] = build_current_squad_context(
            loaded_inputs["current_squad"],
            target_gw=target_gw_int,
            manager_id=manager_id_int,
        )
    if "candidate_rule_features" in loaded_inputs:
        pack["transfer_candidate_shortlist"] = build_transfer_candidate_shortlist(
            loaded_inputs["candidate_rule_features"],
            target_gw=target_gw_int,
            current_squad_context_df=pack.get("current_squad_context"),
            include_owned=include_owned,
        )
        if output_tables_dir is not None:
            output_dir = Path(output_tables_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            pack["transfer_candidate_shortlist"].to_csv(
                output_dir / "weekly_transfer_candidate_shortlist.csv",
                index=False,
            )
    if not pack["current_squad_context"].empty and set(pack["current_squad_context"].columns).issuperset(
        {"element", "player_web_name", "current_squad_priority_score"}
    ):
        transfer_shortlist = pack.get("transfer_candidate_shortlist")
        pack["sell_candidate_review"] = build_sell_candidate_review(
            pack["current_squad_context"],
            transfer_candidate_shortlist_df=transfer_shortlist if transfer_shortlist is not None else None,
            target_gw=target_gw_int,
            bank=bank_float,
        )
        if output_tables_dir is not None:
            output_dir = Path(output_tables_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            pack["sell_candidate_review"].to_csv(
                output_dir / "weekly_sell_candidate_review.csv",
                index=False,
            )
        if (
            transfer_shortlist is not None
            and not transfer_shortlist.empty
            and DEFAULT_LEARNED_CANDIDATE_RULES_PATH.exists()
            and DEFAULT_LEARNED_SELL_HOLD_RULES_PATH.exists()
        ):
            transfer_pair_review = build_transfer_pair_review(
                transfer_shortlist,
                pack["sell_candidate_review"],
                bank=bank_float,
                learned_candidate_rules_df=pd.read_csv(DEFAULT_LEARNED_CANDIDATE_RULES_PATH),
                learned_sell_hold_rules_df=pd.read_csv(DEFAULT_LEARNED_SELL_HOLD_RULES_PATH),
            )
            if output_tables_dir is not None:
                output_dir = Path(output_tables_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                transfer_pair_review.to_csv(
                    output_dir / "weekly_transfer_pair_review.csv",
                    index=False,
                )
            if DEFAULT_TRANSFER_RULE_CANDIDATES_PATH.exists():
                transfer_package_review = build_transfer_package_review(
                    transfer_pair_review,
                    free_transfers=free_transfers_int,
                    transfer_rule_candidates_df=pd.read_csv(DEFAULT_TRANSFER_RULE_CANDIDATES_PATH),
                )
                pack["transfer_package_review"] = transfer_package_review
                if output_tables_dir is not None:
                    output_dir = Path(output_tables_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    transfer_package_review.to_csv(
                        output_dir / "weekly_transfer_package_review.csv",
                        index=False,
                    )
    return pack


def build_learned_weekly_decision_rules(
    *,
    candidate_rule_features: str | Path | pd.DataFrame = DEFAULT_CANDIDATE_RULE_FEATURES_PATH,
    player_selection_rule_results: str | Path | pd.DataFrame = DEFAULT_PLAYER_SELECTION_RULES_PATH,
    manager_transfers: str | Path | pd.DataFrame = DEFAULT_MANAGER_TRANSFERS_PATH,
    manager_picks: str | Path | pd.DataFrame = DEFAULT_MANAGER_PICKS_PATH,
    top_n_sample_managers: str | Path | pd.DataFrame = DEFAULT_TOP_N_SAMPLE_MANAGERS_PATH,
    output_tables_dir: str | Path | None = DEFAULT_OUTPUT_TABLES_DIR,
) -> dict[str, pd.DataFrame]:
    """Build sampled-cohort learned rules for the next-season weekly process."""

    candidate_features_df = _load_dataframe(candidate_rule_features, name="candidate_rule_features")
    player_rules_df = _load_dataframe(player_selection_rule_results, name="player_selection_rule_results")
    transfers_df = _load_dataframe(manager_transfers, name="manager_transfers")
    picks_df = _load_dataframe(manager_picks, name="manager_picks")
    sample_df = _load_dataframe(top_n_sample_managers, name="top_n_sample_managers")

    learned_candidate_rules = build_learned_candidate_shortlist_rules(player_rules_df, sample_df)
    learned_sell_hold_rules = build_learned_sell_hold_rules(candidate_features_df, transfers_df, picks_df, sample_df)

    outputs = {
        "learned_candidate_shortlist_rules": learned_candidate_rules,
        "learned_sell_hold_rules": learned_sell_hold_rules,
    }
    if output_tables_dir is not None:
        output_dir = Path(output_tables_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        learned_candidate_rules.to_csv(output_dir / "learned_candidate_shortlist_rules.csv", index=False)
        learned_sell_hold_rules.to_csv(output_dir / "learned_sell_hold_rules.csv", index=False)
    return outputs
