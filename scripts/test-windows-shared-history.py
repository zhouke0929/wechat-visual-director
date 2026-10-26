"""Exercise real old/new release packages in isolated directories, never user data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.request import ProxyHandler, build_opener, Request


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract(archive: Path, destination: Path) -> Path:
    expected = Path(str(archive) + ".sha256").read_text(encoding="utf-8-sig").split()[0]
    assert sha(archive).lower() == expected.lower(), "Release checksum mismatch"
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            assert (destination / name).resolve().is_relative_to(destination.resolve()), "Unsafe archive member"
        bundle.extractall(destination)
    return destination / "wechat-visual-director"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-archive", type=Path, required=True)
    parser.add_argument("--new-archive", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18931)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.exists():
        raise SystemExit("A new isolated test root is required; nothing was removed.")
    root.mkdir(parents=True)
    evidence = root / "evidence"
    evidence.mkdir()
    api, web = f"http://127.0.0.1:{args.port}/api/v1", f"http://127.0.0.1:{args.port}"
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("VISUAL_DIRECTOR_") and not any(marker in key.upper() for marker in ("API_KEY", "APPSECRET", "APP_SECRET", "ACCESS_TOKEN"))}
    opener = build_opener(ProxyHandler({}))
    active: Path | None = None
    calls = []
    result = {"ok": False, "scope": "real_release_packages_isolated_shared_history", "checks": []}

    def ps(script: Path, *arguments, label: str, override_env=None, allow_failure=False):
        process = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, arguments)],
                                 env=override_env or env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        (evidence / f"{label}.stdout.json").write_text(process.stdout, encoding="utf-8")
        (evidence / f"{label}.stderr.txt").write_text(process.stderr, encoding="utf-8")
        calls.append({"label": label, "script": str(script), "args": list(map(str, arguments)), "exit": process.returncode})
        value = json.loads(process.stdout)
        if not allow_failure:
            assert process.returncode == 0 and value.get("ok"), f"{label}: {value} / {process.stderr}"
        return value

    def request(path, *, data=None, content_type=None, raw=False, intent=False):
        headers = {"Content-Type": content_type} if content_type else {}
        if intent:
            headers["X-Local-Intent"] = "local-operator"
        with opener.open(Request(api + path, data=data, headers=headers), timeout=90) as response:
            body = response.read()
        return body if raw else json.loads(body)

    def multipart(fields, files):
        boundary = "wvd-package-test-" + uuid.uuid4().hex
        body = bytearray()
        for name, value in fields.items():
            body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        for name, (filename, mime, content) in files.items():
            body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode())
            body.extend(content)
            body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        return bytes(body), f"multipart/form-data; boundary={boundary}"

    def create_article(title):
        text = f"# {title}\n\n这是一篇隔离安装验收稿，不含用户资料。\n\n## 核对历史\n\n1. 记录文章\n2. 核对图片\n3. 重新打开\n"
        payload, mime = multipart({}, {"markdown_file": ("article.md", "text/markdown", text.encode())})
        return request("/article-tasks", data=payload, content_type=mime)["task"]

    def check_ids(expected):
        actual = {item["id"] for item in request("/article-tasks")["items"]}
        assert actual == set(expected), (actual, expected)

    try:
        # The harness may run under any Python. Every product process below must
        # use its release's own embedded runtime, verified through doctor.
        old = extract(args.old_archive.resolve(), root / "old-package")
        new = extract(args.new_archive.resolve(), root / "new-package")
        a, b, c = root / "program-codex", root / "program-other-agent", root / "program-reinstalled"
        host, shared = root / "host", root / "shared-user-home"
        common = ("-HostHome", host, "-ApiBase", api, "-WebBase", web)
        active = a / "visual-director.ps1"
        ps(old / "scripts/bootstrap.ps1", "-InstallRoot", a, *common, label="01-old-install")
        first = create_article("旧版本创建的历史文章")
        from PIL import Image
        image = BytesIO()
        Image.new("RGB", (640, 360), "#267d75").save(image, format="PNG")
        payload, mime = multipart({"expected_task_version": first["version"]}, {"image_file": ("cover.png", "image/png", image.getvalue())})
        request(f'/article-tasks/{first["id"]}/preflight/findings/missing_cover/replace-asset', data=payload, content_type=mime)
        # Resolve the controlled image file from the portable dataset, not a guessed URL.
        original_images = {str(p.relative_to(a / "data")): sha(p) for p in (a / "data/image-assets").rglob("*") if p.is_file()}
        template = json.loads((new / "skills/wechat-visual-director/assets/theme-pack-template.json").read_text(encoding="utf-8"))
        template["id"], template["name"] = "shared_history_probe", "共享历史验收主题"
        payload, mime = multipart({}, {"theme_file": ("theme.json", "application/json", json.dumps(template, ensure_ascii=False).encode())})
        request("/theme-packs", data=payload, content_type=mime, intent=True)
        theme_id = template["id"]
        theme_digest = sha(a / f"data/theme-packs/{theme_id}/theme.json")
        ps(active, "stop", "--json", label="02-stop-old")
        active = None

        active = a / "visual-director.ps1"
        ps(new / "scripts/bootstrap.ps1", "-InstallRoot", a, "-UserDataHome", shared, *common, label="03-upgrade-to-shared")
        check_ids([first["id"]])
        doctor = ps(active, "doctor", "--json", label="04-shared-doctor")
        assert Path(doctor["installation"]["running_data_root"]) == shared / "data"
        assert doctor["installation"]["runtime_match"] and doctor["installation"]["version_match"]
        for relative, digest in original_images.items():
            assert sha(shared / "data" / relative) == digest
        assert sha(shared / f"data/theme-packs/{theme_id}/theme.json") == theme_digest
        assert (a / "data/visual-director.db").is_file(), "Original source was removed"
        result["checks"].append("old_release_upgrade_preserves_task_images_and_theme")
        second = create_article("共享版本新增的文章")
        ps(active, "stop", "--json", label="05-stop-first-shared-runtime")
        active = None

        active = b / "visual-director.ps1"
        ps(new / "scripts/bootstrap.ps1", "-InstallRoot", b, "-UserDataHome", shared, *common, label="06-second-program-install")
        check_ids([first["id"], second["id"]])
        via_old_entry = ps(a / "visual-director.ps1", "task", "list", "--json", label="07-old-entry-delegates")
        assert {item["id"] for item in via_old_entry["items"]} == {first["id"], second["id"]}
        for view in ("codex-appdata-view", "other-agent-appdata-view"):
            fake_local = root / view
            fake_local.mkdir()
            ready = ps(new / "skills/wechat-visual-director/scripts/ensure-workbench.ps1", "-UserDataHome", shared,
                       "-HostHome", host, "-NoOpen", label=f"08-{view}", override_env={**env, "LOCALAPPDATA": str(fake_local)})
            assert ready["workbench_ready"]
            assert Path(ready["installation"]["running_data_root"]) == shared / "data"
            assert Path(ready["launcher"]) == active
        result["checks"].append("two_program_entries_and_two_host_views_share_history_and_runtime")

        ps(b / "uninstall.ps1", "-HostHome", host, label="09-uninstall-preserves-shared-history")
        active = None
        assert (shared / "data/visual-director.db").is_file()
        active = c / "visual-director.ps1"
        ps(new / "scripts/bootstrap.ps1", "-InstallRoot", c, "-UserDataHome", shared, *common, label="10-reinstall-third-program")
        check_ids([first["id"], second["id"]])
        assert any(item["id"] == theme_id for item in request("/theme-packs")["items"])
        for relative, digest in original_images.items():
            assert sha(shared / "data" / relative) == digest
        result["checks"].append("uninstall_and_reinstall_preserve_all_shared_history_assets_and_theme")
        ps(active, "stop", "--json", label="11-stop-before-missing-database-test")
        active = None
        database = shared / "data/visual-director.db"
        held = shared / "data/visual-director.db.test-held"
        database.rename(held)
        try:
            failure = ps(c / "visual-director.ps1", "doctor", "--json", label="12-missing-db-blocked", allow_failure=True)
            assert failure.get("ok") is False and not database.exists(), "Missing history was silently replaced"
        finally:
            held.rename(database)
        result["checks"].append("missing_registered_database_does_not_create_an_empty_replacement")
        result.update(ok=True, old_version=(old / "VERSION").read_text().strip(), new_version=(new / "VERSION").read_text().strip(),
                      preserved_task_ids=[first["id"], second["id"]], data_root=str(shared / "data"))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if active and active.is_file():
            try:
                ps(active, "stop", "--json", label="cleanup-stop")
            except Exception as exc:
                result["cleanup_error"] = str(exc)
                result["ok"] = False
        (root / "calls.json").write_text(json.dumps(calls, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
