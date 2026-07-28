from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class TextConsistencyResult:
    status: str
    engine: str
    expected_count: int
    matched_count: int
    human_confirmation_required: bool
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "engine": self.engine,
            "expected_count": self.expected_count,
            "matched_count": self.matched_count,
            "human_confirmation_required": self.human_confirmation_required,
            "reason": self.reason,
        }


def _normalize(value: str) -> str:
    return re.sub(r"[\s，。；：、“”‘’！？,.!?:;（）()《》【】\[\]—\-]+", "", value)


def verify_locked_copy(content: bytes, expected_copy: list[str]) -> TextConsistencyResult:
    """Conservatively verify locked Chinese copy with an optional local OCR engine.

    Tesseract is deliberately optional: the one-line Skill install must remain
    usable without a second cloud key or a heavyweight OCR dependency. When a
    Chinese OCR engine is unavailable or cannot prove every locked string, the
    candidate is kept in human-review state and cannot be accepted silently.
    """

    expected = [_normalize(value) for value in expected_copy if _normalize(value)]
    executable = shutil.which("tesseract")
    if not executable:
        return TextConsistencyResult(
            status="human_required",
            engine="unavailable",
            expected_count=len(expected),
            matched_count=0,
            human_confirmation_required=True,
            reason="local_ocr_engine_unavailable",
        )
    try:
        languages = subprocess.run(
            [executable, "--list-langs"],
            capture_output=True,
            check=True,
            text=True,
            timeout=10,
        ).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return TextConsistencyResult(
            status="human_required",
            engine="tesseract",
            expected_count=len(expected),
            matched_count=0,
            human_confirmation_required=True,
            reason="local_ocr_probe_failed",
        )
    if "chi_sim" not in {value.strip() for value in languages}:
        return TextConsistencyResult(
            status="human_required",
            engine="tesseract",
            expected_count=len(expected),
            matched_count=0,
            human_confirmation_required=True,
            reason="chinese_ocr_language_unavailable",
        )
    try:
        completed = subprocess.run(
            [executable, "stdin", "stdout", "-l", "chi_sim+eng", "--psm", "6"],
            input=content,
            capture_output=True,
            check=True,
            timeout=45,
        )
        recognized = _normalize(completed.stdout.decode("utf-8", errors="replace"))
    except (OSError, subprocess.SubprocessError):
        return TextConsistencyResult(
            status="human_required",
            engine="tesseract",
            expected_count=len(expected),
            matched_count=0,
            human_confirmation_required=True,
            reason="local_ocr_execution_failed",
        )
    matched = sum(1 for value in expected if value in recognized)
    passed = bool(expected) and matched == len(expected)
    return TextConsistencyResult(
        status="passed" if passed else "failed",
        engine="tesseract",
        expected_count=len(expected),
        matched_count=matched,
        human_confirmation_required=not passed,
        reason=None if passed else "locked_copy_not_fully_matched",
    )
