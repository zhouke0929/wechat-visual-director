from __future__ import annotations

import html
import re
from typing import Any

from .foundation_inline import _inline, _body_inline
from .generated_theme import render_generated_hero, render_generated_paragraph, render_generated_quote
from .theme_extensions import render_extended_lead, render_extended_quote, render_extended_hero
from .reading_rules import (ARTICLE_TITLE, BODY, LABEL, LEAD, QUOTE, REFERENCE, SOURCE, ReadingProfile, authored_emphasis, authored_host_css, render_authored_text)


def native_family(config: dict[str, Any]) -> str:
    if config.get("generated_design_system"):
        return "generated"
    variant = config["heading_variant"]
    if variant in {"editorial_left_rule", "masthead_section"}:
        return "editorial"
    if variant == "story_chapter":
        return "warm"
    if variant == "botanical_section":
        return "airy"
    if variant == "indexed_column":
        return "structured"
    if variant == "sticker_section":
        return "campus"
    if variant == "signal_section":
        return "future"
    return "neutral"


def render_lead(content: str, label: str, config: dict[str, Any], family: str, reading: ReadingProfile | None) -> str:
    if family == "generated":
        return render_generated_paragraph(content, config, lead=True, reading=reading)
    accent = config["accent"]
    palette = config.get("palette", {"primary": accent})
    text = render_authored_text(_body_inline(content, config), LEAD, reading)
    extended_lead = render_extended_lead(content, label, config, reading=reading)
    if extended_lead is not None:
        return extended_lead
    elif family == "airy":
        return (
            f'<section data-content-role="lead" data-lead-kind="{html.escape(label)}" '
            f'style="margin:24px 0 30px;padding:4px 0 13px 15px;border-left:3px solid {accent};border-bottom:1px solid {palette.get("sky", accent)};">'
            f'<p style="margin:0 0 7px;color:{accent};font-size:10px;font-weight:700;letter-spacing:.14em;">{html.escape(label)}</p>'
            f'<p style="margin:0;color:#17312D;font-size:17px;font-weight:650;line-height:1.78;">{text}</p>'
            f'<p style="margin:9px 0 -18px;text-align:right;"><span style="display:inline-block;width:14px;height:8px;border-radius:12px 2px 12px 2px;background-color:{palette.get("secondary", accent)};transform:rotate(-14deg);"></span></p></section>'
        )
    elif family == "structured":
        return (
            f'<section data-content-role="lead" data-lead-kind="{html.escape(label)}" '
            f'style="margin:24px 0 30px;border-top:4px solid {accent};border-bottom:1px solid #B9C3BE;white-space:normal;">'
            f'<span style="display:inline-block;width:23%;padding:15px 8px 12px 0;color:{palette.get("secondary", accent)};font-family:Georgia,serif;font-size:9px;font-weight:800;letter-spacing:.12em;vertical-align:top;">LEAD</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:77%;margin:0;padding:13px 0 14px 15px;border-left:1px solid #B9C3BE;color:#24302E;font-size:16px;font-weight:650;line-height:1.8;vertical-align:top;">{text}</p></section>'
        )
    elif family == "warm":
        return (
            f'<section data-content-role="lead" data-lead-kind="{html.escape(label)}" '
            f'style="margin:25px 0 31px;padding:4px 0 14px 17px;border-left:5px solid {palette.get("secondary", accent)};border-bottom:1px solid #D7B995;">'
            f'<p style="margin:-9px 0 10px -25px;"><span style="display:inline-block;padding:5px 10px;background-color:{palette.get("accent_pale", "#FBE9E2")};color:{accent};font-size:10px;font-weight:800;letter-spacing:.12em;transform:rotate(-2deg);">{html.escape(label)}</span></p>'
            f'<p style="margin:0;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:650;line-height:1.84;">{text}</p>'
            f'<p style="margin:9px 0 -20px;text-align:right;"><span style="display:inline-block;width:52px;height:10px;background-color:{palette.get("secondary", accent)};opacity:.72;transform:rotate(-3deg);"></span></p></section>'
        )
    elif family == "campus":
        return (
            f'<section data-content-role="lead" data-lead-kind="{html.escape(label)}" '
            f'style="margin:26px 0 32px;padding:18px 17px 16px 27px;border-left:10px dotted {palette.get("sky", accent)};background-color:{palette.get("surface", "#FFFEFB")};box-shadow:7px 7px 0 {palette.get("secondary_pale", "#FFF6D9")};">'
            f'<p style="margin:-25px 0 15px;"><span style="display:inline-block;padding:5px 11px;background-color:{palette.get("secondary", accent)};color:{palette.get("ink", "#20304A")};font-size:9px;font-weight:800;letter-spacing:.14em;transform:rotate(-2deg);">{html.escape(label)}</span></p>'
            f'<p style="margin:0;color:{palette.get("ink", "#20304A")};font-size:17px;font-weight:680;line-height:1.82;">{text}</p></section>'
        )
    elif family == "future":
        lead_label = label
        lead_cue = (
            f'<section style="margin:0 0 10px;"><span style="display:block;width:24px;border-bottom:2px solid {palette.get("accent", accent)};"></span></section>'
            if config.get("theme_kit") == "future_science_editorial_v1" and lead_label == "本文导读" else
            f'<p style="margin:0 0 10px;color:{palette.get("accent", accent)};font-size:10px;font-weight:800;letter-spacing:.1em;">{html.escape(lead_label)}</p>'
        )
        return (
            f'<section data-content-role="lead" data-lead-kind="{html.escape(lead_label)}" '
            f'style="margin:28px 0 34px;padding:18px 19px 17px;border-radius:4px 38px 4px 22px;background:linear-gradient(135deg,{palette.get("secondary_pale", "#EAF9F6")},{palette.get("pale", "#F3F5FC")});box-shadow:6px 6px 0 {palette.get("sky_pale", "#EEF1FA")};">'
            f'{lead_cue}'
            f'<p style="margin:0;color:{palette.get("ink", "#24304F")};font-size:17px;font-weight:680;line-height:1.82;">{text}</p>'
            f'<p style="margin:10px 0 -22px;text-align:right;"><span style="display:inline-block;width:45px;height:8px;border-radius:14px 3px 14px 3px;background-color:{palette.get("secondary", accent)};transform:rotate(-5deg);"></span></p></section>'
        )
    elif family == "editorial":
        return (
            f'<section data-content-role="lead" data-lead-kind="{html.escape(label)}" '
            f'style="margin:24px 0 31px;border-top:10px solid #202B33;border-bottom:3px solid #202B33;white-space:normal;">'
            f'<span style="display:inline-block;width:22%;padding:15px 7px 13px 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.12em;vertical-align:top;">DECK</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:78%;margin:0;padding:13px 0 15px 16px;border-left:6px solid {accent};color:#202B33;font-size:17px;font-weight:750;line-height:1.78;vertical-align:top;">{text}</p></section>'
        )
    else:
        return (
            f'<section data-content-role="lead" data-lead-kind="{html.escape(label)}" '
            f'style="margin:22px 0 28px;padding:18px 18px 17px;background-color:#EDF7F4;border-top:3px solid {accent};">'
            f'<p style="margin:0 0 7px;color:#4E615E;font-size:11px;font-weight:700;letter-spacing:.14em;">{html.escape(label)}</p>'
            f'<p style="margin:0;color:#17312D;font-size:17px;font-weight:650;line-height:1.75;">{text}</p></section>'
        )


def render_quote(content: str, config: dict[str, Any], family: str, reading: ReadingProfile | None) -> str:
    accent = config["accent"]
    palette = config.get("palette", {"primary": accent})
    text = render_authored_text(_body_inline(content, config), QUOTE, reading)
    generated_quote = render_generated_quote(content, config, reading=reading)
    extended_quote = render_extended_quote(content, config, reading=reading)
    if generated_quote is not None:
        return generated_quote
    elif extended_quote is not None:
        return extended_quote
    elif config.get("quote_variant") == "floating_quote":
        return (
            f'<blockquote style="margin:31px 3px 34px;padding:0 8px 13px 0;border-bottom:1px solid {palette.get("sky", accent)};white-space:normal;">'
            f'<span style="display:inline-block;width:46px;margin-top:-7px;color:{palette.get("secondary", accent)};font-family:Georgia,serif;font-size:72px;font-weight:700;line-height:.72;vertical-align:top;">“</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:82%;padding:4px 0 0 4px;color:#1F2B29;font-family:Georgia,\'Noto Serif SC\',serif;font-size:18px;font-weight:650;line-height:1.9;vertical-align:top;">{text}</span>'
            f'</blockquote>'
        )
    elif config.get("quote_variant") == "evidence_margin":
        return (
            f'<blockquote style="margin:30px 0;padding:4px 0;border-top:1px solid #AEBBB5;border-bottom:1px solid #AEBBB5;white-space:normal;">'
            f'<span style="display:inline-block;width:23%;padding:17px 8px 13px 0;color:{accent};font-family:Georgia,serif;font-size:9px;font-weight:800;letter-spacing:.14em;vertical-align:top;">QUOTE<br>REF</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:77%;padding:15px 0 15px 16px;border-left:4px solid {accent};color:#1F2B29;font-size:17px;font-weight:700;line-height:1.85;vertical-align:top;">{text}</span></blockquote>'
        )
    elif config.get("quote_variant") == "postcard_quote":
        return (
            f'<blockquote style="margin:33px 4px 32px;padding:0 0 15px;border-bottom:1px solid #D7B995;white-space:normal;">'
            f'<span style="display:inline-block;width:19%;margin-top:-11px;color:{palette.get("accent_pale", "#FBE9E2")};font-family:Georgia,serif;font-size:76px;font-weight:700;line-height:.75;vertical-align:top;">“</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:81%;padding:8px 13px 13px 17px;border-left:3px solid {palette.get("accent", accent)};background-color:#FFF9EF;box-shadow:7px 7px 0 {palette.get("secondary_pale", "#FBF2D8")};color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:17px;font-weight:650;line-height:1.9;vertical-align:top;">{text}</span>'
            f'</blockquote>'
        )
    elif config.get("quote_variant") == "pull_quote":
        return (
            f'<blockquote style="margin:33px 0;padding:8px 0 13px;border-top:11px solid #202B33;border-bottom:3px solid #202B33;white-space:normal;">'
            f'<span style="display:inline-block;width:23%;padding:7px 8px 0 0;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:50px;font-weight:800;line-height:.8;vertical-align:top;">“</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:77%;padding:9px 0 11px 16px;border-left:6px solid {accent};color:#202B33;font-family:Georgia,\'Noto Serif SC\',serif;font-size:19px;font-weight:800;line-height:1.78;vertical-align:top;">{text}</span>'
            f'</blockquote>'
        )
    elif config.get("quote_variant") == "campus_quote" and config.get("theme_kit") == "campus_bulletin_v2":
        return (
            f'<blockquote data-theme-grammar="campus-radio-quote" style="margin:27px 0;padding:0 6px 13px 0;border-bottom:2px dashed {palette.get("sky", accent)};">'
            f'<section style="margin:0 0 -4px 10px;font-size:9px;line-height:1.3;">'
            f'<span data-theme-static="true" style="display:inline-block;margin:0;padding:4px 8px;background-color:{palette.get("accent", accent)};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.12em;line-height:1.3;transform:rotate(-3deg);">CAMPUS RADIO</span>'
            f'</section><p style="margin:0 0 0 6px;padding:11px 14px 9px;background-color:{palette.get("secondary_pale", "#FFF6D9")};box-shadow:6px 6px 0 {palette.get("sky_pale", "#EEF4FF")};color:{palette.get("ink", "#20304A")};font-size:17px;font-weight:700;line-height:1.85;overflow-wrap:anywhere;">{text}</p></blockquote>'
        )
    elif config.get("quote_variant") == "campus_quote":
        return (
            f'<blockquote style="margin:32px 0;padding:7px 0 17px;border-bottom:2px dashed {palette.get("sky", accent)};white-space:normal;">'
            f'<span style="box-sizing:border-box;display:inline-block;width:65px;margin-left:4px;padding:14px 5px;background-color:{palette.get("accent", accent)};color:#FFFFFF;font-size:9px;font-weight:800;letter-spacing:.12em;text-align:center;transform:rotate(-3deg);vertical-align:top;">CAMPUS<br>RADIO</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:79%;margin-left:3%;padding:15px 16px;background-color:{palette.get("secondary_pale", "#FFF6D9")};box-shadow:6px 6px 0 {palette.get("sky_pale", "#EEF4FF")};color:{palette.get("ink", "#20304A")};font-size:17px;font-weight:700;line-height:1.85;vertical-align:top;">{text}</span></blockquote>'
        )
    elif config.get("quote_variant") == "_legacy_campus_quote":
        return (
            f'<blockquote style="margin:31px 0;padding:6px 0 14px;border-bottom:2px solid {palette.get("sky", accent)};">'
            f'<p style="width:54px;height:11px;margin:0 0 -5px 13px;background-color:{palette.get("secondary", accent)};transform:rotate(-4deg);"></p>'
            f'<section style="padding:17px 18px;border:2px solid {accent};border-radius:5px 20px 20px 20px;background-color:{palette.get("surface", "#FFFEFB")};box-shadow:6px 6px 0 {palette.get("accent_pale", "#FFF0F5")};">'
            f'<span style="display:inline-block;width:34px;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:42px;font-weight:800;line-height:.8;vertical-align:top;">“</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:87%;color:{palette.get("ink", "#20304A")};font-size:17px;font-weight:700;line-height:1.85;vertical-align:top;">{text}</span>'
            f'</section></blockquote>'
        )
    elif config.get("quote_variant") == "signal_quote" and config.get("theme_kit") == "future_science_editorial_v1":
        return (
            f'<blockquote data-theme-grammar="signal-quotation" style="margin:29px 0;padding:8px 0 11px;border-bottom:2px solid {palette.get("accent_pale", "#FFF1EC")};">'
            f'<span style="display:inline-block;width:10%;color:{palette.get("primary", accent)};font:bold 39px/1 Georgia,serif;vertical-align:top;">“</span>'
            f'<p style="box-sizing:border-box;display:inline-block;width:90%;margin:0;padding-left:4px;color:{palette.get("ink", "#24304F")};font-size:17px;font-weight:700;line-height:1.78;vertical-align:top;">{text}</p></blockquote>'
        )
    elif config.get("quote_variant") == "signal_quote":
        return (
            f'<blockquote style="margin:34px 0;padding:2px 0 12px;white-space:normal;">'
            f'<span style="display:inline-block;width:17%;color:{palette.get("secondary", accent)};font-family:Georgia,serif;font-size:64px;font-weight:800;line-height:.72;vertical-align:top;">“</span>'
            f'<section style="box-sizing:border-box;display:inline-block;width:83%;padding:4px 0 12px 15px;border-bottom:5px solid {palette.get("accent_pale", "#FFF1EC")};vertical-align:top;">'
            f'<p style="margin:0 0 8px;color:{palette.get("accent", accent)};font-size:10px;font-weight:800;letter-spacing:.08em;">证据摘录</p>'
            f'<p style="margin:0;color:{palette.get("ink", "#24304F")};font-size:17px;font-weight:720;line-height:1.86;">{text}</p></section></blockquote>'
        )
    elif config.get("quote_variant") == "_legacy_signal_quote":
        return (
            f'<blockquote style="margin:31px 0;border-top:6px solid {accent};border-bottom:1px solid #B9D8D2;white-space:normal;">'
            f'<span style="display:inline-block;width:20%;padding:16px 7px;color:{palette.get("accent", accent)};font-family:Georgia,serif;font-size:10px;font-weight:800;letter-spacing:.12em;vertical-align:top;">QUOTE</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:80%;padding:15px 0 16px 15px;border-left:2px solid {palette.get("secondary", accent)};color:{palette.get("ink", "#17313D")};font-size:17px;font-weight:720;line-height:1.85;vertical-align:top;">{text}</span></blockquote>'
        )
    elif family == "editorial":
        return (
            f'<blockquote style="margin:30px 6px;padding:24px 12px;border-top:1px solid {accent};border-bottom:1px solid {accent};color:#1F2B29;font-family:Georgia,serif;font-size:20px;line-height:1.75;text-align:center;">{text}</blockquote>'
        )
    else:
        return (
            f'<blockquote style="margin:24px 0;padding:4px 0 4px 17px;border-left:4px solid {accent};color:#41514E;font-size:17px;line-height:1.75;">{text}</blockquote>'
        )


def render_hero(title: str, kicker: str, plan_name: str, version: str, config: dict[str, Any], family: str, reading: ReadingProfile | None) -> str:
    accent = config["accent"]
    palette = config.get("palette", {"primary": accent})
    text = render_authored_text(_inline(title), ARTICLE_TITLE, reading)
    kicker_html = render_authored_text(html.escape(kicker), LABEL, reading)
    generated_hero = render_generated_hero(title, kicker, config, reading=reading)
    extended_hero = render_extended_hero(
        title,
        plan_name,
        version,
        kicker,
        config, reading=reading,
    )
    if generated_hero is not None:
        hero = generated_hero
    elif extended_hero is not None:
        hero = extended_hero
    elif family == "airy":
        hero = (
            f'<header data-content-role="article-metadata-preview" data-theme-grammar="airy-open-cover" style="padding:34px 0 24px;border-bottom:1px solid {palette.get("sky", accent)};">'
            f'<p style="margin:0 0 13px;color:{accent};font:700 10px/1.2 Arial;letter-spacing:.16em;">{kicker_html}</p>'
            f'<h1 style="margin:0;color:#111C1A;font-family:Georgia,\'Noto Serif SC\',serif;font-size:30px;line-height:1.38;font-weight:750;letter-spacing:-.02em;">{text}</h1>'
            f'<p style="margin:19px 0 -7px;white-space:nowrap;"><span style="display:inline-block;width:67%;border-top:1px dotted {palette.get("sky", accent)};vertical-align:middle;"></span><span style="display:inline-block;width:28px;height:14px;margin-left:11px;border-radius:20px 3px 20px 3px;background-color:{palette.get("secondary", accent)};transform:rotate(-12deg);vertical-align:middle;"></span><span style="display:inline-block;width:7px;height:7px;margin-left:7px;border-radius:50%;background-color:{palette.get("accent", accent)};vertical-align:middle;"></span></p>'
            "</header>"
        )
    elif family == "campus":
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:33px 8px 27px 0;">'
            f'<p style="margin:0 0 -8px 19px;"><span style="display:inline-block;padding:5px 12px;background-color:{palette.get("secondary", accent)};color:{palette.get("ink", "#20304A")};font:800 9px/1.2 Georgia,serif;letter-spacing:.14em;transform:rotate(-2deg);">CAMPUS BULLETIN</span></p>'
            f'<section style="padding:22px 18px 19px 28px;border-left:11px dotted {palette.get("sky", accent)};border-bottom:4px solid {accent};background-color:{palette.get("surface", "#FFFEFB")};box-shadow:8px 8px 0 {palette.get("secondary_pale", "#FFF6D9")};">'
            f'<p style="margin:0 0 12px;color:{palette.get("accent", accent)};font:800 9px/1.2 Georgia,serif;letter-spacing:.15em;">{kicker_html}</p>'
            f'<h1 style="margin:0;color:{palette.get("ink", "#20304A")};font-size:30px;line-height:1.38;font-weight:830;letter-spacing:-.02em;">{text}</h1>'
            f'<p style="margin:17px 0 0;border-top:2px dashed {palette.get("sky", accent)};"></p></section>'
            "</header>"
        )
    elif family == "future":
        hero = (
            f'<header data-content-role="article-metadata-preview" style="margin:30px 0 29px;padding:24px 20px 20px;border-left:6px solid {palette.get("primary", accent)};border-radius:0 62px 0 24px;background:linear-gradient(135deg,{palette.get("surface", "#FEFEFF")} 0%,{palette.get("pale", "#F3F5FC")} 48%,{palette.get("secondary_pale", "#EAF9F6")} 100%);box-shadow:8px 8px 0 {palette.get("sky_pale", "#EEF1FA")};">'
            f'<p style="margin:0 0 15px;color:{palette.get("primary", accent)};font:800 9px/1.2 Georgia,serif;letter-spacing:.18em;">FUTURE EDITION <span style="color:{palette.get("accent", accent)};">●</span></p>'
            f'<p style="margin:0 0 9px;color:{accent};font-size:10px;font-weight:750;letter-spacing:.1em;">{kicker_html}</p>'
            f'<h1 style="margin:0;color:{palette.get("ink", "#24304F")};font-size:29px;line-height:1.4;font-weight:830;letter-spacing:-.02em;">{text}</h1>'
            f'<p style="margin:18px 0 -28px;padding-top:11px;border-top:1px solid {palette.get("sky", accent)};text-align:right;"><span style="display:inline-block;width:58px;height:10px;border-radius:16px 3px 16px 3px;background-color:{palette.get("secondary", accent)};transform:rotate(-6deg);"></span><span style="display:inline-block;width:8px;height:8px;margin-left:8px;border-radius:50%;background-color:{palette.get("accent", accent)};"></span></p>'
            "</header>"
        )
    elif family == "warm":
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:33px 0 24px;border-left:6px solid {palette.get("secondary", accent)};border-bottom:1px solid #D7B995;">'
            f'<p style="margin:0 0 13px -7px;"><span style="display:inline-block;padding:5px 11px;background-color:{palette.get("accent_pale", "#FBE9E2")};color:{accent};font:800 10px/1.2 Georgia,serif;letter-spacing:.14em;transform:rotate(-2deg);">{kicker_html}</span></p>'
            f'<section style="padding-left:18px;"><h1 style="margin:0;color:#342B28;font-family:Georgia,\'Noto Serif SC\',serif;font-size:30px;line-height:1.4;font-weight:750;">{text}</h1>'
            f'<p style="width:58px;height:8px;margin:18px 0 -4px;background-color:{palette.get("secondary", accent)};opacity:.72;transform:rotate(-3deg);"></p></section>'
            f'<p style="margin:15px 0 -30px;text-align:right;"><span style="display:inline-block;width:56px;height:10px;background-color:{palette.get("secondary", accent)};opacity:.72;transform:rotate(-3deg);"></span><span style="display:inline-block;width:8px;height:8px;margin-left:8px;border-radius:50%;background-color:{palette.get("accent", accent)};"></span></p>'
            "</header>"
        )
    elif family == "editorial":
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:29px 0 23px;border-top:13px solid #202B33;border-bottom:4px solid #202B33;">'
            f'<p style="margin:0 0 11px;color:{palette.get("accent", accent)};font:800 10px/1.2 Georgia,serif;letter-spacing:.14em;">FEATURE<span style="display:inline-block;width:52px;height:7px;margin-left:11px;background-color:{accent};"></span></p>'
            f'<p style="margin:0 0 10px;color:{accent};font:800 10px/1.2 Arial;letter-spacing:.14em;">{kicker_html}</p>'
            f'<h1 style="margin:0;color:#202B33;font-size:31px;line-height:1.34;font-weight:850;letter-spacing:-.03em;">{text}</h1>'
            f'<p style="margin:17px 0 0;border-top:1px solid #202B33;text-align:right;"><span style="display:inline-block;width:32%;height:8px;background-color:{accent};"></span></p>'
            "</header>"
        )
    elif family == "structured":
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:30px 0 23px;border-top:8px solid {accent};border-bottom:1px solid #AEBBB5;">'
            f'<section style="white-space:normal;"><span style="display:inline-block;width:25%;color:{palette.get("secondary", accent)};font:800 10px/1.2 Georgia,serif;letter-spacing:.14em;vertical-align:top;">FEATURE</span>'
            f'<section style="box-sizing:border-box;display:inline-block;width:75%;padding-left:15px;border-left:1px solid #AEBBB5;vertical-align:top;">'
            f'<p style="margin:0 0 10px;color:{accent};font:700 10px/1.2 Arial;letter-spacing:.14em;">{kicker_html}</p>'
            f'<h1 style="margin:0;color:#111C1A;font-size:29px;line-height:1.38;font-weight:800;letter-spacing:-.02em;">{text}</h1></section></section>'
            f'<p style="margin:17px 0 0;border-top:1px solid #AEBBB5;text-align:right;"><span style="display:inline-block;width:18%;height:6px;background-color:{palette.get("secondary", accent)};"></span></p>'
            "</header>"
        )
    else:
        hero = (
            f'<header data-content-role="article-metadata-preview" style="padding:34px 0 22px;border-bottom:1px solid {accent};">'
            f'<p style="margin:0 0 13px;color:{accent};font:700 11px/1.2 Arial;letter-spacing:.16em;">{kicker_html}</p>'
            f'<h1 style="margin:0;color:#111C1A;font-family:Georgia,\'Noto Serif SC\',serif;font-size:{32 if family == "editorial" else 30}px;line-height:1.35;font-weight:750;letter-spacing:-.02em;">{text}</h1>'
            f'<p style="width:32%;height:3px;margin:18px 0 0;background-color:{palette.get("secondary", accent)};"></p>'
            "</header>"
        )
    hero = re.sub(r"<h1\b", '<h1 data-editor-title="true"', hero, count=1)
    return hero


REFERENCE_LINK_RE = re.compile(r"^\[([^\]]+)]\((https?://[^)]+)\)$", flags=re.IGNORECASE)


def _render_reference_list(items: list[str], config: dict[str, Any], *, reading: ReadingProfile | None = None) -> str:
    """Render citations as subdued metadata, never as steps or checklists."""
    palette = config.get("palette", {})
    primary = palette.get("primary", config["accent"])
    rows: list[str] = []
    for item in items:
        match = REFERENCE_LINK_RE.fullmatch(str(item).strip())
        if match:
            label = render_authored_text(html.escape(match.group(1).strip()), REFERENCE, reading)
            url = match.group(2).strip()
            domain_match = re.match(r"https?://([^/]+)", url, flags=re.IGNORECASE)
            domain = render_authored_text(html.escape(domain_match.group(1) if domain_match else url), REFERENCE, reading)
            content = (
                f'<span style="display:block;color:#4F5B58;font-size:12px;line-height:1.65;">{label}</span>'
                f'<span style="display:block;margin-top:2px;color:#929A97;font:400 9px/1.45 Arial;word-break:break-all;">{domain}</span>'
            )
        else:
            content = f'<span style="color:#4F5B58;font-size:12px;line-height:1.65;">{render_authored_text(_inline(str(item)), REFERENCE, reading)}</span>'
        rows.append(
            '<section data-content-role="reference-item" style="margin:0;padding:9px 0;border-bottom:1px solid #E3E7E4;white-space:normal;">'
            f'<span style="display:inline-block;width:5%;padding-top:7px;color:{primary};font-size:8px;vertical-align:top;">●</span>'
            f'<span style="box-sizing:border-box;display:inline-block;width:95%;vertical-align:top;">{content}</span></section>'
        )
    return (
        '<section data-content-role="reference-list" style="margin:18px 0 25px;padding:4px 0 0;">'
        f'{"".join(rows)}</section>'
    )


def render_paragraph(content: str, config: dict[str, Any], family: str, reading: ReadingProfile | None) -> str:
    if family == "generated":
        return render_generated_paragraph(content, config, reading=reading)
    css = authored_host_css("margin:0 0 18px;color:#34403E;font-size:16px;line-height:1.85;text-align:justify;", BODY, reading)
    return f'<p style="{css}">{authored_emphasis(_body_inline(content, config), reading)}</p>'


def render_source(content: str, reading: ReadingProfile | None) -> str:
    css = authored_host_css("margin:24px 0 12px;padding:10px 2px 0;border-top:1px solid #E1E4E1;color:#7A8381;font-size:12px;font-weight:400;line-height:1.65;", SOURCE, reading)
    return f'<p data-content-role="source" style="{css}">{authored_emphasis(_inline(content), reading)}</p>'
