"""Process-local rollout policy; structural binding and visual tuning are separate."""

from __future__ import annotations

import os
from typing import Literal


def _structure_mode() -> Literal["structured", "legacy", "steps_only"]:
    override = os.environ.get("WVD_RENDERER_PILOT")
    if override is not None:
        # Preserve explicit 1; 0 is a full rollback even with stale trial flags.
        return "structured" if override == "1" else "legacy"
    if os.environ.get("WVD_LOGIC_PATH_PILOT") == "1":
        # A pre-rollout review launcher explicitly requested *only* step anchors.
        return "steps_only"
    return "structured"


def renderer_pilot_enabled() -> bool:
    return _structure_mode() == "structured"


def logic_path_pilot_enabled() -> bool:
    return _structure_mode() != "legacy"


def current_theme_styles_enabled() -> bool:
    """Keep current theme styling independent of list binding; preserve full v1 rollback."""
    return _structure_mode() != "legacy"


def reading_rules_pilot_enabled() -> bool:
    """Keep intentional visual changes separate from compatibility proofs."""
    return renderer_pilot_enabled() and os.environ.get("WVD_READING_RULES_PILOT") == "1"
