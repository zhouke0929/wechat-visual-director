"""Copied into an isolated evaluation output; never used by the installed app."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def configure() -> tuple[Path, int]:
    out = Path(__file__).resolve().parent
    config = json.loads((out / "runtime-config.json").read_text(encoding="utf-8"))
    repo = Path(config["repository"]).resolve()
    port = int(config["port"])
    if not 1024 <= port <= 65535 or port == 8000:
        raise SystemExit("Invalid evaluation port")
    keep = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "PATHEXT", "LOCALAPPDATA",
            "APPDATA", "USERPROFILE", "ALLUSERSPROFILE", "PROGRAMDATA",
            "PROGRAMFILES", "PROGRAMFILES(X86)", "SYSTEMDRIVE", "OS"}
    for key in list(os.environ):
        if key.upper() not in keep:
            del os.environ[key]
    runtime = out / "runtime"
    (runtime / "temp").mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "VISUAL_DIRECTOR_PROJECT_ROOT": str(out / "isolated-root"),
        "VISUAL_DIRECTOR_HOME": str(runtime),
        "VISUAL_DIRECTOR_DB": str(runtime / "data/visual-director.db"),
        "VISUAL_DIRECTOR_ENV_FILE": str(runtime / "empty.env"),
        "VISUAL_DIRECTOR_THEME_PACK_DIR": str(runtime / "theme-packs"),
        "VISUAL_DIRECTOR_IMAGE_PROVIDER": "mock",
        "VISUAL_DIRECTOR_API_BASE": f"http://127.0.0.1:{port}/api/v1",
        "VISUAL_DIRECTOR_WEB_BASE": f"http://127.0.0.1:{port}",
        "VISUAL_DIRECTOR_BRAND_PROFILE": str(runtime / "brand.json"),
        "TEMP": str(runtime / "temp"), "TMP": str(runtime / "temp"),
        "XDG_CACHE_HOME": str(runtime / "cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo / "apps/api/src"))
    return repo, port


def main() -> None:
    _, port = configure()
    args = sys.argv[1:]
    if args == ["serve-isolated"]:
        import socket
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
        import uvicorn
        uvicorn.run("visual_director.main:create_app", factory=True,
                    host="127.0.0.1", port=port)
        return
    if not args or args[0] not in {"theme", "task", "doctor"}:
        raise SystemExit("Evaluation permits only theme/task/doctor or serve-isolated")
    if any(arg.startswith(("--api-base", "--web-base")) for arg in args):
        raise SystemExit("Evaluation connection cannot be overridden")
    if len(args) > 1 and (
        args[0] == "task" and args[1] in {"create", "plan", "open"}
        or args[0] == "theme" and args[1] in {"validate", "install", "list"}
    ):
        if "--no-start" not in sys.argv:
            sys.argv.append("--no-start")
    from visual_director.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
