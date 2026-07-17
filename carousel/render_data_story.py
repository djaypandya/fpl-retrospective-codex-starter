#!/usr/bin/env python3
"""Deterministically render an FPL story spec to PNG slides and one PDF."""

from __future__ import annotations

import hashlib
import importlib.util
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import brand


def font(size: int, index: int = brand.FONT_INDEX_REGULAR) -> ImageFont.FreeTypeFont:
    """Load the same macOS font family used by the reference renderer."""
    try:
        return ImageFont.truetype(brand.SANS, size=size, index=index)
    except OSError:
        return ImageFont.truetype(brand.SANS_FALLBACK, size=size, index=0)


F_TITLE = font(brand.SIZE_TITLE, brand.FONT_INDEX_HEAVY)
F_TITLE_SMALL = font(brand.SIZE_TITLE_SMALL, brand.FONT_INDEX_HEAVY)
F_HEADLINE = font(brand.SIZE_HEADLINE, brand.FONT_INDEX_DEMI)
F_BODY = font(brand.SIZE_BODY, brand.FONT_INDEX_REGULAR)
F_BODY_BOLD = font(brand.SIZE_BODY, brand.FONT_INDEX_DEMI)
F_CHECKLIST = font(brand.SIZE_CHECKLIST, brand.FONT_INDEX_REGULAR)
F_CHECKLIST_BOLD = font(brand.SIZE_CHECKLIST, brand.FONT_INDEX_DEMI)
F_KICKER = font(brand.SIZE_KICKER, brand.FONT_INDEX_DEMI)
F_LABEL = font(brand.SIZE_LABEL, brand.FONT_INDEX_DEMI)
F_CAPSULE = font(brand.SIZE_CAPSULE, brand.FONT_INDEX_DEMI)
F_CAPTION = font(brand.SIZE_CAPTION, brand.FONT_INDEX_REGULAR)
F_FOOTER = font(brand.SIZE_FOOTER, brand.FONT_INDEX_REGULAR)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def make_background(slug: str, slide_no: int) -> Image.Image:
    """A stable grain field. hashlib avoids Python's randomized hash seed."""
    digest = hashlib.sha256(f"fpl-carousel:{slug}:{slide_no}".encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    image = Image.new("RGB", (brand.W, brand.H), brand.BG)
    pixels = image.load()
    for y in range(brand.H):
        for x in range(brand.W):
            delta = rng.choice((-2, -1, 0, 0, 0, 1, 2))
            r = max(0, brand.BG[0] + delta)
            g = max(0, brand.BG[1] + delta)
            b = max(0, brand.BG[2] + delta)
            pixels[x, y] = (r, g, b)
    return image.filter(ImageFilter.GaussianBlur(radius=0.15))


def split_highlight(text: str, phrase: str | None, base: tuple[int, int, int]) -> list[tuple[str, tuple[int, int, int]]]:
    if not phrase:
        return [(text, base)]
    start = text.lower().find(phrase.lower())
    if start < 0:
        return [(text, base)]
    end = start + len(phrase)
    return [(text[:start], base), (text[start:end], brand.ACCENT), (text[end:], base)]


def clusters_from_runs(runs: list[tuple[str, tuple[int, int, int]]]) -> list[list[tuple[str, tuple[int, int, int]]]]:
    """Group run fragments into visual words. A run that starts mid-word (no leading
    space) continues the previous cluster, so highlights never detach punctuation
    (e.g. 'xG' + '. Fade' renders as 'xG.' 'Fade', not 'xG . Fade')."""
    clusters: list[list[tuple[str, tuple[int, int, int]]]] = []
    current: list[tuple[str, tuple[int, int, int]]] = []
    for text, color in runs:
        if not text:
            continue
        parts = text.split()
        if not parts:  # pure whitespace ends any open cluster
            if current:
                clusters.append(current)
                current = []
            continue
        for i, part in enumerate(parts):
            if i == 0 and not text[0].isspace() and current:
                current.append((part, color))
            else:
                if current:
                    clusters.append(current)
                current = [(part, color)]
        if text[-1].isspace():
            clusters.append(current)
            current = []
    if current:
        clusters.append(current)
    return clusters


def draw_wrapped_runs(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    max_w: int,
    runs: list[tuple[str, tuple[int, int, int]]],
    fnt: ImageFont.ImageFont,
    line_gap: int = 14,
) -> int:
    cursor_x, cursor_y = x, y
    line_h = text_size(draw, "Ag", fnt)[1] + line_gap
    space_w, _ = text_size(draw, " ", fnt)
    for cluster in clusters_from_runs(runs):
        word_w = sum(text_size(draw, frag, fnt)[0] for frag, _ in cluster)
        if cursor_x > x and cursor_x + word_w > x + max_w:
            cursor_x = x
            cursor_y += line_h
        for frag, color in cluster:
            draw.text((cursor_x, cursor_y), frag, fill=color, font=fnt)
            cursor_x += text_size(draw, frag, fnt)[0]
        cursor_x += space_w
    return cursor_y + line_h


def draw_paragraphs(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    paragraphs: list[str],
    highlight: str | None,
    fnt: ImageFont.ImageFont = F_BODY,
    base: tuple[int, int, int] = brand.WARM_WHITE,
    line_gap: int = 14,
    para_gap: int = 20,
) -> int:
    for paragraph in paragraphs:
        y = draw_wrapped_runs(draw, x, y, brand.W - 2 * brand.MARGIN, split_highlight(paragraph, highlight, base), fnt, line_gap)
        y += para_gap
    return y


def draw_header(draw: ImageDraw.ImageDraw, story: dict, index: int, total: int) -> None:
    y = 54
    tab = story["tag"].upper()
    tab_w, _ = text_size(draw, tab, F_LABEL)
    draw.rounded_rectangle((brand.MARGIN, y, brand.MARGIN + tab_w + 34, y + 42), radius=7, outline=brand.MID_GREY, width=1)
    draw.text((brand.MARGIN + 17, y + 8), tab, fill=brand.WARM_WHITE, font=F_LABEL)
    season_w, _ = text_size(draw, brand.HEADER_SEASON, F_LABEL)
    draw.text((brand.W - brand.MARGIN - season_w, y + 8), brand.HEADER_SEASON, fill=brand.MUTED, font=F_LABEL)

    bar_y, bar_h = 129, 8
    bar_w = brand.W - 2 * brand.MARGIN
    done_w = int(bar_w * index / total)
    draw.rounded_rectangle((brand.MARGIN, bar_y, brand.MARGIN + bar_w, bar_y + bar_h), radius=4, fill=brand.DARK_GREY)
    draw.rounded_rectangle((brand.MARGIN, bar_y, brand.MARGIN + done_w, bar_y + bar_h), radius=4, fill=brand.ACCENT)

    count = f"{index:02d}/{total:02d}"
    count_w, _ = text_size(draw, count, F_CAPSULE)
    right, top = brand.W - brand.MARGIN, 153
    draw.rounded_rectangle((right - count_w - 32, top, right, top + 38), radius=19, outline=brand.MID_GREY, width=1)
    draw.text((right - count_w - 16, top + 8), count, fill=brand.WARM_WHITE, font=F_CAPSULE)


def draw_footer(draw: ImageDraw.ImageDraw) -> None:
    y = 1268
    draw.line((brand.MARGIN, y, brand.W - brand.MARGIN, y), fill=brand.MID_GREY, width=1)
    by = y + 30
    draw.text((brand.MARGIN, by), brand.FOOTER_LEFT, fill=brand.MUTED, font=F_FOOTER)
    center_w, _ = text_size(draw, brand.FOOTER_CENTER, F_FOOTER)
    draw.text(((brand.W - center_w) / 2, by), brand.FOOTER_CENTER, fill=brand.MUTED, font=F_FOOTER)
    right_w, _ = text_size(draw, brand.FOOTER_RIGHT, F_FOOTER)
    draw.text((brand.W - brand.MARGIN - right_w, by), brand.FOOTER_RIGHT, fill=brand.MUTED, font=F_FOOTER)


def draw_kicker(draw: ImageDraw.ImageDraw, label: str, y: int = 454) -> None:
    draw.rectangle((brand.MARGIN, y, brand.MARGIN + 7, y + 34), fill=brand.ACCENT)
    draw.text((brand.MARGIN + 22, y + 3), label.upper(), fill=brand.ACCENT, font=F_KICKER)


def draw_title_text(draw: ImageDraw.ImageDraw, title: str, highlight: str | None, y: int, fnt: ImageFont.ImageFont) -> int:
    return draw_wrapped_runs(draw, brand.MARGIN, y, brand.W - 2 * brand.MARGIN, split_highlight(title, highlight, brand.WARM_WHITE), fnt, line_gap=12)


def draw_title_slide(draw: ImageDraw.ImageDraw, slide: dict) -> None:
    draw.text((brand.MARGIN, 214), slide["label"].upper(), fill=brand.ACCENT, font=F_KICKER)
    title_end = draw_title_text(draw, slide["title"], slide.get("highlight"), 300, F_TITLE)
    body_y = max(760, title_end + 62)
    draw_paragraphs(draw, brand.MARGIN, body_y, slide["body"], None, F_BODY, brand.WARM_WHITE, 16, 24)


def draw_text_slide(draw: ImageDraw.ImageDraw, slide: dict) -> None:
    draw_title_text(draw, slide["title"], None, 250, F_TITLE_SMALL)
    draw_kicker(draw, slide["kicker"])
    draw_paragraphs(draw, brand.MARGIN, 520, slide["body"], slide.get("highlight"))


def rounded_chart_card(chart_path: Path, max_w: int, max_h: int) -> Image.Image:
    with Image.open(chart_path) as raw:
        chart = raw.convert("RGB")
    pad, radius = 28, 24
    scale = min((max_w - pad * 2) / chart.width, (max_h - pad * 2) / chart.height)
    size = (max(1, round(chart.width * scale)), max(1, round(chart.height * scale)))
    chart = chart.resize(size, Image.Resampling.LANCZOS)
    card = Image.new("RGB", (size[0] + pad * 2, size[1] + pad * 2), brand.CARD_WHITE)
    card.paste(chart, (pad, pad))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=radius, fill=255)
    output = Image.new("RGBA", card.size, (0, 0, 0, 0))
    output.paste(card, mask=mask)
    return output


def draw_chart_slide(image: Image.Image, draw: ImageDraw.ImageDraw, slide: dict, root: Path) -> None:
    headline_end = draw_wrapped_runs(draw, brand.MARGIN, 250, brand.W - 2 * brand.MARGIN, split_highlight(slide["headline"], slide.get("highlight"), brand.WARM_WHITE), F_HEADLINE, line_gap=10)
    chart_path = root / "charts" / slide["chart"]
    card = rounded_chart_card(chart_path, brand.W - 2 * brand.MARGIN, 640)
    card_y = max(385, headline_end + 36)
    # Keep a generous reading gap before the footer, including the caption.
    bottom_limit = 1135
    if card_y + card.height > bottom_limit:
        card = rounded_chart_card(chart_path, brand.W - 2 * brand.MARGIN, bottom_limit - card_y)
    card_x = (brand.W - card.width) // 2
    image.alpha_composite(card, (card_x, card_y))
    caption = slide["caption"]
    cap_w, _ = text_size(draw, caption, F_CAPTION)
    draw.text(((brand.W - cap_w) / 2, card_y + card.height + 18), caption, fill=brand.MUTED, font=F_CAPTION)


def draw_checklist_slide(draw: ImageDraw.ImageDraw, slide: dict) -> None:
    draw_title_text(draw, slide["title"], None, 250, F_TITLE_SMALL)
    draw_kicker(draw, slide["kicker"])
    y = 522
    for row in slide["rows"]:
        draw.ellipse((brand.MARGIN, y + 12, brand.MARGIN + 15, y + 27), fill=brand.ACCENT)
        end = draw_wrapped_runs(draw, brand.MARGIN + 36, y, brand.W - 2 * brand.MARGIN - 36, split_highlight(row, slide.get("highlight"), brand.WARM_WHITE), F_CHECKLIST, line_gap=10)
        y = end + 17


def draw_closing_slide(draw: ImageDraw.ImageDraw, slide: dict) -> None:
    draw_title_text(draw, slide["title"], None, 250, F_TITLE_SMALL)
    draw_kicker(draw, slide["kicker"])
    y = draw_paragraphs(draw, brand.MARGIN, 520, slide["body"], None, F_BODY, brand.MUTED, 13, 16)
    draw_wrapped_runs(draw, brand.MARGIN, y + 18, brand.W - 2 * brand.MARGIN, [(slide["summary"], brand.WARM_WHITE)], F_BODY_BOLD, line_gap=14)


def render_slide(slide: dict, story: dict, index: int, total: int, root: Path) -> Image.Image:
    image = make_background(story["slug"], index).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw_header(draw, story, index, total)
    draw_footer(draw)
    kind = slide["kind"]
    if kind == "title":
        draw_title_slide(draw, slide)
    elif kind == "text":
        draw_text_slide(draw, slide)
    elif kind == "chart":
        draw_chart_slide(image, draw, slide, root)
    elif kind == "checklist":
        draw_checklist_slide(draw, slide)
    elif kind == "closing":
        draw_closing_slide(draw, slide)
    else:
        raise ValueError(f"Unknown slide kind: {kind}")
    return image.convert("RGB")


def load_story(slug: str, root: Path) -> tuple[dict, list[dict]]:
    path = root / "stories" / f"slides_{slug}.py"
    if not path.exists():
        raise FileNotFoundError(f"No story spec at {path}")
    spec = importlib.util.spec_from_file_location(f"slides_{slug}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.STORY, module.SLIDES


def render_story(slug: str, root: Path | None = None) -> tuple[Path, Path, int]:
    root = root or Path(__file__).resolve().parent
    story, slides = load_story(slug, root)
    if story["slug"] != slug:
        raise ValueError("Story slug does not match its file name")
    png_dir = root / "outputs" / slug / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    images: list[Image.Image] = []
    for index, slide in enumerate(slides, 1):
        image = render_slide(slide, story, index, len(slides), root)
        output = png_dir / f"story_slide_{slug}_{index:02d}.png"
        image.save(output, "PNG", optimize=True)
        images.append(image)
    pdf_path = root / "outputs" / slug / f"story_carousel_{slug}.pdf"
    images[0].save(pdf_path, save_all=True, append_images=images[1:], resolution=300.0)
    return png_dir, pdf_path, len(images)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 render_data_story.py <story_slug>")
    png_dir, pdf_path, count = render_story(sys.argv[1])
    print(f"wrote {count} PNG slides to {png_dir}")
    print(f"wrote PDF to {pdf_path}")


if __name__ == "__main__":
    main()
