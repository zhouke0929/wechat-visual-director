"""Native table styles for the six reviewed official-theme candidates."""
from collections.abc import Callable
from dataclasses import dataclass


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


_STYLES: dict[str, tuple[str, _CellStyle]] = {
    "weekend_fieldnotes": ("weekend-fieldnotes-notebook-table", _weekend),
    "after_screening": ("after-screening-scene-ledger-table", _cinema),
    "light_gallery": ("light-gallery-index-table", _light),
    "pixel_live": ("pixel-live-stepped-table", _pixel),
    "collage_fieldguide": ("collage-fieldguide-label-table", _collage),
    "round_table_bistro": ("round-table-bistro-table", _bistro),
}


def render_official_theme_table(
    theme_id: object, rows: list[list[str]], palette: _Palette, gap: int, inline: Callable[[str], str],
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
            style, text = cell_style(_Cell(inline(value), column, columns, head, last, row_index), palette)
            cells.append(f'<{tag}{scope} style="{_CELL_BASE}{style}">{text}</{tag}>')
        return '<tr>' + ''.join(cells) + '</tr>'

    borders = "separate;border-spacing:0" if cell_style is _pixel else "collapse"
    body_rows = ''.join(render_row(row, last=i + 1 == len(body), row_index=i) for i, row in enumerate(body))
    return (
        f'<section data-theme-grammar="{grammar}" style="margin:{gap}px 0;overflow-wrap:anywhere;">'
        f'<table style="width:100%;max-width:100%;border-collapse:{borders};table-layout:fixed;">'
        f'<thead>{render_row(header, head=True)}</thead><tbody>{body_rows}</tbody></table></section>'
    )
