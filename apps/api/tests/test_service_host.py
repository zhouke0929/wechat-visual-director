from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from visual_director.service_host import build_log_config


def test_rotating_service_log_has_a_bounded_number_of_files(tmp_path: Path) -> None:
    log_path = tmp_path / "api.log"
    logging.config.dictConfig(
        build_log_config(log_path, max_bytes=1024, backup_count=2)
    )
    logger = logging.getLogger("uvicorn.error")
    for index in range(80):
        logger.info("event=%s payload=%s", index, "x" * 120)
    for handler in logger.handlers:
        handler.flush()

    files = sorted(tmp_path.glob("api.log*"))
    assert log_path in files
    assert 2 <= len(files) <= 3
    assert {item.name for item in files}.issubset({"api.log", "api.log.1", "api.log.2"})


def test_log_config_uses_five_megabytes_and_three_backups_by_default(
    tmp_path: Path,
) -> None:
    config = build_log_config(tmp_path / "api.log")
    handler = config["handlers"]["rotating_file"]
    assert handler["maxBytes"] == 5 * 1024 * 1024
    assert handler["backupCount"] == 3
