"""Workbench and offline review share viewport, padding and font profiles.

This is a local preview contract, not a claim to emulate WeChat sanitization.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

PREVIEW_CONFIG = json.loads(Path(__file__).with_name("preview_profiles.json").read_text(encoding="utf-8"))
BODY_PADDING_X = PREVIEW_CONFIG["body_padding_x"]
REVIEW_PROFILES = tuple(dict(p, content_width=p["viewport_width"] - 2 * BODY_PADDING_X)
                        for p in PREVIEW_CONFIG["profiles"])


def preview_css() -> str:
    return PREVIEW_CONFIG["normalization_css"] + PREVIEW_CONFIG["mobile_css"]


def scale_preview_fonts(markup: str, profile: dict) -> str:
    """Match the workbench's inline-pixel font adjustment, only on preview HTML."""
    scale = profile["font_scale"]
    if scale == 1:
        return markup

    def style(match: re.Match) -> str:
        value = re.sub(r"font-size\s*:\s*([0-9.]+)px", lambda m: f"font-size:{math.floor(float(m[1]) * scale * 100 + .5) / 100:g}px", match[0])
        return value

    return re.sub(r'style="[^"]*"', style, markup)
