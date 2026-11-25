"""An authored host plan for downstream integration tests, not a product planner.

The same test contract requests a path on the first ordered list, an infographic
of that list if it fits, and one scene. IDs come from the actual parsed fixture.
Tests of editorial judgment should supply their own brief instead.
"""


def submit_fixture(client, task_url, version):
    response = client.get(f"{task_url}/editorial-brief/context")
    response.raise_for_status()
    context = response.json()["context"]["planner_input"]
    blocks = context["article"]["blocks"]
    steps = next((b for b in blocks if b["type"] == "ordered_list"), None)
    scene = next((b for b in blocks if b["type"] == "paragraph"), blocks[0])
    brief = {
        "schema_version": "editorial_brief.v0.1",
        "article": {"article_type": context["requested_article_type"], "audience": ["编辑"],
                    "reader_task": "核对文章的完整交付流程", "narrative": "按原稿顺序呈现信息与操作。"},
        "art_direction": {"tone": ["清晰"], "palette_roles": ["deep_navy", "warm_ivory"],
                          "style_family": "editorial_paper_cut", "avoid_recent_patterns": []},
        "sections": [], "image_intents": [], "facts_locked": True,
    }
    def image(block, purpose, ratio):
        return {"anchor_block_id": block["block_id"], "source_block_ids": [block["block_id"]],
                "purpose": purpose, "necessity": "optional", "aspect_ratio": ratio,
                "visual_metaphor": "编辑桌上的稿纸与标记", "forbidden_elements": ["text_in_model_image", "logo", "qr_code"]}

    if steps:
        brief["sections"].append({"source_block_ids": [steps["block_id"]], "semantic_role": "logic_sequence",
                                  "visual_priority": "high", "component_intent": "logic_path",
                                  "reasoning": "在此测试稿中使用原文的操作顺序。"})
        if 2 <= len(steps["content"]) <= 4:
            brief["image_intents"].append(image(steps, "structured_infographic", "4:3"))
    brief["image_intents"].append(image(scene, "atmosphere", "16:9"))
    return client.post(f"{task_url}/generate-plans", json={
        "mode": "start", "expected_task_version": version, "planner": "host_agent",
        "host_model": "integration-fixture", "editorial_brief": brief,
    })
