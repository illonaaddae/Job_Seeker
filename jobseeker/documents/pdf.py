"""A small PDF writer built on the standard library alone.

The upstream project needed ReportLab for this. Writing it by hand keeps the
whole engine installable with nothing but Python, which matters when it has to
run in a slim container or a CI job. It supports the fourteen standard fonts,
accurate text measurement from the Helvetica metrics, word wrapping, headings,
rules, bullets and automatic page breaks. That is everything a letter or a CV
needs, and nothing else.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field, replace
from pathlib import Path

# Standard Helvetica advance widths in 1/1000 em, characters 32 to 126.
_HELV = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]
_HELV_BOLD = [
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
]

FONTS = {
    "regular": ("Helvetica", _HELV),
    "bold": ("Helvetica-Bold", _HELV_BOLD),
    "italic": ("Helvetica-Oblique", _HELV),
    "bolditalic": ("Helvetica-BoldOblique", _HELV_BOLD),
}
_FONT_KEYS = {"regular": "F1", "bold": "F2", "italic": "F3", "bolditalic": "F4"}

A4 = (595.28, 841.89)
LETTER = (612.0, 792.0)


def text_width(value: str, font: str, size: float) -> float:
    """Measure a string in points for the given standard font and size."""
    widths = FONTS.get(font, FONTS["regular"])[1]
    total = 0
    for char in value:
        code = ord(char)
        total += widths[code - 32] if 32 <= code <= 126 else 556
    return total * size / 1000.0


@dataclass(slots=True)
class Style:
    font: str = "regular"
    size: float = 10.5
    leading: float = 1.45
    color: tuple[float, float, float] = (0.15, 0.16, 0.18)
    space_before: float = 0.0
    space_after: float = 7.0
    align: str = "left"          # left | center | right | justify
    indent: float = 0.0

    @property
    def line_height(self) -> float:
        return self.size * self.leading


# House styles. Deliberately restrained: one accent colour, generous leading.
ACCENT = (0.055, 0.478, 0.525)      # oceanic teal, matches oceaniccoder.dev
INK = (0.11, 0.13, 0.15)
MUTED = (0.42, 0.45, 0.49)
HAIRLINE = (0.85, 0.87, 0.89)

STYLES: dict[str, Style] = {
    "name": Style(font="bold", size=19, leading=1.15, color=INK, space_after=2),
    "tagline": Style(font="regular", size=10, leading=1.3, color=ACCENT, space_after=3),
    "contact": Style(font="regular", size=8.8, leading=1.35, color=MUTED, space_after=2),
    "meta": Style(font="regular", size=9.2, leading=1.4, color=MUTED, space_after=4),
    "h2": Style(font="bold", size=10.5, leading=1.3, color=ACCENT, space_before=10, space_after=4),
    "body": Style(font="regular", size=10.3, leading=1.5, color=INK, space_after=8, align="justify"),
    "bullet": Style(font="regular", size=10, leading=1.45, color=INK, space_after=3, indent=12),
    "small": Style(font="regular", size=9, leading=1.4, color=MUTED, space_after=4),
    "sign": Style(font="regular", size=10.3, leading=1.4, color=INK, space_after=0),
}


def _escape(value: str) -> str:
    out = []
    for char in value:
        code = ord(char)
        if char in "()\\":
            out.append("\\" + char)
        elif 32 <= code <= 126:
            out.append(char)
        elif code in (0x2018, 0x2019):
            out.append("'")
        elif code in (0x201C, 0x201D):
            out.append('"')
        elif code == 0x2026:
            out.append("...")
        elif code in (0x2013, 0x2014):
            # Dashes never appear in generated copy, but a pasted job title might
            # carry one. A comma keeps the house rule intact even here.
            out.append(",")
        elif code == 0x00A0:
            out.append(" ")
        else:
            out.append("?")
    return "".join(out)


def wrap(value: str, font: str, size: float, max_width: float) -> list[str]:
    """Greedy word wrap using real font metrics."""
    lines: list[str] = []
    for paragraph in value.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if text_width(candidate, font, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


@dataclass
class _Page:
    ops: list[str] = field(default_factory=list)


class Document:
    """Flow layout PDF. Content is appended top to bottom and paginates itself."""

    def __init__(
        self,
        page_size: tuple[float, float] = A4,
        margins: tuple[float, float, float, float] = (56, 54, 56, 54),
    ) -> None:
        self.width, self.height = page_size
        self.margin_top, self.margin_right, self.margin_bottom, self.margin_left = margins
        self.pages: list[_Page] = [_Page()]
        self.y = self.height - self.margin_top
        self.title = ""
        self.author = ""

    # ------------------------------------------------------------ geometry

    @property
    def content_width(self) -> float:
        return self.width - self.margin_left - self.margin_right

    @property
    def _page(self) -> _Page:
        return self.pages[-1]

    def _ensure_space(self, needed: float) -> None:
        if self.y - needed < self.margin_bottom:
            self.pages.append(_Page())
            self.y = self.height - self.margin_top

    # -------------------------------------------------------------- drawing

    def _draw_line_of_text(
        self, value: str, x: float, y: float, style: Style, word_spacing: float = 0.0
    ) -> None:
        font_name = _FONT_KEYS[style.font]
        r, g, b = style.color
        ops = self._page.ops
        ops.append("BT")
        ops.append(f"/{font_name} {style.size:.2f} Tf")
        ops.append(f"{r:.3f} {g:.3f} {b:.3f} rg")
        if word_spacing:
            ops.append(f"{word_spacing:.3f} Tw")
        ops.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
        ops.append(f"({_escape(value)}) Tj")
        if word_spacing:
            ops.append("0 Tw")
        ops.append("ET")

    def paragraph(self, value: str, style_name: str | Style = "body", **overrides) -> None:
        """Lay out wrapped text, breaking pages as needed."""
        style = STYLES[style_name] if isinstance(style_name, str) else style_name
        if overrides:
            style = replace(style, **overrides)
        if not value:
            self.spacer(style.space_after)
            return

        self.y -= style.space_before
        available = self.content_width - style.indent
        lines = wrap(value, style.font, style.size, available)

        for index, line in enumerate(lines):
            self._ensure_space(style.line_height)
            x = self.margin_left + style.indent
            word_spacing = 0.0
            is_last = index == len(lines) - 1

            if style.align == "center":
                x += (available - text_width(line, style.font, style.size)) / 2
            elif style.align == "right":
                x += available - text_width(line, style.font, style.size)
            elif style.align == "justify" and not is_last and line.count(" ") > 0:
                slack = available - text_width(line, style.font, style.size)
                # Only stretch when the gap is small, otherwise the line looks torn.
                if 0 < slack < available * 0.22:
                    word_spacing = slack / line.count(" ")

            self.y -= style.line_height
            self._draw_line_of_text(line, x, self.y, style, word_spacing)

        self.y -= style.space_after

    def heading(self, value: str) -> None:
        self.paragraph(value.upper(), "h2")

    def bullets(self, items: list[str], style_name: str = "bullet") -> None:
        style = STYLES[style_name]
        for item in items:
            self._ensure_space(style.line_height)
            marker_style = replace(style, indent=0.0, color=ACCENT)
            # Draw the marker on the first line, then the wrapped text beside it.
            lines = wrap(item, style.font, style.size, self.content_width - style.indent)
            for index, line in enumerate(lines):
                self._ensure_space(style.line_height)
                self.y -= style.line_height
                if index == 0:
                    self._draw_line_of_text("•", self.margin_left, self.y, marker_style)
                self._draw_line_of_text(
                    line, self.margin_left + style.indent, self.y, style
                )
            self.y -= style.space_after

    def rule(self, color: tuple[float, float, float] = HAIRLINE, thickness: float = 0.7,
             space_before: float = 4, space_after: float = 8) -> None:
        self.y -= space_before
        self._ensure_space(thickness + space_after)
        r, g, b = color
        self._page.ops.append(
            f"{r:.3f} {g:.3f} {b:.3f} RG {thickness:.2f} w "
            f"{self.margin_left:.2f} {self.y:.2f} m "
            f"{self.width - self.margin_right:.2f} {self.y:.2f} l S"
        )
        self.y -= space_after

    def accent_bar(
        self, height: float = 3.0, width_ratio: float = 0.18, space_before: float = 9.0
    ) -> None:
        """A short accent rule under the letterhead. The only decoration used."""
        self._ensure_space(height + space_before + 10)
        self.y -= space_before + height
        r, g, b = ACCENT
        self._page.ops.append(
            f"{r:.3f} {g:.3f} {b:.3f} rg {self.margin_left:.2f} {self.y:.2f} "
            f"{self.content_width * width_ratio:.2f} {height:.2f} re f"
        )
        self.y -= 10

    def spacer(self, amount: float) -> None:
        self._ensure_space(amount)
        self.y -= amount

    def key_value_row(self, left: str, right: str, style_name: str = "small") -> None:
        """Two column row used by the CV for role and date pairs."""
        style = STYLES[style_name]
        self._ensure_space(style.line_height)
        self.y -= style.line_height
        self._draw_line_of_text(left, self.margin_left, self.y, style)
        right_width = text_width(right, style.font, style.size)
        self._draw_line_of_text(
            right, self.width - self.margin_right - right_width, self.y, style
        )
        self.y -= style.space_after

    # ----------------------------------------------------------------- save

    def _build(self) -> bytes:
        objects: list[bytes] = []

        def add(payload: bytes) -> int:
            objects.append(payload)
            return len(objects)

        font_ids: dict[str, int] = {}
        for key, (base_font, _) in FONTS.items():
            font_ids[key] = add(
                f"<< /Type /Font /Subtype /Type1 /BaseFont /{base_font} "
                f"/Encoding /WinAnsiEncoding >>".encode("latin-1")
            )

        resources = (
            "<< /Font << "
            + " ".join(f"/{_FONT_KEYS[k]} {font_ids[k]} 0 R" for k in FONTS)
            + " >> >>"
        )

        pages_id = len(objects) + 1 + len(self.pages) * 2 + 1
        page_ids: list[int] = []
        for page in self.pages:
            stream = "\n".join(page.ops).encode("latin-1", errors="replace")
            compressed = zlib.compress(stream, 9)
            content_id = add(
                b"<< /Length "
                + str(len(compressed)).encode()
                + b" /Filter /FlateDecode >>\nstream\n"
                + compressed
                + b"\nendstream"
            )
            page_id = add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 "
                f"{self.width:.2f} {self.height:.2f}] /Resources {resources} "
                f"/Contents {content_id} 0 R >>".encode("latin-1")
            )
            page_ids.append(page_id)

        pages_obj = add(
            (
                f"<< /Type /Pages /Count {len(page_ids)} /Kids ["
                + " ".join(f"{pid} 0 R" for pid in page_ids)
                + "] >>"
            ).encode("latin-1")
        )
        info_id = add(
            f"<< /Title ({_escape(self.title)}) /Author ({_escape(self.author)}) "
            f"/Producer (JobSeeker) >>".encode("latin-1")
        )
        catalog_id = add(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode("latin-1"))

        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, payload in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{index} 0 obj\n".encode("latin-1") + payload + b"\nendobj\n"

        xref_offset = len(out)
        out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
        out += b"0000000000 65535 f \n"
        for offset in offsets[1:]:
            out += f"{offset:010d} 00000 n \n".encode("latin-1")
        out += (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R "
            f"/Info {info_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        ).encode("latin-1")
        return bytes(out)

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self._build())
        return target
