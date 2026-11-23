"""Reading roles shared by article components, independent of theme geometry.

All authored fields, including list items and steps, retain their theme recipe
unless a reviewed override exists. Registering a role or enabling editing hooks
does not restyle a published theme.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from types import MappingProxyType
from typing import Any

from .reading_theme_overrides import THEME_READING_OVERRIDES
from .render_pilot import reading_rules_pilot_enabled


BODY = "body"
ARTICLE_TITLE = "article_title"
SECTION_TITLE = "section_title"
SUBHEADING = "subheading"
LEAD = "lead"
QUOTE = "quote"
LIST_BODY = "list_body"
STEP_BODY = "step_body"
STEP_TITLE = "step_title"
STEP_DETAIL = "step_detail"
TABLE_BODY = "table_body"
TABLE_HEADER = "table_header"
CAPTION = "caption"
SOURCE = "source"
REFERENCE = "reference"
BRAND_FOOTER = "brand_footer"
COMPONENT_TITLE = "component_title"
INLINE_EMPHASIS = "inline_emphasis"
MARKER = "marker"
LABEL = "label"


@dataclass(frozen=True, slots=True)
class TextRule:
    """Readability of a text field, not the decoration/layout around it.

    Before/after are outside the text box. Insets are inside it. For a
    split step, the title's after-gap is added to the following detail's
    inset instead of becoming a second, potentially collapsing margin.
    """
    size_px: float | None = None
    weight: int | None = None
    line_height: float | None = None
    after_px: float | None = None
    wrap: str | None = None
    letter_spacing_em: float | None = None
    before_px: float | None = None
    inset_before_px: float | None = None
    inset_after_px: float | None = None


DEFAULT_READING_RULES: Mapping[str, TextRule] = MappingProxyType({
    BODY: TextRule(16, 400, 1.8, 18, "anywhere", letter_spacing_em=0),
    ARTICLE_TITLE: TextRule(29, 750, 1.34, 24),
    SECTION_TITLE: TextRule(22, 700, 1.46, 12),
    SUBHEADING: TextRule(18, 700, 1.55, 8),
    STEP_TITLE: TextRule(16, 750, 1.5, 3, "anywhere"),
    TABLE_HEADER: TextRule(14, 700, 1.6),
    CAPTION: TextRule(13, 400, 1.6, 8),
    SOURCE: TextRule(12, 400, 1.65, 8),
    REFERENCE: TextRule(13, 400, 1.65, 6),
    BRAND_FOOTER: TextRule(13, 400, 1.65, 8),
    COMPONENT_TITLE: TextRule(17, 700, 1.55, 6),
    INLINE_EMPHASIS: TextRule(weight=700),
    MARKER: TextRule(12, 800, 1.2),
    LABEL: TextRule(11, 700, 1.35),
})

# These are prose, not four independent design decisions. A change to the one
# base rule flows across them unless a deliberate role-level override exists.
_BODY_ROLES = (BODY, LEAD, QUOTE, LIST_BODY, STEP_BODY, STEP_DETAIL, TABLE_BODY)
_INHERITS_BODY = {
    # Preserve the existing geometry unless someone makes a deliberate choice
    # at this role's boundary. The text host can own the geometry too (e.g. a
    # plain step paragraph's margin is already its entire gap to the next).
    # Unset differs from an explicit 0 in an official role override.
    LIST_BODY: {"after_px": None},
    STEP_BODY: {"after_px": None},
    STEP_DETAIL: {"after_px": 0},
    TABLE_BODY: {"after_px": 0},
    LEAD: {"after_px": 20},
    QUOTE: {"after_px": 14},
}

_TEXT_FIELDS = tuple(field.name for field in fields(TextRule))
_DECLARED_TRACKING = {"tight": -0.02, "normal": 0, "relaxed": 0.04}
_METRIC_BOUNDS = {
    "size_px": (10, 42), "weight": (100, 900), "line_height": (1, 2.6),
    "after_px": (0, 48), "before_px": (0, 48), "letter_spacing_em": (-0.06, 0.12),
    "inset_before_px": (0, 32), "inset_after_px": (0, 32),
}


def _check_theme_metrics(theme_id: str, role: str, values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        if value is None and key in _TEXT_FIELDS:
            continue  # A role entry may leave individual properties inherited.
        bounds = _METRIC_BOUNDS.get(key)
        if key == "wrap" and value in ("normal", "anywhere", "break-word"):
            continue
        if bounds and type(value) in (int, float) and bounds[0] <= value <= bounds[1]:
            if key != "weight" or type(value) is int:
                continue
        raise ValueError(f"Invalid official reading metric: {theme_id}.{role}.{key}")

# Coverage uses the sample-book role IDs. Reusing a role here says nothing
# about geometry: a section comparison can still be side-by-side or stacked.
FOUNDATION_READING_ROLES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "hero": (ARTICLE_TITLE, LABEL),
    "lead": (LEAD, LABEL, INLINE_EMPHASIS),
    "paragraph": (BODY, INLINE_EMPHASIS),
    "section_heading": (SECTION_TITLE, MARKER, LABEL),
    "subheading": (SUBHEADING, MARKER),
    "quote": (QUOTE, SOURCE, MARKER, INLINE_EMPHASIS),
    "unordered_list": (LIST_BODY, MARKER, INLINE_EMPHASIS),
    "ordered_list": (LIST_BODY, MARKER, INLINE_EMPHASIS),
    "image_caption": (CAPTION,),
    "table": (TABLE_HEADER, TABLE_BODY, INLINE_EMPHASIS),
    "divider": (),  # A purely visual separator need not contain text.
    "source": (SOURCE,),
    "reference_list": (REFERENCE, MARKER),
    "closing_cta": (BRAND_FOOTER, LABEL),
})

SEMANTIC_READING_ROLES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "question_hook": (COMPONENT_TITLE, INLINE_EMPHASIS, LABEL),
    "numbered_insight": (BODY, MARKER, INLINE_EMPHASIS, LABEL),
    "evidence_callout": (QUOTE, SOURCE, LABEL, INLINE_EMPHASIS),
    "before_after_timeline": (BODY, LABEL, MARKER, INLINE_EMPHASIS),
    "logic_path": (STEP_BODY, STEP_TITLE, STEP_DETAIL, MARKER, LABEL, INLINE_EMPHASIS),
    "concept_explainer": (COMPONENT_TITLE, BODY, LABEL, INLINE_EMPHASIS),
    "case_card": (COMPONENT_TITLE, BODY, LABEL, INLINE_EMPHASIS),
    "warning_note": (BODY, MARKER, LABEL, INLINE_EMPHASIS),
    "action_checklist": (BODY, MARKER, LABEL, INLINE_EMPHASIS),
    "faq_card": (COMPONENT_TITLE, BODY, LABEL, INLINE_EMPHASIS),
    "comparison_card": (BODY, LABEL, MARKER, INLINE_EMPHASIS),
    "section_summary": (BODY, LABEL, MARKER, INLINE_EMPHASIS),
})


@dataclass(frozen=True, slots=True)
class ReadingProfile:
    rules: Mapping[str, TextRule]
    sources: Mapping[str, str]
    field_sources: Mapping[str, Mapping[str, str]]


def _checked_overrides(raw: object, theme_id: str) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, Mapping):
        raise ValueError("Invalid official reading overrides")
    result = {}
    for role, metrics in raw.items():
        if role not in DEFAULT_READING_RULES and role not in _INHERITS_BODY:
            raise ValueError(f"Unknown official reading role: {theme_id}.{role}")
        if not isinstance(metrics, Mapping):
            raise ValueError(f"Invalid official reading metrics: {theme_id}.{role}")
        _check_theme_metrics(theme_id, role, metrics)
        values = {key: value for key, value in metrics.items() if value is not None}
        if values:
            result[role] = values
    return result


def capture_reading_overrides(theme_id: str) -> dict[str, dict[str, Any]]:
    """Copy explicit choices at selection time, even when the display pilot is off."""
    return _checked_overrides(THEME_READING_OVERRIDES.get(theme_id, {}), theme_id)


def resolve_reading_profile(
    config: Mapping[str, Any], *, official: bool, theme_id: str | None = None,
) -> ReadingProfile | None:
    if not official or not reading_rules_pilot_enabled():
        return None
    rules = dict(DEFAULT_READING_RULES)
    sources = dict.fromkeys(rules, "default")
    field_sources = {role: dict.fromkeys(_TEXT_FIELDS, "default") for role in rules}
    for role, changes in _INHERITS_BODY.items():
        rules[role] = replace(rules[BODY], **changes)
        sources[role] = "body default"
        field_sources[role] = {name: "role default" if name in changes else "body default" for name in _TEXT_FIELDS}

    # Only honor the body scale already declared by a built-in theme. A v1
    # user theme, including one that inherits that same theme, never enters.
    design = config.get("generated_design_system")
    declared = design.get("typography") if isinstance(design, Mapping) else None
    scale = declared.get("body_scale") if isinstance(declared, Mapping) else None
    if type(scale) in (int, float) and 0.86 <= scale <= 1.2 and scale != 1:
        for role in (*_BODY_ROLES, STEP_TITLE):
            rule = rules[role]
            if rule.size_px is not None:
                rules[role] = replace(rule, size_px=round(rule.size_px * scale, 2))
                sources[role] = "theme typography.body_scale"
                field_sources[role]["size_px"] = "theme typography.body_scale"
    tracking = declared.get("letter_spacing") if isinstance(declared, Mapping) else None
    # Legacy `normal` is the default rather than a positive theme choice.
    # A reviewed role entry can explicitly specify 0 independent of defaults.
    if isinstance(tracking, str) and tracking != "normal" and tracking in _DECLARED_TRACKING:
        for role in (*_BODY_ROLES, STEP_TITLE):
            rules[role] = replace(rules[role], letter_spacing_em=_DECLARED_TRACKING[tracking])
            sources[role] = "theme typography.letter_spacing"
            field_sources[role]["letter_spacing_em"] = "theme typography.letter_spacing"

    for role, values in _checked_overrides(config.get("reading_overrides", {}), theme_id or "").items():
        rules[role] = replace(rules[role], **values)
        sources[role] = "theme role override"
        field_sources[role].update(dict.fromkeys(values, "theme role override"))
    return ReadingProfile(MappingProxyType(rules), MappingProxyType(sources), MappingProxyType({
        role: MappingProxyType(origins) for role, origins in field_sources.items()
    }))


def reading_gap(role: str, profile: ReadingProfile | None, fallback: float) -> float:
    return authored_metrics(role, profile).get("after_px", fallback)


def apply_reading_css(
    style: str, role: str, profile: ReadingProfile | None, *, inset_before_offset: float = 0,
) -> str:
    values = authored_metrics(role, profile)
    return _apply_rule(style, role, TextRule(**values), inset_before_offset) if values else style


def _apply_rule(style: str, role: str, rule: TextRule, inset_before_offset: float = 0) -> str:
    values = {
        "font-size": f"{rule.size_px:g}px" if rule.size_px is not None else None,
        "font-weight": str(rule.weight) if rule.weight is not None else None,
        "line-height": f"{rule.line_height:g}" if rule.line_height is not None else None,
        "overflow-wrap": rule.wrap,
        "letter-spacing": f"{rule.letter_spacing_em:g}em" if rule.letter_spacing_em is not None else None,
        "margin-top": f"{rule.before_px:g}px" if rule.before_px is not None else None,
        # STEP_TITLE.after is drawn between two text roles by step_content;
        # applying a margin here too would count the same separation twice.
        "margin-bottom": f"{rule.after_px:g}px" if rule.after_px is not None and role != STEP_TITLE else None,
        "padding-top": f"{rule.inset_before_px + inset_before_offset:g}px" if rule.inset_before_px is not None else None,
        "padding-bottom": f"{rule.inset_after_px:g}px" if rule.inset_after_px is not None else None,
    }
    # Replacing declarations at the text host (not the surrounding component)
    # keeps alignment, borders, colors and the marker's geometry intact.
    updated = {name: value for name, value in values.items() if value is not None}
    if not updated:
        return style
    untouched = [item for item in style.split(";") if item.strip() and item.partition(":")[0].strip().lower() not in updated]
    return "".join(f"{item};" for item in untouched) + "".join(f"{n}:{v};" for n, v in updated.items())


_STRONG_OPEN = re.compile(r"<strong\b([^>]*)>")
_STRONG_STYLE = re.compile(r'\bstyle="([^"]*)"')


def apply_reading_emphasis(markup: str, profile: ReadingProfile | None) -> str:
    """Style only inline emphasis already emitted from escaped source text."""
    return authored_emphasis(markup, profile)


def _emphasis_with_rule(markup: str, rule: TextRule) -> str:
    def update(match: re.Match[str]) -> str:
        attrs = match[1]
        inline_style = _STRONG_STYLE.search(attrs)
        new_style = _apply_rule(inline_style[1] if inline_style else "", INLINE_EMPHASIS, rule)
        if inline_style is not None:
            attrs = attrs[:inline_style.start(1)] + new_style + attrs[inline_style.end(1):]
        else:
            attrs += f' style="{new_style}"'
        return f"<strong{attrs}>"

    return _STRONG_OPEN.sub(update, markup)


def authored_metrics(role: str, profile: ReadingProfile | None) -> dict[str, Any]:
    """Only explicit, reviewed choices; never flatten legacy typography by default."""
    if profile is None:
        return {}
    return {key: getattr(profile.rules[role], key) for key, origin in profile.field_sources[role].items()
            if origin == "theme role override"}


def authored_host_css(style: str, role: str, profile: ReadingProfile | None) -> str:
    return apply_reading_css(style, role, profile)


def restore_authored_metrics(role: str, metrics: Mapping[str, Any]) -> ReadingProfile:
    """Restore bounded metrics captured with a deferred field, never raw CSS."""
    if role not in DEFAULT_READING_RULES:
        raise ValueError(f"Unknown reading role: {role}")
    _check_theme_metrics("snapshot", role, metrics)
    return ReadingProfile({role: TextRule(**metrics)}, {role: "snapshot"},
                          {role: dict.fromkeys(metrics, "theme role override")})


def authored_emphasis(markup: str, profile: ReadingProfile | None) -> str:
    if profile is None or INLINE_EMPHASIS not in profile.rules:
        return markup
    values = authored_metrics(INLINE_EMPHASIS, profile)
    return _emphasis_with_rule(markup, TextRule(**values)) if values and "<strong" in markup else markup


def render_authored_text(markup: str, role: str, profile: ReadingProfile | None) -> str:
    """Project trusted, already escaped inline output, never decoration or raw source.

    Inline fields do not own vertical box geometry. Layouts with a text host
    can instead apply authored_host_css and authored_emphasis directly.
    """
    if not markup or profile is None:
        return markup
    text = authored_emphasis(markup, profile)
    values = {key: value for key, value in authored_metrics(role, profile).items()
              if key in {"size_px", "weight", "line_height", "letter_spacing_em", "wrap"}}
    if not values:
        return text
    return f'<span style="{_apply_rule("", role, TextRule(**values))}">{text}</span>'
