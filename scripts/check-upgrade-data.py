"""Installation helper using only the package's Python and standard library."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))
from visual_director.data_recovery import DataRecoveryError
from visual_director.upgrade_data import backup_upgrade_data, capture_upgrade_data, probe_running_data, verify_upgrade_data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["capture", "verify"])
    parser.add_argument("--install-root", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--candidate", action="append", default=[], type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "capture":
            # The working directory is not evidence of dataset ownership.
            result = capture_upgrade_data(args.install_root, running=probe_running_data(args.api_base), candidates=tuple(args.candidate))
            result = backup_upgrade_data(result)
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            args.snapshot.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            result = {"captured": True, "task_count": result["before"]["task_count"],
                      "migration_candidates": result["migration_candidates"], "warnings": result["warnings"]}
        else:
            baseline = json.loads(args.snapshot.read_text(encoding="utf-8"))
            result = verify_upgrade_data(baseline, args.install_root)
        print(json.dumps({"ok": True, "data_continuity": result}, ensure_ascii=False))
        return 0
    except DataRecoveryError as exc:
        print(json.dumps({"ok": False, "next_action": exc.details.get("action", "review_data_migration"), "error": {
            "code": exc.code, "message": exc.message, "details": exc.details}}, ensure_ascii=False))
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": {"code": "upgrade_data_check_failed", "message": type(exc).__name__}}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
