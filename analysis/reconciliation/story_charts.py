"""Build dark-theme charts for the FPL analysis reconciliation."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "reconciliation_results.csv"
CHARTS_DIR = HERE / "charts"

# Exact palette from analysis/transfer_rule_replay_bank/story_charts.py.
BG = (10, 13, 16)
WARM_WHITE = (244, 239, 228)
MUTED = (143, 151, 152)
DARK_GREY = (42, 52, 54)
MID_GREY = (79, 92, 93)
ACCENT = (0, 215, 133)


def _rgb(color: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in color)


BG_C = _rgb(BG)
WARM_WHITE_C = _rgb(WARM_WHITE)
MUTED_C = _rgb(MUTED)
DARK_GREY_C = _rgb(DARK_GREY)
MID_GREY_C = _rgb(MID_GREY)
ACCENT_C = _rgb(ACCENT)

mpl.rcParams.update(
    {
        "font.family": "Arial",
        "axes.facecolor": BG_C,
        "figure.facecolor": BG_C,
        "savefig.facecolor": BG_C,
        "text.color": WARM_WHITE_C,
        "axes.labelcolor": MUTED_C,
        "xtick.color": MUTED_C,
        "ytick.color": MUTED_C,
        "axes.edgecolor": DARK_GREY_C,
    }
)


def load_verified_results() -> pd.DataFrame:
    """Load the reconciliation table and assert the chart inputs."""
    results = pd.read_csv(DATA_PATH)
    required = {"section", "metric", "value", "source", "definition"}
    missing = required - set(results.columns)
    if missing:
        raise ValueError(f"reconciliation_results.csv missing {sorted(missing)}")

    assert metric(results, "replay", "human_total") == 784
    assert metric(results, "replay", "simple_rule_total") == 587
    assert metric(results, "replay", "do_nothing_total") == 534
    assert round(metric(results, "replay", "human_mean"), 2) == 17.42
    assert round(metric(results, "replay", "simple_rule_mean"), 2) == 13.04
    assert round(metric(results, "replay", "do_nothing_mean"), 2) == 11.87
    assert round(metric(results, "form_collapse", "minutes_screened_spearman"), 2) == 0.20
    assert metric(results, "convergence", "replay_form_to_goals_spearman") == 0.19
    assert metric(results, "replay", "actual_buys_outside_rule_pool") == 11
    return results


def metric(results: pd.DataFrame, section: str, name: str) -> float:
    """Read one numeric metric from the long results table."""
    match = results.loc[
        results["section"].eq(section) & results["metric"].eq(name), "value"
    ]
    assert len(match) == 1, (section, name, len(match))
    return float(match.iloc[0])


def _new_figure() -> plt.Figure:
    return plt.figure(figsize=(12.4, 6.2), dpi=180, facecolor=BG_C)


def _title(fig: plt.Figure, title: str, subtitle: str) -> None:
    assert len(title) <= 40, title
    fig.text(
        0.055,
        0.925,
        title,
        color=WARM_WHITE_C,
        fontsize=30,
        fontweight="bold",
        va="top",
    )
    fig.text(0.058, 0.825, subtitle, color=MUTED_C, fontsize=14, va="top")


def _save(fig: plt.Figure, filename: str) -> Path:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    output = CHARTS_DIR / filename
    fig.savefig(output, dpi=180, facecolor=BG_C, transparent=False)
    plt.close(fig)
    with Image.open(output) as rendered:
        rendered.convert("RGB").save(output)
    with Image.open(output) as rendered:
        assert rendered.convert("RGB").getpixel((0, 0)) == BG
    return output


def _clean_axis(ax: plt.Axes) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def chart_1_hierarchy(results: pd.DataFrame) -> Path:
    human = metric(results, "replay", "human_total")
    rule = metric(results, "replay", "simple_rule_total")
    nothing = metric(results, "replay", "do_nothing_total")

    fig = _new_figure()
    _title(
        fig,
        "Human judgment tops this replay",
        "One common metric ranks human > rule > hold. The model tie comes from another experiment.",
    )
    fig.text(
        0.058,
        0.705,
        "SKILLED HUMAN  >  SIMPLE RULE  ≈  MODEL*  >  NOTHING",
        color=WARM_WHITE_C,
        fontsize=18,
        fontweight="bold",
    )

    ax = fig.add_axes([0.25, 0.19, 0.68, 0.43])
    values = [human, rule, nothing]
    labels = ["SKILLED HUMAN", "SIMPLE RULE", "DO NOTHING"]
    colors = [ACCENT_C, MID_GREY_C, DARK_GREY_C]
    y_positions = [2, 1, 0]
    ax.barh(y_positions, values, height=0.42, color=colors)
    for y, value, label, color in zip(y_positions, values, labels, colors):
        ax.text(-18, y, label, color=color if y == 2 else MUTED_C, fontsize=12, fontweight="bold", ha="right", va="center")
        ax.text(value - 12, y, f"{int(value)}", color=BG_C if y == 2 else WARM_WHITE_C, fontsize=24, fontweight="bold", ha="right", va="center")
    ax.text(
        rule + 12,
        1,
        "MODEL ≈ RULE*",
        color=WARM_WHITE_C,
        fontsize=13,
        fontweight="bold",
        va="center",
    )
    ax.set_xlim(0, 900)
    ax.set_ylim(-0.55, 2.55)
    _clean_axis(ax)
    fig.text(
        0.058,
        0.085,
        "*Model was not replay-scored. Its transfer tie is separate. Never compare the 159 and 197 gaps.",
        color=MUTED_C,
        fontsize=11,
    )
    return _save(fig, "chart_1_unified_hierarchy.png")


def chart_2_different_opponents(results: pd.DataFrame) -> Path:
    sim_hold = metric(results, "notebook_simulation", "hold_total")
    sim_engine = metric(results, "notebook_simulation", "engine_total")
    sim_rule = metric(results, "notebook_simulation", "simple_rule_total")
    replay_human = metric(results, "replay", "human_total")
    replay_rule = metric(results, "replay", "simple_rule_total")
    replay_hold = metric(results, "replay", "do_nothing_total")

    fig = _new_figure()
    _title(
        fig,
        "Same rule, different opponents",
        "The rule wins against the model and hold, then loses against the skilled human.",
    )

    left = fig.add_axes([0.06, 0.20, 0.41, 0.48])
    right = fig.add_axes([0.55, 0.20, 0.39, 0.48])

    left.set_title("40-START STRATEGY SIM", loc="left", color=MUTED_C, fontsize=12, fontweight="bold", pad=8)
    left_values = [sim_rule, sim_engine, sim_hold]
    left_labels = ["RULE", "MODEL", "HOLD"]
    left_colors = [ACCENT_C, MID_GREY_C, DARK_GREY_C]
    left_y = [2, 1, 0]
    left.barh(left_y, left_values, height=0.38, color=left_colors)
    for y, value, label, color in zip(left_y, left_values, left_labels, left_colors):
        left.text(-30, y, label, color=color if y == 2 else MUTED_C, fontsize=11, fontweight="bold", ha="right", va="center")
        left.text(value - 8, y, f"{int(value):,}", color=BG_C if y == 2 else WARM_WHITE_C, fontsize=18, fontweight="bold", ha="right", va="center")
    left.set_xlim(-250, 1905)
    left.set_ylim(-0.6, 2.6)
    _clean_axis(left)
    left.text(-220, -0.85, "Mean GW8-34 points across 40 starts", color=MUTED_C, fontsize=10)
    left.text(-220, -1.13, "Rule beats model by 159", color=ACCENT_C, fontsize=12, fontweight="bold")

    right.set_title("45-WINDOW TRANSFER REPLAY", loc="left", color=MUTED_C, fontsize=12, fontweight="bold", pad=8)
    right_values = [replay_human, replay_rule, replay_hold]
    right_labels = ["HUMAN", "RULE", "HOLD"]
    right_colors = [ACCENT_C, MID_GREY_C, DARK_GREY_C]
    right_y = [2, 1, 0]
    right.barh(right_y, right_values, height=0.38, color=right_colors)
    for y, value, label, color in zip(right_y, right_values, right_labels, right_colors):
        right.text(-18, y, label, color=color if y == 2 else MUTED_C, fontsize=11, fontweight="bold", ha="right", va="center")
        right.text(value - 10, y, f"{int(value)}", color=BG_C if y == 2 else WARM_WHITE_C, fontsize=18, fontweight="bold", ha="right", va="center")
    right.set_xlim(-150, 850)
    right.set_ylim(-0.6, 2.6)
    _clean_axis(right)
    right.text(0, -0.85, "Incoming or held points in fixed windows", color=MUTED_C, fontsize=10)
    right.text(0, -1.13, "Rule trails human by 197", color=ACCENT_C, fontsize=12, fontweight="bold")

    fig.text(
        0.5,
        0.055,
        "159 and 197 are different currencies. Compare direction, never magnitude.",
        color=WARM_WHITE_C,
        fontsize=12,
        fontweight="bold",
        ha="center",
    )
    return _save(fig, "chart_2_different_opponents.png")


def chart_3_mechanism(results: pd.DataFrame) -> Path:
    notebook_rho = metric(results, "form_collapse", "minutes_screened_spearman")
    replay_rho = metric(results, "convergence", "replay_form_to_goals_spearman")
    excluded = int(metric(results, "replay", "actual_buys_outside_rule_pool"))

    fig = _new_figure()
    _title(
        fig,
        "Both studies find a weak signal",
        "Different targets tell the same story: form adds little once availability is handled.",
    )

    ax = fig.add_axes([0.31, 0.47, 0.61, 0.22])
    values = [notebook_rho, replay_rho]
    y_positions = [1, 0]
    labels = ["NOTEBOOK: form → next-4 points", "REPLAY STUDY: form → next-4 goals"]
    colors = [ACCENT_C, MID_GREY_C]
    ax.barh(y_positions, values, height=0.35, color=colors)
    for y, value, label, color in zip(y_positions, values, labels, colors):
        ax.text(-0.006, y, label, color=color if y == 1 else MUTED_C, fontsize=12, fontweight="bold", ha="right", va="center")
        ax.text(value + 0.006, y, f"{value:+.2f}", color=WARM_WHITE_C, fontsize=18, fontweight="bold", va="center")
    ax.set_xlim(0, 0.25)
    ax.set_ylim(-0.55, 1.55)
    _clean_axis(ax)

    fig.text(0.06, 0.325, "SAME FAILURE MODE", color=MUTED_C, fontsize=12, fontweight="bold")
    fig.text(0.06, 0.245, "Safe model misses big captain hauls", color=WARM_WHITE_C, fontsize=18, fontweight="bold")
    fig.text(0.06, 0.185, "Captaincy: model -23 points vs rule", color=MUTED_C, fontsize=12)
    fig.text(0.56, 0.245, f"Rule blocks {excluded} of 46 human buys", color=WARM_WHITE_C, fontsize=18, fontweight="bold")
    fig.text(0.56, 0.185, "Injury returns and role judgment sit outside the filter", color=MUTED_C, fontsize=12)
    fig.text(0.06, 0.095, "Both miss upside when a mechanical availability view is too safe.", color=ACCENT_C, fontsize=15, fontweight="bold")
    fig.text(0.06, 0.052, "The 159 simulation gap and 197 replay gap use different metrics.", color=MUTED_C, fontsize=10)
    return _save(fig, "chart_3_agreement.png")


def chart_4_replay_totals(results: pd.DataFrame) -> Path:
    values = [
        metric(results, "replay", "human_total"),
        metric(results, "replay", "simple_rule_total"),
        metric(results, "replay", "do_nothing_total"),
    ]
    means = [
        metric(results, "replay", "human_mean"),
        metric(results, "replay", "simple_rule_mean"),
        metric(results, "replay", "do_nothing_mean"),
    ]

    fig = _new_figure()
    _title(
        fig,
        "The rule beats holding, not judgment",
        "All three totals use the same 45 candidate-available transfer windows.",
    )
    ax = fig.add_axes([0.26, 0.18, 0.67, 0.53])
    labels = ["SKILLED HUMAN", "SIMPLE RULE", "DO NOTHING"]
    colors = [ACCENT_C, MID_GREY_C, DARK_GREY_C]
    y_positions = [2, 1, 0]
    ax.barh(y_positions, values, height=0.46, color=colors)
    for y, value, mean, label, color in zip(y_positions, values, means, labels, colors):
        ax.text(-18, y, label, color=color if y == 2 else MUTED_C, fontsize=12, fontweight="bold", ha="right", va="center")
        ax.text(value - 10, y, f"{int(value)}", color=BG_C if y == 2 else WARM_WHITE_C, fontsize=24, fontweight="bold", ha="right", va="center")
        ax.text(value + 12, y, f"{mean:.2f} per transfer", color=MUTED_C, fontsize=12, va="center")
    ax.set_xlim(0, 930)
    ax.set_ylim(-0.65, 2.65)
    _clean_axis(ax)
    fig.text(0.058, 0.085, "Rule vs hold: +53 points   |   Human vs rule: +197 points", color=WARM_WHITE_C, fontsize=13, fontweight="bold")
    fig.text(0.058, 0.048, "The replay's 197 cannot be compared with the simulation's 159.", color=MUTED_C, fontsize=10)
    return _save(fig, "chart_4_replay_three_way.png")


def main() -> None:
    results = load_verified_results()
    outputs = [
        chart_1_hierarchy(results),
        chart_2_different_opponents(results),
        chart_3_mechanism(results),
        chart_4_replay_totals(results),
    ]
    print("Created charts:")
    for output in outputs:
        with Image.open(output) as image:
            corner = image.convert("RGB").getpixel((0, 0))
            size = image.size
        print(f"- {output.relative_to(HERE)} | size={size} | corner={corner}")
        assert corner == BG


if __name__ == "__main__":
    main()
