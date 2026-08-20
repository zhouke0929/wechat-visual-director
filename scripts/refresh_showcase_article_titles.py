from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from visual_director.brief_compiler import (  # noqa: E402
    apply_visual_system,
    compile_editorial_brief,
)
from visual_director.parser import parse_markdown  # noqa: E402
from visual_director.planner import generate_plans  # noqa: E402
from visual_director.renderer import render_preview  # noqa: E402


SHOWCASES = (
    (
        "01-campus-project-portfolio.md",
        "brief-01-campus-project-portfolio.json",
        "campus.html",
        "youth_campus",
    ),
    (
        "02-neighborhood-coffee-repeat-visits.md",
        "brief-02-neighborhood-coffee-repeat-visits.json",
        "coffee.html",
        "warm_humanist",
    ),
    (
        "03-pop-collaboration-memory.md",
        "brief-03-pop-collaboration-memory.json",
        "pop-collaboration.html",
        "pop_poster",
    ),
)
HERO_PATTERN = re.compile(
    r'<header data-content-role="article-metadata-preview".*?</header>',
    re.DOTALL,
)
BODY_PATTERN = re.compile(r"<body[^>]*>(.*)</body>", re.DOTALL)
SHOWCASE_DOCUMENT_PATTERN = re.compile(
    r'(<div class="wechat-document">).*?(</div></article></main>)',
    re.DOTALL,
)
POP_SHOWCASE_IMAGES = (
    "pop-collaboration-memory.webp",
    "pop-collaboration-experience.webp",
)


def _normalize_brief_for_current_contract(brief: dict) -> dict:
    for image_intent in brief.get("image_intents", []):
        forbidden = list(image_intent.get("forbidden_elements") or [])
        image_intent["forbidden_elements"] = list(
            dict.fromkeys(["text_in_model_image", "qr_code", "logo", *forbidden])
        )[:6]
    return brief


def _hydrate_showcase_images(rendered: str, image_slot_ids: list[str]) -> str:
    hydrated = rendered
    if len(image_slot_ids) != len(POP_SHOWCASE_IMAGES):
        raise RuntimeError("pop showcase image slots no longer match curated assets")
    for index, (slot_id, image_name) in enumerate(zip(image_slot_ids, POP_SHOWCASE_IMAGES)):
        pattern = re.compile(
            rf'<section id="{re.escape(slot_id)}" class="image-slot-anchor"[^>]*>.*?</section>',
            re.DOTALL,
        )
        replacement = (
            f'<section id="{slot_id}" class="image-slot-anchor" '
            'data-image-frame="pop_collage" style="scroll-margin-top:18px;margin:26px 0;">'
            f'<img src="../assets/generated/{image_name}" '
            'loading="eager" decoding="async" '
            'alt="运营已确认的文章配图" '
            'style="display:block;width:100%;height:auto;margin:0;border:0;" />'
            '</section>'
        )
        hydrated, replacement_count = pattern.subn(replacement, hydrated, count=1)
        if replacement_count != 1:
            raise RuntimeError(f"showcase image slot missing: {slot_id}")
    return hydrated


def main() -> int:
    sample_root = ROOT / "samples" / "showcase"
    article_root = ROOT / "site" / "articles"
    for markdown_name, brief_name, article_name, theme_id in SHOWCASES:
        parsed = parse_markdown((sample_root / markdown_name).read_text(encoding="utf-8"))
        brief = _normalize_brief_for_current_contract(
            json.loads((sample_root / brief_name).read_text(encoding="utf-8"))
        )
        plan = (
            compile_editorial_brief(parsed, brief, 5, [])
            if article_name == "pop-collaboration.html"
            else generate_plans(parsed, brief["article"]["article_type"], 5, [])[0]
        )
        plan = apply_visual_system(
            plan,
            theme_id,
            history_window=5,
            recent_summaries=[],
        )
        rendered = render_preview(parsed, plan)
        rendered_hero = HERO_PATTERN.search(rendered)
        if rendered_hero is None:
            raise RuntimeError(f"rendered hero missing: {article_name}")

        target = article_root / article_name
        current = target.read_text(encoding="utf-8")
        if article_name == "pop-collaboration.html":
            rendered = _hydrate_showcase_images(
                rendered,
                [slot["image_slot_id"] for slot in plan.get("image_slots", [])],
            )
            rendered = rendered.replace(
                "/api/v1/theme-assets/",
                "../assets/theme-stickers/",
            )
            rendered_body = BODY_PATTERN.search(rendered)
            if rendered_body is None:
                raise RuntimeError("rendered body missing: pop-collaboration.html")
            replacement = rf'\1{rendered_body.group(1)}\2'
            updated, replacement_count = SHOWCASE_DOCUMENT_PATTERN.subn(
                replacement,
                current,
                count=1,
            )
            if replacement_count != 1:
                raise RuntimeError("showcase document missing: pop-collaboration.html")
            updated = updated.replace(
                "未来科技 · 390PX WECHAT PREVIEW",
                "波普海报 · 390PX WECHAT PREVIEW",
            )
        else:
            updated, replacement_count = HERO_PATTERN.subn(
                rendered_hero.group(0),
                current,
                count=1,
            )
            if replacement_count != 1:
                raise RuntimeError(f"showcase hero missing: {article_name}")
        updated = re.sub(
            r"<title>.*?</title>",
            f"<title>{parsed.title}</title>",
            updated,
            count=1,
        )
        target.write_text(updated, encoding="utf-8", newline="\n")
        print(f"refreshed showcase: {article_name} ({theme_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
