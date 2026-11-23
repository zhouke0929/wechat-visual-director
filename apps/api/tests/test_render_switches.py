"""Default, rollback, and compatibility for process-local launcher switches."""

import pytest

from visual_director.render_pilot import (
    logic_path_pilot_enabled, reading_rules_pilot_enabled, renderer_pilot_enabled,
)


@pytest.mark.parametrize(("full", "steps", "reading", "expected"), [
    (None, None, None, (True, True, False)),   # ordinary install: contracts, release styling
    (None, "0", None, (True, True, False)),    # disabling an old trial does not opt out of contracts
    (None, None, "1", (True, True, True)),     # reading changes still require explicit opt-in
    (None, "1", "1", (False, True, False)),    # keep old logic-only review launchers scoped
    ("1", "1", None, (True, True, False)),     # explicit full trial supersedes logic-only
    ("1", None, "1", (True, True, True)),
    ("0", None, None, (False, False, False)),  # explicit rollback
    ("0", "1", "1", (False, False, False)),    # even when the host retained old preview flags
    ("typo", "1", "1", (False, False, False)),
])
def test_renderer_switch_precedence(monkeypatch, full, steps, reading, expected):
    for key, value in (("WVD_RENDERER_PILOT", full), ("WVD_LOGIC_PATH_PILOT", steps),
                       ("WVD_READING_RULES_PILOT", reading)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    assert (renderer_pilot_enabled(), logic_path_pilot_enabled(), reading_rules_pilot_enabled()) == expected
