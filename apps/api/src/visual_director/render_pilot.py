"""Process-local switches for the isolated, compatibility-first render pilot."""

from __future__ import annotations

import os


def renderer_pilot_enabled() -> bool:
    return os.environ.get("WVD_RENDERER_PILOT") == "1"


def logic_path_pilot_enabled() -> bool:
    # Keep the original review launcher working without opting it into new roles.
    return renderer_pilot_enabled() or os.environ.get("WVD_LOGIC_PATH_PILOT") == "1"


def reading_rules_pilot_enabled() -> bool:
    """Keep intentional visual changes separate from compatibility proofs."""
    return renderer_pilot_enabled() and os.environ.get("WVD_READING_RULES_PILOT") == "1"
