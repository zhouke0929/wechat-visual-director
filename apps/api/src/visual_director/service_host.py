from __future__ import annotations

import argparse
import logging
import logging.config
from pathlib import Path
from typing import Any, Sequence

import uvicorn


DEFAULT_LOG_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 3


def build_log_config(
    log_path: str | Path,
    *,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> dict[str, Any]:
    target = Path(log_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    handler = {
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "standard",
        "filename": str(target),
        "maxBytes": max(1024, int(max_bytes)),
        "backupCount": max(1, int(backup_count)),
        "encoding": "utf-8",
        "delay": True,
    }
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {"rotating_file": handler},
        "loggers": {
            "uvicorn": {
                "handlers": ["rotating_file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["rotating_file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["rotating_file"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["rotating_file"],
            "level": "INFO",
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Visual Director service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--log-max-bytes", type=int, default=DEFAULT_LOG_MAX_BYTES)
    parser.add_argument("--log-backup-count", type=int, default=DEFAULT_LOG_BACKUP_COUNT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.config.dictConfig(
        build_log_config(
            args.log_file,
            max_bytes=args.log_max_bytes,
            backup_count=args.log_backup_count,
        )
    )
    logger = logging.getLogger("visual_director.service_host")
    try:
        uvicorn.run(
            "visual_director.main:app",
            host=args.host,
            port=args.port,
            log_config=None,
            access_log=True,
        )
    except BaseException:
        logger.exception("Visual Director service stopped unexpectedly")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
