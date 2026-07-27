from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import webbrowser
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .version import application_version


DEFAULT_API_BASE = "http://127.0.0.1:8000/api/v1"
DEFAULT_WEB_BASE = "http://127.0.0.1:3000"
CLI_SCHEMA_VERSION = "visual_director_cli.v0.2"


class CliError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = 10,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable
        self.details = details or {}

    def payload(self) -> dict[str, Any]:
        return {
            "ok": False,
            "schema_version": CLI_SCHEMA_VERSION,
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
                "details": self.details,
            },
        }


def _project_root() -> Path:
    explicit = os.environ.get("VISUAL_DIRECTOR_PROJECT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[4]


def _runtime_home() -> Path:
    explicit = os.environ.get("VISUAL_DIRECTOR_HOME")
    path = Path(explicit).expanduser() if explicit else Path.home() / ".visual-director"
    path.mkdir(parents=True, exist_ok=True)
    (path / "logs").mkdir(exist_ok=True)
    return path


def _runtime_state_path() -> Path:
    return _runtime_home() / "runtime.json"


def _installation_summary() -> dict[str, Any]:
    project_root = _project_root()
    install_root_value = os.environ.get("VISUAL_DIRECTOR_INSTALL_ROOT")
    data_root_value = os.environ.get("VISUAL_DIRECTOR_DATA_ROOT")
    database_value = os.environ.get("VISUAL_DIRECTOR_DB")
    config_value = os.environ.get("VISUAL_DIRECTOR_ENV_FILE")
    if data_root_value:
        data_root = Path(data_root_value).expanduser().resolve()
    elif database_value:
        data_root = Path(database_value).expanduser().resolve().parent
    else:
        data_root = project_root / "apps" / "api" / "data"
    config_file = (
        Path(config_value).expanduser().resolve()
        if config_value
        else project_root / ".env.local"
    )
    return {
        "version": application_version(),
        "mode": "persistent" if install_root_value else "source",
        "persistent": bool(install_root_value),
        "install_root": (
            str(Path(install_root_value).expanduser().resolve())
            if install_root_value
            else None
        ),
        "app_root": str(project_root),
        "data_root": str(data_root),
        "config_file": str(config_file),
        "runtime_root": str(_runtime_home().resolve()),
    }


def _read_runtime_state() -> dict[str, Any]:
    path = _runtime_state_path()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _api_origin(api_base: str) -> str:
    normalized = api_base.rstrip("/")
    suffix = "/api/v1"
    return normalized[: -len(suffix)] if normalized.endswith(suffix) else normalized


def _request_json(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10,
) -> dict[str, Any]:
    request = Request(url, data=body, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        code = str(error.get("code") or f"http_{exc.code}")
        exit_code = 4 if code == "preflight_blocked" else 5
        raise CliError(
            code,
            str(error.get("message") or f"请求失败（HTTP {exc.code}）"),
            exit_code=exit_code,
            retryable=bool(error.get("retryable", False)),
            details=error.get("details") if isinstance(error.get("details"), dict) else {},
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise CliError(
            "service_unavailable",
            f"无法连接本地视觉主编服务：{exc}",
            exit_code=3,
            retryable=True,
        ) from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CliError(
            "invalid_service_response",
            "本地服务返回了无法识别的响应",
            exit_code=3,
            retryable=True,
        ) from exc
    if not isinstance(payload, dict):
        raise CliError("invalid_service_response", "本地服务响应格式错误", exit_code=3)
    return payload


def _probe_json(url: str, timeout: float = 1.5) -> dict[str, Any] | None:
    try:
        return _request_json("GET", url, timeout=timeout)
    except CliError:
        return None


def _probe_web(url: str, timeout: float = 1.5) -> bool:
    try:
        request = Request(url, method="GET")
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def _multipart_markdown(
    path: Path,
    *,
    article_type: str | None,
    account_id: str,
) -> tuple[bytes, str]:
    boundary = f"----visual-director-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    def field(name: str, value: str) -> None:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    field("account_id", account_id)
    if article_type:
        field("article_type", article_type)
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="markdown_file"; filename="{path.name}"\r\n'
                "Content-Type: text/markdown; charset=utf-8\r\n\r\n"
            ).encode("utf-8"),
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


def _spawn_detached(
    command: list[str],
    *,
    cwd: Path,
    log_name: str,
    extra_env: dict[str, str] | None = None,
) -> int:
    runtime = _runtime_home()
    log_path = runtime / "logs" / log_name
    launch_command = command
    if os.name == "nt" and Path(command[0]).suffix.lower() in {".cmd", ".bat"}:
        launch_command = [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/s",
            "/c",
            subprocess.list2cmdline(command),
        ]
    with log_path.open("ab") as log:
        child_env = os.environ.copy()
        child_env.update(extra_env or {})
        kwargs: dict[str, Any] = {
            "cwd": str(cwd),
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": subprocess.STDOUT,
            "env": child_env,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(launch_command, **kwargs)
    return process.pid


def _pnpm_command() -> list[str] | None:
    pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
    if pnpm:
        return [pnpm]
    corepack = shutil.which("corepack") or shutil.which("corepack.cmd")
    if corepack:
        return [corepack, "pnpm"]
    return None


def _wait_until(check: Any, *, timeout: float, label: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.25)
    raise CliError(
        "service_start_timeout",
        f"{label}未能在 {int(timeout)} 秒内启动，请检查本地日志",
        exit_code=3,
        retryable=True,
        details={"log_dir": str(_runtime_home() / "logs")},
    )


def _ensure_services(api_base: str, web_base: str, *, timeout: float = 45) -> dict[str, Any]:
    api_health_url = urljoin(f"{_api_origin(api_base)}/", "health")
    api_health = _probe_json(api_health_url)
    web_ready = _probe_web(web_base)
    started: dict[str, int] = {}
    started_commands: dict[str, list[str]] = {}
    root = _project_root()

    if (
        api_health is not None
        and os.environ.get("VISUAL_DIRECTOR_INSTALL_ROOT")
        and str(api_health.get("application_version") or "") != application_version()
    ):
        raise CliError(
            "core_version_mismatch",
            "The running Visual Director API is not the installed version. Stop the old local service, then retry.",
            exit_code=3,
            retryable=True,
            details={
                "installed_version": application_version(),
                "running_version": api_health.get("application_version"),
                "api_base": api_base,
            },
        )

    if api_health is None:
        api_dir = root / "apps" / "api"
        if not (api_dir / "pyproject.toml").exists():
            raise CliError(
                "project_layout_missing",
                "找不到视觉主编 API 目录；请从完整 GitHub 仓库运行",
                exit_code=2,
                details={"expected": str(api_dir)},
            )
        api_command = [
            sys.executable,
            "-m",
            "uvicorn",
            "visual_director.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(_port_from_url(_api_origin(api_base), 8000)),
        ]
        started["api"] = _spawn_detached(
            api_command,
            cwd=api_dir,
            log_name="api.log",
        )
        started_commands["api"] = api_command
        _wait_until(lambda: _probe_json(api_health_url) is not None, timeout=timeout, label="API")
        api_health = _probe_json(api_health_url)

    if not web_ready:
        web_dir = root / "apps" / "web"
        pnpm_command = _pnpm_command()
        if not pnpm_command:
            raise CliError(
                "pnpm_not_found",
                "未找到 pnpm，暂时无法启动排版工作台",
                exit_code=2,
                details={"action": "安装 pnpm 后重新执行 visual-director serve"},
            )
        if not (web_dir / "node_modules").exists():
            raise CliError(
                "web_dependencies_missing",
                "工作台依赖尚未安装",
                exit_code=2,
                details={"action": f"在 {web_dir} 执行 pnpm install"},
            )
        port = str(_port_from_url(web_base, 3000))
        # Alpha uses Next development mode so the API base is resolved for the
        # current local run. Reusing a production build can preserve an old
        # NEXT_PUBLIC_API_BASE_URL and yield a valid page that cannot load its task.
        command = [*pnpm_command, "dev", "-H", "127.0.0.1", "-p", port]
        started["web"] = _spawn_detached(
            command,
            cwd=web_dir,
            log_name="web.log",
            extra_env={"NEXT_PUBLIC_API_BASE_URL": api_base},
        )
        started_commands["web"] = command
        _wait_until(lambda: _probe_web(web_base), timeout=timeout, label="Web 工作台")
        web_ready = True

    if started:
        previous = _read_runtime_state()
        previous_processes = previous.get("processes", {}) if isinstance(previous.get("processes"), dict) else {}
        previous_commands = previous.get("commands", {}) if isinstance(previous.get("commands"), dict) else {}
        if previous.get("api_base") != api_base or previous.get("web_base") != web_base:
            previous_processes = {}
            previous_commands = {}
        state = {
            "schema_version": "runtime_state.v0.2",
            "started_at": datetime.now(UTC).isoformat(),
            "processes": previous_processes | started,
            "commands": previous_commands | started_commands,
            "api_base": api_base,
            "web_base": web_base,
        }
        _runtime_state_path().write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return {"api_health": api_health or {}, "web_ready": web_ready, "started": started}


def _port_from_url(url: str, default: int) -> int:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.port or default


def _process_command_line(pid: int) -> str | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        script = (
            f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}' -ErrorAction SilentlyContinue; "
            "if ($null -ne $p) { [Console]::Out.Write($p.CommandLine) }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
        value = result.stdout.strip()
        return value or None
    proc_cmdline = Path(f"/proc/{pid}/cmdline")
    if proc_cmdline.is_file():
        try:
            return proc_cmdline.read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace").strip() or None
        except OSError:
            return None
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    )
    return result.stdout.strip() or None


def _command_matches_service(service: str, command_line: str) -> bool:
    normalized = command_line.lower().replace("\\", "/")
    if service == "api":
        return "uvicorn" in normalized and "visual_director.main:app" in normalized
    if service == "web":
        return "pnpm" in normalized and " dev" in normalized
    return False


def _terminate_process_tree(pid: int) -> tuple[bool, str]:
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        message = (result.stdout or result.stderr).strip()
        return result.returncode == 0, message
    try:
        os.killpg(os.getpgid(pid), 15)
    except (ProcessLookupError, PermissionError, OSError) as exc:
        return False, str(exc)
    return True, "terminated"


def _stop_services() -> tuple[dict[str, Any], int]:
    state = _read_runtime_state()
    processes = state.get("processes", {}) if isinstance(state.get("processes"), dict) else {}
    if not processes:
        return {
            "ok": True,
            "schema_version": "stop_result.v0.1",
            "stopped": {},
            "already_stopped": True,
            "refused": {},
        }, 0

    stopped: dict[str, int] = {}
    absent: dict[str, int] = {}
    refused: dict[str, dict[str, Any]] = {}
    remaining = dict(processes)
    for service, raw_pid in processes.items():
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            refused[service] = {"pid": raw_pid, "reason": "invalid_pid"}
            continue
        command_line = _process_command_line(pid)
        if command_line is None:
            absent[service] = pid
            remaining.pop(service, None)
            continue
        if not _command_matches_service(service, command_line):
            refused[service] = {
                "pid": pid,
                "reason": "process_identity_mismatch",
                "command_line": command_line,
            }
            continue
        success, message = _terminate_process_tree(pid)
        if success:
            stopped[service] = pid
            remaining.pop(service, None)
        else:
            refused[service] = {"pid": pid, "reason": "termination_failed", "message": message}

    state["processes"] = remaining
    if remaining:
        _runtime_state_path().write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    elif _runtime_state_path().exists():
        _runtime_state_path().unlink()
    payload = {
        "ok": not refused,
        "schema_version": "stop_result.v0.1",
        "stopped": stopped,
        "not_running": absent,
        "already_stopped": not stopped and bool(absent),
        "refused": refused,
    }
    return payload, 0 if not refused else 6


def _doctor(api_base: str, web_base: str) -> tuple[dict[str, Any], int]:
    api_health = _probe_json(urljoin(f"{_api_origin(api_base)}/", "health"))
    web_ready = _probe_web(web_base)
    installation = _installation_summary()
    running_version = (
        str((api_health or {}).get("application_version") or "")
        if api_health is not None
        else None
    )
    version_match = (
        running_version == installation["version"]
        if api_health is not None and installation["persistent"]
        else api_health is not None
    )
    installation["running_version"] = running_version
    installation["version_match"] = version_match
    wenyan_status = (
        # Wenyan's first version probe can take several seconds on Windows,
        # especially when the executable is a global npm .cmd shim.
        _probe_json(f"{api_base.rstrip('/')}/publishers/wenyan/status", timeout=10)
        if api_health is not None
        else None
    )
    warnings: list[str] = []
    if api_health is None:
        warnings.append("core_api_not_running")
    elif installation["persistent"] and not version_match:
        warnings.append("core_version_mismatch")
    if not web_ready:
        warnings.append("workbench_not_running")
    if _pnpm_command() is None:
        warnings.append("pnpm_not_found")
    image_provider = str((api_health or {}).get("image_provider") or "none")
    text_planner_provider = str((api_health or {}).get("text_planner_provider") or "none")
    text_planner_configured = bool((api_health or {}).get("text_planner_configured", False))
    if image_provider == "mock":
        warnings.append("image_generation_mock_only")
    elif image_provider == "manual":
        warnings.append("image_generation_manual_only")
    if text_planner_provider == "mock_text_planner":
        warnings.append("text_planning_rule_fallback")
    elif text_planner_provider not in {"none", ""} and not text_planner_configured:
        warnings.append("text_planning_not_configured")
    core_ready = api_health is not None and version_match
    ok = core_ready and web_ready
    payload = {
        "ok": ok,
        "schema_version": "doctor_result.v0.1",
        "core_ready": core_ready,
        "workbench_ready": web_ready,
        "installation": installation,
        "capabilities": {
            "image_generation": bool(
                (api_health or {}).get("image_provider_configured", False)
                and image_provider not in {"none", "mock"}
            ),
            "mock_image_candidates": image_provider == "mock",
            "host_agent_text_planning": api_health is not None,
            "ai_text_planning": bool(
                text_planner_configured and text_planner_provider != "mock_text_planner"
            ),
            "rule_text_planning": text_planner_provider == "mock_text_planner",
            "wechat_draft": bool((wenyan_status or {}).get("ready", False)),
            "rich_copy": api_health is not None,
            "bundle_export": api_health is not None,
        },
        "planners": {
            "text": {
                "provider": text_planner_provider,
                "model": (api_health or {}).get("text_planner_model"),
                "configured": text_planner_configured,
            }
        },
        "publishers": {"wenyan": wenyan_status},
        "warnings": warnings,
        "api_base": api_base,
        "web_base": web_base,
    }
    return payload, 0 if ok else 3


def _default_task_idempotency_key(args: argparse.Namespace, markdown_path: Path) -> str:
    if args.idempotency_key:
        return str(args.idempotency_key)
    if getattr(args, "new_task", False):
        return f"cli-task-{uuid.uuid4()}"
    digest = hashlib.sha256()
    digest.update(markdown_path.read_bytes())
    digest.update(b"\0")
    digest.update(str(args.account_id).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(args.article_type or "auto").encode("utf-8"))
    return f"cli-task-{digest.hexdigest()}"


def _resolve_planner(requested: str, api_health: dict[str, Any]) -> str:
    if requested in {"rule", "intelligent"}:
        return requested
    return "intelligent" if api_health.get("text_planner_configured") else "rule"


def _get_task_payload(api_base: str, task_id: str) -> dict[str, Any]:
    return _request_json(
        "GET",
        f"{api_base.rstrip('/')}/article-tasks/{task_id}",
        timeout=10,
    )


def _wait_for_plans(api_base: str, task_id: str, *, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_status = "unknown"
    while time.monotonic() < deadline:
        payload = _get_task_payload(api_base, task_id)
        task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
        last_status = str(task.get("status") or "unknown")
        if last_status in {
            "plans_ready",
            "plan_selected",
            "images_review",
            "publication_frozen",
            "mock_draft_created",
        }:
            return payload
        if last_status == "failed":
            raise CliError(
                "plan_generation_failed",
                "Visual plan generation failed",
                exit_code=5,
                details={"task_id": task_id, "last_error": payload.get("last_error")},
            )
        time.sleep(0.5)
    raise CliError(
        "plan_generation_timeout",
        f"Visual plans were not ready within {int(timeout)} seconds",
        exit_code=5,
        retryable=True,
        details={"task_id": task_id, "last_status": last_status},
    )


def _create_task(args: argparse.Namespace) -> dict[str, Any]:
    markdown_path = Path(args.file).expanduser().resolve()
    if not markdown_path.exists() or not markdown_path.is_file():
        raise CliError(
            "input_file_not_found",
            "找不到 Markdown 文件",
            exit_code=2,
            details={"path": str(markdown_path)},
        )
    if markdown_path.suffix.lower() not in {".md", ".markdown"}:
        raise CliError("unsupported_media_type", "只支持 .md 或 .markdown 文件", exit_code=2)
    if markdown_path.stat().st_size > 2 * 1024 * 1024:
        raise CliError("file_too_large", "Markdown 文件不能超过 2MB", exit_code=2)

    if not args.no_start:
        services = _ensure_services(args.api_base, args.web_base, timeout=args.start_timeout)
        api_health = services.get("api_health", {})
    else:
        api_health = _probe_json(urljoin(f"{_api_origin(args.api_base)}/", "health")) or {}

    body, boundary = _multipart_markdown(
        markdown_path,
        article_type=args.article_type,
        account_id=args.account_id,
    )
    payload = _request_json(
        "POST",
        f"{args.api_base.rstrip('/')}/article-tasks",
        body=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Idempotency-Key": _default_task_idempotency_key(args, markdown_path),
        },
        timeout=30,
    )
    task = payload.get("task")
    summary = payload.get("input_summary")
    if not isinstance(task, dict) or not isinstance(summary, dict):
        raise CliError("invalid_service_response", "任务创建响应缺少必要字段", exit_code=3)
    preflight = summary.get("preflight_report") if isinstance(summary.get("preflight_report"), dict) else {}
    planning_allowed = bool(preflight.get("planning_allowed", False))
    task_id = str(task.get("id") or "")
    final_task = task
    plans_generated = False
    planner = None
    auto_plan = bool(args.auto_plan and planning_allowed)
    status = str(task.get("status") or "created")
    if auto_plan and status == "created":
        planner = _resolve_planner(args.planner, api_health)
        generation_body = json.dumps(
            {
                "mode": "start",
                "expected_task_version": task.get("version"),
                "planner": planner,
            }
        ).encode("utf-8")
        _request_json(
            "POST",
            f"{args.api_base.rstrip('/')}/article-tasks/{task_id}/generate-plans",
            body=generation_body,
            headers={"Content-Type": "application/json"},
            timeout=args.plan_timeout,
        )
        plans_generated = True
        detail = _wait_for_plans(args.api_base, task_id, timeout=args.plan_timeout)
        final_task = detail.get("task") if isinstance(detail.get("task"), dict) else task
    elif auto_plan and status == "analyzing":
        planner = _resolve_planner(args.planner, api_health)
        detail = _wait_for_plans(args.api_base, task_id, timeout=args.plan_timeout)
        final_task = detail.get("task") if isinstance(detail.get("task"), dict) else task
    elif auto_plan and status in {"plans_ready", "plan_selected", "images_review", "publication_frozen", "mock_draft_created"}:
        planner = "existing"

    review_path = str(payload.get("review_path") or f'/tasks/{task.get("id", "")}')
    review_url = f"{args.web_base.rstrip('/')}/{review_path.lstrip('/')}"
    opened = False
    if args.open:
        opened = bool(webbrowser.open(review_url, new=2))
    if not planning_allowed:
        next_action = "fix_source"
    elif not auto_plan and str(final_task.get("status") or "") == "created":
        next_action = "generate_editorial_brief"
    else:
        next_action = "human_review"
    return {
        "ok": True,
        "schema_version": "task_create_result.v0.2",
        "task_id": task_id,
        "status": final_task.get("status"),
        "preflight_status": preflight.get("status"),
        "planning_allowed": planning_allowed,
        "draft_creation_allowed": bool(preflight.get("draft_creation_allowed", False)),
        "idempotency_replayed": bool(payload.get("idempotency_replayed", False)),
        "plans_generated": plans_generated,
        "planner": planner,
        "review_url": review_url,
        "opened": opened,
        "next_action": next_action,
    }


def _task_context(args: argparse.Namespace) -> dict[str, Any]:
    payload = _request_json(
        "GET",
        f"{args.api_base.rstrip('/')}/article-tasks/{args.task_id}/editorial-brief/context",
        timeout=30,
    )
    context = payload.get("context")
    if not isinstance(context, dict):
        raise CliError("invalid_service_response", "规划上下文响应缺少 context", exit_code=3)
    return {
        "ok": True,
        "schema_version": "task_planner_context_result.v0.1",
        "task_id": payload.get("task_id", args.task_id),
        "expected_task_version": payload.get("expected_task_version"),
        "context": context,
        "next_action": "write_editorial_brief",
    }


def _load_editorial_brief(path_value: str) -> tuple[Path, dict[str, Any]]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise CliError(
            "brief_file_not_found",
            "找不到 EditorialBrief JSON 文件",
            exit_code=2,
            details={"path": str(path)},
        )
    if path.stat().st_size > 256 * 1024:
        raise CliError("brief_file_too_large", "EditorialBrief JSON 不能超过 256KB", exit_code=2)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise CliError("invalid_brief_encoding", "EditorialBrief 必须使用 UTF-8 编码", exit_code=2) from exc
    except json.JSONDecodeError as exc:
        raise CliError(
            "invalid_brief_json",
            "EditorialBrief 文件不是合法 JSON",
            exit_code=2,
            details={"line": exc.lineno, "column": exc.colno},
        ) from exc
    if not isinstance(raw, dict):
        raise CliError("invalid_brief_json", "EditorialBrief 顶层必须是 JSON 对象", exit_code=2)
    return path, raw


def _plan_task(args: argparse.Namespace) -> dict[str, Any]:
    if not args.no_start:
        _ensure_services(args.api_base, args.web_base, timeout=args.start_timeout)
    _, brief = _load_editorial_brief(args.brief)
    generation_body = json.dumps(
        {
            "mode": "start",
            "expected_task_version": args.expected_task_version,
            "planner": "host_agent",
            "editorial_brief": brief,
            "host_model": args.host_model,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    generation = _request_json(
        "POST",
        f"{args.api_base.rstrip('/')}/article-tasks/{args.task_id}/generate-plans",
        body=generation_body,
        headers={"Content-Type": "application/json"},
        timeout=args.plan_timeout,
    )
    detail = _wait_for_plans(args.api_base, args.task_id, timeout=args.plan_timeout)
    task = detail.get("task") if isinstance(detail.get("task"), dict) else {}
    metadata = (
        generation.get("planner_metadata")
        if isinstance(generation.get("planner_metadata"), dict)
        else {}
    )
    review_url = f"{args.web_base.rstrip('/')}/tasks/{args.task_id}"
    opened = bool(webbrowser.open(review_url, new=2)) if args.open else False
    return {
        "ok": True,
        "schema_version": "task_plan_result.v0.1",
        "task_id": args.task_id,
        "status": task.get("status"),
        "planner": "host_agent",
        "planner_provider": metadata.get("provider"),
        "planner_model": metadata.get("model"),
        "fallback_used": bool(metadata.get("fallback_used", False)),
        "fallback_reason": metadata.get("fallback_reason"),
        "normalization_count": int(metadata.get("normalization_count") or 0),
        "normalization_adjustments": metadata.get("normalization_adjustments") or [],
        "review_url": review_url,
        "opened": opened,
        "next_action": "human_review",
    }


def _task_status(args: argparse.Namespace) -> dict[str, Any]:
    payload = _request_json(
        "GET", f"{args.api_base.rstrip('/')}/article-tasks/{args.task_id}", timeout=10
    )
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    summary = payload.get("input_summary") if isinstance(payload.get("input_summary"), dict) else {}
    preflight = summary.get("preflight_report") if isinstance(summary.get("preflight_report"), dict) else {}
    status = str(task.get("status") or "unknown")
    if preflight.get("status") == "BLOCK":
        next_action = "fix_source"
    elif status in {"publication_frozen", "mock_draft_created"}:
        next_action = "mock_draft_created" if status == "mock_draft_created" else "ready_to_confirm"
    elif status == "failed":
        next_action = "failed"
    else:
        next_action = "human_review"
    return {
        "ok": True,
        "schema_version": "task_status_result.v0.1",
        "task_id": task.get("id", args.task_id),
        "status": status,
        "preflight_status": preflight.get("status"),
        "available_actions": payload.get("available_actions", []),
        "next_action": next_action,
        "review_url": f"{args.web_base.rstrip('/')}/tasks/{args.task_id}",
        "last_error": payload.get("last_error"),
    }


def _emit(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return
    if payload.get("ok"):
        for key, value in payload.items():
            if key not in {"ok", "schema_version"}:
                print(f"{key}: {value}")
    else:
        error = payload.get("error", {})
        print(f"错误 [{error.get('code', 'unknown')}]: {error.get('message', '')}", file=sys.stderr)


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-base", default=os.environ.get("VISUAL_DIRECTOR_API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--web-base", default=os.environ.get("VISUAL_DIRECTOR_WEB_BASE", DEFAULT_WEB_BASE))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="visual-director", description="公众号视觉主编本地 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="检查本地运行状态")
    _add_connection_args(doctor)
    doctor.add_argument("--json", action="store_true", dest="json_output")

    serve = subparsers.add_parser("serve", help="启动本地 API 与工作台")
    _add_connection_args(serve)
    serve.add_argument("--detach", action="store_true", default=True)
    serve.add_argument("--start-timeout", type=float, default=45)
    serve.add_argument("--json", action="store_true", dest="json_output")

    stop = subparsers.add_parser("stop", help="Stop services started by this CLI")
    stop.add_argument("--json", action="store_true", dest="json_output")

    task = subparsers.add_parser("task", help="管理视觉任务")
    task_subparsers = task.add_subparsers(dest="task_command", required=True)

    create = task_subparsers.add_parser("create", help="从 Markdown 创建任务")
    _add_connection_args(create)
    create.add_argument("--file", required=True)
    create.add_argument(
        "--article-type",
        choices=["data_policy", "viewpoint_trend", "tutorial_steps", "lively_growth"],
    )
    create.add_argument("--account-id", default="default")
    create.add_argument("--idempotency-key")
    create.add_argument("--new-task", action="store_true", help="Create another task even if the input is unchanged")
    create.add_argument(
        "--planner",
        choices=["auto", "rule", "intelligent"],
        default="auto",
        help="Planner used before opening the workbench",
    )
    create.add_argument("--no-plan", action="store_false", dest="auto_plan")
    create.set_defaults(auto_plan=True)
    create.add_argument("--plan-timeout", type=float, default=120)
    create.add_argument("--open", action="store_true")
    create.add_argument("--no-start", action="store_true")
    create.add_argument("--start-timeout", type=float, default=45)
    create.add_argument("--json", action="store_true", dest="json_output")

    status = task_subparsers.add_parser("status", help="查看任务状态")
    _add_connection_args(status)
    status.add_argument("task_id")
    status.add_argument("--json", action="store_true", dest="json_output")

    context = task_subparsers.add_parser("context", help="读取宿主 Agent 的安全规划上下文")
    _add_connection_args(context)
    context.add_argument("task_id")
    context.add_argument("--json", action="store_true", dest="json_output")

    plan = task_subparsers.add_parser("plan", help="使用宿主 Agent 生成的 EditorialBrief 生成方案")
    _add_connection_args(plan)
    plan.add_argument("task_id")
    plan.add_argument("--brief", required=True)
    plan.add_argument("--expected-task-version", required=True, type=int)
    plan.add_argument("--host-model", default="host_managed")
    plan.add_argument("--plan-timeout", type=float, default=120)
    plan.add_argument("--open", action="store_true")
    plan.add_argument("--no-start", action="store_true")
    plan.add_argument("--start-timeout", type=float, default=45)
    plan.add_argument("--json", action="store_true", dest="json_output")

    open_task = task_subparsers.add_parser("open", help="打开已有任务")
    _add_connection_args(open_task)
    open_task.add_argument("task_id")
    open_task.add_argument("--json", action="store_true", dest="json_output")

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            payload, exit_code = _doctor(args.api_base, args.web_base)
        elif args.command == "serve":
            services = _ensure_services(args.api_base, args.web_base, timeout=args.start_timeout)
            payload = {
                "ok": True,
                "schema_version": "serve_result.v0.1",
                "api_base": args.api_base,
                "web_base": args.web_base,
                "started": services["started"],
                "reused": not bool(services["started"]),
            }
            exit_code = 0
        elif args.command == "stop":
            payload, exit_code = _stop_services()
        elif args.command == "task" and args.task_command == "create":
            payload, exit_code = _create_task(args), 0
        elif args.command == "task" and args.task_command == "status":
            payload, exit_code = _task_status(args), 0
        elif args.command == "task" and args.task_command == "context":
            payload, exit_code = _task_context(args), 0
        elif args.command == "task" and args.task_command == "plan":
            payload, exit_code = _plan_task(args), 0
        elif args.command == "task" and args.task_command == "open":
            review_url = f"{args.web_base.rstrip('/')}/tasks/{args.task_id}"
            opened = bool(webbrowser.open(review_url, new=2))
            payload = {
                "ok": True,
                "schema_version": "task_open_result.v0.1",
                "task_id": args.task_id,
                "review_url": review_url,
                "opened": opened,
            }
            exit_code = 0
        else:
            parser.error("未知命令")
            return 2
    except CliError as exc:
        payload, exit_code = exc.payload(), exc.exit_code
    _emit(payload, json_output=bool(getattr(args, "json_output", False)))
    return exit_code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
