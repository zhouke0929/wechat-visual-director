# Install WeChat Visual Director for an Agent

Use this file when a user gives you this repository and asks you to install,
upgrade, diagnose, or open WeChat Visual Director. The user should not need to
know the Python, pnpm, or process-management details.

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
2. When installing or explicitly upgrading from this repository, use the platform entry:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\bootstrap.ps1"
```

```bash
bash scripts/bootstrap.sh
```

3. Parse only the final JSON written to stdout. Progress text is written to
   stderr. Do not infer readiness merely because a port or browser page opens.
4. Success requires all of the following:
   - `ok=true`;
   - `installation.persistent=true`;
   - `installation.version_match=true`;
   - `capabilities.host_skill_registered=true`.
5. Follow `next_action`:
   - `create_article`: accept the user's topic, sources, or Markdown and use the
     registered `wechat-visual-director` Skill;
   - `configure_image_provider` or `configure_wechat_publisher`: give the user
     `settings_url`. The user enters private credentials in the local page;
     never ask them to paste those values into the conversation.
6. After first installation, tell the user to start a new host conversation if
   the host only discovers Skills at startup.

## Optional Wenyan publisher

The base installer does not install Node.js or a global npm package. This is an
intentional boundary: layout, preview, rich copy, and bundle export work without
Wenyan. Direct WeChat draft delivery requires the user to opt in to a separate
third-party publisher.

When the user asks for full WeChat draft delivery:

1. Run `doctor --json` and inspect `publishers.wenyan` and
   `capabilities.wechat_draft`.
2. If Wenyan is missing, tell the user that it is not part of the base install.
   Ask them to approve the global npm install, or have them run it themselves:

```powershell
node --version
npm --version
npm install -g @wenyan-md/cli@2.0.11
wenyan --version
```

3. Never claim that the publisher is ready merely because npm exited with code
   zero. Reopen the terminal if needed and confirm `wenyan --version`, then run
   `doctor --json` again.
4. Give the user `settings_url`. The user must enter AppID and AppSecret in the
   local page and confirm the current public egress IP is on the WeChat
   developer allowlist. Never request those credentials in chat.
5. Readiness requires `publishers.wenyan.ready=true` and a successful local
   connection probe. Creating the final draft still requires explicit approval
   in the workbench.

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
