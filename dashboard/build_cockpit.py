#!/usr/bin/env python3.12
"""Build a self-contained, leak-free FPL weekly decision cockpit."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = REPO_ROOT / "outputs/tables"
PROCESSED_DIR = REPO_ROOT / "data/processed"
RAW_DIR = REPO_ROOT / "data/raw"

TABLE_FILES = {
    "buy": TABLE_DIR / "weekly_transfer_candidate_shortlist.csv",
    "sell": TABLE_DIR / "weekly_sell_candidate_review.csv",
    "pairs": TABLE_DIR / "weekly_transfer_pair_review.csv",
    "packages": TABLE_DIR / "weekly_transfer_package_review.csv",
    "captaincy": TABLE_DIR / "my_captaincy_review.csv",
}

FEATURE_COLUMNS = {
    "gameweek", "player_id", "web_name", "team_name", "team_short_name", "position_short", "price",
    "minutes_roll3_mean_prior", "starts_roll3_mean_prior", "sixty_plus_minutes_roll3_mean_prior",
    "minutes_season_to_date_prior", "xgi_per_90_prior", "xgi_season_to_date_prior", "xg_per_90_prior",
    "expected_goals_roll3_mean_prior", "total_points_roll3_mean_prior", "points_per_90_prior",
    "points_season_to_date_prior", "defensive_contribution_per_90_prior", "saves_per_90_prior",
}

CAPTAIN_CEILING_WEIGHTS = {
    "points_per_90": 0.55,
    "xgi_per_90": 0.35,
    "fixture_ease": 0.10,
}

DEFAULT_VISIBLE = {"sell": 5, "buy": 6, "captain_alternatives": 4}

SELL_RISK_LABELS = {
    "role_security_risk_score": "role security is the main risk",
    "position_route_risk_score": "weak position route is the main risk",
    "fixture_risk_score": "upcoming fixtures are the main risk",
    "team_context_risk_score": "weak team context is the main risk",
    "price_value_risk_score": "poor value for the price slot is the main risk",
}

DIGEST_CLAUSE_REWRITES = {
    "buy profile is stronger than sell profile": "stronger buy profile",
    "fixture swing is positive": "positive fixture swing",
    "route-to-points swing is positive": "stronger route to points",
    "sampled-cohort rules support the direction": "cohort rules support the move",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-gw", type=int, required=True, help="Deadline gameweek to prepare for")
    parser.add_argument("--entry-id", type=int, default=816200)
    parser.add_argument("--free-transfers", type=int)
    parser.add_argument("--bank", type=float, help="Money in the bank in GBP millions")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "dashboard/fpl_cockpit.html")
    parser.add_argument("--no-regen", action="store_true", help="Read cached decision tables")
    parser.add_argument("--self-test", action="store_true", help="Run assertions after building")
    return parser.parse_args()


def finite_number(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def integer(value: Any, default: int = 0) -> int:
    number = finite_number(value)
    return int(number) if number is not None else default


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "t"}


def text_value(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and not math.isfinite(value):
        return fallback
    value_text = str(value).strip()
    return fallback if value_text.lower() in {"", "nan", "none", "<na>"} else value_text


def read_csv(path: Path, columns: set[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if columns is None:
        return pd.read_csv(path, low_memory=False)
    return pd.read_csv(path, usecols=lambda column: column in columns, low_memory=False)


def filter_rows(frame: pd.DataFrame, key: str, value: int) -> pd.DataFrame:
    if frame.empty or key not in frame.columns:
        return pd.DataFrame(columns=frame.columns)
    numeric = pd.to_numeric(frame[key], errors="coerce")
    return frame.loc[numeric.eq(value)].copy()


def row_dict(row: pd.Series | None) -> dict[str, Any]:
    return {} if row is None else row.to_dict()


def normalise(values: list[float | None]) -> list[float]:
    valid = [value for value in values if value is not None and math.isfinite(value)]
    if not valid:
        return [50.0 for _ in values]
    low, high = min(valid), max(valid)
    if high == low:
        return [50.0 if value is not None else 0.0 for value in values]
    return [0.0 if value is None else 100.0 * (value - low) / (high - low) for value in values]


def score_percent(value: Any) -> float:
    number = finite_number(value, 0.0) or 0.0
    if abs(number) <= 1.5:
        number *= 100.0
    return round(max(0.0, min(100.0, number)), 1)


def dominant_sell_reason(row: pd.Series) -> str:
    """Reduce a sell review to its single strongest risk phrase."""
    risk_key = max(
        SELL_RISK_LABELS,
        key=lambda key: finite_number(row.get(key), 0.0) or 0.0,
    )
    reason = SELL_RISK_LABELS[risk_key]
    return reason


def distinctive_buy_strength(player: dict[str, Any], peers: list[dict[str, Any]]) -> str:
    """Show the component that most separates a buy from same-position peers."""
    signals = {
        "value": player["value"],
        "fixture": player["components"]["fixture"],
        "route": player["components"]["route"],
        "role": player["components"]["role"],
    }

    def relative_rank(key: str) -> float:
        values = [
            peer["value"] if key == "value" else peer["components"][key]
            for peer in peers
        ]
        value = signals[key]
        return (sum(item < value for item in values) + 0.5 * sum(item == value for item in values)) / len(values)

    standout = max(signals, key=relative_rank)
    if standout == "value":
        return f"elite value · {player['value']:.1f} pts/£m"
    if standout == "fixture":
        return "easiest next-3 fixtures"
    if standout == "route":
        return "strong route to points"
    return "secure role"


def derive_free_transfers(timeline: pd.DataFrame, target_gw: int) -> int:
    """Reconstruct the wallet from transfers used; chip weeks preserve the wallet."""
    free_transfers = 1
    if timeline.empty or "event" not in timeline.columns:
        return free_transfers
    prior = timeline[pd.to_numeric(timeline.get("event"), errors="coerce").lt(target_gw)].copy()
    prior = prior.sort_values("event")
    for _, row in prior.iterrows():
        event = integer(row.get("event"))
        transfers = integer(row.get("event_transfers", row.get("transfer_count_actual", 0)))
        chip = text_value(row.get("chip_name")).lower().replace("_", " ")
        if "wild" in chip or "free hit" in chip or "freehit" in chip:
            free_transfers = min(5, free_transfers + 1)
        else:
            free_transfers = min(5, max(0, free_transfers - transfers) + 1)
        if event == 15:  # 2025/26 AFCON top-up applies entering GW16.
            free_transfers = 5
    return free_transfers


def command_state(timeline: pd.DataFrame, target_gw: int, bank_arg: float | None, ft_arg: int | None) -> dict[str, Any]:
    if timeline.empty or "event" not in timeline.columns:
        before = pd.DataFrame()
    else:
        before = timeline[pd.to_numeric(timeline["event"], errors="coerce").lt(target_gw)].copy()
        before = before.sort_values("event")
    prior = row_dict(before.iloc[-1] if not before.empty else None)

    if bank_arg is not None:
        bank = float(bank_arg)
    else:
        bank_value = finite_number(prior.get("bank_value"))
        raw_bank = finite_number(prior.get("bank"), 0.0) or 0.0
        bank = bank_value if bank_value is not None else raw_bank / 10.0
    free_transfers = int(ft_arg) if ft_arg is not None else derive_free_transfers(timeline, target_gw)

    team_value = finite_number(prior.get("team_value"))
    if team_value is None:
        raw_value = finite_number(prior.get("value"), 0.0) or 0.0
        team_value = raw_value / 10.0 if raw_value > 200 else raw_value

    ranks = []
    for _, row in before.tail(8).iterrows():
        rank = finite_number(row.get("overall_rank"))
        if rank is not None:
            ranks.append({"gw": integer(row.get("event")), "rank": int(rank)})

    used = {"WC": 0, "FH": 0, "BB": 0, "TC": 0}
    for _, row in before.iterrows():
        chip = f"{text_value(row.get('chip_name'))} {text_value(row.get('chip_names'))}".lower()
        if "wild" in chip:
            used["WC"] += 1
        if "freehit" in chip or "free hit" in chip:
            used["FH"] += 1
        if "bboost" in chip or "bench boost" in chip:
            used["BB"] += 1
        if "3xc" in chip or "triple" in chip:
            used["TC"] += 1
    # Cumulative chip_names can repeat; chip_name is the authoritative per-GW field.
    if "chip_name" in before.columns:
        used = {key: 0 for key in used}
        for chip_value in before["chip_name"].dropna().astype(str):
            chip = chip_value.lower()
            if "wild" in chip:
                used["WC"] += 1
            elif "freehit" in chip or "free hit" in chip:
                used["FH"] += 1
            elif "bboost" in chip or "bench" in chip:
                used["BB"] += 1
            elif "3xc" in chip or "triple" in chip:
                used["TC"] += 1

    delta = finite_number(prior.get("overall_rank_delta"), 0.0) or 0.0
    return {
        "bank": round(max(0.0, bank), 1),
        "free_transfers": max(0, free_transfers),
        "team_value": round(team_value or 0.0, 1),
        "overall_rank": integer(prior.get("overall_rank")),
        "rank_delta": int(delta),
        "total_points": integer(prior.get("total_points")),
        "rank_history": ranks,
        "chips_used": used,
        "as_of_gw": integer(prior.get("event")),
    }


def try_regenerate(target_gw: int, entry_id: int, free_transfers: int, bank: float, no_regen: bool) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if no_regen:
        return "cached (--no-regen)", warnings
    original_cwd = Path.cwd()
    try:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        os.chdir(REPO_ROOT)
        from fpl_retro.weekly_decision_system import build_weekly_decision_pack

        build_weekly_decision_pack(
            target_gw=target_gw,
            manager_id=entry_id,
            free_transfers=free_transfers,
            bank=bank,
            output_tables_dir="outputs/tables",
        )
        return "regenerated", warnings
    except Exception as exc:  # The cached pack is an intentional operational fallback.
        message = re.sub(r"\s+", " ", text_value(exc, exc.__class__.__name__))
        warnings.append(f"Decision-pack regeneration failed; cached tables used. {exc.__class__.__name__}: {message}")
        return "cached fallback", warnings
    finally:
        os.chdir(original_cwd)


def load_bootstrap() -> tuple[dict[int, dict[str, Any]], dict[int, str], dict[int, str], dict[int, str]]:
    path = RAW_DIR / "bootstrap_static_smoke.json"
    if not path.exists():
        return {}, {}, {}, {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, {}, {}, {}
    status = {
        integer(item.get("id")): {
            "status": text_value(item.get("status"), "a"),
            "chance": finite_number(item.get("chance_of_playing_next_round")),
            "news": text_value(item.get("news")),
        }
        for item in raw.get("elements", [])
    }
    team_short = {integer(team.get("id")): text_value(team.get("short_name")) for team in raw.get("teams", [])}
    team_name = {integer(team.get("id")): text_value(team.get("name")) for team in raw.get("teams", [])}
    deadlines = {integer(event.get("id")): text_value(event.get("deadline_time")) for event in raw.get("events", [])}
    return status, team_short, team_name, deadlines


def availability(player_id: int, feature: dict[str, Any], bootstrap_status: dict[int, dict[str, Any]]) -> dict[str, Any]:
    live = bootstrap_status.get(player_id, {})
    status = text_value(live.get("status"), "a").lower()
    chance = finite_number(live.get("chance"))
    minutes = finite_number(feature.get("minutes_roll3_mean_prior"), 0.0) or 0.0
    if status != "a" or (chance is not None and chance < 50) or minutes < 45:
        level = "red"
    elif (chance is not None and 50 <= chance < 75) or minutes < 60:
        level = "amber"
    else:
        level = "green"
    labels = {"red": "flagged or below 45 prior min", "amber": "45–59 prior min / rotation risk", "green": "60+ prior min"}
    return {
        "level": level,
        "minutes_prior": round(minutes, 1),
        "chance": chance,
        "news": text_value(live.get("news")),
        "label": labels[level],
    }


def build_schedule(fixtures: pd.DataFrame, target_gw: int) -> dict[int, list[dict[str, Any]]]:
    schedule: dict[int, list[dict[str, Any]]] = {}
    if fixtures.empty:
        return schedule
    events = pd.to_numeric(fixtures.get("event"), errors="coerce")
    future = fixtures.loc[events.between(target_gw, min(38, target_gw + 4))].copy()
    for _, row in future.iterrows():
        gw = integer(row.get("event"))
        home_id, away_id = integer(row.get("team_h")), integer(row.get("team_a"))
        home_name = text_value(row.get("team_h_short_name"), text_value(row.get("team_h_name"), "?"))
        away_name = text_value(row.get("team_a_short_name"), text_value(row.get("team_a_name"), "?"))
        schedule.setdefault(home_id, []).append({
            "gw": gw, "opponent": away_name, "venue": "H", "fdr": finite_number(row.get("team_h_difficulty"), 3.0) or 3.0,
        })
        schedule.setdefault(away_id, []).append({
            "gw": gw, "opponent": home_name, "venue": "A", "fdr": finite_number(row.get("team_a_difficulty"), 3.0) or 3.0,
        })
    return schedule


def fixture_cells(team_id: int, schedule: dict[int, list[dict[str, Any]]], target_gw: int) -> list[dict[str, Any]]:
    team_schedule = schedule.get(team_id, [])
    cells = []
    for gw in range(target_gw, min(38, target_gw + 4) + 1):
        matches = [item for item in team_schedule if item["gw"] == gw]
        if not matches:
            cells.append({"gw": gw, "label": "—", "fdr": None, "blank": True, "double": False})
            continue
        label = " · ".join(f"{match['opponent']} ({match['venue']})" for match in matches)
        if len(matches) > 1:
            label = f"×× {label}"
        cells.append({
            "gw": gw, "label": label, "fdr": round(sum(match["fdr"] for match in matches) / len(matches), 1),
            "blank": False, "double": len(matches) > 1,
        })
    return cells


def get_fixture_context(team_id: int, fixture_map: dict[int, dict[str, Any]], schedule: dict[int, list[dict[str, Any]]], target_gw: int) -> dict[str, Any]:
    fixture = fixture_map.get(team_id, {})
    cells = fixture_cells(team_id, schedule, target_gw)
    first = cells[0] if cells else {"label": "Unknown", "fdr": None, "blank": False, "double": False}
    return {
        "next": first,
        "cells": cells,
        "fdr1": finite_number(fixture.get("fpl_difficulty_mean_next1"), first.get("fdr")),
        "fdr3": finite_number(fixture.get("fpl_difficulty_mean_next3")),
        "fdr5": finite_number(fixture.get("fpl_difficulty_mean_next5")),
        "blank1": truthy(fixture.get("blank_next1")) or bool(first.get("blank")),
        "double1": truthy(fixture.get("double_next1")) or bool(first.get("double")),
    }


def decorate_player(
    *, player_id: int, name: str, team_short: str, position: str, price: float,
    feature_map: dict[int, dict[str, Any]], player_map: dict[int, dict[str, Any]],
    fixture_map: dict[int, dict[str, Any]], schedule: dict[int, list[dict[str, Any]]],
    bootstrap_status: dict[int, dict[str, Any]], target_gw: int,
) -> dict[str, Any]:
    feature = feature_map.get(player_id, {})
    base = player_map.get(player_id, {})
    team_id = integer(base.get("team"), integer(feature.get("team_id")))
    resolved_team = text_value(team_short, text_value(feature.get("team_short_name"), text_value(base.get("team_short_name"), "—")))
    resolved_price = finite_number(price, finite_number(feature.get("price"), finite_number(base.get("price"), 0.0))) or 0.0
    points_prior = finite_number(feature.get("points_season_to_date_prior"), 0.0) or 0.0
    value = points_prior / resolved_price if resolved_price > 0 else 0.0
    position = text_value(position, text_value(feature.get("position_short"), text_value(base.get("position_short"), "—"))).upper()
    fixture = get_fixture_context(team_id, fixture_map, schedule, target_gw)
    return {
        "id": player_id,
        "name": text_value(name, text_value(feature.get("web_name"), text_value(base.get("web_name"), f"Player {player_id}"))),
        "team": resolved_team,
        "team_id": team_id,
        "position": position,
        "price": round(resolved_price, 1),
        "availability": availability(player_id, feature, bootstrap_status),
        "value": round(value, 1),
        "value_context": "value play" if position in {"GKP", "DEF"} else "ceiling role",
        "xgi90": round(finite_number(feature.get("xgi_per_90_prior"), 0.0) or 0.0, 2),
        "points90": round(finite_number(feature.get("points_per_90_prior"), 0.0) or 0.0, 2),
        "form3": round(finite_number(feature.get("total_points_roll3_mean_prior"), 0.0) or 0.0, 2),
        "minutes_prior": round(finite_number(feature.get("minutes_roll3_mean_prior"), 0.0) or 0.0, 1),
        "ownership": round(finite_number(base.get("selected_by_percent"), 0.0) or 0.0, 1),
        "fixture": fixture,
    }


def positive_recommendation(value: Any) -> bool:
    recommendation = text_value(value).lower()
    if not recommendation:
        return True
    if any(blocked in recommendation for blocked in ("avoid", "hold", "not worth", "do not", "reject")):
        return False
    return True


def verdict(score: float) -> str:
    if score >= 75:
        return "Strong"
    if score >= 50:
        return "Consider"
    return "Hold"


def clipped_phrase(value: Any, fallback: str, max_chars: int = 70) -> str:
    phrase = text_value(value, fallback).strip().rstrip(".")
    if len(phrase) <= max_chars:
        return phrase
    clipped = phrase[: max_chars - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{clipped}…"


def compressed_digest_reason(value: Any, fallback: str, max_chars: int = 70) -> str:
    """Keep at most two complete clauses; never end a digest reason with a clipped clause."""
    phrase = text_value(value, fallback).strip().rstrip(".")
    clauses = [clause.strip().rstrip(".") for clause in phrase.split(";") if clause.strip()]
    clauses = [DIGEST_CLAUSE_REWRITES.get(clause.lower(), clause) for clause in clauses]
    selected: list[str] = []
    for clause in clauses[:2]:
        candidate = " · ".join([*selected, clause])
        if len(candidate) > max_chars:
            break
        selected.append(clause)
    if selected:
        return " · ".join(selected)
    fallback_phrase = text_value(fallback, "Evidence supports this call").strip().rstrip(".")
    return fallback_phrase if len(fallback_phrase) <= max_chars else "Evidence supports this call"


def digest_fixture_label(value: Any) -> str:
    label = text_value(value, "fixture pending")
    match = re.fullmatch(r"(.+) \(([HA])\)", label)
    return f"vs {match.group(1)}, {match.group(2)}" if match else label


def edge_classification(value: float, comparison_values: list[float]) -> dict[str, Any]:
    finite_values = [item for item in comparison_values if math.isfinite(item)]
    percentile = 100.0 * sum(item <= value for item in finite_values) / len(finite_values) if finite_values else 0.0
    label = "strong edge" if percentile >= 80 else "modest edge" if percentile >= 50 else "marginal edge"
    return {"label": label, "percentile": round(percentile, 0)}


def confidence_rank(value: Any) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(text_value(value).lower(), 0)


def parse_id_list(value: Any) -> list[int]:
    return [integer(item) for item in text_value(value).split(",") if integer(item)]


def split_alerts(alerts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    urgent = [item for item in alerts if item.get("severity") in {"red", "amber"}]
    opportunities = [item for item in alerts if item.get("severity") == "green"]
    return urgent, opportunities


def lineup_score(player: dict[str, Any]) -> float:
    fdr = finite_number(player.get("fixture", {}).get("fdr1"), 3.0) or 3.0
    route = player.get("xgi90", 0.0) if player.get("position") in {"MID", "FWD"} else player.get("points90", 0.0) / 8.0
    gate = {"green": 1.0, "amber": 0.55, "red": 0.05}.get(player.get("availability", {}).get("level"), 0.05)
    return round(gate * (route + max(0.0, 4.0 - fdr) * 0.12), 3)


def legal_lineup_swap(starter: dict[str, Any], bench_player: dict[str, Any], starters: list[dict[str, Any]]) -> bool:
    if starter["position"] == "GKP" or bench_player["position"] == "GKP":
        return starter["position"] == bench_player["position"] == "GKP"
    counts = {position: sum(player["position"] == position for player in starters) for position in ("DEF", "MID", "FWD")}
    counts[starter["position"]] -= 1
    counts[bench_player["position"]] += 1
    return counts["DEF"] >= 3 and counts["MID"] >= 2 and counts["FWD"] >= 1


def build_lineup_state(
    squad: list[dict[str, Any]], *, apply_best_change: bool, protected_starter_ids: set[int] | None = None,
) -> dict[str, Any]:
    protected_starter_ids = protected_starter_ids or set()
    players = [dict(player) for player in squad]
    for player in players:
        player["lineup_score"] = lineup_score(player)
    starters = [player for player in players if player.get("is_starter")]
    bench = [player for player in players if player.get("is_bench")]

    candidates = []
    for bench_player in bench:
        for starter in starters:
            if starter["id"] in protected_starter_ids or not legal_lineup_swap(starter, bench_player, starters):
                continue
            improvement = bench_player["lineup_score"] - starter["lineup_score"]
            if improvement > 0.15:
                candidates.append((improvement, bench_player, starter))
    candidates.sort(key=lambda item: item[0], reverse=True)
    suggestions = []
    if candidates:
        improvement, bench_player, starter = candidates[0]
        suggestions.append({
            "in_id": bench_player["id"], "out_id": starter["id"],
            "in_name": bench_player["name"], "out_name": starter["name"],
            "summary": f"Start {bench_player['name']} over {starter['name']}",
            "detail": "Prior route plus fixture is stronger after availability gating.",
            "improvement": round(improvement, 3),
        })
        if apply_best_change:
            bench_player.update({"is_starter": True, "is_bench": False})
            starter.update({"is_starter": False, "is_bench": True})

    starters = [player for player in players if player.get("is_starter")]
    bench = [player for player in players if player.get("is_bench")]
    outfield_bench = sorted(
        [player for player in bench if player["position"] != "GKP"],
        key=lambda item: item["lineup_score"], reverse=True,
    )
    bench_gkp = [player for player in bench if player["position"] == "GKP"]
    bench_order = outfield_bench + bench_gkp
    return {
        "squad": players, "starters": starters, "bench": bench,
        "bench_order": [player["id"] for player in bench_order],
        "suggestions": suggestions,
        "answer": "1 change suggested" if suggestions else "No changes — XI confirmed",
        "why": suggestions[0]["summary"] if suggestions else "Post-transfer starters clear the lineup gate",
        "bench_state": "Bench order adjusted" if suggestions else "Bench order ok",
    }


def apply_transfer_plan(
    squad: list[dict[str, Any]], transfer: dict[str, Any], buy_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    replacements = dict(zip(transfer.get("sell_ids", []), transfer.get("buy_ids", [])))
    planned = []
    for current in squad:
        buy_id = replacements.get(current["id"])
        if not buy_id or buy_id not in buy_by_id:
            planned.append(dict(current))
            continue
        incoming = dict(buy_by_id[buy_id])
        incoming.update({
            key: current.get(key)
            for key in ("squad_position", "is_starter", "is_bench", "is_captain", "is_vice", "multiplier")
        })
        incoming["planned_in"] = True
        planned.append(incoming)
    return sorted(planned, key=lambda item: item.get("squad_position", 99))


def clean_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if hasattr(value, "item"):
        return clean_json(value.item())
    return text_value(value)


def build_data(args: argparse.Namespace) -> dict[str, Any]:
    if args.target_gw < 1 or args.target_gw > 38:
        raise ValueError("--target-gw must be between 1 and 38")
    timeline = read_csv(PROCESSED_DIR / "my_gameweek_timeline.csv")
    command = command_state(timeline, args.target_gw, args.bank, args.free_transfers)
    regen_status, warnings = try_regenerate(
        args.target_gw, args.entry_id, command["free_transfers"], command["bank"], args.no_regen,
    )

    raw_tables = {name: read_csv(path) for name, path in TABLE_FILES.items()}
    tables = {
        "buy": filter_rows(raw_tables["buy"], "target_gw", args.target_gw),
        "sell": filter_rows(raw_tables["sell"], "target_gw", args.target_gw),
        "pairs": filter_rows(raw_tables["pairs"], "target_gw", args.target_gw),
        "packages": filter_rows(raw_tables["packages"], "target_gw", args.target_gw),
        "captaincy": filter_rows(raw_tables["captaincy"], "event", args.target_gw),
    }
    for name in ("buy", "sell", "pairs", "packages"):
        if tables[name].empty:
            warnings.append(f"{TABLE_FILES[name].name} has no rows for GW{args.target_gw}.")

    squad_all = read_csv(PROCESSED_DIR / "my_squad_gameweek.csv")
    squad_df = filter_rows(squad_all, "event", args.target_gw)
    if "manager_id" in squad_df.columns:
        manager_ids = pd.to_numeric(squad_df["manager_id"], errors="coerce")
        squad_df = squad_df.loc[manager_ids.eq(args.entry_id)].copy()

    features_all = read_csv(PROCESSED_DIR / "player_gw_features.csv", FEATURE_COLUMNS)
    features = filter_rows(features_all, "gameweek", args.target_gw)
    feature_map = {integer(row.get("player_id")): row.to_dict() for _, row in features.iterrows()}

    fixture_all = read_csv(PROCESSED_DIR / "fixture_difficulty.csv")
    fixture_rows = filter_rows(fixture_all, "gameweek", args.target_gw)
    fixture_map = {integer(row.get("team_id")): row.to_dict() for _, row in fixture_rows.iterrows()}
    fixtures = read_csv(PROCESSED_DIR / "fixtures.csv")
    schedule = build_schedule(fixtures, args.target_gw)

    players = read_csv(PROCESSED_DIR / "players.csv")
    player_map = {integer(row.get("id")): row.to_dict() for _, row in players.iterrows()}
    bootstrap_status_snapshot, bootstrap_team_short, _bootstrap_team_name, deadlines = load_bootstrap()
    target_deadline = deadlines.get(args.target_gw, "")
    live_status_enabled = False
    if target_deadline:
        try:
            live_status_enabled = datetime.fromisoformat(target_deadline.replace("Z", "+00:00")) > datetime.now(timezone.utc)
        except ValueError:
            live_status_enabled = False
    # A current bootstrap status is valid for an upcoming deadline, but leaks future
    # injury news into a historical gameweek. Past builds therefore use priors only.
    bootstrap_status = bootstrap_status_snapshot if live_status_enabled else {}

    def decorated_from_squad(row: pd.Series) -> dict[str, Any]:
        player_id = integer(row.get("element", row.get("id")))
        player = decorate_player(
            player_id=player_id,
            name=text_value(row.get("player_web_name"), text_value(row.get("web_name"))),
            team_short=text_value(row.get("player_team_short_name"), bootstrap_team_short.get(integer(row.get("team_id")), "")),
            position=text_value(row.get("player_position_short")),
            price=finite_number(row.get("player_price"), 0.0) or 0.0,
            feature_map=feature_map, player_map=player_map, fixture_map=fixture_map, schedule=schedule,
            bootstrap_status=bootstrap_status, target_gw=args.target_gw,
        )
        player.update({
            "squad_position": integer(row.get("squad_position")),
            "is_starter": truthy(row.get("is_starter")),
            "is_bench": truthy(row.get("is_bench")),
            "is_captain": truthy(row.get("is_captain")),
            "is_vice": truthy(row.get("is_vice_captain")),
            "multiplier": integer(row.get("multiplier"), 1),
        })
        return player

    ordered_squad = squad_df.sort_values("squad_position") if "squad_position" in squad_df.columns else squad_df
    squad = [decorated_from_squad(row) for _, row in ordered_squad.iterrows()]
    squad_by_id = {player["id"]: player for player in squad}

    buy_rows: list[dict[str, Any]] = []
    for _, row in tables["buy"].iterrows():
        player_id = integer(row.get("player_id"))
        decorated = decorate_player(
            player_id=player_id, name=text_value(row.get("web_name")), team_short="",
            position=text_value(row.get("position_short")), price=finite_number(row.get("price"), 0.0) or 0.0,
            feature_map=feature_map, player_map=player_map, fixture_map=fixture_map, schedule=schedule,
            bootstrap_status=bootstrap_status, target_gw=args.target_gw,
        )
        decorated.update({
            "team_name": text_value(row.get("team_name"), decorated["team"]),
            "score": round(finite_number(row.get("transfer_candidate_score"), 0.0) or 0.0, 3),
            "tier": text_value(row.get("candidate_tier"), "Watch"),
            "reason": text_value(row.get("reason_summary"), "Balanced prior signals place this player on the shortlist."),
            "reason_short": "Balanced prior signals",
            "risk": text_value(row.get("risk_summary"), "Check late availability news."),
            "components": {
                "role": score_percent(row.get("role_security_score")),
                "route": score_percent(row.get("route_to_points_score")),
                "fixture": score_percent(row.get("fixture_score")),
                "value": score_percent(row.get("price_value_score")),
            },
        })
        buy_rows.append(decorated)
    buy_rows.sort(key=lambda item: (item["availability"]["level"] == "red", -item["score"]))
    buy_peers_by_position = {
        position: [player for player in buy_rows if player["position"] == position]
        for position in {player["position"] for player in buy_rows}
    }
    for player in buy_rows:
        player["reason_short"] = distinctive_buy_strength(player, buy_peers_by_position[player["position"]])

    sell_rows: list[dict[str, Any]] = []
    for _, row in tables["sell"].iterrows():
        player_id = integer(row.get("element"))
        decorated = dict(squad_by_id.get(player_id) or decorate_player(
            player_id=player_id, name=text_value(row.get("player_web_name")), team_short="",
            position=text_value(row.get("player_position_short")), price=finite_number(row.get("player_price"), 0.0) or 0.0,
            feature_map=feature_map, player_map=player_map, fixture_map=fixture_map, schedule=schedule,
            bootstrap_status=bootstrap_status, target_gw=args.target_gw,
        ))
        decorated.update({
            "sell_risk": round(finite_number(row.get("sell_risk_score"), 0.0) or 0.0, 3),
            "recommendation": text_value(row.get("sell_recommendation"), "HOLD").upper(),
            "confidence": text_value(row.get("confidence"), "Low"),
            "sell_explanation": dominant_sell_reason(row),
            "sell_detail": text_value(row.get("sell_explanation"), dominant_sell_reason(row)),
            "hold_explanation": text_value(row.get("hold_explanation")),
        })
        sell_rows.append(decorated)
    sell_rows.sort(key=lambda item: (-item["sell_risk"], item["availability"]["level"] == "green"))

    pairs: list[dict[str, Any]] = []
    for _, row in tables["pairs"].iterrows():
        pairs.append({
            "sell_id": integer(row.get("sell_player_id")), "sell_name": text_value(row.get("sell_player_name")),
            "sell_position": text_value(row.get("sell_position")).upper(), "sell_price": round(finite_number(row.get("sell_price"), 0.0) or 0.0, 1),
            "buy_id": integer(row.get("buy_player_id")), "buy_name": text_value(row.get("buy_player_name")),
            "buy_position": text_value(row.get("buy_position")).upper(), "buy_price": round(finite_number(row.get("buy_price"), 0.0) or 0.0, 1),
            "affordable": truthy(row.get("is_affordable")), "upgrade": round(finite_number(row.get("upgrade_score"), 0.0) or 0.0, 2),
            "recommendation": text_value(row.get("recommendation")), "reason": text_value(row.get("reason_summary")),
        })
    affordable_pairs = [
        pair for pair in pairs
        if pair["affordable"] and pair["buy_price"] <= pair["sell_price"] + command["bank"] + 0.001
        and pair["upgrade"] > 0 and positive_recommendation(pair["recommendation"])
    ]
    affordable_pairs.sort(key=lambda item: item["upgrade"], reverse=True)
    affordable_upgrade_values = [pair["upgrade"] for pair in affordable_pairs]
    for pair in pairs:
        pair["edge"] = edge_classification(pair["upgrade"], affordable_upgrade_values)
    best_pair = affordable_pairs[0] if affordable_pairs else None

    package_rows = []
    for _, row in tables["packages"].iterrows():
        package_rows.append({
            "id": text_value(row.get("package_id")), "transfer_count": integer(row.get("transfer_count")),
            "sold_ids": parse_id_list(row.get("sold_player_ids")), "sold_names": text_value(row.get("sold_player_names")),
            "bought_ids": parse_id_list(row.get("bought_player_ids")), "bought_names": text_value(row.get("bought_player_names")),
            "gross_package_score": round(finite_number(row.get("gross_package_score"), 0.0) or 0.0, 3),
            "package_upgrade_score": round(finite_number(row.get("package_upgrade_score"), 0.0) or 0.0, 3),
            "gross_next3": round(finite_number(row.get("gross_expected_gain_next3"), 0.0) or 0.0, 1),
            "hit_cost": integer(row.get("hit_cost")), "scenario": text_value(row.get("hit_scenario")),
            "next1": round(finite_number(row.get("net_package_value_next1"), 0.0) or 0.0, 1),
            "next3": round(finite_number(row.get("net_package_value_next3"), 0.0) or 0.0, 1),
            "next5": round(finite_number(row.get("net_package_value_next5"), 0.0) or 0.0, 1),
            "recommendation": text_value(row.get("recommendation")), "confidence": text_value(row.get("confidence")),
            "reason": text_value(row.get("reason_summary")),
        })
    package_rows.sort(key=lambda item: (item["next3"], item["next5"]), reverse=True)
    best_package = package_rows[0] if package_rows else None
    pair_next3_equivalent = 0.0
    if best_pair and best_package and best_package["gross_package_score"] > 0:
        pair_next3_equivalent = round(
            best_pair["upgrade"] * best_package["gross_next3"] / best_package["gross_package_score"], 1,
        )
    # Precedence: keep the best affordable single pair unless a medium-or-higher
    # package beats its package-calibrated three-GW point equivalent after hits.
    package_beats_pair = bool(
        best_package
        and confidence_rank(best_package["confidence"]) >= confidence_rank("medium")
        and positive_recommendation(best_package["recommendation"])
        and best_package["next3"] > pair_next3_equivalent
    )

    buy_by_id = {player["id"]: player for player in buy_rows}
    if package_beats_pair and best_package:
        scenario_label = best_package["scenario"].replace("-", "−")
        sold_value = sum(squad_by_id.get(player_id, {}).get("price", 0.0) for player_id in best_package["sold_ids"])
        bought_value = sum(buy_by_id.get(player_id, {}).get("price", 0.0) for player_id in best_package["bought_ids"])
        transfer = {
            "branch": "package_override", "action": "package",
            "answer": f"Make {best_package['transfer_count']} transfers ({scenario_label})",
            "headline": f"MAKE {best_package['transfer_count']} TRANSFERS ({scenario_label})",
            "reason": best_package["reason"],
            "reason_short": clipped_phrase(
                f"{best_package['confidence']} confidence and {best_package['next3']:+.0f} net points over 3GW",
                "The package clears the precedence gate.",
            ),
            "upgrade": best_package["package_upgrade_score"],
            "edge": edge_classification(
                best_package["package_upgrade_score"], [item["package_upgrade_score"] for item in package_rows],
            ),
            "bank_left": round(max(0.0, command["bank"] + sold_value - bought_value), 1),
            "decision_state": "PACKAGE OVERRIDE", "sell_ids": best_package["sold_ids"],
            "buy_ids": best_package["bought_ids"], "package_id": best_package["id"],
            "sell_names": best_package["sold_names"], "buy_names": best_package["bought_names"],
        }
    elif best_pair:
        reason_clauses = [clause.strip() for clause in best_pair["reason"].split(";") if clause.strip()]
        transfer = {
            "branch": "single_affordable_pair", "action": "transfer",
            "answer": f"Sell {best_pair['sell_name']} → Buy {best_pair['buy_name']}",
            "headline": f"SELL {best_pair['sell_name']} → BUY {best_pair['buy_name']}",
            "reason": best_pair["reason"] or "The validated pair review finds the strongest affordable upgrade.",
            "reason_short": clipped_phrase(
                "; ".join(reason_clauses[:2]), "Strongest positive affordable upgrade.",
            ),
            "upgrade": best_pair["upgrade"], "edge": best_pair["edge"],
            "bank_left": round(max(0.0, best_pair["sell_price"] + command["bank"] - best_pair["buy_price"]), 1),
            "decision_state": "AFFORDABLE", "sell_ids": [best_pair["sell_id"]], "buy_ids": [best_pair["buy_id"]],
            **best_pair,
        }
    else:
        transfer = {
            "branch": "hold", "action": "hold", "answer": "Hold — bank the transfer",
            "headline": "HOLD — BANK THE TRANSFER",
            "reason": "No positive, affordable pair clears the evidence gate; bank the transfer toward a stronger two-transfer move.",
            "reason_short": "No positive affordable pair clears the evidence gate",
            "upgrade": 0.0, "edge": {"label": "no edge", "percentile": 0.0},
            "bank_left": command["bank"], "decision_state": "BANK FT", "sell_ids": [], "buy_ids": [],
        }
    transfer["reason_short"] = compressed_digest_reason(
        transfer["reason"], transfer["reason_short"],
    )
    hero = dict(transfer)

    hit = None
    if best_package and best_package["hit_cost"] > 0:
        worth = positive_recommendation(best_package["recommendation"]) and best_package["next3"] > 0
        low_confidence = worth and best_package["confidence"].strip().lower() == "low"
        hit = {
            **best_package,
            "worth": worth,
            "low_confidence": low_confidence,
            "verdict": "WORTH IT (low confidence)" if low_confidence else "WORTH IT" if worth else "NOT WORTH IT",
            "is_primary": transfer["branch"] == "package_override" and transfer.get("package_id") == best_package["id"],
        }

    planned_squad = apply_transfer_plan(squad, transfer, buy_by_id)
    current_lineup = build_lineup_state(squad, apply_best_change=False)
    planned_lineup = build_lineup_state(
        planned_squad, apply_best_change=True, protected_starter_ids=set(transfer.get("buy_ids", [])),
    )

    captain_frame = tables["captaincy"]
    if "manager_id" in captain_frame.columns:
        manager_mask = pd.to_numeric(captain_frame["manager_id"], errors="coerce").eq(args.entry_id)
        captain_frame = captain_frame.loc[manager_mask]
    captain_row = row_dict(captain_frame.iloc[0] if not captain_frame.empty else None)
    engine_pick_id = integer(captain_row.get("recommended_candidate_player_id"))
    engine_pick_player = squad_by_id.get(engine_pick_id, {})
    engine_pick_name = text_value(captain_row.get("recommended_candidate_name"), engine_pick_player.get("name", ""))
    engine_pick_position = text_value(
        captain_row.get("recommended_candidate_position"), engine_pick_player.get("position", ""),
    ).upper()

    # Captaincy is presented ceiling-first: owned XI only, no goalkeepers, and no
    # red availability candidates. All three inputs are leak-free deadline priors.
    captain_pool = [
        player for player in planned_lineup["starters"]
        if player["is_starter"]
        and player["position"] != "GKP"
        and player["availability"]["level"] in {"green", "amber"}
    ]
    points_components = normalise([player["points90"] for player in captain_pool])
    xgi_components = normalise([player["xgi90"] for player in captain_pool])
    fixture_components = normalise([
        -(finite_number(player["fixture"].get("fdr1"), 5.0) or 5.0)
        for player in captain_pool
    ])
    captain_options = []
    for player, points_component, xgi_component, fixture_component in zip(
        captain_pool, points_components, xgi_components, fixture_components,
    ):
        rank_score = (
            CAPTAIN_CEILING_WEIGHTS["points_per_90"] * points_component
            + CAPTAIN_CEILING_WEIGHTS["xgi_per_90"] * xgi_component
            + CAPTAIN_CEILING_WEIGHTS["fixture_ease"] * fixture_component
        )
        option = dict(player)
        option.update({
            "captain_ceiling_rank_score": round(rank_score, 1),
            "captain_score": round(rank_score, 1),
            "components": {
                "ceiling": round(points_component, 1),
                "xgi_route": round(xgi_component, 1),
                "fixture": round(fixture_component, 1),
            },
            "template_label": "Template" if player["ownership"] >= 20 else "Differential",
            "is_recommended": False,
        })
        captain_options.append(option)
    captain_options.sort(key=lambda item: item["captain_ceiling_rank_score"], reverse=True)
    captain_options = captain_options[:5]
    if captain_options:
        captain_options[0]["is_recommended"] = True
    recommended_player = captain_options[0] if captain_options else {}
    recommended_id = integer(recommended_player.get("id"))
    recommended_name = text_value(recommended_player.get("name"))
    fixture_label = text_value(recommended_player.get("fixture", {}).get("next", {}).get("label"), "fixture pending")
    minutes_prior = finite_number(recommended_player.get("minutes_prior"), 0.0) or 0.0
    minutes_reason = "nailed 80+ prior minutes" if minutes_prior >= 80 else "secure 60+ prior minutes" if minutes_prior >= 60 else "amber availability"
    reason = (
        f"Highest ceiling in your XI: {finite_number(recommended_player.get('points90'), 0.0):.1f} pp90 "
        f"and {finite_number(recommended_player.get('xgi90'), 0.0):.2f} xGI/90, "
        f"{minutes_reason}, {fixture_label}."
    ) if recommended_player else "No available outfield starter clears the captaincy gate."
    engine_note = (
        f"Model's security-first pick: {engine_pick_name} ({engine_pick_position}) — flags nailed minutes over ceiling; "
        "we lead with ceiling for captaincy."
    ) if engine_pick_name else ""
    captain = {
        "available": bool(captain_options),
        "recommended_id": recommended_id,
        "recommended_name": recommended_name,
        "recommended_score": recommended_player.get("captain_ceiling_rank_score"),
        "reason": reason,
        "engine_pick_id": engine_pick_id,
        "engine_pick_name": engine_pick_name,
        "engine_note": engine_note,
        "options": captain_options,
        "source_note": "Ceiling-first presentation rank: 55% prior points/90, 35% prior xGI/90, 10% next-fixture ease; owned available outfield starters only.",
    }

    starters = planned_lineup["starters"]
    bench = planned_lineup["bench"]
    planned_squad_by_id = {player["id"]: player for player in planned_lineup["squad"]}

    red_squad = sum(player["availability"]["level"] == "red" for player in planned_lineup["squad"])
    hard_three = sum((finite_number(player["fixture"].get("fdr3"), 3.0) or 3.0) >= 4 for player in planned_lineup["squad"])
    blank_xi = sum(player["fixture"].get("blank1", False) for player in starters)
    double_xi = sum(player["fixture"].get("double1", False) for player in starters)
    green_bench = sum(player["availability"]["level"] == "green" for player in bench)
    easy_bench = sum((finite_number(player["fixture"].get("fdr1"), 5.0) or 5.0) <= 3 for player in bench)
    # Preserve the existing chip heuristic input; the ceiling-first override is
    # deliberately scoped to captaincy presentation only.
    captain_player = planned_squad_by_id.get(engine_pick_id, {})
    captain_fdr = finite_number(captain_player.get("fixture", {}).get("fdr1"), 5.0) or 5.0
    captain_green = captain_player.get("availability", {}).get("level") == "green"
    captain_double = bool(captain_player.get("fixture", {}).get("double1"))
    chip_scores = {
        "TC": min(100.0, (45 if captain_green else 5) + (30 if captain_fdr <= 2 else 12 if captain_fdr <= 3 else 0) + (35 if captain_double else 0)),
        "BB": min(100.0, green_bench * 14 + easy_bench * 9 + (15 if green_bench == 4 else 0)),
        "WC": min(100.0, red_squad * 22 + hard_three * 8),
        "FH": min(100.0, blank_xi * 18 + double_xi * 10 + (25 if double_xi >= 4 else 0)),
    }
    chip_reasons = {
        "TC": f"Captain is {'green' if captain_green else 'not green'} availability, FDR {captain_fdr:.1f}{' with a double' if captain_double else ''}.",
        "BB": f"{green_bench}/4 bench players are green; {easy_bench}/4 have FDR 3 or easier.",
        "WC": f"{red_squad} squad flags and {hard_three} players with hard next-three fixture averages.",
        "FH": f"{blank_xi} starting-XI blanks and {double_xi} starting-XI doubles in the next GW.",
    }
    chips = [
        {"code": code, "score": round(score, 0), "verdict": verdict(score), "reason": chip_reasons[code],
         "used": command["chips_used"].get(code, 0), "heuristic": True}
        for code, score in chip_scores.items()
    ]

    actual_captain = next((player for player in squad if player.get("is_captain")), None)
    captain["fixture_answer"] = digest_fixture_label(fixture_label)
    captain["reason_short"] = compressed_digest_reason(
        f"Top ceiling: {finite_number(recommended_player.get('points90'), 0.0):.1f} pp90 · "
        f"{finite_number(recommended_player.get('xgi90'), 0.0):.2f} xGI/90",
        "Highest ceiling in the planned XI",
    ) if recommended_player else "No captain clears the availability gate"
    captain["current_text"] = (
        f"you have: {actual_captain['name']} ✓"
        if actual_captain and actual_captain["id"] == recommended_id
        else f"you have: {actual_captain['name']} — switch" if actual_captain
        else "current armband unavailable"
    )

    chip_names = {"TC": "Triple Captain", "BB": "Bench Boost", "WC": "Wildcard", "FH": "Free Hit"}
    top_chip = max(chips, key=lambda item: item["score"])
    play_chip = top_chip["verdict"] == "Strong"
    chip_plan = {
        "code": top_chip["code"] if play_chip else None,
        "answer": f"Play {chip_names[top_chip['code']]}" if play_chip else "Hold all chips",
        "reason_short": (
            f"{chip_names[top_chip['code']]} clears Strong at {top_chip['score']:.0f}/100"
            if play_chip else "No chip advisor reaches the Strong threshold"
        ),
        "subline": (
            f"{chip_names[top_chip['code']]} is Strong at {top_chip['score']:.0f}/100"
            if play_chip else f"{chip_names[top_chip['code']]} nearest at {top_chip['score']:.0f}/100"
        ),
        "top_advisor_code": top_chip["code"], "top_advisor_verdict": top_chip["verdict"],
        "top_advisor_score": top_chip["score"],
    }
    chip_plan["reason_short"] = compressed_digest_reason(
        chip_plan["reason_short"], "No chip clears the decision threshold",
    )

    plan = {
        "transfer": {
            **transfer,
            "subline": f"£{transfer['bank_left']:.1f}m bank · {transfer['decision_state'].lower()}",
        },
        "captain": {
            "player_id": recommended_id, "name": recommended_name,
            "answer": f"{recommended_name} ({captain['fixture_answer']})" if recommended_name else "No captain available",
            "fixture": captain["fixture_answer"], "reason_short": captain["reason_short"],
            "subline": captain["current_text"],
        },
        "lineup": {
            "answer": planned_lineup["answer"],
            "reason_short": compressed_digest_reason(planned_lineup["why"], "Lineup gate is clear"),
            "subline": planned_lineup["bench_state"], "suggestions": planned_lineup["suggestions"],
        },
        "chip": chip_plan,
    }

    classified_alerts = []
    for player in starters:
        if player["availability"]["level"] == "red":
            classified_alerts.append({"severity": "red", "text": f"Replace {player['name']} — flagged or below the minutes gate."})
        elif player["availability"]["level"] == "amber":
            classified_alerts.append({"severity": "amber", "text": f"Rotation watch: {player['name']} is below 60 prior minutes."})
    if command["free_transfers"] == 0 and any(player["availability"]["level"] == "red" for player in starters):
        classified_alerts.append({"severity": "red", "text": "0 free transfers with a forced availability decision — price the hit carefully."})
    doubles = [player["name"] for player in planned_lineup["squad"] if player["fixture"].get("double1")]
    if doubles:
        classified_alerts.append({"severity": "green", "text": f"Double-GW opportunity in squad: {', '.join(doubles[:3])}."})
    cheap_green = [player for player in buy_rows if player["price"] <= 5.0 and player["availability"]["level"] == "green"]
    if cheap_green:
        classified_alerts.append({"severity": "green", "text": f"Cheap enabler available: {cheap_green[0]['name']} at £{cheap_green[0]['price']:.1f}m."})
    severity_order = {"red": 0, "amber": 1, "green": 2}
    classified_alerts.sort(key=lambda item: severity_order[item["severity"]])
    alerts, opportunities = split_alerts(classified_alerts)

    deadline = deadlines.get(args.target_gw, "")
    if deadline:
        try:
            parsed = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            deadline_label = parsed.strftime("%a %d %b · %H:%M UTC")
        except ValueError:
            deadline_label = f"Next deadline · GW{args.target_gw}"
    else:
        deadline_label = f"Next deadline · GW{args.target_gw}"

    missing_columns = []
    expected_feature_columns = {"minutes_roll3_mean_prior", "points_per_90_prior", "xgi_per_90_prior", "points_season_to_date_prior"}
    missing_columns.extend(f"player_gw_features.{column}" for column in sorted(expected_feature_columns - set(features.columns)))
    expected_fixture_columns = {"fpl_difficulty_mean_next1", "fpl_difficulty_mean_next3", "fpl_difficulty_mean_next5"}
    missing_columns.extend(f"fixture_difficulty.{column}" for column in sorted(expected_fixture_columns - set(fixture_rows.columns)))
    if missing_columns:
        warnings.append("Missing optional columns: " + ", ".join(missing_columns))

    fixture_players = [dict(player) for player in planned_lineup["starters"]]
    fixture_bench = [dict(player) for player in planned_lineup["bench"]]
    fixture_targets = [dict(player) for player in buy_rows[:5]]
    data = {
        "meta": {"target_gw": args.target_gw, "entry_id": args.entry_id, "deadline": deadline_label},
        "command": command,
        "display": DEFAULT_VISIBLE,
        "plan": plan,
        "alerts": alerts,
        "opportunities": opportunities,
        "hero": hero,
        "hit": hit,
        "sell": sell_rows,
        "buy": buy_rows,
        "pairs": pairs,
        "captain": captain,
        "squad": squad,
        "starters": starters,
        "bench": bench,
        "bench_order": planned_lineup["bench_order"],
        "lineup_suggestions": planned_lineup["suggestions"],
        "lineups": {"planned": planned_lineup, "current": current_lineup},
        "chips": chips,
        "fixtures": {"players": fixture_players, "bench": fixture_bench, "targets": fixture_targets, "gameweeks": list(range(args.target_gw, min(38, args.target_gw + 4) + 1))},
        "provenance": {
            "pack_status": regen_status,
            "plan_branch": transfer["branch"],
            "pair_next3_equivalent": pair_next3_equivalent,
            "warnings": warnings,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "injury_source": "live bootstrap + minutes priors" if live_status_enabled else "minutes priors only (historical deadline)",
            "sources": [
                "outputs/tables/weekly_* decision tables", "outputs/tables/my_captaincy_review.csv",
                "data/processed/my_squad_gameweek.csv", "data/processed/my_gameweek_timeline.csv",
                "data/processed/player_gw_features.csv", "data/processed/fixture_difficulty.csv",
                "data/processed/fixtures.csv", "data/processed/players.csv", "data/raw/bootstrap_static_smoke.json",
            ],
            "missing_columns": missing_columns,
        },
        "availability_test_samples": {
            "green": next((player_id for player_id, feature in feature_map.items() if availability(player_id, feature, bootstrap_status)["level"] == "green"), None),
            "low_minutes_red": next((player_id for player_id, feature in feature_map.items() if (finite_number(feature.get("minutes_roll3_mean_prior"), 0.0) or 0.0) < 45 and availability(player_id, feature, bootstrap_status)["level"] == "red"), None),
        },
    }
    return clean_json(data)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FPL Weekly Decision Cockpit</title>
<style>
:root {
  --bg:#0A0D10; --panel:#101419; --panel2:#14191f; --warm:#F4EFE4; --green:#00D785;
  --red:#E5484D; --amber:#E5A23D; --muted:#8F9798; --line:rgba(244,239,228,.08);
  --soft:rgba(244,239,228,.045); --green-soft:rgba(0,215,133,.10); --red-soft:rgba(229,72,77,.10);
  --amber-soft:rgba(229,162,61,.10); --radius:12px;
}
* { box-sizing:border-box; }
html { color-scheme:dark; background:var(--bg); scroll-behavior:smooth; scroll-padding-top:96px; }
body { margin:0; min-width:0; overflow-x:hidden; background:var(--bg); color:var(--warm); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; font-size:14px; }
button, input { font:inherit; }
button { color:inherit; }
.command-strip { position:sticky; top:0; z-index:20; min-height:72px; display:grid; grid-template-columns:minmax(180px,.9fr) minmax(350px,1.15fr) minmax(285px,1.2fr) max-content; align-items:center; gap:clamp(10px,1.25vw,18px); padding:9px 22px; border-bottom:1px solid var(--line); background:rgba(12,16,19,.97); backdrop-filter:blur(14px); }
.command-strip > * { min-width:0; }
.gw-lockup { display:flex; align-items:center; gap:14px; min-width:0; }
.gw-lockup > div:last-child { min-width:0; }
.gw { font-size:28px; line-height:1; font-weight:900; letter-spacing:-.04em; }
.page-identity { display:block; max-width:100%; margin-bottom:3px; overflow:hidden; color:#a6adae; font-size:9px; font-weight:800; letter-spacing:.07em; white-space:nowrap; text-overflow:ellipsis; }
.deadline { color:var(--amber); font-size:12px; font-weight:750; letter-spacing:.02em; }
.rank-lockup { display:flex; align-items:center; justify-content:center; gap:14px; min-width:0; }
.rank-number { font-size:19px; font-weight:850; letter-spacing:-.02em; white-space:nowrap; }
.rank-caption, .eyebrow, .micro { color:var(--muted); font-size:10px; line-height:1.35; text-transform:uppercase; letter-spacing:.11em; font-weight:800; }
.rank-delta.up, .good { color:var(--green); }
.rank-delta.down, .bad { color:var(--red); }
.rank-delta.flat { color:var(--muted); }
.spark { width:110px; height:30px; flex:0 0 110px; }
.points-total { padding-left:12px; border-left:1px solid var(--line); white-space:nowrap; }
.wallet { display:flex; justify-content:flex-end; align-items:center; flex-wrap:wrap; gap:7px 13px; color:#c9c5bd; }
.wallet strong { color:var(--warm); font-size:13px; }
.wallet-item { white-space:nowrap; }
.wallet-item.constrained strong { color:var(--red); }
.chip-pills { display:flex; gap:5px; }
.chip-pill, .pill { border:1px solid var(--line); border-radius:999px; padding:3px 7px; font-size:10px; font-weight:850; letter-spacing:.05em; text-transform:uppercase; }
.chip-pill.used { color:#62696b; text-decoration:line-through; background:rgba(143,151,152,.06); }
.anchor-nav { display:flex; align-items:center; justify-content:flex-end; gap:2px; white-space:nowrap; }
.anchor-nav a { padding:5px 6px; border-radius:5px; color:var(--muted); font-size:9px; font-weight:800; letter-spacing:.04em; text-decoration:none; transition:color .15s ease,background .15s ease; }
.anchor-nav a:hover,.anchor-nav a.active { color:var(--warm); background:var(--soft); }
.digest-band { max-width:1800px; margin:0 auto; padding:18px 22px 0; }
.digest-head { display:flex; align-items:flex-end; justify-content:space-between; gap:14px; margin:0 0 10px; }
.digest-title { margin:0; font-size:clamp(22px,2.2vw,34px); line-height:1; letter-spacing:-.035em; }
.digest-clear { color:var(--muted); font-size:10px; }
.digest-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
.digest-card { min-width:0; min-height:164px; display:flex; flex-direction:column; padding:15px 15px 12px; border:1px solid var(--line); border-radius:11px; background:linear-gradient(145deg,var(--panel2),var(--panel)); box-shadow:0 12px 30px rgba(0,0,0,.14); }
.digest-answer { margin:8px 0 7px; color:var(--warm); font-size:clamp(21px,1.7vw,30px); line-height:1.08; font-weight:900; letter-spacing:-.035em; }
.digest-answer .action { color:var(--green); }
.digest-why { color:#b7b5ae; font-size:11px; line-height:1.35; }
.digest-sub { margin-top:6px; color:var(--muted); font-size:10px; }
.details-link { margin-top:auto; padding-top:10px; color:var(--muted); font-size:9px; font-weight:850; letter-spacing:.07em; text-decoration:none; text-transform:uppercase; }
.details-link:hover { color:var(--green); }
.alert-zone { min-height:0; display:flex; align-items:stretch; margin-bottom:10px; border:1px solid var(--line); border-radius:8px; overflow:hidden; background:#0c1013; }
.alert-zone.hidden { display:none; }
.alerts { display:flex; width:100%; overflow-x:auto; scrollbar-width:thin; }
.alert { display:flex; align-items:center; padding:7px 13px; font-size:12px; font-weight:700; border-right:1px solid var(--line); white-space:nowrap; }
.alert.red { color:#ff8f92; background:var(--red-soft); border-top:2px solid var(--red); }
.alert.amber { color:#efbd69; background:var(--amber-soft); border-top:2px solid var(--amber); }
.opportunity-note { display:inline-flex; align-items:center; margin:0 14px 12px; padding:6px 9px; border:1px solid rgba(0,215,133,.18); border-radius:7px; color:#8bcdb4; background:rgba(0,215,133,.055); font-size:10px; }
.dashboard { max-width:1800px; margin:0 auto; padding:18px 22px 28px; display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:16px; }
.panel { min-width:0; background:var(--panel); border:1px solid var(--line); border-radius:var(--radius); box-shadow:0 16px 40px rgba(0,0,0,.12); overflow:hidden; }
.transfers { grid-column:span 7; }
.captaincy { grid-column:span 5; }
.lineup { grid-column:span 7; }
.chips { grid-column:span 5; }
.planner { grid-column:1 / -1; }
.panel-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; padding:16px 18px 11px; border-bottom:1px solid var(--line); }
.panel-head h2 { margin:2px 0 0; font-size:15px; line-height:1.2; letter-spacing:.045em; text-transform:uppercase; }
.panel-head h2 span { color:#b5b3ac; font-weight:700; }
.info-tip { position:relative; flex:0 0 auto; width:24px; height:24px; display:grid; place-items:center; border:1px solid var(--line); border-radius:50%; color:var(--muted); background:transparent; cursor:help; font-size:12px; }
.info-tip::after { content:attr(data-tip); pointer-events:none; position:absolute; top:29px; right:0; z-index:9; width:260px; padding:8px 9px; border:1px solid var(--line); border-radius:7px; color:#c4c1ba; background:#0c1013; font-size:10px; line-height:1.4; text-align:left; opacity:0; transform:translateY(-3px); transition:.14s ease; }
.info-tip:hover::after,.info-tip:focus::after { opacity:1; transform:translateY(0); }
.hero { margin:14px; padding:19px 20px 18px; border:1px solid rgba(0,215,133,.25); border-left:3px solid var(--green); border-radius:11px; background:linear-gradient(135deg,rgba(0,215,133,.09),rgba(0,215,133,.015) 58%); }
.hero.hold { border-color:rgba(229,162,61,.24); border-left-color:var(--amber); background:linear-gradient(135deg,rgba(229,162,61,.08),rgba(229,162,61,.015) 58%); }
.hero h1 { margin:6px 0 8px; max-width:860px; font-size:clamp(22px,1.55vw,28px); line-height:1.04; letter-spacing:-.035em; }
.reason { color:#c8c5bd; font-size:13px; line-height:1.5; max-width:920px; }
.inline-detail { margin-top:7px; color:var(--muted); font-size:10px; }
.inline-detail summary { width:max-content; cursor:pointer; color:#a8afaf; font-weight:750; }
.inline-detail div { max-width:900px; padding:7px 0 0; line-height:1.45; }
.hero-metrics { display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:14px; }
.metric { color:var(--muted); font-size:11px; }
.metric strong { display:block; color:var(--warm); font-size:16px; margin-top:2px; }
.edge-chip { display:inline-flex; align-items:center; width:max-content; padding:3px 7px; border:1px solid rgba(0,215,133,.22); border-radius:999px; color:#81d9b7; background:var(--green-soft); font-size:9px; font-weight:850; letter-spacing:.04em; text-transform:uppercase; }
.raw-score { display:inline-block; margin-top:4px; color:var(--muted); font-size:9px; font-weight:650; }
.hit-alternative { margin:0 14px 14px; border:1px solid rgba(229,162,61,.18); border-radius:9px; background:rgba(229,162,61,.035); }
.hit-alternative summary { padding:10px 12px; list-style:none; cursor:pointer; color:#c2a16c; font-size:10px; line-height:1.4; }
.hit-alternative summary::-webkit-details-marker { display:none; }
.hit-alternative[open] summary { border-bottom:1px solid var(--line); }
.hit-card { margin:0; padding:12px 14px; display:grid; grid-template-columns:minmax(0,1fr) minmax(170px,260px); gap:18px; align-items:center; border-radius:0 0 9px 9px; background:var(--panel2); }
.hit-card.worth { border-left:3px solid var(--green); }
.hit-card.low-confidence { border-left:3px solid var(--amber); }
.hit-card.not-worth { border-left:3px solid var(--red); }
.hit-title { font-size:15px; font-weight:850; }
.hit-title .verdict { margin-left:7px; }
.hit-title .verdict.caution { color:var(--amber); }
.hit-note { margin-top:4px; color:var(--muted); font-size:11px; line-height:1.35; }
.payoff { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; align-items:end; height:56px; }
.payoff-item { position:relative; height:100%; display:flex; flex-direction:column; justify-content:flex-end; align-items:center; gap:3px; color:var(--muted); font-size:9px; }
.payoff-bar { width:80%; min-height:3px; border-radius:3px 3px 0 0; background:var(--green); opacity:.85; }
.payoff-bar.negative { background:var(--red); }
.payoff-value { color:var(--warm); font-weight:800; font-size:10px; }
.decision-tables { display:grid; grid-template-columns:.88fr 1.12fr; border-top:1px solid var(--line); }
.table-block { min-width:0; padding:14px; }
.table-block + .table-block { border-left:1px solid var(--line); }
.subhead { display:flex; justify-content:space-between; gap:8px; align-items:flex-start; margin-bottom:9px; }
.subhead h3 { margin:0; font-size:13px; }
.count { color:var(--muted); font-size:10px; }
.table-scroll { width:100%; overflow:auto; max-height:440px; border:1px solid var(--line); border-radius:9px; }
table { width:100%; border-collapse:collapse; font-size:11px; }
th { position:sticky; top:0; z-index:2; background:#171c22; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-size:9px; text-align:left; padding:8px 7px; border-bottom:1px solid var(--line); white-space:nowrap; }
td { vertical-align:top; padding:8px 7px; border-bottom:1px solid var(--line); line-height:1.35; }
tbody tr:last-child td { border-bottom:0; }
tbody tr { transition:background .15s ease; }
tbody tr:hover { background:rgba(244,239,228,.035); }
tbody tr.selected { background:var(--green-soft); box-shadow:inset 2px 0 var(--green); }
tbody tr.quarantine { opacity:.48; background:rgba(229,72,77,.035); }
tbody tr.extra-row { display:none; }
tbody.show-all tr.extra-row { display:table-row; }
.row-reason { display:flex; align-items:flex-start; justify-content:space-between; gap:6px; }
.reason-toggle { flex:0 0 auto; width:22px; height:22px; display:grid; place-items:center; border:0; border-radius:5px; color:var(--muted); background:transparent; cursor:pointer; font-size:11px; }
.reason-toggle:hover { color:var(--green); background:var(--soft); }
.row-detail { display:none; margin-top:6px; padding-top:6px; border-top:1px solid var(--line); color:var(--muted); font-size:9px; line-height:1.45; }
tr.detail-open .row-detail { display:block; }
.pair-affordance { display:inline-flex; margin-top:5px; color:#8fcdb5; font-size:9px; font-weight:850; opacity:.58; }
tr:hover .pair-affordance,tr.selected .pair-affordance { color:var(--green); opacity:1; }
.expander-button { width:100%; margin-top:8px; padding:7px; border:1px solid var(--line); border-radius:7px; color:var(--muted); background:transparent; cursor:pointer; font-size:9px; font-weight:800; letter-spacing:.05em; text-transform:uppercase; }
.expander-button:hover { color:var(--warm); background:var(--soft); }
.player-name { color:var(--warm); font-weight:800; white-space:nowrap; }
.player-sub { color:var(--muted); font-size:9px; margin-top:2px; }
.availability { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; box-shadow:0 0 0 2px rgba(255,255,255,.035); }
.availability.green { background:var(--green); }
.availability.amber { background:var(--amber); }
.availability.red { background:var(--red); }
.pill.sell { color:#ff8f92; background:var(--red-soft); border-color:rgba(229,72,77,.22); }
.pill.hold { color:var(--muted); background:rgba(143,151,152,.06); }
.pill.tier-a, .pill.strong, .pill.template { color:#65e9b7; background:var(--green-soft); border-color:rgba(0,215,133,.22); }
.pill.tier-b, .pill.consider { color:#efbd69; background:var(--amber-soft); border-color:rgba(229,162,61,.22); }
.pill.differential { color:#b9c1c2; background:rgba(143,151,152,.07); }
.component-stack { min-width:110px; display:grid; grid-template-columns:repeat(4,1fr); gap:3px; }
.component { display:grid; gap:2px; }
.component-track { height:4px; border-radius:4px; background:rgba(244,239,228,.075); overflow:hidden; }
.component-fill { display:block; height:100%; background:var(--green); }
.component:nth-child(2) .component-fill { background:#41b88a; }
.component:nth-child(3) .component-fill { background:var(--amber); }
.component:nth-child(4) .component-fill { background:#a6adae; }
.component-label { color:var(--muted); font-size:7px; letter-spacing:.02em; }
.table-controls { display:flex; flex-wrap:wrap; gap:6px; margin:0 0 9px; }
.sort-button { cursor:pointer; border:1px solid var(--line); background:transparent; border-radius:6px; color:var(--muted); padding:4px 7px; font-size:9px; text-transform:uppercase; letter-spacing:.05em; }
.sort-button.active { color:var(--green); border-color:rgba(0,215,133,.28); background:var(--green-soft); }
.budget-control { padding:9px 10px; margin-bottom:9px; border:1px solid var(--line); border-radius:8px; background:var(--soft); }
.budget-row { display:flex; justify-content:space-between; gap:10px; color:var(--muted); font-size:10px; }
.budget-row strong { color:var(--warm); }
input[type="range"] { width:100%; height:4px; margin:9px 0 3px; accent-color:var(--green); }
.what-if { margin:9px 0 0; padding:8px 10px; overflow:auto; white-space:nowrap; border-radius:8px; background:var(--green-soft); color:#c9efe0; font-size:10px; line-height:1.35; }
.empty { margin:14px; padding:18px; border:1px dashed rgba(143,151,152,.25); border-radius:9px; color:var(--muted); text-align:center; }
.captain-hero { margin:14px; padding:18px; border-radius:11px; border:1px solid rgba(0,215,133,.25); background:var(--green-soft); }
.captain-name { margin:5px 0 4px; font-size:28px; line-height:1; font-weight:900; letter-spacing:-.04em; }
.engine-note { margin-top:9px; color:var(--muted); font-size:10px; line-height:1.45; }
.captain-fixture { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin-top:9px; }
.fixture-pill { display:inline-flex; align-items:center; border-radius:6px; padding:3px 6px; font-size:9px; font-weight:800; border:1px solid var(--line); background:rgba(143,151,152,.06); white-space:nowrap; }
.fixture-pill.easy, .fixture-cell.easy { color:#99f0cd; background:rgba(0,215,133,.16); }
.fixture-pill.medium, .fixture-cell.medium { color:#e8e2d7; background:rgba(143,151,152,.12); }
.fixture-pill.caution, .fixture-cell.caution { color:#f3c579; background:rgba(229,162,61,.17); }
.fixture-pill.hard, .fixture-cell.hard { color:#ff9c9f; background:rgba(229,72,77,.18); }
.fixture-pill.blank, .fixture-cell.blank { color:#646d70; background:rgba(143,151,152,.04); }
.captain-list { padding:0 14px 14px; }
.captain-option { display:grid; grid-template-columns:minmax(max-content,1fr) minmax(135px,.7fr) auto; gap:10px; align-items:center; padding:10px 3px; border-bottom:1px solid var(--line); }
.captain-option:last-child { border-bottom:0; }
.captain-option.recommended { box-shadow:inset 2px 0 var(--green); padding-left:9px; background:linear-gradient(90deg,var(--green-soft),transparent); }
.captain-option-main { min-width:max-content; }
.captain-badges { display:flex; align-items:center; flex-wrap:nowrap; gap:6px; white-space:nowrap; }
.captain-badges > *, .ownership-pill { flex:0 0 auto; white-space:nowrap; }
.captain-option .component-stack { grid-template-columns:repeat(3,1fr); }
.captain-rank { color:var(--muted); display:inline-block; width:17px; font-size:10px; }
.armband { display:inline-grid; place-items:center; min-width:18px; height:18px; padding:0 4px; margin-left:4px; border-radius:5px; color:#07110d; background:var(--green); font-size:9px; font-weight:950; }
.captain-score { text-align:right; font-size:16px; font-weight:850; }
.source-note { color:var(--muted); font-size:10px; line-height:1.45; padding:10px 14px 13px; border-top:1px solid var(--line); }
.pitch { margin:14px; padding:18px 12px; min-height:390px; display:grid; align-content:space-around; gap:15px; border-radius:12px; border:1px solid rgba(0,215,133,.12); background:linear-gradient(rgba(5,50,34,.42),rgba(5,34,25,.32)),repeating-linear-gradient(0deg,rgba(255,255,255,.014) 0,rgba(255,255,255,.014) 42px,transparent 42px,transparent 84px); box-shadow:inset 0 0 50px rgba(0,0,0,.25); }
.pitch-row { display:flex; justify-content:space-evenly; gap:7px; }
.player-card { position:relative; min-width:76px; max-width:112px; padding:8px 7px 7px; border:1px solid rgba(244,239,228,.12); border-radius:9px; background:rgba(10,13,16,.84); text-align:center; }
.player-card.red { opacity:.47; border-color:rgba(229,72,77,.35); }
.player-card.amber { border-color:rgba(229,162,61,.32); }
.player-card .player-name { display:block; overflow:hidden; text-overflow:ellipsis; font-size:10px; }
.player-card .fixture-pill { margin-top:5px; max-width:100%; overflow:hidden; text-overflow:ellipsis; }
.player-card .availability { position:absolute; top:7px; left:7px; }
.player-card .armband { position:absolute; top:-7px; right:-5px; }
.bench-zone { padding:0 14px 14px; }
.bench-row { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
.bench-card { min-width:0; padding:9px; border-radius:9px; border:1px solid var(--line); background:var(--panel2); }
.bench-card.red { opacity:.46; }
.bench-order { color:var(--muted); font-size:9px; margin-bottom:5px; }
.lineup-advice { margin:10px 0 0; padding:9px 11px; border-radius:8px; border-left:2px solid var(--amber); color:#e8c98e; background:var(--amber-soft); font-size:11px; }
.lineup-advice.clear { color:var(--muted); border-left-color:var(--green); background:var(--green-soft); }
.state-toggle { display:inline-flex; gap:2px; padding:3px; border:1px solid var(--line); border-radius:8px; background:#0c1013; }
.state-toggle button { padding:5px 8px; border:0; border-radius:5px; color:var(--muted); background:transparent; cursor:pointer; font-size:9px; font-weight:850; }
.state-toggle button.active { color:var(--warm); background:var(--soft); }
.state-caption { margin:-4px 14px 12px; color:var(--muted); font-size:9px; }
.chips-list { padding:5px 14px 14px; }
.chip-row { padding:14px 2px; border-bottom:1px solid var(--line); }
.chip-row:last-child { border-bottom:0; }
.chip-row.used { opacity:.38; filter:saturate(.35); }
.zone-call { margin:12px 14px 4px; padding:11px 12px; display:grid; gap:3px; border:1px solid rgba(0,215,133,.18); border-radius:9px; background:var(--green-soft); }
.zone-call strong { font-size:17px; }
.zone-call span { color:var(--muted); font-size:10px; }
.chip-top { display:grid; grid-template-columns:38px 1fr auto; gap:10px; align-items:center; }
.chip-code { display:grid; place-items:center; width:34px; height:34px; border:1px solid var(--line); border-radius:9px; font-weight:900; }
.meter { height:7px; border-radius:8px; overflow:hidden; background:rgba(244,239,228,.07); }
.meter-fill { display:block; height:100%; background:var(--muted); border-radius:8px; }
.meter-fill.consider { background:var(--amber); }
.meter-fill.strong { background:var(--green); }
.chip-verdict { min-width:72px; text-align:right; font-weight:850; }
.chip-reason { margin:7px 0 0 48px; color:var(--muted); font-size:10px; line-height:1.4; }
.heuristic-label { color:var(--amber); font-size:9px; }
.planner-tools { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:10px; cursor:pointer; }
.planner-wrap { overflow:auto; margin:0 14px 14px; border:1px solid var(--line); border-radius:9px; }
.fixture-table { min-width:820px; }
.fixture-table td, .fixture-table th { text-align:center; }
.fixture-table td:first-child, .fixture-table th:first-child { position:sticky; left:0; z-index:1; text-align:left; background:#151a20; min-width:150px; }
.fixture-table th:first-child { z-index:3; }
.fixture-cell { min-width:112px; padding:9px 6px; border-radius:5px; font-size:9px; font-weight:800; }
.target-row td:first-child { box-shadow:inset 3px 0 var(--green); }
.target-label { color:var(--green); font-size:8px; text-transform:uppercase; letter-spacing:.06em; }
.footer { max-width:1800px; margin:0 auto; padding:0 22px 28px; color:var(--muted); }
.footer-grid { display:grid; grid-template-columns:1.15fr 1fr; gap:22px; padding:14px 0; border-top:1px solid var(--line); font-size:10px; line-height:1.5; }
.footer strong { color:#c8c4ba; }
.warning { color:#e6b566; }
.footer-line { padding-top:12px; text-align:center; color:var(--warm); font-size:12px; font-weight:750; letter-spacing:.01em; }
.muted { color:var(--muted); }
.nowrap { white-space:nowrap; }
@media (max-width:1320px) {
  .decision-tables { grid-template-columns:1fr; }
  .table-block + .table-block { border-left:0; border-top:1px solid var(--line); }
  .command-strip { gap:10px; }
  .anchor-nav a { padding:5px 4px; }
}
@media (max-width:1100px) {
  .command-strip { grid-template-columns:1fr 1.4fr; }
  .wallet { justify-content:flex-end; }
  .anchor-nav { justify-content:flex-start; overflow:auto; }
  .digest-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .transfers,.captaincy,.lineup,.chips { grid-column:1 / -1; }
  .captaincy { grid-row:auto; }
}
@media (max-width:720px) {
  .command-strip { grid-template-columns:1fr; }
  .rank-lockup { justify-content:flex-start; }
  .wallet { grid-column:auto; }
  .anchor-nav { justify-content:flex-start; }
  .digest-band { padding:14px 12px 0; }
  .digest-grid { grid-template-columns:1fr; }
  .digest-card { min-height:145px; }
  .dashboard { padding:12px; gap:12px; }
  .hit-card { grid-template-columns:1fr; }
  .captain-option { grid-template-columns:1fr; }
  .captain-score { text-align:left; }
  .bench-row { grid-template-columns:repeat(2,1fr); }
  .player-card { min-width:62px; }
  .footer { padding:0 12px 22px; }
  .footer-grid { grid-template-columns:1fr; }
}
</style>
</head>
<body>
<header id="command" class="command-strip" aria-label="Gameweek command strip"></header>
<section id="plan" class="digest-band" aria-labelledby="digest-title">
  <div id="alert-zone" class="alert-zone hidden" aria-label="Urgent weekly alerts"><div id="alerts" class="alerts"></div></div>
  <div class="digest-head"><h1 id="digest-title" class="digest-title"></h1><div id="digest-clear" class="digest-clear"></div></div>
  <div id="digest-cards" class="digest-grid"></div>
</section>
<main class="dashboard">
  <section id="transfers" class="panel transfers" aria-labelledby="transfers-title">
    <div class="panel-head"><h2 id="transfers-title">Transfers <span>— who comes in, who goes out?</span></h2><button class="info-tip" data-tip="Availability first · route and fixtures next · form muted" aria-label="Transfer methodology">ⓘ</button></div>
    <div id="transfer-hero"></div>
    <div id="opportunity-notes"></div>
    <div id="hit-decision"></div>
    <div class="decision-tables">
      <div class="table-block"><div id="sell-review"></div></div>
      <div class="table-block"><div id="buy-shortlist"></div></div>
    </div>
  </section>
  <section id="captain" class="panel captaincy" aria-labelledby="captain-title">
    <div class="panel-head"><h2 id="captain-title">Captain <span>— who doubles this week?</span></h2><button class="info-tip" data-tip="Ceiling-first · available outfield planned XI" aria-label="Captain methodology">ⓘ</button></div>
    <div id="captain-content"></div>
  </section>
  <section id="team" class="panel lineup" aria-labelledby="lineup-title">
    <div class="panel-head"><h2 id="lineup-title">Team sheet <span>— who starts?</span></h2><div class="state-toggle" aria-label="Squad view"><button class="active" data-lineup-state="planned">Plan applied</button><button data-lineup-state="current">Current squad</button></div><button class="info-tip" data-tip="Availability first, then prior route and next-fixture ease; planned transfers are applied before comparison." aria-label="Team-sheet methodology">ⓘ</button></div>
    <div id="lineup-content"></div>
  </section>
  <section id="chips" class="panel chips" aria-labelledby="chips-title">
    <div class="panel-head"><h2 id="chips-title">Chips <span>— play one or hold?</span></h2><button class="info-tip" data-tip="Heuristics · sample-light · not a learned model · play only when verdict is Strong" aria-label="Chip methodology">ⓘ</button></div>
    <div id="chips-content"></div>
  </section>
  <section id="fixtures" class="panel planner" aria-labelledby="planner-title">
    <div class="panel-head"><h2 id="planner-title">Fixtures <span>— the next five weeks</span></h2><label class="planner-tools"><input id="target-toggle" type="checkbox"> Show bench + targets</label><button class="info-tip" data-tip="Known fixture schedule only; default rows are the post-transfer planned XI." aria-label="Fixture methodology">ⓘ</button></div>
    <div id="planner-content"></div>
  </section>
</main>
<footer id="footer" class="footer"></footer>
<script>
const DATA = __DATA__;

const dom = (selector) => document.querySelector(selector);
const safe = (value, fallback = "—") => value === null || value === "" ? fallback : value;
const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const esc = (value) => String(safe(value, "")).replace(/[&<>"']/g, (character) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[character]));
const money = (value) => `£${number(value).toFixed(1)}m`;
const signed = (value, digits = 1) => `${number(value) >= 0 ? "+" : ""}${number(value).toFixed(digits)}`;
const cap = (value) => String(safe(value, "")).toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());

function availabilityDot(player) {
  const item = player.availability || {level:"red",label:"availability missing"};
  return `<span class="availability ${esc(item.level)}" title="${esc(item.label)} · ${number(item.minutes_prior).toFixed(0)} prior min"></span>`;
}

function fixtureTone(fdr, blank = false) {
  if (blank || fdr === null) return "blank";
  if (number(fdr, 5) <= 2) return "easy";
  if (number(fdr, 5) <= 3) return "medium";
  if (number(fdr, 5) <= 4) return "caution";
  return "hard";
}

function fixturePill(player) {
  const fixture = (player.fixture || {}).next || {label:"Unknown",fdr:null,blank:false};
  return `<span class="fixture-pill ${fixtureTone(fixture.fdr, fixture.blank)}">${esc(fixture.label)}${fixture.fdr === null ? "" : ` · ${number(fixture.fdr).toFixed(1)}`}</span>`;
}

function componentBars(components, keys) {
  const labels = {role:"Role",route:"Route",fixture:"Fix",value:"Value",ceiling:"Ceil",security:"Sec",xgi_route:"xGI"};
  return `<div class="component-stack">${keys.map((key) => {
    const width = Math.max(0, Math.min(100, number((components || {})[key])));
    return `<div class="component"><div class="component-track"><span class="component-fill" style="width:${width}%"></span></div><span class="component-label">${labels[key]}</span></div>`;
  }).join("")}</div>`;
}

function sparkline(history) {
  if (!history || history.length < 2) return `<span class="micro">rank history building</span>`;
  const values = history.map((item) => number(item.rank));
  const low = Math.min(...values), high = Math.max(...values), spread = Math.max(1, high - low);
  const points = values.map((value, index) => {
    const x = 4 + index * (102 / Math.max(1, values.length - 1));
    const y = 4 + ((value - low) / spread) * 21;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<svg class="spark" viewBox="0 0 110 30" role="img" aria-label="Overall rank over recent gameweeks"><line x1="3" y1="26" x2="107" y2="26" stroke="rgba(244,239,228,.08)"/><polyline points="${points}" fill="none" stroke="#00D785" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function renderCommand() {
  const command = DATA.command;
  const delta = number(command.rank_delta);
  const deltaClass = delta < 0 ? "up" : delta > 0 ? "down" : "flat";
  const deltaArrow = delta < 0 ? "↑" : delta > 0 ? "↓" : "→";
  const rank = number(command.overall_rank).toLocaleString();
  const chips = Object.entries(command.chips_used || {}).map(([code, used]) => `<span class="chip-pill ${number(used) > 0 ? "used" : ""}" title="${number(used)} used">${esc(code)}</span>`).join("");
  dom("#command").innerHTML = `
    <div class="gw-lockup"><div class="gw">GW${DATA.meta.target_gw}</div><div><div class="page-identity">Decision Cockpit · ${DATA.meta.entry_id}</div><div class="deadline">${esc(DATA.meta.deadline)}</div></div></div>
    <div class="rank-lockup"><div><div class="rank-caption">Overall rank after GW${command.as_of_gw}</div><div class="rank-number">${rank} <span class="rank-delta ${deltaClass}">${deltaArrow} ${Math.abs(delta).toLocaleString()}</span></div></div>${sparkline(command.rank_history)}<div class="points-total"><div class="rank-caption">Season</div><strong>${number(command.total_points).toLocaleString()} pts</strong></div></div>
    <div class="wallet"><span class="wallet-item"><span class="rank-caption">Bank</span> <strong>${money(command.bank)}</strong></span><span class="wallet-item ${number(command.free_transfers) === 0 ? "constrained" : ""}"><span class="rank-caption">FT</span> <strong>×${number(command.free_transfers)}</strong></span><span class="wallet-item"><span class="rank-caption">Team value</span> <strong>${money(command.team_value)}</strong></span><span class="chip-pills">${chips}</span></div>
    <nav class="anchor-nav" aria-label="Cockpit sections"><a href="#plan" data-anchor="plan">Plan</a><a href="#transfers" data-anchor="transfers">Transfers</a><a href="#captain" data-anchor="captain">Captain</a><a href="#team" data-anchor="team">Team</a><a href="#chips" data-anchor="chips">Chips</a><a href="#fixtures" data-anchor="fixtures">Fixtures</a></nav>`;
}

function renderAlerts() {
  const zone = dom("#alert-zone");
  if (!DATA.alerts.length) {
    zone.classList.add("hidden");
    dom("#alerts").innerHTML = "";
    dom("#digest-clear").textContent = "✓ no urgent flags";
    return;
  }
  zone.classList.remove("hidden");
  dom("#digest-clear").textContent = "";
  const icons = {red:"●",amber:"●"};
  dom("#alerts").innerHTML = DATA.alerts.map((alert) => `<div class="alert ${esc(alert.severity)}"><span aria-hidden="true">${icons[alert.severity]}&nbsp;</span>${esc(alert.text)}</div>`).join("");
}

function digestAnswer(key, item) {
  if (key === "transfer") {
    if (item.action === "transfer") return `<span class="action">Sell ${esc(item.sell_name)}</span> → <span class="action">Buy ${esc(item.buy_name)}</span>`;
    if (item.action === "package") return `<span class="action">${esc(item.answer)}</span>`;
    return `<span class="action">Hold</span> — bank the transfer`;
  }
  if (key === "captain") return `<span class="action">${esc(item.name)}</span> (${esc(item.fixture)})`;
  if (key === "lineup") return item.suggestions.length ? `<span class="action">1 change</span> suggested` : `<span class="action">No changes</span> — XI confirmed`;
  return item.code ? `<span class="action">${esc(item.answer)}</span>` : `<span class="action">Hold</span> all chips`;
}

function renderDigest() {
  const zones = {transfer:"transfers",captain:"captain",lineup:"team",chip:"chips"};
  const labels = {transfer:"TRANSFER",captain:"CAPTAIN",lineup:"LINEUP",chip:"CHIP"};
  dom("#digest-title").textContent = `Your GW${DATA.meta.target_gw} plan`;
  dom("#digest-cards").innerHTML = Object.keys(zones).map((key) => {
    const item = DATA.plan[key];
    return `<article class="digest-card" data-digest-card="${key}"><div class="eyebrow">${labels[key]}</div><div class="digest-answer">${digestAnswer(key,item)}</div><div class="digest-why" title="${esc(item.reason_short)}">${esc(item.reason_short)}</div><div class="digest-sub">${esc(item.subline)}</div><a class="details-link" href="#${zones[key]}">details ↓</a></article>`;
  }).join("");
}

function renderHero() {
  const hero = DATA.plan.transfer;
  const score = hero.action === "hold" ? `<span class="muted">No qualifying edge</span>` : `<span class="edge-chip">${esc(hero.edge.label)}</span><span class="raw-score">raw ${signed(hero.upgrade,2)}</span>`;
  dom("#transfer-hero").innerHTML = `<article class="hero ${hero.action === "hold" ? "hold" : ""}"><div class="eyebrow">Committed transfer plan</div><h1>${esc(hero.headline)}</h1><div class="reason">${esc(hero.reason_short)}</div><details class="inline-detail"><summary>Why this move ▾</summary><div>${esc(hero.reason)}</div></details><div class="hero-metrics"><div class="metric">Upgrade signal<strong>${score}</strong></div><div class="metric">Bank after move<strong>${money(hero.bank_left)}</strong></div><div class="metric">Decision state<strong>${esc(hero.decision_state)}</strong></div></div></article>`;
  dom("#opportunity-notes").innerHTML = DATA.opportunities.map((item) => `<div class="opportunity-note">↗ ${esc(item.text)}</div>`).join("");
}

function renderHit() {
  const hit = DATA.hit;
  if (!hit) {
    dom("#hit-decision").innerHTML = "";
    return;
  }
  const values = [hit.next1, hit.next3, hit.next5];
  const scale = Math.max(1, ...values.map((value) => Math.abs(number(value))));
  const bars = values.map((value, index) => `<div class="payoff-item"><span class="payoff-value">${signed(value,0)}</span><span class="payoff-bar ${number(value) < 0 ? "negative" : ""}" style="height:${Math.max(5,Math.abs(number(value))/scale*32)}px"></span><span>${["1 GW","3 GW","5 GW"][index]}</span></div>`).join("");
  const cardClass = hit.worth ? (hit.low_confidence ? "low-confidence" : "worth") : "not-worth";
  const verdictClass = hit.worth ? (hit.low_confidence ? "caution" : "good") : "bad";
  const scenario = esc(String(hit.scenario).replace("-","−"));
  const countWords = {2:"two",3:"three",4:"four",5:"five"};
  const countLabel = `${countWords[number(hit.transfer_count)] || number(hit.transfer_count)}-transfer`;
  const status = hit.is_primary ? "part of this week's plan" : "not part of this week's plan";
  dom("#hit-decision").innerHTML = `<details class="hit-alternative"><summary>${hit.is_primary ? "Committed" : "Alternative"}: ${scenario} ${countLabel} package · projects ${signed(hit.next3,0)} net over 3GW · ${esc(String(hit.confidence).toLowerCase())} confidence — ${status} ▸</summary><div class="hit-card ${cardClass}"><div><div class="hit-title">${scenario} hit → net ${signed(hit.next3,0)} over 3 GW <span class="verdict ${verdictClass}">${esc(hit.verdict)}</span></div><div class="hit-note">${esc(hit.reason)}</div></div><div class="payoff">${bars}</div></div></details>`;
}

let selectedSellId = DATA.plan.transfer.action === "transfer" ? number(DATA.plan.transfer.sell_id) : (DATA.sell[0] ? number(DATA.sell[0].id) : 0);
let budgetLimit = 0;
let buySort = "score";

function selectedSell() {
  return DATA.sell.find((item) => number(item.id) === selectedSellId) || DATA.sell[0] || null;
}

function installReasonToggles(containerSelector) {
  document.querySelectorAll(`${containerSelector} [data-reason-toggle]`).forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    const row = button.closest("tr");
    row.classList.toggle("detail-open");
    button.textContent = row.classList.contains("detail-open") ? "⌃" : "⌄";
    button.setAttribute("aria-expanded", row.classList.contains("detail-open") ? "true" : "false");
  }));
}

function renderSell() {
  if (!DATA.sell.length) {
    dom("#sell-review").innerHTML = `<div class="subhead"><h3>Most replaceable in your squad</h3></div><div class="empty">Insufficient sell-review data for GW${DATA.meta.target_gw}</div>`;
    return;
  }
  const visibleLimit = number(DATA.display.sell,5);
  const rows = DATA.sell.map((player,index) => `<tr data-sell-id="${number(player.id)}" class="${index >= visibleLimit ? "extra-row" : ""} ${number(player.id) === selectedSellId ? "selected" : ""} ${player.availability.level === "red" ? "quarantine" : ""}"><td>${availabilityDot(player)}<span class="player-name">${esc(player.name)}</span><div class="player-sub">${esc(player.position)} · ${money(player.price)}</div><span class="pair-affordance">Pair →</span></td><td><span class="pill ${String(player.recommendation).includes("SELL") ? "sell" : "hold"}">${esc(player.recommendation)}</span><div class="player-sub">${esc(player.confidence)}</div></td><td><div class="row-reason"><span>${esc(player.sell_explanation)}</span><button class="reason-toggle" data-reason-toggle aria-label="Expand reason" aria-expanded="false">⌄</button></div><div class="row-detail">${esc(player.sell_detail)}${player.hold_explanation ? ` · Hold case: ${esc(player.hold_explanation)}` : ""}</div></td></tr>`).join("");
  const expander = DATA.sell.length > visibleLimit ? `<button class="expander-button" data-row-expander="sell">Show all ${DATA.sell.length}</button>` : "";
  dom("#sell-review").innerHTML = `<div class="subhead"><h3>Most replaceable</h3><span class="count">Top ${Math.min(visibleLimit,DATA.sell.length)} of ${DATA.sell.length}</span></div><div class="table-scroll"><table><thead><tr><th>Player</th><th>Call</th><th>Why</th></tr></thead><tbody id="sell-body">${rows}</tbody></table></div>${expander}`;
  installReasonToggles("#sell-review");
  const expandButton = dom('[data-row-expander="sell"]');
  if (expandButton) expandButton.addEventListener("click", () => {
    const body = dom("#sell-body");
    body.classList.toggle("show-all");
    expandButton.textContent = body.classList.contains("show-all") ? `Show top ${visibleLimit}` : `Show all ${DATA.sell.length}`;
  });
  document.querySelectorAll("[data-sell-id]").forEach((row) => row.addEventListener("click", () => {
    selectedSellId = number(row.dataset.sellId);
    const sell = selectedSell();
    budgetLimit = sell ? number(sell.price) + number(DATA.command.bank) : number(DATA.command.bank);
    renderSell();
    renderBuy();
  }));
}

function buyCandidates() {
  const sell = selectedSell();
  const position = sell ? sell.position : "";
  const filtered = DATA.buy.filter((player) => (!position || player.position === position) && number(player.price) <= budgetLimit + 0.001);
  const sorters = {
    score:(a,b) => number(b.score)-number(a.score),
    price:(a,b) => number(a.price)-number(b.price),
    role:(a,b) => number(b.components.role)-number(a.components.role),
    fixture:(a,b) => number(b.components.fixture)-number(a.components.fixture)
  };
  return [...filtered].sort((a,b) => (a.availability.level === "red") - (b.availability.level === "red") || sorters[buySort](a,b));
}

function renderBuy() {
  const sell = selectedSell();
  if (!sell && budgetLimit === 0) budgetLimit = 15;
  const maxPrice = Math.max(15, budgetLimit, ...DATA.buy.map((player) => number(player.price)));
  const candidates = buyCandidates();
  const best = candidates[0] || null;
  const pair = best && sell ? DATA.pairs.find((item) => number(item.sell_id) === number(sell.id) && number(item.buy_id) === number(best.id)) : null;
  const left = best ? Math.max(0, budgetLimit - number(best.price)) : 0;
  let whatIf = `Select a squad player to filter the shortlist by position and affordability.`;
  if (sell && best) {
    whatIf = `${esc(sell.name)} out · ${money(budgetLimit)} budget → ${esc(best.name)} in · ${money(left)} left${pair ? ` · <span class="edge-chip">${esc(pair.edge.label)}</span> <span class="raw-score">raw ${signed(pair.upgrade,2)}</span>` : ""}`;
  } else if (sell) {
    whatIf = `No ${esc(sell.position)} buy is affordable at ${money(budgetLimit)}. Adjust the budget or bank the move.`;
  }
  const controls = ["score","price","role","fixture"].map((key) => `<button class="sort-button ${buySort === key ? "active" : ""}" data-buy-sort="${key}">${key}</button>`).join("");
  const visibleLimit = number(DATA.display.buy,6);
  const rows = candidates.map((player,index) => `<tr class="${index >= visibleLimit ? "extra-row" : ""} ${player.availability.level === "red" ? "quarantine" : ""}"><td>${availabilityDot(player)}<span class="player-name">${esc(player.name)}</span><div class="player-sub">${esc(player.team)} · ${esc(player.position)} · ${money(player.price)}</div></td><td><span class="pill ${String(player.tier).toLowerCase().includes("a") ? "tier-a" : "tier-b"}">${esc(player.tier)}</span><div class="player-sub">${number(player.value).toFixed(1)} pts/£m · ${esc(player.value_context)}</div></td><td>${componentBars(player.components,["role","route","fixture","value"])}</td><td><div class="row-reason"><span>${esc(player.reason_short)}</span><button class="reason-toggle" data-reason-toggle aria-label="Expand reason" aria-expanded="false">⌄</button></div><div class="row-detail">${esc(player.reason)} · Risk: ${esc(player.risk)} · Form context ${number(player.form3).toFixed(1)}</div></td></tr>`).join("");
  const expander = candidates.length > visibleLimit ? `<button class="expander-button" data-row-expander="buy">Show all ${candidates.length}</button>` : "";
  const body = DATA.buy.length ? `<div class="table-scroll"><table><thead><tr><th>Player</th><th>Tier / value</th><th>Components</th><th>Why</th></tr></thead><tbody id="buy-body">${rows || `<tr><td colspan="4">No affordable ${esc(sell ? sell.position : "")} candidates at this budget.</td></tr>`}</tbody></table></div>${expander}` : `<div class="empty">Insufficient buy-shortlist data for GW${DATA.meta.target_gw}</div>`;
  dom("#buy-shortlist").innerHTML = `<div class="subhead"><h3>Buy shortlist</h3><span class="count">Top ${Math.min(visibleLimit,candidates.length)} of ${candidates.length} affordable · ${esc(sell ? sell.position : "all positions")}</span></div><div class="table-controls">Sort ${controls}</div><div class="budget-control"><div class="budget-row"><span>What-if budget</span><strong id="budget-label">${money(budgetLimit)}</strong></div><input id="budget-slider" type="range" min="3.5" max="${maxPrice.toFixed(1)}" step="0.1" value="${budgetLimit.toFixed(1)}" aria-label="Maximum purchase budget"><div class="what-if">${whatIf}</div></div>${body}`;
  installReasonToggles("#buy-shortlist");
  const expandButton = dom('[data-row-expander="buy"]');
  if (expandButton) expandButton.addEventListener("click", () => {
    const bodyElement = dom("#buy-body");
    bodyElement.classList.toggle("show-all");
    expandButton.textContent = bodyElement.classList.contains("show-all") ? `Show top ${visibleLimit}` : `Show all ${candidates.length}`;
  });
  const slider = dom("#budget-slider");
  if (slider) slider.addEventListener("input", () => { budgetLimit = number(slider.value); renderBuy(); });
  document.querySelectorAll("[data-buy-sort]").forEach((button) => button.addEventListener("click", () => { buySort = button.dataset.buySort; renderBuy(); }));
}

function renderCaptain() {
  const captain = DATA.captain;
  if (!captain.available || !captain.recommended_name) {
    dom("#captain-content").innerHTML = `<div class="empty">Insufficient captaincy data for GW${DATA.meta.target_gw}</div>`;
    return;
  }
  const plan = DATA.plan.captain;
  const recommended = captain.options.find((item) => number(item.id) === number(plan.player_id)) || captain.options[0] || null;
  const heroFixture = recommended ? fixturePill(recommended) : "";
  const heroAvailability = recommended ? availabilityDot(recommended) : "";
  const heroOwnership = recommended ? `<span class="pill ownership-pill ${recommended.template_label.toLowerCase()}">${esc(recommended.template_label)} · ${number(recommended.ownership).toFixed(1)}%</span>` : "";
  const heroScore = recommended ? `<span class="pill template">Ceiling score · ${number(recommended.captain_ceiling_rank_score).toFixed(1)} / 100</span>` : "";
  const heroArmband = recommended && recommended.is_captain ? `<span class="armband">(C)</span>` : recommended && recommended.is_vice ? `<span class="armband">(V)</span>` : "";
  const options = captain.options.slice(1,1+number(DATA.display.captain_alternatives,4)).map((player,index) => `<div class="captain-option"><div class="captain-option-main"><span class="captain-rank">${index+2}</span>${availabilityDot(player)}<span class="player-name">${esc(player.name)}</span>${player.is_captain ? `<span class="armband">(C)</span>` : player.is_vice ? `<span class="armband">(V)</span>` : ""}<div class="player-sub captain-badges">${fixturePill(player)}<span class="pill ownership-pill ${player.template_label.toLowerCase()}">${esc(player.template_label)} · ${number(player.ownership).toFixed(1)}%</span></div></div><div>${componentBars(player.components,["ceiling","xgi_route","fixture"])}</div><div class="captain-score">${number(player.captain_ceiling_rank_score).toFixed(1)}<div class="player-sub">/ 100</div></div></div>`).join("");
  const engineDetail = captain.engine_note ? `<details class="inline-detail"><summary>Alternative model view ▾</summary><div>${esc(captain.engine_note)}</div></details>` : "";
  dom("#captain-content").innerHTML = `<div class="captain-hero"><div class="eyebrow">Committed captain</div><div class="captain-name">${heroAvailability}${esc(plan.name)}${heroArmband}</div><div class="reason">${esc(plan.reason_short)}</div><details class="inline-detail"><summary>Why this captain ▾</summary><div>${esc(captain.reason)}</div></details>${engineDetail}<div class="captain-fixture">${heroFixture}${heroOwnership}${heroScore}</div></div><div class="captain-list">${options}</div>`;
}

function playerCard(player, stateName) {
  const isPlanCaptain = stateName === "planned" && number(player.id) === number(DATA.plan.captain.player_id);
  const armband = isPlanCaptain || (stateName === "current" && player.is_captain) ? `<span class="armband">C</span>` : stateName === "current" && player.is_vice ? `<span class="armband">V</span>` : "";
  return `<div class="player-card ${esc(player.availability.level)}">${availabilityDot(player)}${armband}<span class="player-name">${esc(player.name)}</span>${fixturePill(player)}</div>`;
}

let lineupState = "planned";

function renderLineup() {
  const state = DATA.lineups[lineupState];
  if (!state || !state.squad.length) {
    dom("#lineup-content").innerHTML = `<div class="empty">Insufficient squad data for GW${DATA.meta.target_gw}</div>`;
    return;
  }
  const order = ["GKP","DEF","MID","FWD"];
  const rows = order.map((position) => {
    const players = state.starters.filter((player) => player.position === position);
    return players.length ? `<div class="pitch-row">${players.map((player) => playerCard(player,lineupState)).join("")}</div>` : "";
  }).join("");
  const bench = state.bench_order.map((playerId) => state.bench.find((item) => number(item.id) === number(playerId))).filter(Boolean);
  const benchCards = bench.map((player,index) => `<div class="bench-card ${esc(player.availability.level)}"><div class="bench-order">${player.position === "GKP" ? "GK reserve" : `Bench ${index+1}`}</div><div>${availabilityDot(player)}<span class="player-name">${esc(player.name)}</span></div><div class="player-sub">${fixturePill(player)}</div></div>`).join("");
  const suggestion = state.suggestions[0] || null;
  const advice = suggestion ? `<div class="lineup-advice">${lineupState === "planned" ? "✓ Plan applies" : "⚠ Current flag"}: ${esc(suggestion.summary)}<details class="inline-detail"><summary>Why ▾</summary><div>${esc(suggestion.detail)}</div></details></div>` : `<div class="lineup-advice clear">✓ No lineup change clears the comparison gate.</div>`;
  const caption = lineupState === "planned" ? "Transfer and recommended lineup state applied." : "Today’s actual squad before the committed plan.";
  dom("#lineup-content").innerHTML = `<div class="state-caption">${caption}</div><div class="pitch">${rows}</div><div class="bench-zone"><div class="subhead"><h3>Bench order</h3><span class="count">${state.bench.length} players</span></div><div class="bench-row">${benchCards}</div>${advice}</div>`;
  document.querySelectorAll("[data-lineup-state]").forEach((button) => button.classList.toggle("active", button.dataset.lineupState === lineupState));
}

function renderChips() {
  const names = {TC:"Triple Captain",BB:"Bench Boost",WC:"Wildcard",FH:"Free Hit"};
  dom("#chips-content").innerHTML = `<div class="zone-call"><div class="eyebrow">Committed chip call</div><strong>${esc(DATA.plan.chip.answer)}</strong><span>${esc(DATA.plan.chip.subline)}</span></div><div class="chips-list">${DATA.chips.map((chip) => {
    const verdictClass = chip.verdict.toLowerCase();
    return `<div class="chip-row ${number(chip.used) > 0 ? "used" : ""}"><div class="chip-top"><div class="chip-code">${esc(chip.code)}</div><div><div class="micro">${esc(names[chip.code])} · ${number(chip.used) > 0 ? `${number(chip.used)} used` : "available"}</div><div class="meter"><span class="meter-fill ${verdictClass}" style="width:${Math.max(0,Math.min(100,number(chip.score)))}%"></span></div></div><div class="chip-verdict ${verdictClass === "strong" ? "good" : verdictClass === "consider" ? "" : "muted"}">${esc(chip.verdict)} · ${number(chip.score).toFixed(0)}</div></div><details class="inline-detail chip-reason"><summary>Why ▾</summary><div><span class="heuristic-label">Heuristic</span> · ${esc(chip.reason)}</div></details></div>`;
  }).join("")}</div>`;
}

function fixtureCell(cell) {
  return `<div class="fixture-cell ${fixtureTone(cell.fdr,cell.blank)}">${esc(cell.label)}${cell.fdr === null ? "" : `<div class="player-sub">FDR ${number(cell.fdr).toFixed(1)}</div>`}</div>`;
}

function renderPlanner() {
  const showTargets = dom("#target-toggle").checked;
  const playerRows = DATA.fixtures.players.map((player) => ({...player,isTarget:false}));
  const benchRows = showTargets ? DATA.fixtures.bench.map((player) => ({...player,isTarget:false,isBench:true})) : [];
  const ownedIds = [...DATA.fixtures.players,...DATA.fixtures.bench].map((player) => number(player.id));
  const targetRows = showTargets ? DATA.fixtures.targets.filter((target) => !ownedIds.includes(number(target.id))).map((player) => ({...player,isTarget:true,isBench:false})) : [];
  const rows = [...playerRows,...benchRows,...targetRows];
  if (!rows.length) {
    dom("#planner-content").innerHTML = `<div class="empty">Insufficient fixture data for GW${DATA.meta.target_gw}</div>`;
    return;
  }
  const header = DATA.fixtures.gameweeks.map((gw) => `<th>GW${number(gw)}</th>`).join("");
  const body = rows.map((player) => `<tr class="${player.isTarget ? "target-row" : ""}"><td>${availabilityDot(player)}<span class="player-name">${esc(player.name)}</span> <span class="muted">${esc(player.position)}</span>${player.isTarget ? `<div class="target-label">Buy target</div>` : player.isBench ? `<div class="target-label muted">Bench</div>` : ""}</td>${((player.fixture || {}).cells || []).map((cell) => `<td>${fixtureCell(cell)}</td>`).join("")}</tr>`).join("");
  dom("#planner-content").innerHTML = `<div class="planner-wrap"><table class="fixture-table"><thead><tr><th>Player</th>${header}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderFooter() {
  const provenance = DATA.provenance;
  const warnings = provenance.warnings.length ? provenance.warnings.map((warning) => `<div class="warning">⚠ ${esc(warning)}</div>`).join("") : `<div>✓ All requested target-GW tables were available.</div>`;
  dom("#footer").innerHTML = `<div class="footer-grid"><div><strong>Provenance</strong> · GW${DATA.meta.target_gw} · entry ${DATA.meta.entry_id} · decision pack ${esc(provenance.pack_status)} · generated ${esc(provenance.generated_at)}<br>Plan branch: ${esc(provenance.plan_branch)} · pair 3GW equivalent ${signed(provenance.pair_next3_equivalent,1)} pts<br>Availability source: ${esc(provenance.injury_source)}<br>${provenance.sources.map(esc).join(" · ")}${warnings}</div><div><strong>Signal hierarchy</strong><br>Availability → xGI / position route + value + forward fixtures → <span class="muted">form is context only</span><br>Fixture schedule cells use known fixtures; recommendation signals use target-GW prior/forward columns only.</div></div><div class="footer-line">Signals rank options and protect the floor — you make the final call.</div>`;
}

function setupScrollSpy() {
  const links = [...document.querySelectorAll("[data-anchor]")];
  const sections = links.map((link) => dom(`#${link.dataset.anchor}`)).filter(Boolean);
  if (!("IntersectionObserver" in window)) return;
  const observer = new IntersectionObserver((entries) => {
    const visible = entries.filter((entry) => entry.isIntersecting).sort((a,b) => b.intersectionRatio-a.intersectionRatio)[0];
    if (!visible) return;
    links.forEach((link) => link.classList.toggle("active", link.dataset.anchor === visible.target.id));
  }, {rootMargin:"-15% 0px -70% 0px",threshold:[0,.2,.6]});
  sections.forEach((section) => observer.observe(section));
}

function renderAll() {
  renderCommand(); renderAlerts(); renderDigest(); renderHero(); renderHit();
  const sell = selectedSell();
  budgetLimit = sell ? number(sell.price) + number(DATA.command.bank) : 15;
  renderSell(); renderBuy(); renderCaptain(); renderLineup(); renderChips(); renderPlanner(); renderFooter();
  dom("#target-toggle").addEventListener("change", renderPlanner);
  document.querySelectorAll("[data-lineup-state]").forEach((button) => button.addEventListener("click", () => { lineupState = button.dataset.lineupState; renderLineup(); }));
  setupScrollSpy();
}

renderAll();
</script>
</body>
</html>"""


def render_html(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    encoded = encoded.replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA__", encoded)


def validate_data(data: dict[str, Any]) -> None:
    plan = data["plan"]
    assert set(plan) == {"transfer", "captain", "lineup", "chip"}, "digest must contain exactly four answers"
    assert all(len(item["reason_short"]) <= 70 for item in plan.values()), "digest reason exceeds 70 characters"

    transfer = plan["transfer"]
    assert transfer["headline"] == data["hero"]["headline"], "digest transfer and transfer zone disagree"
    assert transfer["bank_left"] == data["hero"]["bank_left"], "transfer bank-left values disagree"
    assert plan["captain"]["name"] == data["captain"]["recommended_name"], "digest captain and captain zone disagree"
    assert plan["captain"]["reason_short"] == data["captain"]["reason_short"], "captain reasons disagree"
    assert plan["lineup"]["answer"] == data["lineups"]["planned"]["answer"], "digest lineup and planned sheet disagree"
    assert plan["lineup"]["suggestions"] == data["lineups"]["planned"]["suggestions"], "lineup suggestions disagree"

    top_chip = max(data["chips"], key=lambda item: item["score"])
    assert plan["chip"]["top_advisor_code"] == top_chip["code"], "digest chip is not the top advisor"
    assert plan["chip"]["top_advisor_verdict"] == top_chip["verdict"], "digest chip verdict and advisor disagree"
    assert (plan["chip"]["code"] is not None) == (top_chip["verdict"] == "Strong"), "Strong-only chip rule failed"
    assert plan["chip"]["answer"].startswith("Play ") == (top_chip["verdict"] == "Strong"), "chip answer violates Strong-only rule"

    planned_ids = {player["id"] for player in data["lineups"]["planned"]["squad"]}
    if transfer["action"] != "hold":
        assert not planned_ids.intersection(transfer["sell_ids"]), "sold player remains in planned squad"
        assert set(transfer["buy_ids"]).issubset(planned_ids), "bought player missing from planned squad"
        sold_ids = set(transfer["sell_ids"])
        assert all(item["out_id"] not in sold_ids for item in plan["lineup"]["suggestions"]), "planned lineup mentions starting a sold player"

    planned_starter_ids = {player["id"] for player in data["lineups"]["planned"]["starters"]}
    assert {player["id"] for player in data["fixtures"]["players"]} == planned_starter_ids, "fixture default is not the planned XI"
    assert data["display"] == DEFAULT_VISIBLE, "progressive-disclosure limits changed unexpectedly"
    assert len(data["captain"]["options"][1: 1 + DEFAULT_VISIBLE["captain_alternatives"]]) == 4, "captain leaderboard must render ranks 2–5"

    assert all(item["severity"] in {"red", "amber"} for item in data["alerts"]), "green alert leaked into urgent strip"
    assert all(item["severity"] == "green" for item in data["opportunities"]), "non-green alert leaked into opportunity notes"
    classifier_sample = [
        {"severity": "red", "text": "red branch"},
        {"severity": "amber", "text": "amber branch"},
        {"severity": "green", "text": "green branch"},
    ]
    urgent_sample, opportunity_sample = split_alerts(classifier_sample)
    assert [item["severity"] for item in urgent_sample] == ["red", "amber"], "red/amber classifier branch failed"
    assert [item["severity"] for item in opportunity_sample] == ["green"], "green classifier branch failed"


def run_self_test(data: dict[str, Any], output: Path, html: str) -> None:
    assert output.exists() and output.stat().st_size > 0, "HTML output missing"
    assert html.count("const DATA =") == 1, "expected exactly one inlined DATA payload"
    assert html.count("<script>") == 1 and html.count("</script>") == 1, "expected exactly one script block"
    assert html.count("<style>") == 1 and html.count("</style>") == 1, "expected exactly one style block"
    forbidden = re.compile(r"https?://|cdn|<link|@import|src=[\"']http", re.IGNORECASE)
    assert not forbidden.search(html), "HTML contains an external reference"
    assert "Decision Cockpit · ${DATA.meta.entry_id}" in html, "page identity is missing"
    assert "Your GW" in html, "digest title renderer is missing"
    assert "Show bench + targets" in html, "fixture progressive disclosure is missing"
    assert "Show all ${DATA.sell.length}" in html and "Show all ${candidates.length}" in html, "row expanders are missing"
    assert "Signals rank options and protect the floor — you make the final call." in html, "honest footer changed"
    assert len(data["squad"]) == 15, f"expected 15 squad players, got {len(data['squad'])}"
    assert len(data["sell"]) == 15, f"expected 15 sell rows, got {len(data['sell'])}"
    assert data["buy"], "buy shortlist is empty"
    assert data["captain"]["recommended_name"], "recommended captain is missing"
    captain_options = data["captain"]["options"]
    captain_scores = [option["captain_ceiling_rank_score"] for option in captain_options]
    starter_ids = {player["id"] for player in data["starters"]}
    assert captain_options and captain_options[0]["is_recommended"], "top ceiling option is not recommended"
    assert data["captain"]["recommended_id"] == captain_options[0]["id"], "captain headline and ranking disagree"
    assert captain_scores == sorted(captain_scores, reverse=True), "captain ranking is not ceiling-score ordered"
    assert all(0 <= score <= 100 for score in captain_scores), "captain score is outside the 0–100 scale"
    assert all(option["id"] in starter_ids for option in captain_options), "captain option is not in the starting XI"
    assert all(option["position"] != "GKP" for option in captain_options), "goalkeeper leaked into captain options"
    assert all(option["availability"]["level"] in {"green", "amber"} for option in captain_options), "red captain option leaked through availability gate"
    assert any(option["position"] in {"MID", "FWD"} for option in captain_options), "captain shortlist has no attackers"
    if data["meta"]["target_gw"] == 10:
        assert data["captain"]["recommended_name"] == "Haaland", "GW10 captain must be Haaland"
        assert data["captain"]["engine_pick_name"] == "Tarkowski", "GW10 engine security pick must remain visible"
        assert any(option["is_captain"] for option in captain_options), "GW10 actual captain is not marked"
        assert any(option["is_vice"] for option in captain_options), "GW10 actual vice-captain is not marked"
    hero = data["hero"]
    if hero["action"] == "transfer":
        assert hero["buy_price"] <= hero["sell_price"] + data["command"]["bank"] + 0.001, "hero is unaffordable"
        assert hero["bank_left"] >= 0, "hero bank-left is negative"
    assert "NaN" not in html and "undefined" not in html, "invalid placeholder leaked into HTML"
    samples = data["availability_test_samples"]
    assert samples["green"] is not None, "no hand-checkable green availability sample"
    assert samples["low_minutes_red"] is not None, "no hand-checkable low-minutes red sample"
    print("Self-test PASS")
    print(f"  squad={len(data['squad'])}; sell={len(data['sell'])}; buy={len(data['buy'])}")
    captain_top = ", ".join(f"{option['name']} {option['captain_ceiling_rank_score']:.1f}" for option in captain_options)
    print(f"  captain={data['captain']['recommended_name']}; top={captain_top}")
    print(f"  engine security pick={data['captain']['engine_pick_name']}; hero={hero['headline']}")
    print(f"  plan branch={data['provenance']['plan_branch']}; digest cards={len(data['plan'])}")
    print(f"  availability samples: green={samples['green']}, low-minutes red={samples['low_minutes_red']}")
    print("  offline references=0; DATA=1; script=1; style=1; invalid placeholders=0")


def main() -> int:
    args = parse_args()
    output = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    data = build_data(args)
    validate_data(data)
    html = render_html(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"Wrote {output} ({len(html):,} bytes)")
    print(f"Decision pack: {data['provenance']['pack_status']}")
    for warning in data["provenance"]["warnings"]:
        print(f"Warning: {warning}")
    if args.self_test:
        run_self_test(data, output, html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
