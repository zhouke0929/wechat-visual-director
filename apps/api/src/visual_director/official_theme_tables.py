"""Theme-specific native table styles, including compatibility for saved plans."""
from collections.abc import Callable
from dataclasses import dataclass

from .reading_rules import TABLE_HEADER, TABLE_BODY, ReadingProfile, render_authored_text
from .theme_drawings import render_drawing


@dataclass(frozen=True)
class _Cell:
    text: str
    column: int
    columns: int
    header: bool
    last: bool = False
    row_index: int = 0

    @property
    def first(self) -> bool:
        return self.column == 0

    @property
    def next_column(self) -> bool:
        return self.column + 1 < self.columns

    @property
    def multi_column(self) -> bool:
        return self.columns > 2

    @property
    def emphasized_first(self) -> bool:
        return self.first and not self.multi_column

    def body_fill(self, palette: dict[str, str], stripe: str, *, first_fill: str = "surface") -> str:
        # The first column of a wide table need not describe the other cells.
        # Apply stripes by row, never as a visual row-header marker.
        if self.multi_column:
            return palette[stripe if self.row_index % 2 else "surface"]
        return palette[first_fill if self.first else "surface"]


_Palette = dict[str, str]
_CellStyle = Callable[[_Cell, _Palette], tuple[str, str]]
_CELL_BASE = "text-align:left;white-space:normal;word-break:break-word;overflow-wrap:anywhere;"


def _weekend(c: _Cell, p: _Palette) -> tuple[str, str]:
    if c.header:
        top = p["accent"] if c.emphasized_first else p["primary"]
        fill = p["accent_pale"] if c.emphasized_first else p["pale"]
        rule = f'border-bottom:2px solid {p["primary"]};'
        label = f'color:{p["ink"]};font-size:14px;font-weight:700;line-height:1.45;'
        # The paper color belongs to the whole header cell, even for short labels.
        edge = f'border-right:1px solid {p["secondary"]};' if c.next_column else ""
        return (
            f'padding:6px 10px 5px;vertical-align:top;border-top:2px solid {top};background-color:{fill};'
            + rule + label + edge, c.text,
        )
    stub = c.emphasized_first and c.next_column
    bottom = f'1px solid {p["primary"]}' if c.last else f'1px dashed {p["secondary"]}'
    edge = f'border-right:1px solid {p["secondary"]};' if c.next_column and (stub or c.multi_column) else ""
    fill = c.body_fill(p, "secondary_pale", first_fill="secondary_pale" if stub else "surface")
    return (
        f'padding:9px 10px;vertical-align:top;color:{p["ink"]};font-size:14px;line-height:1.62;'
        f'font-weight:{600 if stub else 400};background-color:{fill};'
        f'border-bottom:{bottom};{edge}', c.text,
    )


def _cinema(c: _Cell, p: _Palette) -> tuple[str, str]:
    edge = f'border-left:3px solid {p["primary"]};' if c.first else ""
    if c.header:
        dark = c.multi_column or c.first
        return (
            f'padding:9px;vertical-align:top;border-top:3px solid {p["accent" if dark else "secondary"]};'
            f'border-bottom:1px solid {p["secondary"]};{edge}'
            f'background-color:{p["primary" if dark else "secondary_pale"]};'
            f'color:{p["surface" if dark else "accent"]};font-size:13px;font-weight:700;line-height:1.45;', c.text,
        )
    bottom = f'2px solid {p["secondary"]}' if c.last else f'1px solid {p["secondary_pale"]}'
    return (
        f'padding:8px 9px;vertical-align:top;{edge}border-bottom:{bottom};'
        f'background-color:{c.body_fill(p, "accent_pale", first_fill="accent_pale")};color:{p["ink"]};'
        f'font-size:14px;font-weight:{600 if c.emphasized_first else 400};line-height:1.6;', c.text,
    )


def _light(c: _Cell, p: _Palette) -> tuple[str, str]:
    crease = p["sky"]
    stub = c.first and c.next_column
    edge = f'border-right:1px solid {crease};' if c.next_column and (c.first or c.multi_column) else ""
    color = f'color:{p["ink"]};vertical-align:top;'
    if c.header:
        return (
            f'{color}padding:8px 9px;background-color:{p["pale" if c.emphasized_first else "sky_pale"]};'
            f'border-top:3px solid {p["secondary_pale" if c.emphasized_first else "sky_pale"]};'
            f'border-bottom:1px solid {crease};{edge}font-size:13px;font-weight:700;line-height:1.45;', c.text,
        )
    return (
        f'{color}padding:9px 8px;border-bottom:1px solid {crease if c.last else p["secondary"]};{edge}'
        f'background-color:{c.body_fill(p, "sky_pale")};font-size:14px;font-weight:{600 if stub and c.columns == 2 else 400};'
        'line-height:1.55;', c.text,
    )


def _pixel(c: _Cell, p: _Palette) -> tuple[str, str]:
    if c.header:
        edge = f'border-left:4px solid {p["accent"]};' if c.first else ""
        seam = (f'border-right:1px solid {p["secondary"]};' if c.multi_column
                else f'border-right:3px solid {p["surface"]};') if c.next_column else ""
        return (
            f'padding:{"8px 8px 8px 4px" if c.first else "8px"};vertical-align:top;'
            f'font-size:14px;line-height:1.45;color:{p["primary"]};font-weight:760;'
            f'background-color:{p["secondary_pale" if c.emphasized_first else "pale"]};'
            f'border-bottom:{4 if c.emphasized_first else 2}px solid {p["primary"]};{edge}{seam}', c.text,
        )
    dense = c.multi_column
    divider = p["secondary" if dense else "secondary_pale"]
    edge = f'border-right:1px solid {divider};' if c.next_column else ""
    return (
        f'padding:{7 if dense else 8}px;vertical-align:top;font-size:{14 if dense else 15}px;line-height:1.55;'
        f'color:{p["ink"]};font-weight:{650 if c.emphasized_first else 400};background-color:{c.body_fill(p, "pale")};'
        f'border-bottom:{2 if c.last else 1}px solid {p["secondary" if c.last else "secondary_pale"]};{edge}', c.text,
    )


def _collage(c: _Cell, p: _Palette) -> tuple[str, str]:
    blue, rule = p["primary"], "#CAD8E9"
    if c.multi_column:
        edge = f'border-right:1px solid {rule};' if c.next_column else ""
    else:
        edge = f'border-right:2px solid {blue};' if c.first and c.next_column else ""
    color = f'color:{p["ink"]};vertical-align:top;'
    if c.header:
        return (
            f'{color}padding:8px 8px 7px;border-top:2px solid {blue};border-bottom:2px solid {blue};{edge}'
            f'background-color:{p["secondary_pale" if c.multi_column else "secondary" if c.first else "pale"]};'
            'font-size:13px;line-height:1.5;font-weight:700;',
            c.text,
        )
    return (
        f'{color}padding:7px 8px;background-color:{c.body_fill(p, "pale", first_fill="pale")};{edge}'
        f'font-size:14px;line-height:1.58;border-bottom:{2 if c.emphasized_first and c.last else 1}px solid {blue if c.last else rule};',
        c.text,
    )


def _bistro(c: _Cell, p: _Palette) -> tuple[str, str]:
    green, divider = p["primary"], p["secondary"]
    if c.header:
        seam = f'border-left:1px solid {divider};' if not c.first else ""
        return (
            f'background-color:{green};color:{p["surface"]};font-size:14px;font-weight:700;'
            f'line-height:1.46;padding:8px;vertical-align:top;border:0;border-bottom:3px solid {divider};{seam}', c.text,
        )
    rule = f'3px double {green}' if c.last else f'1px dashed {divider}'
    return (
        f'color:{p["ink"]};font-size:14px;line-height:1.62;padding:8px;vertical-align:top;'
        f'border:0;border-bottom:{rule};background-color:{c.body_fill(p, "pale", first_fill="pale")};', c.text,
    )


def _window(c: _Cell, p: _Palette) -> tuple[str, str]:
    # A continuous selected header and grid like a classic desktop file list.
    # All columns have the same visual weight; striping follows the rows.
    edge = f'border-right:1px solid {p["secondary" if c.next_column else "primary"]};'
    if c.first:
        edge += f'border-left:1px solid {p["primary"]};'
    if c.header:
        return (
            f'padding:6px 8px;vertical-align:top;background-color:{p["secondary_pale"]};'
            f'border-top:2px solid {p["primary"]};border-bottom:1px solid {p["primary"]};{edge}'
            f'color:{p["ink"]};font-size:13px;font-weight:750;line-height:1.5;', c.text,
        )
    return (
        f'padding:7px 8px;vertical-align:top;background-color:{p["pale" if c.row_index % 2 else "surface"]};'
        f'border-bottom:1px solid {p["primary" if c.last else "secondary"]};{edge}'
        f'color:{p["ink"]};font-size:14px;line-height:1.6;', c.text,
    )


def _folded_fan(c: _Cell, p: _Palette) -> tuple[str, str]:
    # The upper paper edge is attached to the cells, not a spacer above the grid.
    edge = f'border-right:1px solid {p["secondary"]};' if c.next_column else ""
    if c.header:
        return (
            f'padding:6px 8px;vertical-align:top;background-color:{p["sky_pale"]};'
            f'border-top:3px solid {p["sky"]};border-bottom:1px solid {p["primary"]};{edge}'
            f'color:{p["primary"]};font-size:13px;font-weight:750;line-height:1.5;', c.text,
        )
    return (
        f'padding:7px 8px;vertical-align:top;background-color:{p["sky_pale" if c.row_index % 2 else "surface"]};'
        f'border-bottom:1px {"solid" if c.last else "dotted"} {p["primary" if c.last else "secondary"]};{edge}'
        f'color:{p["ink"]};font-size:14px;line-height:1.6;', c.text,
    )


def _indigo_cloth(c: _Cell, p: _Palette) -> tuple[str, str]:
    # The bound edge and stitched row rules are part of the cells.
    seam = f'border-right:1px solid {p["sky_pale"]};' if c.next_column else ""
    if c.header:
        return (
            f'padding:7px 8px;vertical-align:top;background-color:{p["pale"]};'
            f'border-top:3px solid {p["primary"]};border-bottom:1px solid {p["sky"]};{seam}'
            f'color:{p["primary"]};font-size:13px;font-weight:750;line-height:1.5;', c.text,
        )
    bottom = f'3px double {p["sky"]}' if c.last else f'1px dashed {p["secondary"]}'
    fill = p["pale" if c.row_index % 2 else "surface"]
    return (
        f'padding:7px 8px;vertical-align:top;background-color:{fill};border-bottom:{bottom};{seam}'
        f'color:{p["ink"]};font-size:14px;line-height:1.6;', c.text,
    )


def _night_walk(c: _Cell, p: _Palette) -> tuple[str, str]:
    # A single night sign with a warm lower edge; all header cells stay peers.
    if c.header:
        seam = f'border-right:1px solid {p["secondary"]};' if c.next_column else ""
        return (
            f'padding:7px 8px;vertical-align:top;background-color:{p["primary"]};'
            f'border-bottom:2px solid {p["sky"]};{seam}'
            f'color:{p["surface"]};font-size:13px;font-weight:750;line-height:1.5;', c.text,
        )
    seam = f'border-right:1px solid {p["sky_pale"]};' if c.next_column else ""
    fill = p["sky_pale" if c.row_index % 2 else "surface"]
    return (
        f'padding:7px 8px;vertical-align:top;background-color:{fill};'
        f'border-bottom:1px solid {p["primary" if c.last else "sky_pale"]};{seam}'
        f'color:{p["ink"]};font-size:14px;line-height:1.6;', c.text,
    )


_INK_TABLE_RIDGE = {
    "width": 92, "height": 13,
    "parts": [
        {"kind": "polyline", "points": [[12, 11], [20, 10], [28, 6], [32, 7], [38, 3],
                                       [41, 4], [45, 6], [50, 6], [58, 10], [64, 11]],
         "stroke": "secondary", "stroke_width": .85},
        {"kind": "polyline", "points": [[45, 11], [51, 10], [61, 5], [66, 6], [72, 2],
                                       [76, 4], [83, 8], [89, 10], [91, 11]],
         "stroke": "sky", "stroke_width": 1.05},
        {"kind": "polyline", "points": [[2, 11], [24, 11], [34, 10], [38, 11]],
         "stroke": "secondary", "stroke_width": .55},
    ],
}


def _ink_table(c: _Cell, p: _Palette) -> tuple[str, str]:
    # Open paper edges and quiet rules: let text and the landscape do the work.
    edge = f'border-right:1px solid {p["secondary_pale"]};' if c.next_column else ""
    if c.header:
        return (
            f'padding:7px 8px;vertical-align:top;background-color:{p["sky_pale"]};{edge}'
            f'border-top:1px solid {p["sky"]};border-bottom:1px solid {p["primary"]};'
            f'color:{p["primary"]};font-family:Georgia,\'Noto Serif SC\',serif;'
            'font-size:14px;font-weight:700;line-height:1.5;', c.text,
        )
    bottom = f'1px solid {p["primary"]}' if c.last else f'1px dotted {p["secondary"]}'
    return (
        f'padding:7px 8px;vertical-align:top;background-color:{p["sky_pale" if c.row_index % 2 else "surface"]};{edge}'
        f'border-bottom:{bottom};color:{p["ink"]};font-size:14px;line-height:1.6;', c.text,
    )


def _ticket_table(c: _Cell, p: _Palette) -> tuple[str, str]:
    seam = f'border-right:1px solid {p["secondary_pale"]};' if c.next_column else ""
    if c.header:
        return (
            f'padding:7px 8px;vertical-align:top;background-color:{p["pale"]};{seam}'
            f'border-top:3px double {p["primary"]};border-bottom:1px dashed {p["secondary"]};'
            f'color:{p["primary"]};font-size:14px;font-weight:700;line-height:1.5;', c.text,
        )
    bottom = f'1px solid {p["primary"]}' if c.last else f'1px dashed {p["secondary"]}'
    fill = p["sky_pale" if c.row_index % 2 else "surface"]
    return (
        f'padding:7px 8px;vertical-align:top;background-color:{fill};{seam}'
        f'border-bottom:{bottom};color:{p["ink"]};font-size:14px;line-height:1.6;', c.text,
    )


_STYLES: dict[str, tuple[str, _CellStyle]] = {
    "weekend_fieldnotes": ("weekend-fieldnotes-notebook-table", _weekend),
    "after_screening": ("after-screening-scene-ledger-table", _cinema),
    "light_gallery": ("light-gallery-index-table", _light),
    "pixel_live": ("pixel-live-stepped-table", _pixel),
    "collage_fieldguide": ("collage-fieldguide-label-table", _collage),
    "retro_window": ("retro-window-directory-table", _window),
    "folded_fan_detail": ("folded-fan-paper-table", _folded_fan),
    "indigo_cloth": ("indigo-cloth-stitched-table", _indigo_cloth),
    "night_walk_illustration": ("night-walk-sign-table", _night_walk),
    "ink_traces": ("ink-traces-landscape-table", _ink_table),
    "ticket_and_stub": ("ticket-and-stub-perforated-table", _ticket_table),  # Already-saved plans only.
    "round_table_bistro": ("round-table-bistro-table", _bistro),  # Already-saved plans only.
}


def render_official_theme_table(
    theme_id: object, rows: list[list[str]], palette: _Palette, gap: int, inline: Callable[[str], str],
    *, reading: ReadingProfile | None = None, project_text: Callable[[str], str] | None = None,
) -> str | None:
    """Use a reviewed style only for its own pack; never add a decorative row."""
    if not isinstance(theme_id, str) or theme_id not in _STYLES or not rows:
        return None
    grammar, cell_style = _STYLES[theme_id]
    header, *body = rows
    columns = len(header)

    def render_row(row: list[str], *, head: bool = False, last: bool = False, row_index: int = 0) -> str:
        tag, scope = ('th', ' scope="col"') if head else ('td', '')
        cells = []
        for column, value in enumerate(row):
            authored = render_authored_text(inline(value), TABLE_HEADER if head else TABLE_BODY, reading)
            style, text = cell_style(_Cell(project_text(authored) if project_text else authored, column, columns, head, last, row_index), palette)
            cells.append(f'<{tag}{scope} style="{_CELL_BASE}{style}">{text}</{tag}>')
        return '<tr>' + ''.join(cells) + '</tr>'

    borders = "separate;border-spacing:0" if cell_style is _pixel else "collapse"
    body_rows = ''.join(render_row(row, last=i + 1 == len(body), row_index=i) for i, row in enumerate(body))
    # A low ridge meets the top edge directly. Never insert a decorative table
    # row or put artwork inside a data cell where it would change column widths.
    edge = (f'<section aria-hidden="true" style="text-align:right;font-size:0;line-height:0;">'
            f'{render_drawing(_INK_TABLE_RIDGE, palette)}</section>') if cell_style is _ink_table else ""
    return (
        f'<section data-theme-grammar="{grammar}" style="margin:{gap}px 0;overflow-wrap:anywhere;">'
        f'{edge}<table style="width:100%;max-width:100%;border-collapse:{borders};table-layout:fixed;">'
        f'<thead>{render_row(header, head=True)}</thead><tbody>{body_rows}</tbody></table></section>'
    )
