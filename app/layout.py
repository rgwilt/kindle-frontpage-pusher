"""
Renders a curated list of Headline objects into a newspaper-front-page-style
PNG at the Kindle's exact panel resolution, using Pillow directly (no
browser/headless-Chromium involved -- just PIL's ImageDraw + a bundled
serif font).

To avoid every refresh looking like the same template re-filled with new
text, render_digest() randomly picks one of several distinct front-page
layouts (a big lead story, a split feature/sidebar arrangement, a dense
wire-service-style multi-column grid) each time it's called.
"""
from __future__ import annotations

import io
import logging
import random
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("frontpage.layout")

FONT_DIR = "/usr/share/fonts/truetype/liberation"
FONT_SERIF_BOLD = f"{FONT_DIR}/LiberationSerif-Bold.ttf"
FONT_SERIF_REGULAR = f"{FONT_DIR}/LiberationSerif-Regular.ttf"
FONT_SERIF_ITALIC = f"{FONT_DIR}/LiberationSerif-Italic.ttf"

MARGIN = 56
GUTTER = 36
MASTHEAD_TITLE_SIZE = 96
MASTHEAD_DATE_SIZE = 30
LINE_SPACING = 1.12

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_masthead(draw, width, paper_name, date_str) -> int:
    """Draws the masthead (title/date/rules) and returns the y where body content starts."""
    y = MARGIN
    title_font = _font(FONT_SERIF_BOLD, MASTHEAD_TITLE_SIZE)
    date_font = _font(FONT_SERIF_REGULAR, MASTHEAD_DATE_SIZE)

    draw.line([(MARGIN, y), (width - MARGIN, y)], fill=0, width=4)
    y += 10
    title_w = draw.textlength(paper_name, font=title_font)
    draw.text(((width - title_w) / 2, y), paper_name, font=title_font, fill=0)
    y += MASTHEAD_TITLE_SIZE + 6
    draw.line([(MARGIN, y), (width - MARGIN, y)], fill=0, width=2)
    y += 8
    date_w = draw.textlength(date_str, font=date_font)
    draw.text(((width - date_w) / 2, y), date_str, font=date_font, fill=0)
    y += MASTHEAD_DATE_SIZE + 10
    draw.line([(MARGIN, y), (width - MARGIN, y)], fill=0, width=4)
    y += 26
    return y


def _draw_headline_block(draw, x, y, col_width, headline, headline_font, source_font) -> int:
    """Draws one headline + source attribution + divider, returns the new y."""
    line_h = int(headline_font.size * LINE_SPACING)
    for line in _wrap_text(draw, headline.title.upper(), headline_font, col_width):
        draw.text((x, y), line, font=headline_font, fill=0)
        y += line_h
    y += 8
    draw.text((x, y), f"— {headline.source}", font=source_font, fill=0)
    y += source_font.size + 12
    draw.line([(x, y), (x + col_width, y)], fill=140, width=1)
    y += 14
    return y


def _block_height(draw, col_width, headline, headline_font, source_font) -> int:
    line_h = int(headline_font.size * LINE_SPACING)
    n_lines = max(1, len(_wrap_text(draw, headline.title.upper(), headline_font, col_width)))
    return n_lines * line_h + 8 + source_font.size + 12 + 14


def _layout_columns(draw, headlines, columns, headline_font, source_font, body_bottom) -> tuple[int, list]:
    """
    Greedily fills `columns` (list of (x, width, start_y)) with headline
    blocks, always adding the next block to whichever column currently has
    the most room. Returns (count_used, final_y_per_column).
    """
    col_y = [c[2] for c in columns]
    used = 0
    for h in headlines:
        # Pick the column with the most remaining room.
        idx = min(range(len(columns)), key=lambda i: col_y[i])
        x, width, _ = columns[idx]
        h_height = _block_height(draw, width, h, headline_font, source_font)
        if col_y[idx] + h_height > body_bottom:
            # No column has room left.
            if all(col_y[i] + _block_height(draw, columns[i][1], h, headline_font, source_font) > body_bottom
                   for i in range(len(columns))):
                break
            continue
        col_y[idx] = _draw_headline_block(draw, x, col_y[idx], width, h, headline_font, source_font)
        used += 1
    return used, col_y


def _template_lead_grid(draw, width, height, headlines, body_top, body_bottom) -> int:
    """One big lead story across the top, remaining headlines in a 2-col grid below."""
    if not headlines:
        return 0
    hero_font = _font(FONT_SERIF_BOLD, 58)
    hero_source_font = _font(FONT_SERIF_ITALIC, 26)
    y = _draw_headline_block(draw, MARGIN, body_top, width - 2 * MARGIN, headlines[0], hero_font, hero_source_font)
    y += 8
    draw.line([(MARGIN, y - 22), (width - MARGIN, y - 22)], fill=0, width=3)

    headline_font = _font(FONT_SERIF_BOLD, 32)
    source_font = _font(FONT_SERIF_ITALIC, 21)
    col_width = (width - 2 * MARGIN - GUTTER) // 2
    columns = [(MARGIN, col_width, y), (MARGIN + col_width + GUTTER, col_width, y)]
    used, col_y = _layout_columns(draw, headlines[1:], columns, headline_font, source_font, body_bottom)

    gutter_x = MARGIN + col_width + GUTTER // 2
    draw.line([(gutter_x, y), (gutter_x, max(col_y))], fill=180, width=1)
    return used + 1


def _template_split_feature(draw, width, height, headlines, body_top, body_bottom) -> int:
    """A wide feature column on the left, a narrower stacked sidebar on the right."""
    if not headlines:
        return 0
    left_width = int((width - 2 * MARGIN - GUTTER) * 0.6)
    right_x = MARGIN + left_width + GUTTER
    right_width = width - 2 * MARGIN - GUTTER - left_width

    feature_font = _font(FONT_SERIF_BOLD, 46)
    feature_source_font = _font(FONT_SERIF_ITALIC, 24)
    left_columns = [(MARGIN, left_width, body_top)]
    left_used, left_y = _layout_columns(
        draw, headlines[:4], left_columns, feature_font, feature_source_font, body_bottom
    )

    sidebar_font = _font(FONT_SERIF_BOLD, 25)
    sidebar_source_font = _font(FONT_SERIF_ITALIC, 18)
    right_columns = [(right_x, right_width, body_top)]
    right_used, right_y = _layout_columns(
        draw, headlines[left_used:], right_columns, sidebar_font, sidebar_source_font, body_bottom
    )

    divider_x = MARGIN + left_width + GUTTER // 2
    draw.line([(divider_x, body_top), (divider_x, max(left_y[0], right_y[0]))], fill=180, width=1)
    return left_used + right_used


def _template_three_column(draw, width, height, headlines, body_top, body_bottom) -> int:
    """A dense, wire-service-style grid: three narrower columns, more compact type."""
    headline_font = _font(FONT_SERIF_BOLD, 26)
    source_font = _font(FONT_SERIF_ITALIC, 18)
    col_width = (width - 2 * MARGIN - 2 * GUTTER) // 3
    columns = [
        (MARGIN, col_width, body_top),
        (MARGIN + col_width + GUTTER, col_width, body_top),
        (MARGIN + 2 * (col_width + GUTTER), col_width, body_top),
    ]
    used, col_y = _layout_columns(draw, headlines, columns, headline_font, source_font, body_bottom)
    for i in (0, 1):
        gx = columns[i][0] + col_width + GUTTER // 2
        draw.line([(gx, body_top), (gx, max(col_y))], fill=180, width=1)
    return used


TEMPLATES = {
    "lead_grid": _template_lead_grid,
    "split_feature": _template_split_feature,
    "three_column": _template_three_column,
}


def render_digest(
    headlines: list,
    width: int = 1264,
    height: int = 1680,
    paper_name: str = "THE KINDLE TIMES",
    date_str: str | None = None,
    template: str | None = None,
) -> tuple[bytes, int]:
    """
    Render `headlines` (objects with .title/.source) into a newspaper-style
    PNG sized exactly (width, height), picking a random layout template
    each call (unless `template` names one explicitly) so refreshes vary.

    Returns (png_bytes, headlines_used).
    """
    canvas = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(canvas)

    if date_str is None:
        date_str = datetime.now().strftime("%A, %B %-d, %Y")

    body_top = _draw_masthead(draw, width, paper_name, date_str)
    body_bottom = height - MARGIN

    chosen = template or random.choice(list(TEMPLATES))
    log.info("Rendering digest using template '%s'", chosen)
    used = TEMPLATES[chosen](draw, width, height, headlines, body_top, body_bottom)

    dropped = len(headlines) - used
    if dropped > 0:
        log.info("Digest layout: %d headline(s) didn't fit and were dropped", dropped)

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue(), used
