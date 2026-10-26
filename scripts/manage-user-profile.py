"""Bundled stdlib-only installer bridge; never print config contents."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))
from visual_director.data_recovery import DataRecoveryError
from visual_director.user_profile import prepare_user_profile, register_user_install


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "register"))
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--api-base")
    parser.add_argument("--web-base")
    args = parser.parse_args()
    try:
        result = prepare_user_profile(args.home, args.install_root) if args.mode == "prepare" else {
            "profile": register_user_install(args.home, args.install_root, api_base=args.api_base, web_base=args.web_base)}
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
        return 0
    except DataRecoveryError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}}, ensure_ascii=False))
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": {"code": "user_profile_prepare_failed", "message": type(exc).__name__}}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
