# Install WeChat Visual Director for an Agent

Use this file when a user gives you this repository and asks you to install,
upgrade, diagnose, or open WeChat Visual Director. The user should not need to
know the Python or process-management details. Normal installation must not
invoke npm, pnpm, or install a global Node.js package.

## Safety boundary

- Work only from the repository URL or local source path supplied by the user.
- Never read, print, copy, or request API keys, AppSecret, cookies, or tokens in chat.
- Do not start `uvicorn`, `next dev`, `vite`, or a temporary clone manually.
- Do not delete the source repository. Installed program files live under
  `%LOCALAPPDATA%\wechat-visual-director` on Windows or
  `~/Library/Application Support/wechat-visual-director` on macOS.
- Creating a WeChat draft still requires explicit confirmation in the workbench;
  final mass publishing is outside this installer.

## Install or upgrade

1. If `%LOCALAPPDATA%\wechat-visual-director\visual-director.ps1` exists and the
   user did not ask to upgrade, run `doctor --json` first. A new conversation is
   not a reason to reinstall.
2. On Windows x64, prefer the fixed GitHub Release package. It already contains
   Python 3.11.9, backend dependencies, and the built workbench. Do not clone the
   repository and do not install Git, Python, Node.js, pnpm, or Wenyan for a normal
   user installation.

```powershell
$installer = Join-Path $env:TEMP "wechat-visual-director-install-alpha20.ps1"
Invoke-WebRequest "https://github.com/zhouke0929/wechat-visual-director/releases/download/v0.1.0-alpha.20/install-release.ps1" -OutFile $installer
powershell -NoProfile -ExecutionPolicy Bypass -File $installer
```

   Parse the final JSON. The release installer downloads both the x64 ZIP and its
   checksum, verifies SHA-256, extracts to a temporary directory, and then runs the
   same persistent bootstrap contract. Success additionally reports
   `runtime_mode=bundled_python` and `bundled_runtime=true`.

3. Only use the source bootstrap when the user explicitly requests source
   development/audit, supplies a local source checkout, or is using the macOS
   Technical Preview:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\bootstrap.ps1"
```

```bash
bash scripts/bootstrap.sh
```

4. Parse only the final JSON written to stdout. Progress text is written to
   stderr. Do not infer readiness merely because a port or browser page opens.
5. Success requires all of the following:
   - `ok=true`;
   - `installation.persistent=true`;
   - `installation.version_match=true`;
   - `capabilities.host_skill_registered=true`.
6. Follow `next_action`:
   - `create_article`: accept the user's topic, sources, or Markdown and use the
     registered `wechat-visual-director` Skill;
   - `configure_image_provider` or `configure_wechat_publisher`: give the user
     `settings_url`. The user enters private credentials in the local page;
     never ask them to paste those values into the conversation.
7. After first installation, tell the user to start a new host conversation if
   the host only discovers Skills at startup.

## Built-in WeChat publisher

The release contains a prebuilt workbench and a built-in publisher that calls
the official WeChat API directly. Do not install Node.js, Wenyan, or any global
npm package on the user's machine.

When the user asks for full WeChat draft delivery:

1. Run `doctor --json` and inspect `publishers.wechat` and
   `capabilities.wechat_draft`.
2. Give the user `settings_url`. The user must enter AppID and AppSecret in the
   local page and confirm the current public egress IP is on the WeChat
   developer allowlist. Never request those credentials in chat.
3. Readiness requires `publishers.wechat.ready=true` and a successful local
   connection probe. Access tokens are memory-only. Creating the final draft
   still requires explicit approval in the workbench.
4. A `wechat_draft_result_unknown` response must not be retried automatically.
   Ask the user to inspect the WeChat draft box first.

## Diagnose an existing installation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File \
  "$env:LOCALAPPDATA\wechat-visual-director\visual-director.ps1" doctor --json
```

Use the returned error code and action. Do not work around a version mismatch
by running the source API or Web project directly.

If tasks appear missing after a reinstall, do not move only the SQLite file.
Stop the service and run `data scan --json`, adding `--candidate <old-data-root>`
when the old source location is known. A dataset consists of the database,
`image-assets`, and `publication-assets`. Non-empty targets require explicit
`data recover --from <root> --activate --yes`; the command creates a backup first.

## Uninstall

Only uninstall when the user explicitly asks.

Preserve tasks, images, and private configuration so a later reinstall can
continue where the user stopped:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File \
  "$env:LOCALAPPDATA\wechat-visual-director\uninstall.ps1"
```

Permanently remove the installed program, tasks, images, and private
configuration only when the user explicitly requests a complete purge:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File \
  "$env:LOCALAPPDATA\wechat-visual-director\uninstall.ps1" -Purge
```

Both modes remove host Skill registrations. Neither mode may delete the Git
source repository supplied by the user.

On macOS use the stable `visual-director` and `uninstall.sh` files under the
Application Support install root. macOS support remains Technical Preview until
the release has passed a real-device end-to-end review.
