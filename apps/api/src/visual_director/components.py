from __future__ import annotations

import html
import re
from typing import Any

from .parser import ParsedArticle


REF_RE = re.compile(r"^(block-\d{3})(?::item:(\d+))?$")


def _inline(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("\n", "<br>")


def _resolve(parsed: ParsedArticle, reference: str) -> str:
    match = REF_RE.fullmatch(reference)
    if not match:
        raise ValueError(f"无法解析内容绑定：{reference}")
    block_id, item_index = match.groups()
    block = next((item for item in parsed.blocks if item.id == block_id), None)
    if block is None:
        raise ValueError(f"内容块不存在：{block_id}")
    if item_index is None:
        return str(block.content)
    return str(block.content[int(item_index)])


def _one(parsed: ParsedArticle, bindings: dict[str, Any], role: str) -> str:
    reference = bindings[role]
    if not isinstance(reference, str):
        raise ValueError(f"{role} 应为单个内容引用")
    return _resolve(parsed, reference)


def _many(parsed: ParsedArticle, bindings: dict[str, Any], role: str) -> list[str]:
    references = bindings[role]
    if not isinstance(references, list):
        raise ValueError(f"{role} 应为内容引用数组")
    return [_resolve(parsed, reference) for reference in references]


DEFAULT_PALETTE = {
    "primary": "#117C73",
    "secondary": "#F4C84A",
    "accent": "#F06A4B",
    "sky": "#58B9E4",
    "pale": "#E9F7F3",
    "secondary_pale": "#FFF7D5",
    "accent_pale": "#FFF0E9",
    "sky_pale": "#EAF7FD",
    "surface": "#FFFEFA",
    "ink": "#20312E",
}


def _plain_list(items: list[str], accent: str) -> str:
    rows = []
    for index, item in enumerate(items, 1):
        rows.append(
            '<p style="margin:0 0 12px;color:#34403E;font-size:16px;line-height:1.75;">'
            f'<strong style="color:{accent};">{index:02d}.</strong> {_inline(item)}</p>'
        )
    return '<section style="margin:24px 0;">' + "".join(rows) + "</section>"


def render_component(slot: dict[str, Any], parsed: ParsedArticle, palette: dict[str, str] | None = None) -> str:
    component_type = slot["component_type"]
    variant = slot["variant"]
    bindings = slot["content_bindings"]
    colors = {**DEFAULT_PALETTE, **(palette or {})}
    primary = colors["primary"]
    secondary = colors["secondary"]
    accent = colors["accent"]
    sky = colors["sky"]
    pale = colors["pale"]
    secondary_pale = colors["secondary_pale"]
    accent_pale = colors["accent_pale"]
    sky_pale = colors["sky_pale"]
    surface = colors["surface"]
    ink = colors["ink"]

    if component_type == "question_hook":
        title = _inline(_one(parsed, bindings, "title"))
        if variant == "plain_question":
            return f'<p style="margin:28px 0 20px;color:{primary};font-size:20px;font-weight:750;line-height:1.6;text-align:center;">{title}</p>'
        if variant == "warm_letter_prompt":
            return (
                f'<section style="margin:30px 0 26px;padding:0 14px 17px;border-left:4px solid {accent};border-bottom:1px solid #E7D4BD;background-color:#FFF8ED;">'
                f'<p style="display:inline-block;margin:0 0 13px;padding:5px 10px;background-color:{accent};color:#FFFFFF;font-family:Georgia,serif;font-size:9px;font-weight:700;letter-spacing:.14em;">A NOTE FOR YOU</p>'
                f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:19px;font-weight:750;line-height:1.72;">{title}</p>'
                f'<p style="margin:12px 0 0;color:{accent};font-size:10px;font-weight:700;letter-spacing:.08em;">从你的真实选择出发 ···</p>'
                f'</section>'
            )
        if variant == "editorial_deck_question":
            return (
                f'<section style="margin:30px 0 27px;padding:16px 0;border-top:4px solid {ink};border-bottom:1px solid {ink};white-space:normal;">'
                f'<span style="display:inline-block;width:52px;color:{accent};font-family:Georgia,serif;font-size:48px;font-weight:700;line-height:.9;vertical-align:top;">Q.</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:82%;padding-left:15px;border-left:1px solid #C8C4BA;vertical-align:top;">'
                f'<p style="margin:0 0 7px;color:#727873;font-size:8px;font-weight:750;letter-spacing:.18em;">OPENING QUESTION</p>'
                f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:20px;font-weight:750;line-height:1.65;">{title}</p>'
                f'</section></section>'
            )
        if variant == "grid_query_panel":
            return (
                f'<section style="margin:28px 0 26px;border:1px solid {primary};background-color:{surface};">'
                f'<section style="padding:7px 11px;border-bottom:1px solid {primary};background-color:{pale};white-space:normal;">'
                f'<span style="display:inline-block;width:68%;color:{primary};font-size:8px;font-weight:800;letter-spacing:.16em;">QUERY REGISTER</span>'
                f'<span style="display:inline-block;width:32%;color:{accent};font-family:Georgia,serif;font-size:10px;font-weight:700;text-align:right;">Q-01 / OPEN</span></section>'
                f'<section style="padding:17px 15px 16px;border-left:7px solid {secondary};">'
                f'<p style="margin:0;color:{ink};font-size:18px;font-weight:750;line-height:1.65;">{title}</p>'
                f'<p style="margin:12px 0 0;padding-top:7px;border-top:1px dotted #AEBAB5;color:{primary};font-size:9px;font-weight:750;letter-spacing:.12em;">INPUT → JUDGEMENT → ACTION</p>'
                f'</section></section>'
            )
        return (
            '<section style="margin:28px 0 24px;text-align:center;">'
            f'<p style="margin:0 0 8px;color:{primary};font-size:9px;font-weight:750;letter-spacing:.18em;">'
            f'<span style="display:inline-block;width:18px;height:3px;margin:0 8px 2px 0;background-color:{secondary};vertical-align:middle;"></span>QUESTION'
            f'<span style="display:inline-block;width:5px;height:5px;margin:0 0 2px 8px;border-radius:50%;background-color:{accent};vertical-align:middle;"></span></p>'
            f'<section style="display:inline-block;max-width:86%;padding:15px 20px;border:1px solid {sky};border-radius:20px 20px 5px 20px;background-color:{sky_pale};box-shadow:5px 5px 0 {secondary_pale};color:{ink};font-size:18px;font-weight:750;line-height:1.6;">'
            f'{title}</section></section>'
        )

    if component_type == "numbered_insight":
        items = _many(parsed, bindings, "items")
        if variant == "plain_numbered_list":
            return _plain_list(items, primary)
        if variant == "scrapbook_index":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="margin:0 0 11px;padding:0 0 11px;border-bottom:1px dashed #D8C6AE;white-space:normal;">'
                    f'<span style="display:inline-block;width:42px;padding:5px 0;border-radius:12px 12px 3px 12px;background-color:{accent_pale};color:{accent};font-family:Georgia,serif;font-size:15px;font-weight:750;text-align:center;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:83%;margin:0;padding:3px 0 0 13px;color:{ink};font-size:15px;font-weight:650;line-height:1.72;vertical-align:top;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:27px 0;padding:17px 17px 8px;border:1px solid #E5D3B9;border-radius:3px 18px 5px 18px;background-color:#FFF9EF;box-shadow:5px 5px 0 {secondary_pale};">'
                f'<p style="margin:-25px 0 16px;"><span style="display:inline-block;padding:6px 12px;background-color:{secondary};color:{ink};font-size:9px;font-weight:800;letter-spacing:.14em;">FIELD NOTES · {len(items):02d}</span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "coordinate_index":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="border-top:1px solid #B7C5C0;white-space:normal;">'
                    f'<span style="display:inline-block;width:52px;padding:13px 7px;color:{primary};font-family:Georgia,serif;font-size:14px;font-weight:750;vertical-align:top;">R{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:12px 12px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;font-weight:650;line-height:1.7;vertical-align:top;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};">'
                f'<section style="padding:8px 10px;background-color:{primary};color:#FFFFFF;white-space:normal;">'
                f'<span style="display:inline-block;width:68%;font-size:8px;font-weight:800;letter-spacing:.16em;">INSIGHT COORDINATES</span>'
                f'<span style="display:inline-block;width:32%;font-family:Georgia,serif;font-size:9px;text-align:right;">ROWS {len(items):02d}</span></section>'
                f'{"".join(rows)}'
                f'<p style="margin:0;padding:6px 10px;border-top:1px solid #B7C5C0;color:#74807C;font-size:8px;letter-spacing:.1em;">SOURCE LOCKED / CONTENT UNCHANGED</p></section>'
            )
        if variant == "magazine_index":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="margin:0;border-bottom:1px solid #DED9CF;white-space:normal;">'
                    f'<span style="display:inline-block;width:58px;padding:13px 0 10px;color:{accent};font-family:Georgia,serif;font-size:31px;font-weight:700;line-height:1;letter-spacing:-.06em;vertical-align:top;">{index:02d}</span>'
                    f'<section style="box-sizing:border-box;display:inline-block;width:78%;min-height:60px;padding:12px 0 11px 15px;border-left:1px solid #B8BDB6;vertical-align:top;">'
                    f'<p style="margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:15px;font-weight:700;line-height:1.65;">{_inline(item)}</p>'
                    f'</section></section>'
                )
            return (
                f'<section style="margin:26px 0;padding:17px 0 14px;border-top:3px solid {ink};border-bottom:1px solid {ink};">'
                f'<p style="margin:0 0 5px;color:{accent};font-size:9px;font-weight:750;letter-spacing:.16em;">'
                f'{len(items):02d} POINTS<span style="display:inline-block;width:38%;height:1px;margin:0 0 3px 12px;background-color:#D9D5CA;"></span></p>'
                f'{"".join(rows)}'
                f'<p style="margin:11px 0 0;color:#737C78;font-size:9px;letter-spacing:.1em;text-align:right;">核对信息，再做决定</p>'
                f'</section>'
            )
        rows = []
        item_palettes = (
            (primary, pale, "#FFFFFF"),
            (secondary, secondary_pale, ink),
            (accent, accent_pale, "#FFFFFF"),
            (sky, sky_pale, "#FFFFFF"),
        )
        for index, item in enumerate(items, 1):
            item_accent, item_pale, number_color = item_palettes[(index - 1) % len(item_palettes)]
            rows.append(
                '<section style="margin:0 0 10px;white-space:normal;">'
                f'<span style="display:inline-block;width:36px;height:36px;border-radius:12px 12px 4px 12px;background-color:{item_accent};color:{number_color};font-size:12px;font-weight:750;line-height:36px;text-align:center;vertical-align:middle;">{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:80%;margin-left:10px;padding:12px 14px;border-left:3px solid {item_accent};border-radius:2px 14px 14px 2px;background-color:{item_pale};vertical-align:middle;">'
                f'<p style="margin:0;color:{ink};font-size:15px;font-weight:650;line-height:1.65;">{_inline(item)}</p></section></section>'
            )
        return (
            '<section style="margin:26px 0;">'
            f'<p style="margin:0 0 9px;color:{primary};font-size:9px;font-weight:750;letter-spacing:.16em;">'
            f'<span style="display:inline-block;width:7px;height:7px;margin-right:5px;border-radius:50%;background-color:{accent};"></span>'
            f'<span style="display:inline-block;width:7px;height:7px;margin-right:5px;border-radius:50%;background-color:{secondary};"></span>'
            f'<span style="display:inline-block;width:22px;height:2px;margin:0 12px 2px 0;background-color:{sky};"></span>KEY POINTS</p>'
            f'{"".join(rows)}</section>'
        )

    if component_type == "evidence_callout":
        evidence = _inline(_one(parsed, bindings, "evidence"))
        if variant == "plain_evidence_note":
            return f'<blockquote style="margin:25px 0;padding:4px 0 4px 16px;border-left:3px solid {primary};color:#3F4A47;font-size:16px;line-height:1.8;">{evidence}</blockquote>'
        if variant == "annotated_note":
            return (
                f'<section style="margin:29px 0;padding:0 17px 18px;border:1px solid #E1CDB2;border-radius:3px 17px 4px 17px;background-color:#FFF8EB;box-shadow:5px 5px 0 {accent_pale};">'
                f'<p style="margin:-8px 0 13px;"><span style="display:inline-block;padding:5px 12px;background-color:{secondary};color:{ink};font-size:9px;font-weight:800;letter-spacing:.12em;">已核对的依据</span></p>'
                f'<p style="margin:0;padding-left:14px;border-left:3px solid {accent};color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:16px;font-weight:650;line-height:1.86;">{evidence}</p>'
                f'<p style="margin:12px 0 0;color:{accent};font-size:9px;font-weight:750;letter-spacing:.08em;text-align:right;">ANNOTATED · KEEP THIS IN MIND</p></section>'
            )
        if variant == "evidence_register":
            return (
                f'<section style="margin:28px 0;border:1px solid {primary};background-color:{surface};">'
                f'<section style="padding:7px 11px;border-bottom:1px solid {primary};background-color:{pale};white-space:normal;">'
                f'<span style="display:inline-block;width:72%;color:{primary};font-size:8px;font-weight:800;letter-spacing:.16em;">EVIDENCE REGISTER</span>'
                f'<span style="display:inline-block;width:28%;color:{accent};font-family:Georgia,serif;font-size:9px;font-weight:750;text-align:right;">VERIFIED</span></section>'
                f'<section style="padding:15px 15px 16px;border-left:7px solid {secondary};">'
                f'<p style="margin:0;color:{ink};font-size:16px;font-weight:700;line-height:1.82;">{evidence}</p>'
                f'<p style="margin:12px 0 0;padding-top:8px;border-top:1px dotted #AEBAB5;color:#6D7874;font-size:8px;letter-spacing:.1em;">ID E-01 · FACT BINDING LOCKED</p></section></section>'
            )
        if variant == "editorial_margin_quote":
            return (
                f'<section style="margin:28px 0;padding:22px 17px 18px;border-top:4px solid {ink};border-bottom:1px solid {ink};background-color:#FBF5E9;">'
                f'<p style="margin:0 0 14px;padding-left:10px;border-left:2px solid {accent};color:{accent};font-size:8px;font-weight:750;letter-spacing:.14em;">EDITOR\'S NOTE · 关键判断</p>'
                f'<section style="white-space:normal;">'
                f'<span style="display:inline-block;width:42px;color:{accent_pale};font-family:Georgia,serif;font-size:68px;font-weight:700;line-height:.78;vertical-align:top;">“</span>'
                f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;padding:2px 0 0 13px;border-left:1px solid #D6CFC2;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;font-weight:750;line-height:1.85;vertical-align:top;">{evidence}</p>'
                f'</section>'
                f'<p style="margin:17px 0 0;padding-top:9px;border-top:1px solid #DAD5CA;color:{primary};font-size:10px;font-weight:750;letter-spacing:.06em;">先核对依据，再确认顺序</p>'
                f'</section>'
            )
        return (
            f'<section style="margin:28px 0;padding:18px 18px 19px;border:1px solid {primary};border-radius:4px 20px 20px 20px;background-color:{surface};box-shadow:5px 5px 0 {sky_pale};">'
            f'<p style="margin:0 0 10px;color:{primary};font-size:9px;font-weight:750;letter-spacing:.16em;white-space:nowrap;">'
            f'<span style="display:inline-block;width:8px;height:8px;margin-right:8px;border-radius:50%;background-color:{accent};"></span>'
            f'EVIDENCE / 证据<span style="display:inline-block;width:26px;height:3px;margin:0 0 2px 12px;background-color:{secondary};"></span></p>'
            f'<p style="margin:0;color:{ink};font-size:16px;font-weight:650;line-height:1.8;">{evidence}</p></section>'
        )

    if component_type == "before_after_timeline":
        before = _inline(_one(parsed, bindings, "before"))
        after = _inline(_one(parsed, bindings, "after"))
        if variant == "stacked_before_after":
            return (
                '<section style="margin:25px 0;">'
                f'<p style="margin:0 0 10px;padding:14px;border-left:4px solid {accent};background-color:{accent_pale};line-height:1.7;"><strong>之前：</strong>{before}</p>'
                f'<p style="margin:0;padding:14px;border-left:4px solid {primary};background-color:{pale};line-height:1.7;"><strong>之后：</strong>{after}</p></section>'
            )
        return (
            f'<section style="margin:28px 0;padding:3px 0 3px 13px;border-left:2px dotted {sky};">'
            '<section style="margin:0 0 20px;padding-left:13px;">'
            f'<span style="display:inline-block;margin:0 0 8px;padding:5px 11px;border-radius:4px 12px 12px 12px;background-color:{accent};color:#FFFFFF;font-size:11px;font-weight:750;">改革前</span>'
            f'<p style="margin:0;padding:12px 14px;border-radius:4px 14px 14px 14px;background-color:{accent_pale};color:{ink};font-size:15px;line-height:1.75;">{before}</p></section>'
            '<section style="padding-left:13px;">'
            f'<span style="display:inline-block;margin:0 0 8px;padding:5px 11px;border-radius:4px 12px 12px 12px;background-color:{primary};color:#FFFFFF;font-size:11px;font-weight:750;">改革后</span>'
            f'<p style="margin:0;padding:12px 14px;border-radius:4px 14px 14px 14px;background-color:{pale};color:{ink};font-size:15px;line-height:1.75;">{after}</p></section></section>'
        )

    if component_type == "logic_path":
        items = _many(parsed, bindings, "items")
        if variant == "plain_steps":
            return _plain_list(items, primary)
        if variant == "airy_route":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="margin:0 0 11px;white-space:normal;">'
                    f'<span style="display:inline-block;width:34px;height:34px;border:2px solid {sky};border-radius:50%;background-color:{surface};color:{primary};font-family:Georgia,serif;font-size:11px;font-weight:750;line-height:34px;text-align:center;vertical-align:middle;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0 0 0 10px;padding:10px 13px;border-radius:15px 15px 15px 3px;background-color:{sky_pale};color:{ink};font-size:14px;font-weight:650;line-height:1.68;vertical-align:middle;">{_inline(item)}</p>'
                    f'</section>'
                )
            return (
                f'<section style="margin:27px 0;padding:16px 13px 8px;border-top:1px solid {sky};border-bottom:1px solid {sky};">'
                f'<p style="margin:0 0 14px;color:{primary};font-size:9px;font-weight:800;letter-spacing:.16em;">FLOW / 让行动自然发生 <span style="color:{accent};">→</span></p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "process_register":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="border-top:1px solid #B7C5C0;white-space:normal;">'
                    f'<span style="display:inline-block;width:52px;padding:13px 7px;color:{primary};font-family:Georgia,serif;font-size:13px;font-weight:750;vertical-align:top;">P-{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:69%;margin:0;padding:12px 10px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;font-weight:650;line-height:1.68;vertical-align:top;">{_inline(item)}</p>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:14%;padding:15px 5px;color:{accent};font-size:8px;font-weight:800;text-align:right;vertical-align:top;">NEXT</span>'
                    f'</section>'
                )
            return (
                f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};">'
                f'<p style="margin:0;padding:8px 10px;background-color:{primary};color:#FFFFFF;font-size:8px;font-weight:800;letter-spacing:.16em;">PROCESS REGISTER / {len(items):02d} STEPS</p>'
                f'{"".join(rows)}</section>'
            )
        if variant == "folded_stair":
            rows = []
            stair_colors = (secondary, "#E98768", "#5FA99E", sky, primary)
            count = max(1, len(items))
            for index, item in enumerate(items, 1):
                progress = 1 if count == 1 else (index - 1) / (count - 1)
                width = round(68 + 32 * progress)
                margin = 100 - width
                background = stair_colors[(index - 1) % len(stair_colors)]
                number_color = ink if index == 1 else "#FFFFFF"
                rows.append(
                    f'<section style="box-sizing:border-box;width:{width}%;min-height:58px;margin:0 0 8px {margin}%;padding:11px 12px;background-color:{background};white-space:normal;">'
                    f'<span style="display:inline-block;width:36px;color:{number_color};font-family:Georgia,serif;font-size:16px;font-weight:750;line-height:1.5;opacity:.76;vertical-align:top;">{index:02d}</span>'
                    f'<strong style="display:inline-block;width:78%;color:{ink};font-size:13px;line-height:1.6;vertical-align:top;">{_inline(item)}</strong>'
                    f'</section>'
                )
            return (
                f'<section style="margin:28px 0;padding:19px 16px 16px;border:1px solid #C9C4B9;background-color:#F7F0E3;">'
                f'<p style="margin:0 0 7px;color:{accent};font-size:8px;font-weight:750;letter-spacing:.15em;">BACKCASTING / {len(items):02d}</p>'
                f'<p style="margin:0 0 18px;padding-bottom:12px;border-bottom:1px solid #CFC9BD;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:19px;font-weight:750;line-height:1.55;">从终点出发，<br>倒推今天的行动。</p>'
                f'{"".join(rows)}</section>'
            )
        route_colors = (
            (accent, accent_pale, "#FFFFFF"),
            (secondary, secondary_pale, ink),
            (primary, pale, "#FFFFFF"),
            (sky, sky_pale, "#FFFFFF"),
        )
        rows = []
        for index, item in enumerate(items, 1):
            node_accent, node_pale, node_text = route_colors[(index - 1) % len(route_colors)]
            rows.append(
                '<section style="margin:0 0 12px;white-space:normal;">'
                f'<span style="display:inline-block;width:40px;height:40px;border:2px solid {surface};border-radius:50%;background-color:{node_accent};box-shadow:0 0 0 2px {node_pale};color:{node_text};font-size:12px;font-weight:750;line-height:40px;text-align:center;vertical-align:middle;">{index:02d}</span>'
                f'<section style="box-sizing:border-box;display:inline-block;width:80%;margin-left:10px;padding:13px 15px;border:1px solid {node_accent};border-radius:3px 15px 15px 15px;background-color:{node_pale};vertical-align:middle;">'
                f'<p style="margin:0;color:{ink};font-size:15px;font-weight:700;line-height:1.65;">{_inline(item)}</p></section></section>'
            )
        return (
            '<section style="margin:28px 0;">'
            f'<p style="margin:0 0 13px;color:{primary};font-size:11px;font-weight:750;letter-spacing:.12em;">'
            f'<span style="display:inline-block;width:18px;height:3px;margin:0 7px 2px 0;background-color:{secondary};vertical-align:middle;"></span>从终点出发 · 反向规划学习路线</p>'
            f'{"".join(rows)}</section>'
        )

    if component_type == "concept_explainer":
        title = _inline(_one(parsed, bindings, "title"))
        definition = _inline(_one(parsed, bindings, "definition"))
        if variant == "plain_definition":
            return f'<section style="margin:25px 0;padding:16px;border-left:4px solid {primary};background-color:{pale};"><strong style="color:{primary};">{title}</strong><p style="margin:8px 0 0;line-height:1.8;">{definition}</p></section>'
        return (
            '<section style="margin:28px 0;">'
            f'<p style="margin:0 0 -1px 14px;"><span style="display:inline-block;padding:6px 12px;border-radius:12px 12px 0 0;background-color:{primary};color:#FFFFFF;font-size:10px;font-weight:750;letter-spacing:.12em;">CONCEPT / 概念</span></p>'
            f'<section style="padding:18px 18px 19px;border:1px solid {primary};border-radius:4px 16px 16px 16px;background-color:{pale};box-shadow:5px 5px 0 {secondary_pale};">'
            f'<p style="margin:0 0 9px;color:{primary};font-size:17px;font-weight:750;line-height:1.55;">{title}</p>'
            f'<p style="margin:0;color:#3D4845;font-size:16px;line-height:1.85;">{definition}</p></section></section>'
        )

    if component_type == "case_card":
        title = _inline(_one(parsed, bindings, "title"))
        body = _inline(_one(parsed, bindings, "body"))
        if variant == "plain_case":
            return f'<section style="margin:25px 0;padding:16px;border-left:4px solid {primary};background-color:{surface};"><strong style="color:{primary};">案例｜{title}</strong><p style="margin:8px 0 0;color:{ink};font-size:15px;line-height:1.8;">{body}</p></section>'
        return (
            f'<section style="margin:30px 0;padding:0 18px 18px;border:1px solid {primary};border-radius:3px 18px 18px 18px;background-color:{surface};box-shadow:6px 6px 0 {secondary_pale};">'
            f'<p style="display:inline-block;margin:-1px 0 14px;padding:6px 12px;background-color:{accent};color:#FFFFFF;font-size:9px;font-weight:750;letter-spacing:.16em;">CASE FILE</p>'
            f'<p style="margin:0 0 9px;color:{primary};font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;font-weight:750;line-height:1.55;">{title}</p>'
            f'<p style="margin:0;padding-top:11px;border-top:1px dashed {secondary};color:{ink};font-size:15px;line-height:1.85;">{body}</p></section>'
        )

    if component_type == "warning_note":
        body = _inline(_one(parsed, bindings, "body"))
        if variant == "plain_warning":
            return f'<p style="margin:24px 0;padding:13px 15px;border-left:4px solid {accent};background-color:{accent_pale};color:{ink};font-size:15px;line-height:1.75;"><strong>注意：</strong>{body}</p>'
        return (
            f'<section style="margin:28px 0;padding:16px 17px;border:1px solid {accent};border-radius:14px 3px 14px 3px;background-color:{accent_pale};">'
            f'<p style="margin:-25px 0 12px;"><span style="display:inline-block;padding:6px 13px;background-color:{secondary};color:{ink};font-size:9px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">RISK CHECK</span></p>'
            f'<p style="margin:0;color:{ink};font-size:15px;font-weight:650;line-height:1.8;">{body}</p></section>'
        )

    if component_type == "action_checklist":
        items = _many(parsed, bindings, "items")
        if variant == "plain_checklist":
            rows = [f'<p style="margin:0 0 10px;color:{ink};font-size:15px;line-height:1.75;">□ {_inline(item)}</p>' for item in items]
            return f'<section style="margin:24px 0;padding:15px;border-left:3px solid {primary};background-color:{pale};">{"".join(rows)}</section>'
        if variant == "soft_tick_list":
            rows = []
            for item in items:
                rows.append(
                    f'<section style="margin:0 0 9px;padding:11px 13px;border-radius:15px 15px 15px 4px;background-color:{pale};white-space:normal;">'
                    f'<span style="display:inline-block;width:23px;height:23px;border-radius:50%;background-color:{primary};color:#FFFFFF;font-size:12px;font-weight:800;line-height:23px;text-align:center;vertical-align:top;">✓</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;padding-left:10px;color:{ink};font-size:14px;line-height:1.7;vertical-align:top;">{_inline(item)}</p></section>'
                )
            return f'<section style="margin:27px 0;"><p style="margin:0 0 12px;color:{primary};font-size:9px;font-weight:800;letter-spacing:.15em;">READY WHEN YOU ARE · 行动清单</p>{"".join(rows)}</section>'
        if variant == "proofing_checklist":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="padding:11px 0;border-top:1px solid #CFCAC0;white-space:normal;">'
                    f'<span style="display:inline-block;width:42px;color:{accent};font-family:Georgia,serif;font-size:17px;font-weight:750;vertical-align:top;">{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:76%;margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:14px;font-weight:650;line-height:1.72;vertical-align:top;">{_inline(item)}</p>'
                    f'<span style="display:inline-block;width:20px;height:20px;border:1px solid {ink};font-size:0;vertical-align:top;"></span></section>'
                )
            return (
                f'<section style="margin:27px 0;padding:16px 16px 5px;border-top:4px solid {ink};border-bottom:1px solid {ink};background-color:#FBF6EC;">'
                f'<p style="margin:0 0 14px;color:{accent};font-size:8px;font-weight:800;letter-spacing:.18em;">PROOF DESK / FINAL CHECK</p>{"".join(rows)}</section>'
            )
        if variant == "audit_matrix":
            rows = []
            for index, item in enumerate(items, 1):
                rows.append(
                    f'<section style="border-top:1px solid #B7C5C0;white-space:normal;">'
                    f'<span style="display:inline-block;width:46px;padding:12px 7px;color:{primary};font-family:Georgia,serif;font-size:12px;font-weight:750;vertical-align:top;">A{index:02d}</span>'
                    f'<p style="box-sizing:border-box;display:inline-block;width:68%;margin:0;padding:11px 10px;border-left:1px solid #B7C5C0;color:{ink};font-size:14px;line-height:1.7;vertical-align:top;">{_inline(item)}</p>'
                    f'<span style="box-sizing:border-box;display:inline-block;width:17%;padding:13px 5px;color:{accent};font-size:8px;font-weight:800;text-align:right;vertical-align:top;">TO VERIFY</span></section>'
                )
            return f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};"><p style="margin:0;padding:8px 10px;background-color:{primary};color:#FFFFFF;font-size:8px;font-weight:800;letter-spacing:.16em;">ACTION AUDIT MATRIX</p>{"".join(rows)}</section>'
        rows = []
        for index, item in enumerate(items, 1):
            rows.append(
                f'<section style="margin:0;padding:11px 0;border-bottom:1px dashed #D8D2C6;white-space:normal;">'
                f'<span style="display:inline-block;width:24px;height:24px;border:1px solid {primary};border-radius:4px;color:{primary};font-size:10px;font-weight:750;line-height:24px;text-align:center;vertical-align:top;">{index:02d}</span>'
                f'<p style="display:inline-block;width:84%;margin:0 0 0 11px;color:{ink};font-size:15px;line-height:1.7;vertical-align:top;">{_inline(item)}</p></section>'
            )
        return f'<section style="margin:28px 0;padding:17px 17px 7px;border:1px solid {primary};background-color:{surface};"><p style="margin:0 0 7px;color:{accent};font-size:9px;font-weight:800;letter-spacing:.16em;">ACTION CHECKLIST / 行动清单</p>{"".join(rows)}</section>'

    if component_type == "faq_card":
        question = _inline(_one(parsed, bindings, "question"))
        answer = _inline(_one(parsed, bindings, "answer"))
        if variant == "plain_qa":
            return f'<section style="margin:25px 0;"><p style="margin:0 0 8px;color:{primary};font-size:17px;font-weight:750;">Q：{question}</p><p style="margin:0;color:{ink};font-size:15px;line-height:1.8;">A：{answer}</p></section>'
        if variant == "conversation_bubble":
            return (
                f'<section style="margin:27px 0;">'
                f'<section style="width:84%;margin:0 0 10px;padding:12px 15px;border-radius:18px 18px 18px 4px;background-color:{sky_pale};">'
                f'<p style="margin:0;color:{primary};font-size:15px;font-weight:750;line-height:1.7;"><span style="margin-right:7px;color:{sky};font-family:Georgia,serif;">Q</span>{question}</p></section>'
                f'<section style="width:84%;margin-left:8%;padding:13px 15px;border-radius:18px 4px 18px 18px;background-color:{pale};box-shadow:4px 4px 0 {secondary_pale};">'
                f'<p style="margin:0;color:{ink};font-size:15px;line-height:1.8;"><strong style="margin-right:7px;color:{accent};font-family:Georgia,serif;">A</strong>{answer}</p></section></section>'
            )
        if variant == "advice_letter":
            return (
                f'<section style="margin:29px 0;padding:0 17px 18px;border:1px solid #E2CEB1;border-radius:3px 18px 4px 18px;background-color:#FFF8EC;box-shadow:5px 5px 0 {accent_pale};">'
                f'<p style="display:inline-block;margin:-1px 0 14px;padding:5px 11px;background-color:{accent};color:#FFFFFF;font-size:8px;font-weight:800;letter-spacing:.15em;">REPLY LETTER</p>'
                f'<p style="margin:0 0 12px;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:750;line-height:1.68;">来信：{question}</p>'
                f'<p style="margin:0;padding-top:12px;border-top:1px dashed #D7C3A6;color:#4A514D;font-size:15px;line-height:1.84;">回信：{answer}</p></section>'
            )
        if variant == "qa_register":
            return (
                f'<section style="margin:27px 0;border:1px solid {primary};background-color:{surface};">'
                f'<p style="margin:0;padding:7px 10px;background-color:{primary};color:#FFFFFF;font-size:8px;font-weight:800;letter-spacing:.16em;">Q&A REGISTER / ENTRY 01</p>'
                f'<section style="padding:13px 14px;border-bottom:1px solid #B7C5C0;white-space:normal;"><span style="display:inline-block;width:35px;color:{accent};font-family:Georgia,serif;font-size:18px;font-weight:750;vertical-align:top;">Q</span><p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;color:{ink};font-size:15px;font-weight:750;line-height:1.68;vertical-align:top;">{question}</p></section>'
                f'<section style="padding:13px 14px 15px;white-space:normal;"><span style="display:inline-block;width:35px;color:{primary};font-family:Georgia,serif;font-size:18px;font-weight:750;vertical-align:top;">A</span><p style="box-sizing:border-box;display:inline-block;width:86%;margin:0;color:{ink};font-size:14px;line-height:1.82;vertical-align:top;">{answer}</p></section></section>'
            )
        return (
            f'<section style="margin:28px 0;padding:17px 0 15px;border-top:4px solid {ink};border-bottom:1px solid {ink};background-color:#FBF6EC;">'
            f'<section style="padding:0 15px 15px;white-space:normal;">'
            f'<span style="display:inline-block;width:50px;color:{accent};font-family:Georgia,serif;font-size:28px;font-weight:750;line-height:1;vertical-align:top;">Q/</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;color:{ink};font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:750;line-height:1.68;vertical-align:top;">{question}</p></section>'
            f'<section style="padding:14px 15px 0;border-top:1px solid #CFCAC0;white-space:normal;">'
            f'<span style="display:inline-block;width:50px;color:{primary};font-family:Georgia,serif;font-size:20px;font-weight:750;line-height:1.2;vertical-align:top;">A/</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:82%;margin:0;color:{ink};font-size:14px;line-height:1.84;vertical-align:top;">{answer}</p></section></section>'
        )

    if component_type == "comparison_card":
        left = _inline(_one(parsed, bindings, "left"))
        right = _inline(_one(parsed, bindings, "right"))
        if variant == "plain_comparison":
            return f'<section style="margin:25px 0;"><p style="margin:0 0 9px;padding:12px;background-color:{accent_pale};line-height:1.75;"><strong>一：</strong>{left}</p><p style="margin:0;padding:12px;background-color:{pale};line-height:1.75;"><strong>二：</strong>{right}</p></section>'
        return (
            f'<section style="margin:28px 0;padding:16px;border:1px solid #D8D3C8;background-color:{surface};white-space:normal;">'
            f'<p style="margin:0 0 13px;color:{primary};font-size:9px;font-weight:800;letter-spacing:.16em;">SIDE BY SIDE / 对比</p>'
            f'<section style="box-sizing:border-box;display:inline-block;width:48%;padding:14px;border-top:4px solid {accent};background-color:{accent_pale};vertical-align:top;"><p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{left}</p></section>'
            f'<section style="box-sizing:border-box;display:inline-block;width:48%;margin-left:4%;padding:14px;border-top:4px solid {primary};background-color:{pale};vertical-align:top;"><p style="margin:0;color:{ink};font-size:14px;line-height:1.75;">{right}</p></section></section>'
        )

    if component_type == "section_summary":
        items = _many(parsed, bindings, "items")
        if variant == "plain_summary":
            return _plain_list(items, primary)
        rows = []
        for item in items:
            rows.append(f'<p style="margin:0 0 9px;color:{ink};font-size:15px;line-height:1.7;"><span style="color:{accent};font-weight:800;">—</span> {_inline(item)}</p>')
        return (
            f'<section style="margin:30px 0;padding:18px 19px;border-top:4px solid {primary};background-color:{pale};">'
            f'<p style="margin:0 0 12px;color:{primary};font-family:Georgia,serif;font-size:11px;font-weight:800;letter-spacing:.16em;">CHAPTER TAKEAWAY</p>'
            f'{"".join(rows)}</section>'
        )

    raise ValueError(f"没有组件渲染器：{component_type}.{variant}")
