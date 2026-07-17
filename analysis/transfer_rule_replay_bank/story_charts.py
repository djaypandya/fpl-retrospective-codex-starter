"""Build four dark-theme charts for the bank-aware transfer-rule replay."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "replay_bank_results.csv"
BASELINE_PATH = HERE.parent / "transfer_rule_replay" / "replay_results.csv"
CHARTS_DIR = HERE / "charts"

# Exact constants from the existing transfer replay.
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


def load_verified_results() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read both CSVs and assert every number used by the charts."""
    results = pd.read_csv(DATA_PATH)
    baseline = pd.read_csv(BASELINE_PATH)
    scored = results.loc[results["rule_pick_name"].ne("NO_CANDIDATE")].copy()
    baseline_scored = baseline.loc[
        baseline["rule_pick_name"].ne("NO_CANDIDATE")
    ].copy()

    assert len(results) == len(baseline) == 46
    assert len(scored) == 45
    assert int(scored["actual_pts"].sum()) == 784
    assert int(scored["rule_pts"].sum()) == 587
    assert int(scored["delta"].sum()) == -197
    assert round(float(scored["delta"].mean()), 2) == -4.38
    assert (
        int((scored["delta"] > 0).sum()),
        int((scored["delta"] < 0).sum()),
        int((scored["delta"] == 0).sum()),
    ) == (18, 22, 5)
    assert len(baseline_scored) == 43
    assert int(baseline_scored["delta"].sum()) == -191
    assert round(float(baseline_scored["delta"].mean()), 2) == -4.44
    assert (
        int((baseline_scored["delta"] > 0).sum()),
        int((baseline_scored["delta"] < 0).sum()),
        int((baseline_scored["delta"] == 0).sum()),
    ) == (14, 24, 5)
    changed = results["rule_pick_name"].ne(baseline["rule_pick_name"])
    assert int(changed.sum()) == 13
    assert int(results["delta"].sum() - baseline["delta"].sum()) == -6
    return results, scored, baseline


def _new_figure() -> plt.Figure:
    return plt.figure(figsize=(12.4, 6.2), dpi=180, facecolor=BG_C)


def _title(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(
        0.055,
        0.925,
        title,
        color=WARM_WHITE_C,
        fontsize=32,
        fontweight="bold",
        va="top",
    )
    fig.text(0.058, 0.815, subtitle, color=MUTED_C, fontsize=15, va="top")


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


def chart_1_before_after(scored: pd.DataFrame, baseline: pd.DataFrame) -> Path:
    baseline_gap = abs(int(baseline["delta"].sum()))
    bank_gap = abs(int(scored["delta"].sum()))
    change = bank_gap - baseline_gap

    fig = _new_figure()
    _title(
        fig,
        "A fairer cap did not close the gap.",
        "Actual's advantage grew by 6 points when every transfer could use the bank.",
    )
    ax = fig.add_axes([0.29, 0.19, 0.64, 0.50])
    labels = ["SALE PRICE ONLY", "SALE + PRE-DEADLINE BANK"]
    values = [baseline_gap, bank_gap]
    colors = [MID_GREY_C, ACCENT_C]
    y = [1, 0]
    ax.barh(y, values, height=0.38, color=colors)
    for y_pos, value, label, color in zip(y, values, labels, colors):
        ax.text(-7, y_pos + 0.11, label, color=color, fontsize=12, fontweight="bold", ha="right")
        ax.text(value - 5, y_pos, f"{value}", color=BG_C, fontsize=28, fontweight="bold", ha="right", va="center")
        ax.text(value + 5, y_pos, "actual advantage", color=MUTED_C, fontsize=13, va="center")
    ax.text(
        0,
        -0.62,
        f"BUDGET-CAP DEFICIT REMOVED  0   |   FAIR-BUDGET DEFICIT LEFT  {bank_gap}   |   CHANGE  +{change}",
        color=WARM_WHITE_C,
        fontsize=13,
        fontweight="bold",
        ha="left",
    )
    ax.set_xlim(0, 245)
    ax.set_ylim(-0.85, 1.5)
    ax.axis("off")
    return _save(fig, "chart_1_before_after.png")


def chart_2_outcome(scored: pd.DataFrame, baseline: pd.DataFrame) -> Path:
    bank_counts = [18, 22, 5]
    baseline_scored = baseline.loc[baseline["rule_pick_name"].ne("NO_CANDIDATE")]
    baseline_counts = [14, 24, 5]
    bank_mean = float(scored["delta"].mean())
    baseline_mean = float(baseline_scored["delta"].mean())

    fig = _new_figure()
    _title(
        fig,
        "Fair budget lifted wins, not the points gap.",
        "Outcome counts improved while the average gap barely moved.",
    )
    ax = fig.add_axes([0.25, 0.22, 0.68, 0.46])
    rows = [(1, bank_counts, "BANK-AWARE", bank_mean, 45), (0, baseline_counts, "SALE-ONLY", baseline_mean, 43)]
    for y_pos, counts, label, mean, n in rows:
        left = 0
        for count, color, outcome in zip(counts, [ACCENT_C, MID_GREY_C, DARK_GREY_C], ["W", "L", "T"]):
            ax.barh(y_pos, count, left=left, height=0.38, color=color)
            text_color = BG_C if outcome == "W" else WARM_WHITE_C
            ax.text(left + count / 2, y_pos, f"{count} {outcome}", color=text_color, fontsize=15, fontweight="bold", ha="center", va="center")
            left += count
        ax.text(-1.5, y_pos + 0.10, label, color=ACCENT_C if y_pos else MUTED_C, fontsize=13, fontweight="bold", ha="right")
        ax.text(48.5, y_pos, f"{mean:.2f} pts / transfer\nn={n} scored", color=WARM_WHITE_C, fontsize=14, fontweight="bold", va="center")
    ax.set_xlim(0, 60)
    ax.set_ylim(-0.6, 1.55)
    ax.axis("off")
    return _save(fig, "chart_2_outcome.png")


def chart_3_pick_changes(results: pd.DataFrame, baseline: pd.DataFrame) -> Path:
    changed = int(results["rule_pick_name"].ne(baseline["rule_pick_name"]).sum())
    unchanged = len(results) - changed
    net_effect = int(results["delta"].sum() - baseline["delta"].sum())

    fig = _new_figure()
    _title(
        fig,
        "Extra budget changed 13 picks, lost 6 points.",
        "The added budget changed choices, but the new choices did not improve the replay total.",
    )
    fig.text(0.06, 0.69, f"{changed}", color=ACCENT_C, fontsize=72, fontweight="bold", va="top")
    fig.text(0.19, 0.655, "picks changed", color=WARM_WHITE_C, fontsize=23, fontweight="bold", va="top")
    fig.text(0.19, 0.585, f"{unchanged} stayed the same", color=MUTED_C, fontsize=15, va="top")
    fig.text(0.62, 0.69, f"{net_effect:+d}", color=WARM_WHITE_C, fontsize=72, fontweight="bold", va="top")
    fig.text(0.77, 0.655, "net rule points", color=WARM_WHITE_C, fontsize=23, fontweight="bold", va="top")
    fig.text(0.77, 0.585, "bank-aware minus sale-only", color=MUTED_C, fontsize=15, va="top")

    ax = fig.add_axes([0.06, 0.20, 0.87, 0.15])
    ax.barh(0, changed, height=0.42, color=ACCENT_C)
    ax.barh(0, unchanged, left=changed, height=0.42, color=DARK_GREY_C)
    ax.text(changed / 2, 0, f"{changed} changed", color=BG_C, fontsize=15, fontweight="bold", ha="center", va="center")
    ax.text(changed + unchanged / 2, 0, f"{unchanged} unchanged", color=WARM_WHITE_C, fontsize=15, fontweight="bold", ha="center", va="center")
    ax.set_xlim(0, 46)
    ax.axis("off")
    return _save(fig, "chart_3_pick_changes.png")


def chart_4_big_losses(results: pd.DataFrame) -> Path:
    requested = [(20, "Gabriel"), (16, "Wilson"), (15, "Bruno G.")]
    cases = []
    for gw, actual_name in requested:
        match = results.loc[
            results["gw"].eq(gw) & results["actual_in_name"].eq(actual_name)
        ]
        assert len(match) == 1
        row = match.iloc[0]
        cases.append(row)
    assert [int(row["delta"]) for row in cases] == [-56, -41, -40]

    fig = _new_figure()
    _title(
        fig,
        "Fair cash did not fix the three biggest misses.",
        "The rule kept its old picks after the cap rose.",
    )
    ax = fig.add_axes([0.31, 0.16, 0.62, 0.53])
    y_positions = [2, 1, 0]
    for y_pos, row in zip(y_positions, cases):
        actual_pts = int(row["actual_pts"])
        rule_pts = int(row["rule_pts"])
        ax.barh(y_pos + 0.14, actual_pts, height=0.23, color=ACCENT_C)
        ax.barh(y_pos - 0.14, rule_pts, height=0.23, color=MID_GREY_C)
        ax.text(actual_pts + 2, y_pos + 0.14, f"{row['actual_in_name']}  {actual_pts}", color=ACCENT_C, fontsize=13, fontweight="bold", va="center")
        ax.text(rule_pts + 2, y_pos - 0.14, f"{row['rule_pick_name']}  {rule_pts}", color=MUTED_C, fontsize=13, fontweight="bold", va="center")
        ax.text(-4, y_pos, f"GW{int(row['gw'])}\n{int(row['delta']):+d}", color=WARM_WHITE_C, fontsize=14, fontweight="bold", ha="right", va="center")
    ax.set_xlim(0, 120)
    ax.set_ylim(-0.55, 2.55)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(
        0.31,
        0.09,
        "Gabriel missed the minutes screen. Wilson and Bruno G. lost the form ranking.",
        color=MUTED_C,
        fontsize=12,
        ha="left",
    )
    return _save(fig, "chart_4_big_losses.png")


def main() -> None:
    results, scored, baseline = load_verified_results()
    outputs = [
        chart_1_before_after(scored, baseline),
        chart_2_outcome(scored, baseline),
        chart_3_pick_changes(results, baseline),
        chart_4_big_losses(results),
    ]
    assert len(outputs) == 4
    print("Created charts:")
    for output in outputs:
        with Image.open(output) as image:
            corner = image.convert("RGB").getpixel((0, 0))
        print(f"- {output.relative_to(HERE)} | corner={corner} | expected={BG}")
        assert corner == BG


if __name__ == "__main__":
    main()
