# 完整产品安装与恢复

wechat-visual-director 由轻量 Skill 与本地工作台组成。普通用户安装必须同时完成两者；不要只复制 Skill，也不要克隆源码作为运行环境。

## 安装或升级

1. Windows 若 `%LOCALAPPDATA%\wechat-visual-director\visual-director.ps1` 已存在，macOS 若 `~/Library/Application Support/wechat-visual-director/visual-director` 已存在，先运行 `doctor --json`。只有入口不存在或用户明确要求升级时才下载安装。
2. Windows x64 使用固定 Agent 安装器入口。它会读取当前公开版本、校验 Release 的 SHA-256，安装内置 Python、后端和生产工作台，并注册轻量 Skill：

```powershell
$installer = Join-Path $env:TEMP "wechat-visual-director-install.ps1"
Invoke-WebRequest "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/scripts/install-release.ps1" -OutFile $installer
powershell -NoProfile -ExecutionPolicy Bypass -File $installer
```

3. macOS 使用对应入口，脚本自动识别 Apple Silicon 或 Intel：

```bash
installer="$(mktemp -t wechat-visual-director-install.XXXXXX)"
curl -fsSL "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/scripts/install-release.sh" -o "$installer"
bash "$installer"
```

4. 只解析 stdout 的最终 JSON。成功必须满足 `ok=true`、`runtime_mode=bundled_python`、`bundled_runtime=true`、`installation.persistent=true`、`installation.version_match=true`、`installation.runtime_match=true` 和 `capabilities.host_skill_registered=true`。
5. 安装结果提供 `workbench_url` 时立即打开。仅在 `first_install=true` 时按 `first_run_guide` 返回不超过五行的首次教程；升级、修复和既有安装检查不重复。
6. 普通安装不得安装 Git、Homebrew、系统 Python、Node.js、pnpm 或 Wenyan，也不得手动启动 `uvicorn`、Vite 或源码开发服务。

只有用户明确要求源码开发或审计，并已经提供独立源码检出时，才运行该源码根目录的 `scripts/bootstrap.ps1` 或 `scripts/bootstrap.sh`。当前 Skill 目录永远不视为源码仓库。

## 私密配置

图片 API 与微信公众号凭据只允许用户本人在安装结果返回的 `settings_url` 中填写。不要读取、回显或要求用户把 API Key、AppSecret、Cookie 或 Token 粘贴到对话。

## 卸载

只有用户明确要求时才卸载。默认卸载保留任务、图片与私密配置；彻底清理必须额外得到用户明确要求并使用 `-Purge`（Windows）或 `--purge`（macOS）。卸载必须同时移除 Codex、通用 Agent 和 OpenCode 的 Skill 注册，且不得删除用户提供的源码仓库。
