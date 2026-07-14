"""Build the four dark-theme charts for the transfer-rule replay story."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "replay_results.csv"
CHARTS_DIR = HERE / "charts"

# Exact constants from carousel/brand.py.
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


def load_verified_results() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the replay CSV and assert the verified communication numbers."""
    results = pd.read_csv(DATA_PATH)
    scored = results.loc[results["rule_pick_name"].ne("NO_CANDIDATE")].copy()
    scored["outspent_cap"] = scored["actual_in_price"] > scored["out_sell_price"]

    assert len(results) == 46
    assert len(scored) == 43
    assert int(results["agreement"].sum()) == 3
    assert int(scored["actual_pts"].sum()) == 758
    assert int(scored["rule_pts"].sum()) == 567
    assert int(scored["delta"].sum()) == -191
    assert round(float(scored["delta"].mean()), 2) == -4.44
    assert (
        int((scored["delta"] > 0).sum()),
        int((scored["delta"] < 0).sum()),
        int((scored["delta"] == 0).sum()),
    ) == (14, 24, 5)

    expected_segments = {
        False: (23, -43, -1.87, 9, 11, 3),
        True: (20, -148, -7.40, 5, 13, 2),
    }
    for outspent, expected in expected_segments.items():
        segment = scored.loc[scored["outspent_cap"].eq(outspent)]
        actual = (
            len(segment),
            int(segment["delta"].sum()),
            round(float(segment["delta"].mean()), 2),
            int((segment["delta"] > 0).sum()),
            int((segment["delta"] < 0).sum()),
            int((segment["delta"] == 0).sum()),
        )
        assert actual == expected

    return results, scored


def _new_figure() -> plt.Figure:
    return plt.figure(figsize=(12.4, 6.2), dpi=180, facecolor=BG_C)


def _title(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(
        0.055,
        0.925,
        title,
        color=WARM_WHITE_C,
        fontsize=36,
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
    return output


def chart_1_headline(scored: pd.DataFrame) -> Path:
    actual = int(scored["actual_pts"].sum())
    rule = int(scored["rule_pts"].sum())
    gap = actual - rule

    fig = _new_figure()
    _title(
        fig,
        "Actual picks beat the rule by 191 points.",
        "Both sides are scored over the same 43 holding windows.",
    )
    ax = fig.add_axes([0.075, 0.18, 0.85, 0.48])
    ax.set_xlim(495, 830)
    ax.set_ylim(-0.68, 0.68)
    ax.plot([rule, actual], [0, 0], color=DARK_GREY_C, linewidth=11, solid_capstyle="round")
    ax.scatter(rule, 0, s=720, color=MUTED_C, edgecolors=BG_C, linewidths=3, zorder=3)
    ax.scatter(actual, 0, s=720, color=ACCENT_C, edgecolors=BG_C, linewidths=3, zorder=3)

    ax.text(rule, 0.22, "RULE", color=MUTED_C, fontsize=13, fontweight="bold", ha="center")
    ax.text(rule, 0.08, f"{rule}", color=WARM_WHITE_C, fontsize=28, fontweight="bold", ha="center")
    ax.text(actual, 0.22, "ACTUAL", color=ACCENT_C, fontsize=13, fontweight="bold", ha="center")
    ax.text(actual, 0.08, f"{actual}", color=WARM_WHITE_C, fontsize=28, fontweight="bold", ha="center")
    ax.annotate(
        "",
        xy=(actual, -0.27),
        xytext=(rule, -0.27),
        arrowprops={"arrowstyle": "<->", "color": MUTED_C, "linewidth": 1.8},
    )
    ax.text(
        (actual + rule) / 2,
        -0.37,
        f"{gap}-point gap",
        color=WARM_WHITE_C,
        fontsize=16,
        fontweight="bold",
        ha="center",
    )

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _save(fig, "chart_1_headline.png")


def chart_2_decomposition(scored: pd.DataFrame) -> Path:
    outspent = scored.loc[scored["outspent_cap"]]
    fair = scored.loc[~scored["outspent_cap"]]
    total_loss = abs(int(scored["delta"].sum()))
    cap_loss = abs(int(outspent["delta"].sum()))
    fair_loss = abs(int(fair["delta"].sum()))
    share = round(100 * cap_loss / total_loss)

    fig = _new_figure()
    _title(
        fig,
        "The budget cap created 77% of the loss.",
        "The rule could not use banked funds when the manager bought above the sale price.",
    )
    fig.text(0.06, 0.70, f"{share}%", color=ACCENT_C, fontsize=68, fontweight="bold", va="top")
    fig.text(
        0.245,
        0.665,
        "of the 191-point deficit came from\n20 transfers that outspent the cap",
        color=WARM_WHITE_C,
        fontsize=20,
        fontweight="bold",
        va="top",
        linespacing=1.25,
    )

    ax = fig.add_axes([0.06, 0.18, 0.88, 0.25])
    ax.barh(0, cap_loss, height=0.46, color=ACCENT_C)
    ax.barh(0, fair_loss, left=cap_loss, height=0.46, color=DARK_GREY_C)
    ax.text(cap_loss / 2, 0, "-148", color=BG_C, fontsize=27, fontweight="bold", ha="center", va="center")
    ax.text(cap_loss + fair_loss / 2, 0, "-43", color=WARM_WHITE_C, fontsize=22, fontweight="bold", ha="center", va="center")
    ax.text(
        0,
        -0.42,
        "YOU OUTSPENT THE CAP\n20 transfers  |  -7.40 per transfer",
        color=ACCENT_C,
        fontsize=12,
        fontweight="bold",
        ha="left",
        va="top",
        linespacing=1.35,
    )
    ax.text(
        cap_loss + 2,
        -0.42,
        "BUDGET-FAIR FIGHTS\n23 transfers  |  -1.87 per transfer",
        color=MUTED_C,
        fontsize=12,
        fontweight="bold",
        ha="left",
        va="top",
        linespacing=1.35,
    )
    ax.set_xlim(0, total_loss)
    ax.set_ylim(-0.72, 0.55)
    ax.axis("off")
    return _save(fig, "chart_2_decomposition.png")


def chart_3_fair_fights(scored: pd.DataFrame) -> Path:
    fair = scored.loc[~scored["outspent_cap"]]
    outspent = scored.loc[scored["outspent_cap"]]
    values = [round(float(fair["delta"].mean()), 2), round(float(outspent["delta"].mean()), 2)]
    labels = ["Budget-fair fights\n23 transfers", "You outspent the cap\n20 transfers"]
    records = ["9 W   11 L   3 T", "5 W   13 L   2 T"]

    fig = _new_figure()
    _title(
        fig,
        "With a fair budget, the rule was close.",
        "The cap made the average loss almost four times worse.",
    )
    ax = fig.add_axes([0.27, 0.18, 0.67, 0.49])
    y = [1, 0]
    ax.barh(y, values, height=0.34, color=[ACCENT_C, MID_GREY_C])
    ax.axvline(0, color=DARK_GREY_C, linewidth=1.5)

    for y_pos, value, record, color in zip(y, values, records, [ACCENT_C, MUTED_C]):
        if abs(value) > 4:  # long bar: label inside so it clears the y-axis labels
            ax.text(value + 0.3, y_pos, f"{value:.2f}", color=WARM_WHITE_C, fontsize=24, fontweight="bold", ha="left", va="center")
        else:
            ax.text(value - 0.18, y_pos, f"{value:.2f}", color=WARM_WHITE_C, fontsize=24, fontweight="bold", ha="right", va="center")
        ax.text(0.25, y_pos, record, color=color, fontsize=15, fontweight="bold", ha="left", va="center")

    ax.set_yticks(y, labels=labels)
    ax.tick_params(axis="y", length=0, labelsize=15, pad=18)
    ax.set_xlim(-8.3, 3.2)
    ax.set_xticks([-8, -6, -4, -2, 0, 2])
    ax.tick_params(axis="x", length=0, labelsize=11)
    ax.set_xlabel("Rule minus actual points per transfer", fontsize=12, labelpad=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _save(fig, "chart_3_fair_fights.png")


def chart_4_cases(scored: pd.DataFrame) -> Path:
    cases = [
        (3, "Semenyo vs Reijnders", 31),
        (16, "Calvert-Lewin vs Thiago", 21),
        (27, "Hill vs Mukiele", 14),
        (15, "Merino vs Bruno G.", -40),
        (16, "Dewsbury-Hall vs Wilson", -41),
        (20, "Lewis-Potter vs Gabriel", -56),
    ]
    expected = {(gw, rule): delta for gw, rule, delta in cases}
    for gw, rule_name, delta in cases:
        rule_pick = rule_name.split(" vs ")[0]
        match = scored.loc[(scored["gw"].eq(gw)) & (scored["rule_pick_name"].eq(rule_pick))]
        assert len(match) == 1
        assert int(match.iloc[0]["delta"]) == expected[(gw, rule_name)]

    fig = _new_figure()
    _title(
        fig,
        "Premium buys drove the three biggest misses.",
        "Rule pick vs actual pick, scored over the actual holding window.",
    )
    ax = fig.add_axes([0.31, 0.12, 0.63, 0.59])
    y = list(range(len(cases)))[::-1]
    values = [case[2] for case in cases]
    colors = [ACCENT_C if value > 0 else MID_GREY_C for value in values]
    labels = [f"GW{gw}  {names}" for gw, names, _ in cases]
    ax.barh(y, values, height=0.55, color=colors)
    ax.axvline(0, color=DARK_GREY_C, linewidth=1.6)

    for y_pos, value in zip(y, values):
        if value > 0:
            ax.text(value + 1.2, y_pos, f"+{value}", color=ACCENT_C, fontsize=15, fontweight="bold", ha="left", va="center")
        else:
            ax.text(value - 1.2, y_pos, f"{value}", color=WARM_WHITE_C, fontsize=15, fontweight="bold", ha="right", va="center")

    ax.text(
        34,
        1.0,
        "ALL 3 BIG LOSSES\npremium buys the cap excluded",
        color=MUTED_C,
        fontsize=12,
        fontweight="bold",
        ha="right",
        va="center",
        linespacing=1.35,
    )
    ax.set_yticks(y, labels=labels)
    ax.tick_params(axis="y", length=0, labelsize=13, pad=12)
    ax.set_xlim(-66, 36)
    ax.set_xticks([-60, -40, -20, 0, 20])
    ax.tick_params(axis="x", length=0, labelsize=11)
    ax.set_xlabel("Rule minus actual points", fontsize=12, labelpad=9)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _save(fig, "chart_4_cases.png")


def main() -> None:
    _, scored = load_verified_results()
    outputs = [
        chart_1_headline(scored),
        chart_2_decomposition(scored),
        chart_3_fair_fights(scored),
        chart_4_cases(scored),
    ]
    print("Created charts:")
    for output in outputs:
        print(f"- {output.relative_to(HERE)}")


if __name__ == "__main__":
    main()
