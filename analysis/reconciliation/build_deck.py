"""Build and self-check the 16:9 FPL reconciliation deck."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "reconciliation_results.csv"
OUTPUT_PATH = HERE / "reconciliation_deck.pptx"
CHARTS_DIR = HERE / "charts"

SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5

# Exact palette from the bank-aware replay deck.
BG = (10, 13, 16)
WARM_WHITE = (244, 239, 228)
MUTED = (143, 151, 152)
DARK_GREY = (42, 52, 54)
MID_GREY = (79, 92, 93)
ACCENT = (0, 215, 133)
FONT = "Arial"

FOOTER_TEXT = "159 and 197 use different metrics. Compare direction, never magnitude."


def _color(rgb: tuple[int, int, int]) -> RGBColor:
    return RGBColor(*rgb)


def metric(results: pd.DataFrame, section: str, name: str) -> float:
    match = results.loc[
        results["section"].eq(section) & results["metric"].eq(name), "value"
    ]
    assert len(match) == 1, (section, name, len(match))
    return float(match.iloc[0])


def verify_source_numbers() -> pd.DataFrame:
    """Assert every visible number used by the deck."""
    results = pd.read_csv(DATA_PATH)
    assert metric(results, "replay", "human_total") == 784
    assert metric(results, "replay", "simple_rule_total") == 587
    assert metric(results, "replay", "do_nothing_total") == 534
    assert round(metric(results, "replay", "human_mean"), 2) == 17.42
    assert round(metric(results, "replay", "simple_rule_mean"), 2) == 13.04
    assert round(metric(results, "replay", "do_nothing_mean"), 2) == 11.87
    assert metric(results, "replay", "actual_buys_outside_rule_pool") == 11
    assert round(metric(results, "form_collapse", "all_players_spearman"), 2) == 0.79
    assert round(metric(results, "form_collapse", "minutes_screened_spearman"), 2) == 0.20
    assert metric(results, "notebook_simulation", "hold_total") == 1481
    assert metric(results, "notebook_simulation", "engine_total") == 1680
    assert metric(results, "notebook_simulation", "simple_rule_total") == 1839
    assert metric(results, "notebook_simulation", "engine_minus_hold") == 199
    assert metric(results, "notebook_simulation", "engine_minus_simple_rule") == -159
    assert metric(results, "notebook_simulation", "transfer_engine_minus_simple") == -33
    assert metric(results, "notebook_simulation", "captaincy_engine_minus_simple") == -23
    return results


def set_background(slide) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _color(BG)


def add_text(
    slide,
    text: str,
    left: float,
    top: float,
    width: float,
    height: float,
    *,
    size: float,
    color: tuple[int, int, int] = WARM_WHITE,
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    line_spacing: float = 1.0,
    name: str | None = None,
):
    shape = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    if name:
        shape.name = name
    frame = shape.text_frame
    frame.clear()
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    frame.word_wrap = True
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.line_spacing = line_spacing
    paragraph.space_before = Pt(0)
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _color(color)
    return shape


def add_title(slide, text: str, *, color: tuple[int, int, int] = WARM_WHITE) -> None:
    assert "\n" not in text
    assert len(text) <= 40, text
    add_text(
        slide,
        text,
        0.75,
        0.52,
        11.83,
        0.55,
        size=38,
        color=color,
        bold=True,
        name="Title",
    )


def add_footer(slide) -> None:
    add_text(
        slide,
        FOOTER_TEXT,
        0.75,
        7.15,
        11.83,
        0.18,
        size=10,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
        name="Metric guard footer",
    )


def add_notes(slide, text: str) -> None:
    assert FOOTER_TEXT.split(".")[0] in text or "different" in text.lower()
    frame = slide.notes_slide.notes_text_frame
    frame.clear()
    paragraph = frame.paragraphs[0]
    paragraph.space_before = Pt(0)
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0, 0, 0)


def add_picture_contain(
    slide,
    path: Path,
    left: float,
    top: float,
    width: float,
    height: float,
    *,
    name: str,
):
    with Image.open(path) as image:
        image_ratio = image.width / image.height
    box_ratio = width / height
    if image_ratio >= box_ratio:
        render_width = width
        render_height = width / image_ratio
        render_left = left
        render_top = top + (height - render_height) / 2
    else:
        render_height = height
        render_width = height * image_ratio
        render_left = left + (width - render_width) / 2
        render_top = top
    picture = slide.shapes.add_picture(
        str(path),
        Inches(render_left),
        Inches(render_top),
        width=Inches(render_width),
        height=Inches(render_height),
    )
    picture.name = name
    return picture


def add_title_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "FPL ANALYSIS RECONCILIATION",
        0.75,
        0.82,
        11.83,
        0.3,
        size=15,
        color=ACCENT,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Kicker",
    )
    add_text(
        slide,
        "One FPL truth, not two",
        0.75,
        2.25,
        11.83,
        0.85,
        size=54,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
        name="Title",
    )
    add_text(
        slide,
        "Why a simple rule can beat a model and still lose to a skilled human",
        1.25,
        3.43,
        10.83,
        0.55,
        size=22,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        name="Subtitle",
    )
    add_text(
        slide,
        "Entry 816200  |  FPL 2025/26",
        0.75,
        5.86,
        11.83,
        0.28,
        size=15,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        name="Context",
    )
    add_footer(slide)
    add_notes(
        slide,
        "The two reports appear to disagree, but they ask different questions. The key is to separate the opponents and the scoring units. The 159 simulation gap and 197 replay gap use different metrics and cannot be compared as magnitudes.",
    )


def add_contradiction_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_title(slide, "The headlines look opposite")
    add_text(slide, "40-START STRATEGY SIM", 0.8, 1.55, 5.5, 0.3, size=14, color=MUTED, bold=True, name="Left label")
    add_text(slide, "+159", 0.78, 2.05, 3.0, 0.9, size=60, color=ACCENT, bold=True, name="Left stat")
    add_text(slide, "simple rule\nvs model", 3.05, 2.16, 2.7, 0.9, size=25, bold=True, line_spacing=1.05, name="Left headline")
    add_text(slide, "The model also beat hold by 199.", 0.82, 3.45, 5.2, 0.4, size=17, color=MUTED, name="Left detail")

    add_text(slide, "45-WINDOW TRANSFER REPLAY", 6.85, 1.55, 5.6, 0.3, size=14, color=MUTED, bold=True, name="Right label")
    add_text(slide, "+197", 6.82, 2.05, 3.0, 0.9, size=60, color=ACCENT, bold=True, name="Right stat")
    add_text(slide, "human buys\nvs simple rule", 9.25, 2.16, 3.0, 0.9, size=25, bold=True, line_spacing=1.05, name="Right headline")
    add_text(slide, "The rule still beat holding by 53.", 6.87, 3.45, 5.2, 0.4, size=17, color=MUTED, name="Right detail")

    add_text(
        slide,
        "The signs differ because the opponents differ.",
        0.8,
        5.35,
        11.7,
        0.5,
        size=24,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Takeaway",
    )
    add_text(
        slide,
        "159 is a simulated-season mean. 197 is a summed replay gap.",
        0.8,
        5.95,
        11.7,
        0.35,
        size=17,
        color=ACCENT,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Currency warning",
    )
    add_footer(slide)
    add_notes(
        slide,
        "The left number compares two full strategies across 40 starting squads. The right number compares one manager's actual incoming players with rule picks over fixed holding windows. The 159 and 197 gaps use different metrics and must not be compared in size.",
    )


def add_opponent_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_title(slide, "The opponent changed", color=ACCENT)
    add_text(slide, "NOTEBOOK QUESTION", 0.8, 1.55, 5.5, 0.3, size=14, color=MUTED, bold=True, name="Notebook label")
    add_text(slide, "Can the rule beat\na model and no transfers?", 0.8, 2.05, 5.4, 1.25, size=30, bold=True, line_spacing=1.05, name="Notebook question")
    add_text(slide, "Yes, in the 40-start strategy simulation.", 0.8, 3.62, 5.4, 0.5, size=18, color=ACCENT, bold=True, name="Notebook answer")

    add_text(slide, "REPLAY QUESTION", 6.8, 1.55, 5.5, 0.3, size=14, color=MUTED, bold=True, name="Replay label")
    add_text(slide, "Can the rule beat\nthe manager's actual buys?", 6.8, 2.05, 5.4, 1.25, size=30, bold=True, line_spacing=1.05, name="Replay question")
    add_text(slide, "No, on the 45 scored transfer windows.", 6.8, 3.62, 5.4, 0.5, size=18, color=ACCENT, bold=True, name="Replay answer")

    add_text(
        slide,
        "Different opponents can produce different winners without contradiction.",
        1.0,
        5.45,
        11.33,
        0.6,
        size=25,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Conclusion",
    )
    add_footer(slide)
    add_notes(
        slide,
        "The reconciliation is an opponent change, not a statistical trick. The rule is strong against a model and passivity, but a skilled human can sit above it. The 159 and 197 results remain different metrics.",
    )


def add_chart_slide(
    prs: Presentation, filename: str, shape_name: str, notes: str
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    path = CHARTS_DIR / filename
    assert path.exists(), path
    add_picture_contain(slide, path, 0.35, 0.2, 12.63, 6.8, name=shape_name)
    add_footer(slide)
    add_notes(slide, notes)


def add_truth_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_title(slide, "The rule is a floor, not a ceiling")
    add_text(
        slide,
        "SKILLED HUMAN  >  SIMPLE RULE  ~  MODEL  >  NOTHING",
        0.8,
        1.72,
        11.73,
        0.65,
        size=29,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Hierarchy",
    )
    add_text(slide, "FLOOR", 1.05, 3.0, 4.7, 0.45, size=18, color=MUTED, bold=True, name="Floor label")
    add_text(slide, "Rule beats passivity", 1.05, 3.55, 4.9, 0.6, size=30, color=ACCENT, bold=True, name="Floor headline")
    add_text(slide, "Cheap, clear, repeatable", 1.05, 4.35, 4.9, 0.4, size=18, color=MUTED, name="Floor detail")

    add_text(slide, "CEILING", 7.35, 3.0, 4.7, 0.45, size=18, color=MUTED, bold=True, name="Ceiling label")
    add_text(slide, "Judgment finds upside", 7.35, 3.55, 4.9, 0.6, size=30, bold=True, name="Ceiling headline")
    add_text(slide, "Role changes, news, packages", 7.35, 4.35, 4.9, 0.4, size=18, color=MUTED, name="Ceiling detail")
    add_text(
        slide,
        "Use the rule to narrow the field. Use judgment to make the call.",
        0.8,
        5.72,
        11.73,
        0.48,
        size=22,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Action line",
    )
    add_footer(slide)
    add_notes(
        slide,
        "The rule is a strong cheap floor because it beats holding and ties the model on transfers. It is not a ceiling because the human replay result is higher and judgment can use role changes and package context. The 159 and 197 gaps use different metrics.",
    )


def add_action_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_title(slide, "Use the rule, then add judgment")
    actions = [
        ("1", "Filter availability", "Starts, recent minutes, injury news, likely role"),
        ("2", "Build the shortlist", "Recent points as context, plus xGI, fixtures, price"),
        ("3", "Review the package", "Bank, cash released, hits, squad structure"),
        ("4", "Make the upside call", "Role change, captain ceiling, reasons to break the rule"),
    ]
    top = 1.48
    for number, heading, body in actions:
        add_text(slide, number, 0.85, top, 0.45, 0.45, size=23, color=ACCENT, bold=True, name=f"Action {number} number")
        add_text(slide, heading, 1.52, top, 4.2, 0.42, size=24, bold=True, name=f"Action {number} heading")
        add_text(slide, body, 5.85, top + 0.02, 6.2, 0.42, size=17, color=MUTED, name=f"Action {number} detail")
        top += 1.18
    add_text(
        slide,
        "Only promote a new model when it beats this rule on decision points.",
        0.85,
        6.35,
        11.65,
        0.4,
        size=20,
        color=ACCENT,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Guardrail",
    )
    add_footer(slide)
    add_notes(
        slide,
        "Start with availability, use the rule to shortlist, then add xGI, fixtures, package budget, and ceiling judgment. A new model must beat the rule on full decision points. Keep 159 and 197 separate because they use different metrics.",
    )


def add_caveat_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_title(slide, "Keep the two currencies apart", color=ACCENT)
    add_text(
        slide,
        "159",
        0.85,
        1.45,
        2.0,
        0.85,
        size=54,
        color=WARM_WHITE,
        bold=True,
        name="Simulation stat",
    )
    add_text(slide, "40-start simulated-season mean gap", 2.45, 1.68, 4.1, 0.5, size=18, color=MUTED, name="Simulation definition")
    add_text(
        slide,
        "197",
        6.85,
        1.45,
        2.0,
        0.85,
        size=54,
        color=WARM_WHITE,
        bold=True,
        name="Replay stat",
    )
    add_text(slide, "45-window summed transfer-replay gap", 8.45, 1.68, 4.1, 0.5, size=18, color=MUTED, name="Replay definition")
    caveats = [
        "One manager and one season. Luck can shape the replay gap.",
        "Replay points ignore XI use, captaincy, benching, and transfer hits.",
        "Eleven of 46 human buys failed at least one locked rule filter.",
        "The notebook hold baseline means no transfers, with Engine selection and captaincy.",
        "The model has no complete clean replay score, so its placement stays qualitative.",
    ]
    top = 3.0
    for index, caveat in enumerate(caveats, start=1):
        add_text(slide, str(index), 0.88, top, 0.35, 0.34, size=17, color=MUTED, bold=True, name=f"Caveat {index} number")
        add_text(slide, caveat, 1.42, top, 10.75, 0.52, size=17, name=f"Caveat {index} text")
        top += 0.72
    add_footer(slide)
    add_notes(
        slide,
        "This is the main reading rule. The 159 result is a paired mean simulated-season strategy gap. The 197 result is a summed one-manager transfer replay gap. They use different metrics. Other limits include luck, replay omissions, filter exclusions, and no complete model replay score.",
    )


def add_close_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "Keep the floor. Hunt the ceiling.",
        0.75,
        1.28,
        11.83,
        0.8,
        size=48,
        color=ACCENT,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Title",
    )
    add_text(
        slide,
        "The simple rule protects against passivity.\nSkilled judgment adds role, context, and upside.",
        1.25,
        2.65,
        10.83,
        1.2,
        size=28,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
        line_spacing=1.15,
        name="Close statement",
    )
    add_text(
        slide,
        "Different opponents. One unified truth.",
        0.8,
        5.35,
        11.73,
        0.45,
        size=22,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        name="Close line",
    )
    add_text(
        slide,
        "Never compare the 159 and 197 gaps as magnitudes.",
        0.8,
        6.0,
        11.73,
        0.4,
        size=18,
        color=WARM_WHITE,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Final warning",
    )
    add_footer(slide)
    add_notes(
        slide,
        "The close is practical. Keep the simple floor, then use human judgment for the ceiling. The reports reconcile through different opponents, while the 159 and 197 gaps remain different metrics that cannot be compared in size.",
    )


def build_deck() -> Path:
    verify_source_numbers()
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_WIDTH_IN)
    prs.slide_height = Inches(SLIDE_HEIGHT_IN)

    add_title_slide(prs)
    add_contradiction_slide(prs)
    add_opponent_slide(prs)
    add_chart_slide(
        prs,
        "chart_1_unified_hierarchy.png",
        "Unified hierarchy chart",
        "The common replay ranks the human at 784, the rule at 587, and holding at 534. The model sits beside the rule only because the separate transfer-layer simulation was a tie. The 159 and 197 gaps use different metrics.",
    )
    add_chart_slide(
        prs,
        "chart_2_different_opponents.png",
        "Different opponents chart",
        "The rule wins against the model and no transfers in the 40-start strategy simulation. It loses against the human but beats holding in the 45-window replay. The 159 simulation gap and 197 replay gap use different metrics.",
    )
    add_chart_slide(
        prs,
        "chart_3_agreement.png",
        "Mechanism agreement chart",
        "The notebook's screened form-to-points rank link is 0.20. The replay story's form-to-goals link is 0.19. The targets differ, but both are weak. The studies also share a safe-rule failure mode. The 159 and 197 gaps remain different metrics.",
    )
    add_truth_slide(prs)
    add_action_slide(prs)
    add_caveat_slide(prs)
    add_close_slide(prs)
    assert len(prs.slides) == 10
    prs.save(OUTPUT_PATH)
    return OUTPUT_PATH


def self_check(path: Path) -> None:
    """Read the PPTX back and assert slide, bounds, font, title, and notes rules."""
    prs = Presentation(path)
    assert len(prs.slides) == 10
    assert prs.slide_width == Inches(SLIDE_WIDTH_IN)
    assert prs.slide_height == Inches(SLIDE_HEIGHT_IN)
    print(f"Deck self-check: {path.name}")
    print(f"Slides: {len(prs.slides)}")
    for slide_number, slide in enumerate(prs.slides, start=1):
        background_rgb = slide.background.fill.fore_color.rgb
        assert background_rgb == _color(BG), (slide_number, background_rgb)
        notes = slide.notes_slide.notes_text_frame.text.strip()
        assert notes, f"Slide {slide_number} has no speaker notes"
        assert "different" in notes.lower(), f"Slide {slide_number} notes lack metric guard"
        footer_shapes = [shape for shape in slide.shapes if shape.name == "Metric guard footer"]
        assert len(footer_shapes) == 1, (slide_number, len(footer_shapes))
        print(f"Slide {slide_number}: {len(slide.shapes)} shapes | notes={len(notes)} chars")
        for shape in slide.shapes:
            right = shape.left + shape.width
            bottom = shape.top + shape.height
            assert shape.left >= 0 and shape.top >= 0, (slide_number, shape.name)
            assert right <= prs.slide_width, (slide_number, shape.name, "right overflow")
            assert bottom <= prs.slide_height, (slide_number, shape.name, "bottom overflow")
            assert not shape.is_placeholder, (slide_number, shape.name, "placeholder")
            if shape.has_text_frame:
                assert shape.text.strip(), (slide_number, shape.name, "empty text")
                if shape.name == "Title":
                    assert "\n" not in shape.text, (slide_number, "wrapped title source")
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.text:
                            assert run.font.name == FONT, (
                                slide_number,
                                shape.name,
                                run.text,
                                run.font.name,
                            )
    print("Self-check passed: 10 slides, bounds, backgrounds, Arial, titles, notes, and metric guards.")


def main() -> None:
    output = build_deck()
    self_check(output)


if __name__ == "__main__":
    main()
