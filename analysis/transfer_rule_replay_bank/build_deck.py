"""Build and self-check the 16:9 bank-aware transfer replay deck."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "replay_bank_results.csv"
BASELINE_PATH = HERE.parent / "transfer_rule_replay" / "replay_results.csv"
OUTPUT_PATH = HERE / "transfer_rule_replay_bank_deck.pptx"
CHARTS_DIR = HERE / "charts"

SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5

# Exact palette from the existing transfer replay deck.
BG = (10, 13, 16)
WARM_WHITE = (244, 239, 228)
MUTED = (143, 151, 152)
DARK_GREY = (42, 52, 54)
MID_GREY = (79, 92, 93)
ACCENT = (0, 215, 133)
FONT = "Arial"


def _color(rgb: tuple[int, int, int]) -> RGBColor:
    return RGBColor(*rgb)


def verify_source_numbers() -> None:
    """Assert every aggregate used in visible deck copy."""
    results = pd.read_csv(DATA_PATH)
    baseline = pd.read_csv(BASELINE_PATH)
    scored = results.loc[results["rule_pick_name"].ne("NO_CANDIDATE")]
    baseline_scored = baseline.loc[baseline["rule_pick_name"].ne("NO_CANDIDATE")]
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
    assert int(results["agreement"].sum()) == 3
    assert int(results["actual_in_pool"].sum()) == 35
    assert len(baseline_scored) == 43
    assert int(baseline_scored["delta"].sum()) == -191
    assert (
        int((baseline_scored["delta"] > 0).sum()),
        int((baseline_scored["delta"] < 0).sum()),
        int((baseline_scored["delta"] == 0).sum()),
    ) == (14, 24, 5)
    assert int(results["rule_pick_name"].ne(baseline["rule_pick_name"]).sum()) == 13
    assert int(results["delta"].sum() - baseline["delta"].sum()) == -6


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


def add_notes(slide, text: str) -> None:
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
        "BANK-AWARE TRANSFER RULE REPLAY",
        0.75,
        0.78,
        11.833,
        0.3,
        size=14,
        color=ACCENT,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Kicker",
    )
    add_text(
        slide,
        "Did a fair budget rescue\nthe simple transfer rule?",
        0.75,
        2.0,
        11.833,
        1.5,
        size=46,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
        line_spacing=0.92,
        name="Title",
    )
    add_text(
        slide,
        "Entry 816200  |  FPL 2025/26",
        0.75,
        3.78,
        11.833,
        0.4,
        size=18,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        name="Subtitle",
    )
    add_text(
        slide,
        "A leak-free rematch of 46 non-chip transfers",
        0.75,
        5.95,
        11.833,
        0.3,
        size=14,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        name="Method line",
    )
    add_notes(
        slide,
        "This is the fair-budget rematch of the earlier sale-price-only replay. We changed only the candidate price cap. The question is whether access to the real pre-deadline bank rescues the simple form rule.",
    )


def add_setup_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "One change: the rule can use your bank.",
        0.75,
        0.58,
        11.833,
        0.6,
        size=38,
        bold=True,
        name="Title",
    )
    add_text(slide, "OLD CAP", 0.8, 1.75, 3.2, 0.3, size=13, color=MUTED, bold=True, name="Old cap label")
    add_text(slide, "sale price", 0.8, 2.18, 3.2, 0.55, size=30, color=MUTED, bold=True, name="Old cap")
    add_text(slide, "FAIRER CAP", 4.9, 1.75, 3.2, 0.3, size=13, color=ACCENT, bold=True, name="New cap label")
    add_text(slide, "sale + T-1 bank", 4.9, 2.18, 4.1, 0.55, size=30, color=ACCENT, bold=True, name="New cap")
    add_text(slide, "UNCHANGED", 9.35, 1.75, 2.8, 0.3, size=13, color=MUTED, bold=True, name="Unchanged label")
    add_text(slide, "filters, ranking, scoring", 9.35, 2.18, 3.0, 0.85, size=24, bold=True, name="Unchanged")
    add_text(
        slide,
        "Position match  |  prior squad exclusion  |  45+ prior mean minutes  |  prior 4-GW form",
        0.8,
        4.15,
        11.7,
        0.4,
        size=17,
        color=WARM_WHITE,
        name="Locked rule",
    )
    add_text(
        slide,
        "46 transfers  |  chip GWs 6, 13, 23, 34 excluded  |  windows stay [T-4, T-1]",
        0.8,
        5.78,
        11.7,
        0.34,
        size=14,
        color=MUTED,
        name="Method footer",
    )
    add_notes(
        slide,
        "For a transfer in gameweek T, we read the bank from the event T minus 1 picks file and divide the stored tenths by ten. Every other filter, tiebreak, holding window, and chip exclusion stays unchanged, so this is a clean one-change comparison.",
    )


def add_big_number_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "The fair budget did not close the gap.",
        0.75,
        0.58,
        11.833,
        0.6,
        size=40,
        bold=True,
        name="Title",
    )
    add_text(slide, "RULE MINUS ACTUAL", 0.8, 1.82, 4.9, 0.28, size=13, color=MUTED, bold=True, name="Stat label")
    add_text(slide, "-197", 0.75, 2.18, 5.3, 1.15, size=76, color=ACCENT, bold=True, name="Big stat")
    add_text(slide, "784 actual points\n587 rule points", 7.05, 2.10, 4.8, 1.3, size=28, bold=True, line_spacing=1.22, name="Totals")
    add_text(slide, "45 scored transfers  |  -4.38 per transfer", 7.05, 3.72, 5.1, 0.4, size=16, color=MUTED, name="Sample")
    add_text(slide, "The sale-only rule was -191. The added bank changed 13 picks and cost 6 more points.", 0.8, 5.58, 11.7, 0.5, size=18, color=MUTED, name="Comparison")
    add_notes(
        slide,
        "The answer is no. Across 45 candidate-available rows, actual picks scored 784 and rule picks scored 587. The bank-aware deficit is 197 points. Compared with minus 191 before, the extra budget changed choices but made the total six points worse.",
    )


def add_chart_slide(prs: Presentation, filename: str, name: str, notes: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    path = CHARTS_DIR / filename
    assert path.exists(), path
    add_picture_contain(slide, path, 0.5, 0.5, 12.333, 6.5, name=name)
    add_notes(slide, notes)


def add_signal_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "Two things a bigger budget cannot buy.",
        0.75,
        0.58,
        11.833,
        0.6,
        size=40,
        bold=True,
        name="Title",
    )
    # Left: the judgment gap - buys the rule structurally cannot make
    add_text(slide, "11 of 46", 0.8, 2.0, 5.4, 1.0, size=60, color=ACCENT, bold=True, name="Pool stat")
    add_text(slide, "BUYS THE RULE CANNOT MAKE", 0.85, 3.05, 5.5, 0.3, size=14, color=ACCENT, bold=True, name="Pool label")
    add_text(slide, "Injury and rotation returns like Gabriel (24 min) and Saka (29 min) fail a mechanical 45-minute filter, even when affordable.", 0.85, 3.5, 5.4, 1.4, size=15, color=MUTED, line_spacing=1.2, name="Pool caption")
    # Right: the weak-signal gap
    add_text(slide, "+0.35 vs +0.19", 6.75, 2.0, 5.8, 1.0, size=48, bold=True, name="Signal stat")
    add_text(slide, "xGI BEATS FORM", 6.8, 3.05, 5.5, 0.3, size=14, color=MUTED, bold=True, name="Signal label")
    add_text(slide, "Trailing xGI ranks an attacker's next 4 gameweeks of goals about twice as well as trailing form (Spearman, prior study). The rule ranks by the weaker signal.", 6.8, 3.5, 5.6, 1.4, size=15, color=MUTED, line_spacing=1.2, name="Signal caption")
    add_text(slide, "You backed players a filter rejects and read situations a form score misses. Money does not close that.", 0.8, 5.75, 11.7, 0.5, size=17, color=WARM_WHITE, name="Context")
    add_notes(
        slide,
        "The two real reasons the rule loses, and neither is budget. First, 11 of 46 of your actual buys fail the rule's own minutes or price filters, including injury and rotation returns like Gabriel and Saka that a mechanical screen would never surface. Second, the ranking signal is weak: prior work found trailing xGI links with future goals about twice as strongly as trailing form. These are associations, not guarantees.",
    )


def add_action_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "Use it to shortlist, not to decide.",
        0.75,
        0.58,
        11.833,
        0.6,
        size=40,
        bold=True,
        name="Title",
    )
    items = [
        ("1", "Use all package cash.", "Count the bank and cash released by every planned sale."),
        ("2", "Screen attackers with trailing xGI.", "Use recent FPL points as context, not the engine."),
        ("3", "Keep the minutes check, then add role and fixtures.", "Availability protects the shortlist, but it does not finish it."),
        ("4", "Let the rule narrow options.", "Make the final call with the whole squad and transfer package in view."),
    ]
    top = 1.55
    for number, heading, body in items:
        add_text(slide, number, 0.8, top, 0.45, 0.42, size=22, color=MUTED, bold=True, name=f"Action {number} number")
        add_text(slide, heading, 1.45, top, 9.9, 0.4, size=23, color=ACCENT if number == "1" else WARM_WHITE, bold=True, name=f"Action {number} heading")
        add_text(slide, body, 1.45, top + 0.46, 10.4, 0.34, size=16, color=MUTED, name=f"Action {number} body")
        top += 1.22
    add_notes(
        slide,
        "The operating choice is to keep human judgment but improve the screen. Work with the package budget, use trailing xGI for attacker threat, retain the availability check, and make the final decision with role, fixtures, and squad structure included.",
    )


def add_close_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "Keep judgment, upgrade the signal.",
        0.75,
        0.58,
        11.833,
        0.6,
        size=40,
        color=ACCENT,
        bold=True,
        name="Title",
    )
    add_text(slide, "READ THE RESULT WITH THESE LIMITS", 0.8, 1.5, 11.7, 0.3, size=14, color=MUTED, bold=True, name="Caveat header")
    caveats = [
        "One manager and one season. This is descriptive, not causal.",
        "37 of 46 moves were in multi-transfer GWs. Full-bank primary: -197. First-leg-only sensitivity: -170 across a smaller scored set.",
        "Four actual buys also used cash released by another same-GW leg, so sale plus prior bank was not always the full package budget.",
        "Only 35 actual incoming players passed every locked filter. Minutes and feature-price quirks still excluded real buys.",
        "Holding windows ignore captaincy, benching, hits, and whether the rule pick would start.",
    ]
    top = 2.05
    for index, caveat in enumerate(caveats, start=1):
        add_text(slide, "•", 0.82, top, 0.3, 0.34, size=17, color=MUTED, name=f"Caveat {index} bullet")
        add_text(slide, caveat, 1.22, top, 11.0, 0.72, size=16, name=f"Caveat {index} text")
        top += 0.88
    add_notes(
        slide,
        "The decision stays practical: keep judgment, use the full package budget, and strengthen the player screen. Read the exact totals with care because this is one season, the primary and sensitivity score different candidate-available sets, and the per-leg cap still misses cash released inside some same-week packages.",
    )


def build_deck() -> Path:
    verify_source_numbers()
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_WIDTH_IN)
    prs.slide_height = Inches(SLIDE_HEIGHT_IN)
    add_title_slide(prs)
    add_setup_slide(prs)
    add_big_number_slide(prs)
    add_chart_slide(
        prs,
        "chart_1_before_after.png",
        "Before and after gap chart",
        "The sale-only replay was 191 points behind. The bank-aware replay was 197 behind. The bank changed the pool, but this form ranking did not use the wider pool well enough to close the gap.",
    )
    add_chart_slide(
        prs,
        "chart_2_outcome.png",
        "Outcome record chart",
        "The bank-aware rule won 18 fights, lost 22, and tied five. That is a better record than 14, 24, and five before. Yet the average stayed near minus 4.4 points because the size of the losses still mattered.",
    )
    add_chart_slide(
        prs,
        "chart_3_pick_changes.png",
        "Pick change chart",
        "Thirteen rule picks changed when the bank was added. Those changes had a net effect of minus six rule points relative to the old replay. More choice did not improve this ranking engine.",
    )
    add_chart_slide(
        prs,
        "chart_4_big_losses.png",
        "Three biggest misses chart",
        "The fair budget did not change the three former headline misses. Gabriel was affordable but failed the minutes screen. Wilson and Bruno G. were affordable but lost the form ranking. These large holding-window gaps can still contain luck.",
    )
    add_signal_slide(prs)
    add_action_slide(prs)
    add_close_slide(prs)
    assert len(prs.slides) == 10
    prs.save(OUTPUT_PATH)
    return OUTPUT_PATH


def self_check(path: Path) -> None:
    """Read the PPTX back and assert slide, bounds, font, and notes rules."""
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
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.text:
                            assert run.font.name == FONT, (
                                slide_number,
                                shape.name,
                                run.text,
                                run.font.name,
                            )
    print("Self-check passed: 10 slides, bounds, backgrounds, Arial, placeholders, and notes.")


def main() -> None:
    output = build_deck()
    self_check(output)


if __name__ == "__main__":
    main()
