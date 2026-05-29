"""Weekly Fantasy Premier League decision-system orchestration."""

from __future__ import annotations

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
DEFAULT_OUTPUT_TABLES_DIR = Path("outputs/tables")


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
    return pack
