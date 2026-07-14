"""Build and self-check the 16:9 transfer-rule replay PowerPoint deck."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "replay_results.csv"
OUTPUT_PATH = HERE / "transfer_rule_replay_deck.pptx"
CHARTS_DIR = HERE / "charts"

SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5

# Exact constants from carousel/brand.py.
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
    """Assert every replay aggregate used in visible deck copy."""
    results = pd.read_csv(DATA_PATH)
    scored = results.loc[results["rule_pick_name"].ne("NO_CANDIDATE")].copy()
    scored["outspent_cap"] = scored["actual_in_price"] > scored["out_sell_price"]
    fair = scored.loc[~scored["outspent_cap"]]
    outspent = scored.loc[scored["outspent_cap"]]

    assert len(results) == 46
    assert len(scored) == 43
    assert len(results) - len(scored) == 3
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
    assert (len(fair), int(fair["delta"].sum()), round(float(fair["delta"].mean()), 2)) == (23, -43, -1.87)
    assert (len(outspent), int(outspent["delta"].sum()), round(float(outspent["delta"].mean()), 2)) == (20, -148, -7.40)


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
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
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
        "TRANSFER RULE REPLAY",
        0.75,
        0.75,
        11.833,
        0.28,
        size=14,
        color=ACCENT,
        bold=True,
        align=PP_ALIGN.CENTER,
        name="Kicker",
    )
    add_text(
        slide,
        "Would a simple transfer rule\nhave beaten your judgment?",
        0.75,
        2.0,
        11.833,
        1.5,
        size=44,
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
        3.75,
        11.833,
        0.4,
        size=18,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        name="Subtitle",
    )
    add_text(
        slide,
        "A prior-only replay of 46 real transfers",
        0.75,
        5.9,
        11.833,
        0.3,
        size=14,
        color=MUTED,
        align=PP_ALIGN.CENTER,
        name="Method line",
    )
    add_notes(
        slide,
        "We asked a narrow question: would one simple transfer rule have beaten the manager's real choices? The replay covers entry 816200 in the 2025/26 season. Treat the answer as descriptive, not causal.",
    )


def add_rule_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "We tested one rule on 46 real transfers.",
        0.75,
        0.6,
        11.833,
        0.55,
        size=40,
        bold=True,
        name="Title",
    )

    columns = [0.8, 4.55, 8.3]
    step_numbers = ["1", "2", "3"]
    step_titles = ["Match the position", "Set the screen", "Choose on form"]
    step_bodies = [
        "Exclude the prior squad and the other same-week incoming players.",
        "Keep players at or below the sale price who averaged 45+ minutes over the prior 4 GWs.",
        "Take the highest prior 4-GW points form.",
    ]
    for x, number, title, body in zip(columns, step_numbers, step_titles, step_bodies):
        add_text(slide, number, x, 1.75, 0.5, 0.65, size=42, color=ACCENT, bold=True, name=f"Step {number} number")
        add_text(slide, title, x, 2.55, 3.15, 0.42, size=22, bold=True, name=f"Step {number} heading")
        add_text(slide, body, x, 3.12, 3.15, 1.25, size=15, color=MUTED, line_spacing=1.1, name=f"Step {number} body")

    add_text(
        slide,
        "TEST",
        0.8,
        5.35,
        0.7,
        0.25,
        size=12,
        color=MUTED,
        bold=True,
        name="Test label",
    )
    add_text(
        slide,
        "Score the rule pick and actual pick over the same real holding window.",
        1.55,
        5.31,
        10.4,
        0.38,
        size=16,
        name="Test statement",
    )
    add_text(
        slide,
        "Leak-free replay: 46 non-chip transfers  |  43 candidates  |  3 no-candidate pushes",
        0.8,
        6.42,
        11.7,
        0.3,
        size=12,
        color=MUTED,
        name="Method footer",
    )
    add_notes(
        slide,
        "The rule uses only the four gameweeks before each move, so the ranking does not see the outcome. It matches position, applies the minutes and sale-price screens, then ranks by four-gameweek form. We compare both players over the actual holding window and exclude chip gameweeks.",
    )


def add_big_number_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "The rule would have cost 191 points.",
        0.75,
        0.6,
        11.833,
        0.55,
        size=40,
        bold=True,
        name="Title",
    )
    add_text(slide, "RULE MINUS ACTUAL", 0.8, 2.0, 4.9, 0.28, size=13, color=MUTED, bold=True, name="Stat label")
    add_text(slide, "-191", 0.75, 2.35, 5.6, 1.1, size=72, color=ACCENT, bold=True, name="Big stat")
    add_text(
        slide,
        "758 actual points\n567 rule points",
        7.1,
        2.18,
        4.7,
        1.25,
        size=26,
        bold=True,
        line_spacing=1.25,
        name="Point totals",
    )
    add_text(
        slide,
        "43 scored transfers  |  -4.44 per transfer",
        7.1,
        3.72,
        4.7,
        0.4,
        size=15,
        color=MUTED,
        name="Sample context",
    )
    add_text(
        slide,
        "14 wins  |  24 losses  |  5 ties",
        0.8,
        5.75,
        11.7,
        0.4,
        size=18,
        color=MUTED,
        name="Outcome counts",
    )
    add_notes(
        slide,
        "The answer is no: the rule finished 191 points behind the actual picks across 43 scored transfers. Three no-candidate rows were pushes and do not enter these totals. The score is a holding-window comparison and does not include captaincy, benching, or package effects.",
    )


def add_chart_slide(prs: Presentation, filename: str, shape_name: str, notes: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    path = CHARTS_DIR / filename
    assert path.exists(), path
    add_picture_contain(slide, path, 0.5, 0.5, 12.333, 6.5, name=shape_name)
    add_notes(slide, notes)


def add_signal_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "Form alone is too weak to run the transfer.",
        0.75,
        0.6,
        11.833,
        0.55,
        size=38,
        bold=True,
        name="Title",
    )

    add_text(slide, "+0.35", 0.75, 2.0, 3.4, 0.95, size=60, color=ACCENT, bold=True, name="xGI stat")
    add_text(slide, "TRAILING xGI", 0.8, 3.1, 3.2, 0.28, size=13, color=ACCENT, bold=True, name="xGI label")
    add_text(slide, "Link with next-4-GW goals", 0.8, 3.55, 3.2, 0.5, size=15, color=MUTED, name="xGI caption")

    add_text(slide, "+0.19", 4.9, 2.0, 3.4, 0.95, size=60, bold=True, name="Form stat")
    add_text(slide, "TRAILING FORM", 4.95, 3.1, 3.2, 0.28, size=13, color=MUTED, bold=True, name="Form label")
    add_text(slide, "Link with next-4-GW goals", 4.95, 3.55, 3.2, 0.5, size=15, color=MUTED, name="Form caption")

    add_text(slide, "3/46", 9.0, 2.0, 3.1, 0.95, size=60, bold=True, name="Agreement stat")
    add_text(slide, "SAME PICK", 9.05, 3.1, 3.0, 0.28, size=13, color=MUTED, bold=True, name="Agreement label")
    add_text(slide, "The rule rarely matched you", 9.05, 3.55, 3.0, 0.5, size=15, color=MUTED, name="Agreement caption")

    add_text(
        slide,
        "Prior attacker analysis used Spearman links. xGI carried the stronger forward signal.",
        0.8,
        5.85,
        11.7,
        0.38,
        size=16,
        color=MUTED,
        name="Context line",
    )
    add_notes(
        slide,
        "The replay rule chose a different player on 43 of 46 transfers, but difference alone is not quality. Prior work in this repo found trailing xGI more closely linked with next-four-gameweek goals for attackers than trailing form, at +0.35 versus +0.19. These are associations, not causal effects or guarantees.",
    )


def add_action_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "Keep judgment, but upgrade the screen.",
        0.75,
        0.6,
        11.833,
        0.55,
        size=40,
        bold=True,
        name="Title",
    )

    items = [
        ("1", "Never cap a buy at the sale price.", "Keep banked funds in the choice set.", True),
        ("2", "Screen attackers with trailing xGI.", "Use raw form as context, not the engine.", False),
        ("3", "Keep the 45-minute screen.", "It protects against weak playing-time bets.", False),
        ("4", "Use the rule as a shortlist.", "Make the final call with team context and transfer packages.", False),
    ]
    top = 1.65
    for number, heading, body, highlight in items:
        add_text(slide, number, 0.8, top, 0.45, 0.4, size=22, color=MUTED, bold=True, name=f"Action {number} number")
        add_text(
            slide,
            heading,
            1.45,
            top,
            8.9,
            0.38,
            size=22,
            color=ACCENT if highlight else WARM_WHITE,
            bold=True,
            name=f"Action {number} heading",
        )
        add_text(slide, body, 1.45, top + 0.48, 9.8, 0.3, size=15, color=MUTED, name=f"Action {number} body")
        top += 1.22

    add_notes(
        slide,
        "The operating choice is to keep human judgment and improve the first screen. Banked cash must stay available, and attacker shortlists should lean on trailing xGI rather than raw form alone. The minutes filter remains useful, but the rule should narrow options rather than make the final transfer.",
    )


def add_close_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide)
    add_text(
        slide,
        "Keep judgment, upgrade the signal.",
        0.75,
        0.6,
        11.833,
        0.55,
        size=40,
        color=ACCENT,
        bold=True,
        name="Title",
    )
    add_text(
        slide,
        "Read the result with these limits:",
        0.8,
        1.55,
        11.7,
        0.4,
        size=20,
        bold=True,
        name="Caveat header",
    )

    caveats = [
        "Descriptive replay, not a causal test.",
        "One manager, one season, n=43 scored transfers.",
        "Candidate prices are season-static, not deadline prices. Cap checks at +£0.3m / -£0.3m stayed negative: -209 / -229.",
        "Holding windows ignore captaincy, benching, and multi-transfer packages.",
        "The fair-fight subset is small at n=23, so near parity is indicative, not precise.",
    ]
    top = 2.15
    for index, caveat in enumerate(caveats, start=1):
        add_text(slide, "•", 0.82, top, 0.3, 0.32, size=16, color=MUTED, name=f"Caveat {index} bullet")
        add_text(slide, caveat, 1.22, top, 11.0, 0.62, size=16, color=WARM_WHITE, name=f"Caveat {index} text")
        top += 0.82

    add_notes(
        slide,
        "This is a descriptive replay for one manager and one season, with season-static candidate prices and a small fair-fight subset. The scoring also leaves out captaincy, benching, and multi-transfer package effects, while the price sensitivity still remained negative. The decision is to keep judgment, preserve banked-fund flexibility, and upgrade the attacker signal.",
    )


def build_deck() -> Path:
    verify_source_numbers()
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_WIDTH_IN)
    prs.slide_height = Inches(SLIDE_HEIGHT_IN)

    add_title_slide(prs)
    add_rule_slide(prs)
    add_big_number_slide(prs)
    add_chart_slide(
        prs,
        "chart_1_headline.png",
        "Headline comparison chart",
        "Read the dumbbell from left to right: 567 points for the rule and 758 for the actual picks. The 191-point gap uses the same 43 holding windows on both sides. This is the replay outcome under fixed scoring choices, not a causal estimate.",
    )
    add_chart_slide(
        prs,
        "chart_2_decomposition.png",
        "Budget decomposition chart",
        "This is the twist: 148 of the 191 lost points sit in the 20 transfers where the manager spent above the sale-price cap. That is 77 percent of the full deficit. The rule's own budget constraint drives this arithmetic split.",
    )
    add_chart_slide(
        prs,
        "chart_3_fair_fights.png",
        "Fair-fight comparison chart",
        "When both sides fit the sale-price cap, the rule lost 1.87 points per transfer instead of 7.40. The fair subset finished 9 wins, 11 losses, and 3 ties. With only 23 fair fights, near parity is indicative rather than precise.",
    )
    add_chart_slide(
        prs,
        "chart_4_cases.png",
        "Six case studies chart",
        "The rule produced real wins, led by Semenyo at plus 31, but its largest misses were bigger. Gabriel, Wilson, and Bruno G. were all premium buys that the sale-price cap excluded. These individual holding-window outcomes can still contain a lot of luck.",
    )
    add_signal_slide(prs)
    add_action_slide(prs)
    add_close_slide(prs)

    assert len(prs.slides) == 10
    prs.save(OUTPUT_PATH)
    return OUTPUT_PATH


def self_check(path: Path) -> None:
    """Read the PPTX back and assert layout, font, placeholder, and notes rules."""
    prs = Presentation(path)
    assert len(prs.slides) == 10
    assert prs.slide_width == Inches(SLIDE_WIDTH_IN)
    assert prs.slide_height == Inches(SLIDE_HEIGHT_IN)

    print(f"Deck self-check: {path.name}")
    print(f"Slides: {len(prs.slides)}")
    for slide_number, slide in enumerate(prs.slides, start=1):
        background_rgb = slide.background.fill.fore_color.rgb
        assert background_rgb == _color(BG), (slide_number, background_rgb)
        assert slide.notes_slide.notes_text_frame.text.strip(), f"Slide {slide_number} has no speaker notes"
        print(f"Slide {slide_number}: {len(slide.shapes)} shapes")
        for index, shape in enumerate(slide.shapes, start=1):
            right = shape.left + shape.width
            bottom = shape.top + shape.height
            assert shape.left >= 0 and shape.top >= 0, (slide_number, shape.name)
            assert right <= prs.slide_width, (slide_number, shape.name, "right overflow")
            assert bottom <= prs.slide_height, (slide_number, shape.name, "bottom overflow")
            assert not shape.is_placeholder, (slide_number, shape.name, "unexpected placeholder")

            preview = ""
            if shape.has_text_frame:
                preview = " ".join(shape.text.split())[:72]
                assert preview, (slide_number, shape.name, "empty text frame")
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.text:
                            assert run.font.name == FONT, (slide_number, shape.name, run.text, run.font.name)
            shape_type = str(shape.shape_type)
            print(
                f"  {index:02d}. {shape.name!r} | {shape_type} | "
                f"x={shape.left / 914400:.2f} y={shape.top / 914400:.2f} "
                f"w={shape.width / 914400:.2f} h={shape.height / 914400:.2f} | {preview!r}"
            )
    print("Self-check passed: slide count, bounds, backgrounds, fonts, placeholders, and notes.")


def main() -> None:
    output = build_deck()
    self_check(output)


if __name__ == "__main__":
    main()
