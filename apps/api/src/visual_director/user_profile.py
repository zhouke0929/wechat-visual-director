"""One persistent user dataset across Windows hosts and program installations.

No directory guessing or database merging. Called by the packaged installer only;
legacy sources are copied, verified, and retained, never deleted.
"""
from __future__ import annotations

import json
import hashlib
import os
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .data_recovery import DataRecoveryError, _copy_dataset
from .upgrade_data import dataset_snapshot

SCHEMA = "user_profile.v1"


def _asset_signature(assets: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(assets, sort_keys=True).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def profile_lock(home: Path):
    home.mkdir(parents=True, exist_ok=True)
    with (home / ".profile.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DataRecoveryError("user_profile_busy", "另一安装操作正在使用共享数据，请稍后重试") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_user_profile(home: Path) -> dict[str, Any] | None:
    home = home.resolve()
    file = home / "profile.json"
    if not file.exists():
        return None
    try:
        value = json.loads(file.read_text(encoding="utf-8-sig"))
        if value["schema_version"] != SCHEMA or not value["profile_id"]:
            raise ValueError("schema")
        for key, relative in (("data_root", "data"), ("runtime_root", "runtime"),
                              ("config_file", "config/.env.local")):
            if Path(value[key]).resolve() != home / relative:
                raise ValueError("path")
        if not (home / "data/visual-director.db").is_file():
            raise DataRecoveryError("shared_data_missing", "登记的历史数据库缺失，已停止，未创建空库",
                                    details={"data_root": str(home / "data")})
        if not dataset_snapshot(home / "data")["healthy"]:
            raise ValueError("database")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise DataRecoveryError("user_profile_invalid", "共享数据登记无效，已停止，未回退到空数据库") from exc
    return value


def prepare_user_profile(home: Path, install_root: Path) -> dict[str, Any]:
    home, install_root = home.resolve(), install_root.resolve()
    with profile_lock(home):
        manifest = install_root / "install.json"
        metadata = json.loads(manifest.read_text(encoding="utf-8-sig")) if manifest.is_file() else {}
        if metadata.get("user_data_home") and Path(metadata["user_data_home"]).resolve() != home:
            raise DataRecoveryError("shared_data_source_confirmation_required", "这套程序已绑定另一份共享历史，请先确认来源，不自动切换")
        existing = read_user_profile(home)
        if existing:
            legacy = install_root / "data"
            if (legacy / "visual-director.db").is_file() and legacy != Path(existing["data_root"]):
                snapshot = dataset_snapshot(legacy)
                known = existing.get("legacy_source") == str(legacy)
                unchanged = (snapshot["database_sha256"] == existing.get("legacy_database_sha256") and
                             _asset_signature(snapshot["assets"]) == existing.get("legacy_assets_sha256"))
                if (snapshot["task_count"] or snapshot["assets"]) and not (known and unchanged):
                    raise DataRecoveryError("shared_history_conflict", "这套程序还有另一份历史，未自动覆盖或合并；请先确认如何保留",
                                            details={"legacy_data_root": str(legacy), "legacy_task_count": snapshot["task_count"],
                                                     "shared_data_root": existing["data_root"], "action": "review_legacy_history"})
            return {"profile": existing, "created": False, "copied_legacy": False}
        if (home / "data").exists() or (home / "config").exists():
            raise DataRecoveryError("shared_data_unregistered", "发现未登记的共享数据，需确认恢复，不能重新初始化",
                                    details={"user_data_home": str(home)})
        legacy = install_root / "data"
        if manifest.is_file():
            recorded = Path(metadata.get("install_root", str(install_root)))
            previous = Path(metadata["data_root"])
            if os.path.normcase(os.path.abspath(previous)) != os.path.normcase(os.path.abspath(recorded / "data")):
                raise DataRecoveryError("shared_data_source_confirmation_required", "现有安装使用自定义数据位置，请先确认来源")
            if metadata.get("config_file") and os.path.normcase(os.path.abspath(metadata["config_file"])) != os.path.normcase(
                os.path.abspath(recorded / "config/.env.local")
            ):
                raise DataRecoveryError("shared_data_source_confirmation_required", "现有安装使用自定义配置位置，请先确认来源")
        before = dataset_snapshot(legacy)
        if not before["exists"] and before["assets"]:
            raise DataRecoveryError("legacy_database_missing", "旧数据含图片或主题但数据库缺失，请先恢复，不创建空库")
        stage = home / f".initialize-{uuid.uuid4().hex}"
        stage.mkdir()
        try:
            if before["exists"]:
                _copy_dataset(legacy, stage / "data")
            else:
                (stage / "data").mkdir()
                sqlite3.connect(stage / "data/visual-director.db").close()
            staged = dataset_snapshot(stage / "data")
            if staged["task_ids"] != before["task_ids"] or staged["assets"] != before["assets"]:
                raise DataRecoveryError("shared_data_copy_failed", "历史任务、图片或主题复制校验未通过")
            config_dir = install_root / "config"
            if config_dir.is_dir():
                # Do not follow redirected files or copy arbitrary outside trees.
                if any(p.is_symlink() for p in config_dir.rglob("*")):
                    raise DataRecoveryError("shared_config_redirected", "旧配置目录包含重定向，需人工确认")
                shutil.copytree(config_dir, stage / "config")
            else:
                (stage / "config").mkdir()
            if not (stage / "config/.env.local").exists():
                (stage / "config/.env.local").touch()
            after = dataset_snapshot(legacy)
            if after["task_ids"] != before["task_ids"] or after["assets"] != before["assets"] or after["database_sha256"] != before["database_sha256"]:
                raise DataRecoveryError("legacy_data_changed", "复制期间旧数据发生变化，请关闭旧工作台后重试")
            # Rename complete trees, then publish the registry last. A crash never
            # makes an empty replacement database look like a successful migration.
            os.replace(stage / "data", home / "data")
            os.replace(stage / "config", home / "config")
            (home / "runtime").mkdir(exist_ok=True)
            profile = {"schema_version": SCHEMA, "profile_id": str(uuid.uuid4()),
                       "user_data_home": str(home), "data_root": str(home / "data"),
                       "config_file": str(home / "config/.env.local"), "runtime_root": str(home / "runtime"),
                       "legacy_source": str(legacy) if before["exists"] else None,
                       "active_install_root": None, "legacy_database_sha256": before["database_sha256"],
                       "legacy_assets_sha256": _asset_signature(before["assets"]),
                       "api_base": "http://127.0.0.1:8000/api/v1", "web_base": "http://127.0.0.1:8000"}
            _atomic_json(home / "profile.json", profile)
            return {"profile": profile, "created": True, "copied_legacy": before["exists"],
                    "preserved_source": str(legacy), "task_count": staged["task_count"]}
        finally:
            shutil.rmtree(stage, ignore_errors=True)


def register_user_install(home: Path, install_root: Path, *, api_base: str | None = None,
                          web_base: str | None = None) -> dict[str, Any]:
    home, install_root = home.resolve(), install_root.resolve()
    with profile_lock(home):
        profile = read_user_profile(home)
        if profile is None:
            raise DataRecoveryError("user_profile_missing", "共享数据尚未准备完成")
        manifest = json.loads((install_root / "install.json").read_text(encoding="utf-8-sig"))
        if Path(manifest["data_root"]).resolve() != Path(profile["data_root"]):
            raise DataRecoveryError("shared_data_binding_mismatch", "程序未绑定同一份历史数据，拒绝登记")
        if manifest.get("user_profile_id") and manifest["user_profile_id"] != profile["profile_id"]:
            raise DataRecoveryError("shared_data_binding_mismatch", "共享历史身份不一致，拒绝登记")
        for address in (api_base, web_base):
            if address:
                url = urlsplit(address)
                if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password:
                    raise DataRecoveryError("shared_runtime_not_local", "共享工作台只允许本地地址")
        profile["active_install_root"] = str(install_root)
        if api_base:
            profile["api_base"] = api_base
        if web_base:
            profile["web_base"] = web_base
        _atomic_json(home / "profile.json", profile)
        return profile
