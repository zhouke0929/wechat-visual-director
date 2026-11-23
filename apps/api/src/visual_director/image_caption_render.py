"""Carry approved caption typography from preview to late-bound image assets."""
from __future__ import annotations

import html
import json
import re

from .reading_rules import CAPTION, ReadingProfile, authored_metrics, restore_authored_metrics


def caption_metrics_attribute(profile: ReadingProfile | None) -> str:
    values = authored_metrics(CAPTION, profile)
    if not values:
        return ""
    encoded = html.escape(json.dumps(values, separators=(",", ":")), quote=True)
    return f' data-image-caption-metrics="{encoded}"'


def stored_caption_profile(placeholder: str) -> ReadingProfile | None:
    match = re.search(r'\bdata-image-caption-metrics="([^"]*)"', placeholder)
    if not match:
        return None
    metrics = json.loads(html.unescape(match[1]))
    if not isinstance(metrics, dict):
        raise ValueError("Invalid image caption metrics")
    return restore_authored_metrics(CAPTION, metrics)
