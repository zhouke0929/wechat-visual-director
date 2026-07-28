from __future__ import annotations

from visual_director import ocr_verifier


def test_ocr_verifier_requires_human_confirmation_without_local_engine(monkeypatch) -> None:
    monkeypatch.setattr(ocr_verifier.shutil, "which", lambda _: None)

    result = ocr_verifier.verify_locked_copy(
        b"not-an-image-because-the-engine-is-unavailable",
        ["填报前完成三项核对", "核对成绩和位次"],
    )

    assert result.status == "human_required"
    assert result.engine == "unavailable"
    assert result.expected_count == 2
    assert result.human_confirmation_required is True
    assert result.reason == "local_ocr_engine_unavailable"
