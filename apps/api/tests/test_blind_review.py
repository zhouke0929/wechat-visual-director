from pathlib import Path

from fastapi.testclient import TestClient

from visual_director.main import create_app


def complete_submission(reviewer_id: str, assignment_token: str) -> dict:
    rating = {"left": 4, "right": 3, "reason": "方案 A 的规划重点更清晰"}
    return {
        "reviewer_id": reviewer_id,
        "assignment_token": assignment_token,
        "scores": {
            "article_understanding": rating,
            "component_planning": rating,
            "image_planning": rating,
            "style_direction": rating,
            "history_freshness": rating,
            "direct_adoption": rating,
        },
        "preferred_candidate": "left",
        "preference_reason": "更愿意继续编辑方案 A",
    }


def test_blind_review_hides_sources_randomizes_and_locks_submission(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "blind.db"))
    eval_set_id = app.state.blind_review_dataset.eval_set_id
    sample_total = len(app.state.blind_review_dataset.samples)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/blind-reviews/{eval_set_id}",
            params={"reviewer_id": "product_owner"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["progress"] == {"completed": 0, "total": sample_total}
        assert len(payload["samples"]) == sample_total
        serialized = response.text.lower()
        assert "qwen" not in serialized
        assert "baseline" not in serialized
        assert "candidate\"" not in serialized

        sample = payload["samples"][0]
        assert [item["label"] for item in sample["candidates"]] == ["方案 A", "方案 B"]
        for candidate in sample["candidates"]:
            preview = client.get(candidate["preview_url"])
            assert preview.status_code == 200
            assert "width:100%" in preview.text
            assert "width:390px" not in preview.text

        submission = complete_submission("product_owner", sample["assignment_token"])
        submitted = client.post(
            f"/api/v1/blind-reviews/{eval_set_id}/samples/{sample['sample_id']}/submissions",
            json=submission,
        )
        assert submitted.status_code == 201
        assert submitted.json()["locked"] is True

        repeated = client.post(
            f"/api/v1/blind-reviews/{eval_set_id}/samples/{sample['sample_id']}/submissions",
            json=submission,
        )
        assert repeated.status_code == 409
        assert repeated.json()["error"]["code"] == "version_conflict"

        refreshed = client.get(
            f"/api/v1/blind-reviews/{eval_set_id}",
            params={"reviewer_id": "product_owner"},
        ).json()
        assert refreshed["progress"] == {"completed": 1, "total": sample_total}
        assert refreshed["samples"][0]["submitted"] is True


def test_blind_review_rejects_changed_assignment_and_early_reveal(tmp_path: Path) -> None:
    app = create_app(str(tmp_path / "blind-guard.db"))
    eval_set_id = app.state.blind_review_dataset.eval_set_id
    with TestClient(app) as client:
        payload = client.get(
            f"/api/v1/blind-reviews/{eval_set_id}",
            params={"reviewer_id": "operator"},
        ).json()
        sample = payload["samples"][0]
        invalid = complete_submission("operator", "0" * 64)
        rejected = client.post(
            f"/api/v1/blind-reviews/{eval_set_id}/samples/{sample['sample_id']}/submissions",
            json=invalid,
        )
        assert rejected.status_code == 409
        assert rejected.json()["error"]["code"] == "assignment_changed"

        reveal = client.get(f"/api/v1/blind-reviews/{eval_set_id}/results")
        assert reveal.status_code == 409
        assert reveal.json()["error"]["code"] == "review_incomplete"
