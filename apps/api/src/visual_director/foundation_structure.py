from __future__ import annotations

from typing import Any

from .parser import ContentBlock
from .render_pilot import current_theme_styles_enabled
from .foundation_inline import _inline
from .heading_numbers import has_explicit_heading_number
from .generated_theme import render_generated_heading, render_generated_break, render_generated_table
from .theme_extensions import render_extended_heading, render_extended_break, render_extended_table
from .reading_rules import SECTION_TITLE, SUBHEADING, TABLE_BODY, TABLE_HEADER, ReadingProfile, render_authored_text


def _render_thematic_break(config: dict[str, Any]) -> str:
    generated = render_generated_break(config)
    if generated is not None:
        return generated
    extended = render_extended_break(config)
    if extended is not None:
        return extended
    palette = config.get("palette", {})
    accent = config["accent"]
    heading_variant = config.get("heading_variant")
    if heading_variant == "botanical_section":
        sky = palette.get("sky", accent)
        secondary = palette.get("secondary", accent)
        return (
            '<p data-content-role="thematic-break" style="margin:34px 0;text-align:center;white-space:nowrap;">'
            f'<span style="display:inline-block;width:29%;height:1px;background-color:{sky};"></span>'
            f'<span style="display:inline-block;width:15px;height:9px;margin:0 10px;border-radius:14px 3px 14px 3px;background-color:{secondary};transform:rotate(-15deg);"></span>'
            f'<span style="display:inline-block;width:29%;height:1px;background-color:{sky};"></span></p>'
        )
    if heading_variant == "story_chapter":
        return (
            '<p data-content-role="thematic-break" style="margin:35px 0;border-top:1px dashed #D7B995;text-align:center;">'
            f'<span style="display:inline-block;width:11px;height:11px;margin-top:-7px;border:1px solid {palette.get("primary", accent)};border-radius:50%;background-color:{palette.get("surface", "#FFFCF7")};"></span>'
            f'<span style="display:inline-block;width:42px;height:9px;margin:-6px 0 0 9px;background-color:{palette.get("secondary", accent)};opacity:.7;transform:rotate(-3deg);"></span></p>'
        )
    if heading_variant == "masthead_section":
        return (
            '<p data-content-role="thematic-break" style="margin:35px 0;border-top:3px solid #202B33;">'
            f'<span style="display:block;width:31%;height:8px;background-color:{palette.get("accent", accent)};"></span></p>'
        )
    if heading_variant == "indexed_column":
        return (
            '<p data-content-role="thematic-break" style="margin:35px 0;border-top:1px solid #AEBBB5;text-align:right;">'
            f'<span style="display:inline-block;width:18%;height:5px;background-color:{palette.get("secondary", accent)};"></span>'
            f'<span style="display:inline-block;width:9px;height:9px;margin-left:8px;border:2px solid {palette.get("primary", accent)};vertical-align:middle;"></span></p>'
        )
    if heading_variant == "sticker_section":
        return (
            '<p data-content-role="thematic-break" style="margin:36px 0;text-align:center;white-space:nowrap;">'
            f'<span style="display:inline-block;width:19%;height:1px;border-top:2px dashed {palette.get("sky", accent)};"></span>'
            f'<span style="display:inline-block;width:30px;height:12px;margin:0 10px;background-color:{palette.get("secondary", accent)};transform:rotate(-4deg);vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:10px;height:10px;margin-right:10px;border-radius:50%;background-color:{palette.get("accent", accent)};vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:19%;height:1px;border-top:2px dashed {palette.get("sky", accent)};"></span></p>'
        )
    if heading_variant == "signal_section":
        return (
            '<p data-content-role="thematic-break" style="margin:38px 0;text-align:center;white-space:nowrap;">'
            f'<span style="display:inline-block;width:20%;height:1px;background-color:{palette.get("sky", accent)};vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:18px;height:7px;margin:0 8px;border-radius:12px 2px 12px 2px;background-color:{palette.get("secondary", accent)};transform:rotate(-12deg);vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:7px;height:7px;margin-right:8px;border-radius:50%;background-color:{palette.get("accent", accent)};vertical-align:middle;"></span>'
            f'<span style="display:inline-block;width:20%;height:1px;background-color:{palette.get("primary", accent)};vertical-align:middle;"></span></p>'
        )
    return (
        f'<p data-content-role="thematic-break" style="height:1px;margin:34px 0;background-color:{accent};"></p>'
    )


def _has_explicit_heading_number(value: str) -> bool:
    return has_explicit_heading_number(value)


def _render_heading(block: ContentBlock, config: dict[str, Any], section_index: int, *, reading: ReadingProfile | None = None) -> str:
    accent = config["accent"]
    palette = config.get("palette", {})
    secondary = palette.get("secondary", accent)
    content = str(block.content).strip()
    level = block.level or 2

    generated = render_generated_heading(content, level, section_index, config, reading=reading)
    if generated is not None:
        return generated
    extended = render_extended_heading(content, level, section_index, config, reading=reading)
    if extended is not None:
        return extended

    text = render_authored_text(_inline(content), SECTION_TITLE if level == 2 else SUBHEADING, reading)
    if level == 2 and config["heading_variant"] == "botanical_section":
        section_label = "SECTION" if _has_explicit_heading_number(content) else f"SECTION {section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:43px 0 21px;padding-left:13px;border-left:3px solid {accent};">'
            f'<p style="margin:0 0 6px;color:#76837E;font-family:Georgia,serif;font-size:9px;font-weight:700;letter-spacing:.18em;">{section_label}</p>'
            f'<strong style="display:block;color:#14201F;font-family:Georgia,\'Noto Serif SC\',serif;font-size:22px;line-height:1.5;">{text}</strong>'
            f'<p style="margin:10px 0 0;border-top:1px solid {secondary};font-size:0;line-height:0;"><span style="display:block;width:14px;height:8px;margin-left:-2px;border-radius:12px 2px 12px 2px;background-color:{accent};font-size:0;line-height:0;transform:rotate(-16deg);">&#160;</span></p>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "indexed_column":
        section_label = "IDX" if _has_explicit_heading_number(content) else f"{section_index:02d}"
        sizing = "box-sizing:border-box;" if current_theme_styles_enabled() else ""
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:44px 0 22px;border-top:4px solid {accent};white-space:normal;">'
            f'<span style="{sizing}display:inline-block;width:21%;padding:12px 8px 10px 0;color:{secondary};font-family:Georgia,serif;font-size:28px;font-weight:800;line-height:1;vertical-align:top;">{section_label}</span>'
            f'<strong style="box-sizing:border-box;display:inline-block;width:79%;padding:10px 0 11px 14px;border-left:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;color:#14201F;font-size:21px;line-height:1.48;vertical-align:top;">{text}</strong>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "story_chapter":
        section_label = "CHAPTER" if _has_explicit_heading_number(content) else f"CHAPTER {section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:44px 0 22px;padding:3px 0 12px 17px;border-left:5px solid {secondary};border-bottom:1px solid #D7B995;">'
            f'<p style="margin:-9px 0 11px -18px;"><span style="display:inline-block;padding:5px 10px;background-color:{palette.get("accent_pale", "#FBE9E2")};color:{accent};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.12em;transform:rotate(-2deg);">{section_label}</span></p>'
            f'<strong style="display:block;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:22px;line-height:1.52;">{text}</strong>'
            f'<p style="margin:9px 0 -17px;text-align:right;"><span style="display:inline-block;width:46px;height:9px;background-color:{secondary};opacity:.72;transform:rotate(-3deg);"></span></p>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "masthead_section":
        section_label = "SECTION" if _has_explicit_heading_number(content) else f"{section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:45px 0 23px;padding:11px 0 13px;border-top:11px solid #202B33;border-bottom:3px solid #202B33;">'
            f'<p style="margin:0 0 8px;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:12px;font-weight:800;letter-spacing:.1em;">{section_label}<span style="display:inline-block;width:46px;height:6px;margin-left:10px;background-color:{accent};"></span></p>'
            f'<strong style="display:block;color:#202B33;font-size:21px;font-weight:850;line-height:1.48;">{text}</strong>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "sticker_section":
        section_label = "CAMPUS BULLETIN" if _has_explicit_heading_number(content) else f"COURSE NOTE {section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:45px 0 23px;padding:0 8px 8px 0;">'
            f'<p style="margin:0 0 -8px 17px;"><span style="display:inline-block;padding:5px 12px;background-color:{secondary};color:{palette.get("ink", "#20304A")};font-size:9px;font-weight:800;letter-spacing:.13em;transform:rotate(-2deg);">{section_label}</span></p>'
            f'<section style="padding:19px 17px 16px 26px;border-left:10px dotted {palette.get("sky", accent)};border-bottom:3px solid {accent};background-color:{palette.get("surface", "#FFFEFB")};box-shadow:7px 7px 0 {palette.get("secondary_pale", "#FFF6D9")};">'
            f'<strong style="display:block;color:{palette.get("ink", "#20304A")};font-size:21px;line-height:1.5;">{text}</strong>'
            f'</section></section>'
        )

    if level == 2 and config["heading_variant"] == "signal_section":
        if config.get("theme_kit") == "future_science_editorial_v1":
            numbered = not _has_explicit_heading_number(content)
            signal = palette.get("secondary", accent)
            pulse = palette.get("accent", accent)
            rail = palette.get("sky_pale", "#EEF1FA")
            wash = palette.get("secondary_pale", "#EAF9F6")
            ink = palette.get("ink", "#24304F")
            marker = (
                f'<span style="display:inline-block;padding:0 4px;border-radius:12px 12px 12px 5px;background-color:{wash};border-bottom:1px solid {signal};color:{ink};font:800 13px/20px Georgia,serif;vertical-align:middle;">{section_index:02d}</span>'
                if numbered else
                f'<span style="display:inline-block;width:15px;height:7px;border-radius:12px 4px 12px 4px;background-color:{signal};transform:rotate(-12deg);vertical-align:middle;"></span>'
                f'<span style="display:inline-block;width:5px;height:5px;margin-left:3px;border-radius:50%;background-color:{pulse};vertical-align:middle;"></span>'
            )
            return (
                f'<section data-heading-level="2" data-auto-numbered="{str(numbered).lower()}" data-theme-grammar="signal-junction" '
                f'style="margin:39px 0 20px;white-space:normal;">'
                f'<span style="display:inline-block;width:9%;padding-top:4px;color:{ink};vertical-align:top;">{marker}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:91%;padding-left:6px;vertical-align:top;">'
                f'<strong style="display:block;color:{ink};font-size:21px;line-height:1.5;overflow-wrap:anywhere;">{text}</strong>'
                f'<section style="height:3px;margin-top:9px;border-radius:6px;background-color:{rail};"><span style="display:block;width:34px;height:3px;border-radius:6px;background-color:{pulse};"></span></section>'
                '</section></section>'
            )
        section_label = "专题" if _has_explicit_heading_number(content) else f"{section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:48px 0 24px;padding:0 0 10px;white-space:normal;">'
            f'<span style="display:inline-block;width:19%;color:{palette.get("sky_pale", "#EEF1FA")};font-family:Georgia,serif;font-size:46px;font-weight:800;line-height:.92;vertical-align:top;">{section_label}</span>'
            f'<section style="box-sizing:border-box;display:inline-block;width:81%;padding:2px 0 10px 16px;border-left:5px solid {palette.get("secondary", accent)};vertical-align:top;">'
            f'<strong style="display:block;color:{palette.get("ink", "#24304F")};font-size:21px;line-height:1.52;">{text}</strong>'
            f'<p style="height:3px;margin:11px 0 0;background:linear-gradient(90deg,{palette.get("accent", accent)} 0%,{palette.get("accent", accent)} 28%,{palette.get("sky_pale", "#EEF1FA")} 28%);"></p></section>'
            "</section>"
        )

    if level == 2 and config["heading_variant"] == "numbered_marker":
        if _has_explicit_heading_number(content):
            return (
                '<section data-heading-level="2" data-auto-numbered="false" style="margin:40px 0 20px;padding-top:13px;'
                f'border-top:2px solid {accent};">'
                f'<strong style="display:block;color:#14201F;font-size:22px;line-height:1.48;letter-spacing:.01em;">{text}</strong>'
                "</section>"
            )
        return (
            '<section data-heading-level="2" data-auto-numbered="true" style="margin:40px 0 20px;">'
            f'<span class="heading-number" style="display:inline-block;width:32px;height:32px;margin-right:9px;border-radius:50%;background-color:{accent};color:#fff;font:700 14px/32px Arial;text-align:center;vertical-align:top;">{section_index:02d}</span>'
            f'<strong style="display:inline-block;max-width:82%;margin-top:1px;color:#14201F;font-size:22px;line-height:1.45;letter-spacing:.01em;vertical-align:top;">{text}</strong>'
            "</section>"
        )

    if level == 2:
        section_label = "SECTION" if _has_explicit_heading_number(content) else f"SECTION {section_index:02d}"
        return (
            f'<section data-heading-level="2" data-auto-numbered="{str(not _has_explicit_heading_number(content)).lower()}" '
            f'style="margin:42px 0 20px;padding-left:14px;border-left:3px solid {accent};">'
            f'<p style="margin:0 0 5px;color:#7A7F7C;font:600 10px/1.2 Arial;letter-spacing:.18em;">{section_label}</p>'
            f'<strong style="display:block;color:#14201F;font-family:Georgia,serif;font-size:22px;line-height:1.48;">{text}</strong>'
            "</section>"
        )

    if level == 3:
        if config["heading_variant"] == "botanical_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;white-space:normal;">'
                f'<span style="display:inline-block;width:19px;height:13px;margin:3px 8px 0 0;border-radius:16px 3px 16px 3px;background-color:{accent};transform:rotate(-8deg);vertical-align:top;"></span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:87%;padding-bottom:7px;border-bottom:1px solid {secondary};vertical-align:top;">'
                f'<strong style="color:#263331;font-size:18px;line-height:1.55;font-weight:750;">{text}</strong></section>'
                "</section>"
            )
        if config["heading_variant"] == "indexed_column":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;padding:0 0 8px;border-bottom:1px solid #B9C3BE;white-space:normal;">'
                f'<span style="display:inline-block;width:35px;color:{accent};font-family:Georgia,serif;font-size:11px;font-weight:800;vertical-align:top;">SUB</span>'
                f'<strong style="display:inline-block;width:86%;color:#263331;font-size:18px;line-height:1.55;font-weight:750;vertical-align:top;">{text}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "story_chapter":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;white-space:normal;">'
                f'<span style="display:inline-block;width:23px;height:23px;margin:0 9px 0 0;border:1px solid {accent};border-radius:50%;color:{accent};font-size:12px;font-weight:800;line-height:23px;text-align:center;transform:rotate(-7deg);vertical-align:top;">✦</span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:86%;padding:0 0 8px;border-bottom:1px dashed #D7B995;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;line-height:1.58;vertical-align:top;">{text}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "masthead_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:30px 0 13px;padding:0 0 8px;border-bottom:2px solid #202B33;white-space:normal;">'
                f'<span style="display:block;width:30px;height:7px;margin:0 0 8px;background-color:{palette.get("accent", accent)};"></span>'
                f'<strong style="display:block;color:#202B33;font-size:18px;line-height:1.5;font-weight:850;">{text}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "sticker_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;white-space:normal;">'
                f'<span style="display:inline-block;width:32px;height:13px;margin:5px 9px 0 0;background-color:{palette.get("secondary", accent)};transform:rotate(-4deg);vertical-align:top;"></span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:84%;padding:0 0 8px;border-bottom:2px dashed {palette.get("sky", accent)};color:{palette.get("ink", "#20304A")};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "_legacy_sticker_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;white-space:normal;">'
                f'<span style="display:inline-block;width:25px;height:25px;margin-right:9px;border-radius:9px 9px 3px 9px;background-color:{palette.get("accent", accent)};color:#FFFFFF;font-size:12px;font-weight:800;line-height:25px;text-align:center;transform:rotate(-5deg);vertical-align:top;">✦</span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:85%;padding:1px 0 8px;border-bottom:2px dashed {palette.get("sky", accent)};color:{palette.get("ink", "#20304A")};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "signal_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:30px 0 14px;white-space:normal;">'
                f'<span style="display:inline-block;width:18px;height:8px;margin:6px 10px 0 0;border-radius:12px 2px 12px 2px;background-color:{palette.get("secondary", accent)};transform:rotate(-12deg);vertical-align:top;"></span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:87%;padding:0 0 8px;color:{palette.get("ink", "#24304F")};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong>'
                "</section>"
            )
        if config["heading_variant"] == "_legacy_signal_section":
            return (
                '<section data-heading-level="3" data-auto-numbered="false" style="margin:29px 0 13px;padding-bottom:8px;border-bottom:1px solid #B9D8D2;white-space:normal;">'
                f'<span style="display:inline-block;width:35px;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.1em;vertical-align:top;">NODE</span>'
                f'<strong style="box-sizing:border-box;display:inline-block;width:86%;padding-left:12px;border-left:2px solid {palette.get("secondary", accent)};color:{palette.get("ink", "#17313D")};font-size:18px;line-height:1.55;vertical-align:top;">{text}</strong>'
                "</section>"
            )
        return (
            '<section data-heading-level="3" data-auto-numbered="false" style="margin:27px 0 12px;">'
            f'<span style="display:inline-block;width:13px;height:3px;margin:0 8px 5px 0;background-color:{accent};vertical-align:middle;"></span>'
            f'<strong style="display:inline;color:#263331;font-size:18px;line-height:1.55;font-weight:750;">{text}</strong>'
            "</section>"
        )

    return (
        '<p data-heading-level="4" data-auto-numbered="false" '
        f'style="margin:22px 0 9px;color:{accent};font-size:16px;line-height:1.55;font-weight:750;">{text}</p>'
    )


def _render_table(rows: list[list[str]], config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str:
    if not rows:
        return ""
    generated = render_generated_table(rows, config, reading=reading)
    if generated is not None:
        return generated
    markup = _render_classic_table(rows, config, reading=reading)
    # Newly supported wide tables have little room per column on a phone.
    # Wrap long IDs inside their own cells; do not elide or alter source text.
    if any(len(row) > 4 for row in rows):
        markup = markup.replace('<table style="', '<table style="overflow-wrap:anywhere;word-break:break-word;', 1)
    return markup


def _render_classic_table(rows: list[list[str]], config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str:
    extended = render_extended_table(rows, config, reading=reading)
    if extended is not None:
        return extended
    accent = config["accent"]
    header, *body = rows
    if config.get("table_variant") == "ledger_grid":
        palette = config.get("palette", {})
        secondary = palette.get("secondary", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-top:4px solid {accent};border-bottom:1px solid #AEBBB5;background-color:#FFFFFF;color:{accent};font-size:12px;line-height:1.4;text-align:left;">{render_authored_text(_inline(cell), TABLE_HEADER, reading)}</th>'
            for cell in header
        )
        trs = []
        for row_index, row in enumerate(body):
            # WeChat can expand an empty decorative row to a full line on paste.
            bottom = f"3px solid {secondary}" if row_index == len(body) - 1 else "1px solid #D1D8D4"
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:{bottom};background-color:{"#F3F6F1" if cell_index == 0 else "#FFFFFF"};color:#34403E;font-size:13px;line-height:1.55;vertical-align:top;">{render_authored_text(_inline(cell), TABLE_BODY, reading)}</td>'
                for cell_index, cell in enumerate(row)
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            '<section style="margin:24px 0;overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    if config.get("table_variant") == "soft_ledger":
        palette = config.get("palette", {})
        secondary = palette.get("secondary", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-bottom:2px solid {accent};background-color:#FFF8ED;color:{accent};font-family:Georgia,\'Noto Serif SC\',serif;font-size:12px;line-height:1.45;text-align:left;">{render_authored_text(_inline(cell), TABLE_HEADER, reading)}</th>'
            for cell in header
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px dashed #D7B995;background-color:{"#FFFCF7" if cell_index else "#FBF2D8"};color:#342B28;font-size:13px;line-height:1.58;vertical-align:top;">{render_authored_text(_inline(cell), TABLE_BODY, reading)}</td>'
                for cell_index, cell in enumerate(row)
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            f'<section style="margin:24px 0;padding-left:7px;border-left:5px solid {secondary};overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    if config.get("table_variant") == "editorial_matrix":
        palette = config.get("palette", {})
        editorial_accent = palette.get("accent", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-top:10px solid #202B33;border-bottom:3px solid #202B33;background-color:#FFFFFF;color:#202B33;font-size:12px;font-weight:850;line-height:1.4;text-align:left;">{render_authored_text(_inline(cell), TABLE_HEADER, reading)}</th>'
            for cell in header
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px solid #202B33;border-left:{f"5px solid {editorial_accent}" if cell_index == 0 else "0"};background-color:{"#EEF2F3" if row_index % 2 == 0 else "#FFFFFF"};color:#202B33;font-size:13px;line-height:1.55;vertical-align:top;">{render_authored_text(_inline(cell), TABLE_BODY, reading)}</td>'
                for cell_index, cell in enumerate(row)
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            '<section style="margin:24px 0;overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    if config.get("table_variant") == "campus_grid":
        palette = config.get("palette", {})
        secondary = palette.get("secondary", accent)
        sky = palette.get("sky", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-bottom:3px solid {accent};background-color:{palette.get("secondary_pale", "#FFF6D9")};color:{palette.get("ink", "#20304A")};font-size:12px;font-weight:800;line-height:1.4;text-align:left;">{render_authored_text(_inline(cell), TABLE_HEADER, reading)}</th>'
            for cell in header
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px dashed {sky};background-color:{"#EEF4FF" if row_index % 2 == 0 else "#FFFEFB"};color:{palette.get("ink", "#20304A")};font-size:13px;line-height:1.55;vertical-align:top;">{render_authored_text(_inline(cell), TABLE_BODY, reading)}</td>'
                for cell in row
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            f'<section style="margin:24px 0;padding:6px;border:2px solid {accent};border-radius:14px 14px 4px 14px;box-shadow:5px 5px 0 {secondary};overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    if config.get("table_variant") == "signal_matrix":
        palette = config.get("palette", {})
        secondary = palette.get("secondary", accent)
        ths = "".join(
            f'<th style="padding:10px 8px;border-top:4px solid {accent};border-bottom:1px solid #B9D8D2;background-color:{palette.get("surface", "#FBFEFD")};color:{accent};font-size:12px;font-weight:800;line-height:1.4;text-align:left;">{render_authored_text(_inline(cell), TABLE_HEADER, reading)}</th>'
            for cell in header
        )
        trs = []
        for row_index, row in enumerate(body):
            cells = "".join(
                f'<td style="padding:11px 8px;border-bottom:1px solid #CFE2DE;border-left:{f"3px solid {secondary}" if cell_index == 0 else "0"};background-color:{"#F1F4FF" if row_index % 2 == 0 else "#FBFEFD"};color:{palette.get("ink", "#17313D")};font-size:13px;line-height:1.55;vertical-align:top;">{render_authored_text(_inline(cell), TABLE_BODY, reading)}</td>'
                for cell_index, cell in enumerate(row)
            )
            trs.append(f"<tr>{cells}</tr>")
        return (
            '<section style="margin:24px 0;overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
            "</section>"
        )
    ths = "".join(
        f'<th style="padding:10px 8px;background-color:{accent};color:#fff;font-size:13px;line-height:1.4;text-align:left;border:1px solid {accent};">{render_authored_text(_inline(cell), TABLE_HEADER, reading)}</th>'
        for cell in header
    )
    trs = []
    for row_index, row in enumerate(body):
        background = "#F7F4EC" if row_index % 2 == 0 else "#FFFFFF"
        cells = "".join(
            f'<td style="padding:10px 8px;background-color:{background};color:#34403E;font-size:13px;line-height:1.5;border:1px solid #D9DED9;vertical-align:top;">{render_authored_text(_inline(cell), TABLE_BODY, reading)}</td>'
            for cell in row
        )
        trs.append(f"<tr>{cells}</tr>")
    return (
        '<section style="margin:22px 0;overflow-x:auto;">'
        f'<table style="width:100%;border-collapse:collapse;table-layout:fixed;"><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
        "</section>"
    )
