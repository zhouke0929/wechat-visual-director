# Install WeChat Visual Director for an Agent

This is the canonical one-link installation entry for the complete product. Use
it when a user gives you this document or repository and asks you to install,
upgrade, diagnose, or open WeChat Visual Director. A successful installation
must include both the lightweight Agent Skill and the local workbench; copying
the repository into a Skill directory is not a completed installation. The user
should not need to know the Python or process-management details. Normal
installation must not invoke npm, pnpm, or install a global Node.js package.

After a generic Skill installer copies the Skill, read its `SKILL.md` and run the
bundled `ensure-workbench` helper below to finish setup in the same turn. This
includes Codex's `skill-installer`: copying files is a step, not proof that the
workbench is ready. Do not edit the host's system installer. If the user explicitly
wants files only, or execution is unavailable, end with a useful handoff instead:
"公众号视觉主编已添加。接下来直接说‘打开公众号工作台’，或给出文章主题；第一次使用时会自动准备本地工作台。支持生图的 Agent 还可以生成正文配图和封面候选。"
Do not claim the workbench is ready without checking it. Do not require a new
conversation unless the host actually needs a reload. The distributable Skill is
at `skills/wechat-visual-director/`; read its opening onboarding instructions.
For installation or first use, run its `scripts/ensure-workbench.ps1` or
`scripts/ensure-workbench.sh` to install only if missing, start, check and open it.
The full-product installation flow below remains the preferred one-turn path.
If an existing installation needs an explicitly requested upgrade, use the
current Release installer below; the default ensure-workbench flow reuses an
existing installation and is not a substitute for that upgrade.

Do not pass the repository root to a generic Skill installer. The repository is
the development source tree, not the distributable Skill folder. The optional
Skill-only compatibility URL is
`https://github.com/zhouke0929/wechat-visual-director/tree/main/skills/wechat-visual-director`,
and its first-use helper completes the workbench later. Prefer the Release flow
below when you can complete the full installation in this turn.

## Safety boundary

- Work only from the repository URL or local source path supplied by the user.
- Never read, print, copy, or request API keys, AppSecret, cookies, or tokens in chat.
- Do not start `uvicorn`, `next dev`, `vite`, or a temporary clone manually.
- Do not delete the source repository. Installed program files live under
  `%LOCALAPPDATA%\wechat-visual-director` on Windows or
  `~/Library/Application Support/wechat-visual-director` on macOS.
- Creating a WeChat draft still requires explicit confirmation in the workbench;
  final mass publishing is outside this installer.

## Version selection: do not inherit a stale documentation pin

For a fresh installation or an explicit upgrade, the version source of truth is
`https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/VERSION`,
not a version copied from a README, search snippet, screenshot, old conversation,
or historical release note. Use the current `main/scripts/install-release.ps1`
or `main/scripts/install-release.sh` entry below, with no version override.
These installers resolve `main/VERSION` themselves and verify the matching
Release package's SHA-256. Do not reuse an installer downloaded for an old test.

Confirm that tag `v<version>` has a published Release with the package and checksum
for this machine. Do not use GitHub's `/releases/latest` as the only version
source: the project currently publishes prereleases. If VERSION and the available
assets disagree, or a download fails, report that installation is incomplete;
do not silently downgrade or fall back to a source checkout. If two reads disagree,
re-fetch the raw source or GitHub Contents API with cache revalidation rather than
trusting a cached rendered page.

After installation, compare the actual installed version in the result / doctor
output with the intended version as well as checking `version_match=true`.
That flag alone only establishes consistency within the installation; it does
not prove that the intended current public version was selected. Include the
actual installed version in the completion receipt.

Exceptions: honor a version explicitly requested by the user; ordinary reopening
reuses a healthy existing installation and is not a request to upgrade. Historical
documents under `docs/releases/` describe their own release, not today's default.

## Install or upgrade

1. If `%LOCALAPPDATA%\wechat-visual-director\visual-director.ps1` exists and the
   user did not ask to upgrade, run `doctor --json` first. A new conversation is
   not a reason to reinstall.
2. On Windows x64, use the stable Agent installer entry. It resolves the current
   public version and downloads the matching GitHub Release package. It contains
   Python 3.11.9, backend dependencies, and the built workbench. Do not clone the
   repository and do not install Git, Python, Node.js, pnpm, or Wenyan for a normal
   user installation.

```powershell
$installer = Join-Path $env:TEMP "wechat-visual-director-install.ps1"
Invoke-WebRequest "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/scripts/install-release.ps1" -OutFile $installer
powershell -NoProfile -ExecutionPolicy Bypass -File $installer
```

   Parse the final JSON. The release installer downloads both the x64 ZIP and its
   checksum, verifies SHA-256, extracts to a temporary directory, and then runs the
   same persistent bootstrap contract. Success additionally reports
   `runtime_mode=bundled_python` and `bundled_runtime=true`.

3. On macOS, use the self-contained Release installer. It detects Apple Silicon
   or Intel, downloads only the matching `tar.gz` and checksum, and installs the
   bundled Python runtime without Git, Homebrew, system Python, Node.js, pnpm, or
   Wenyan:

```bash
installer="$(mktemp -t wechat-visual-director-install.XXXXXX)"
curl -fsSL "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/scripts/install-release.sh" -o "$installer"
bash "$installer"
```

   Parse the final JSON and require `runtime_mode=bundled_python` and
   `bundled_runtime=true`. Open `workbench_url` with the default browser after the
   health check succeeds.

4. Only use the source bootstrap when the user explicitly requests source
   development/audit and supplies a complete local source checkout:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\bootstrap.ps1"
```

```bash
bash scripts/bootstrap.sh
```

5. Parse only the final JSON written to stdout. Progress text is written to
   stderr. Do not infer readiness merely because a port or browser page opens.
6. Success requires all of the following:
   - `ok=true`;
   - `installation.persistent=true`;
   - `installation.version_match=true`;
   - `installation.runtime_match=true`;
   - `capabilities.host_skill_registered=true`.
   The installer registers the same lightweight package under Codex, the generic
   Agent Skill directory, and OpenCode. It must not copy `apps/`, `docs/` or
   `.github/` into any Skill directory.
7. Follow `next_action`:
   - `create_article`: accept the user's topic, sources, or Markdown and use the
     registered `wechat-visual-director` Skill;
   - `configure_image_provider` or `configure_wechat_publisher`: give the user
     `settings_url`. The user enters private credentials in the local page;
     never ask them to paste those values into the conversation.
8. After successful installation or first-use setup, return a concise receipt
   instead of replying with only "installed". Keep it to no more than five lines
   and use `first_run_guide` from the bootstrap result when available. Tell the
   user, in their language:
   - they can ask for a WeChat article by topic or provide Markdown for typesetting;
     existing plain text or Markdown is given to the Agent for structure cleanup
     and semantic planning, not uploaded directly to the workbench;
   - the Agent will return a local workbench link for theme, image, and cover review;
   - if the current Agent supports native image generation, after confirming the
     theme they can ask it to generate and insert images for the current article;
   - private image API and WeChat credentials belong only in Local Settings, and
     the product creates drafts rather than mass publishing automatically.
   The homepage now shows its brief guide without an acknowledgement button.
   `onboarding_pending` remains a compatibility field, not a reason to repeat the
   tutorial. Use `first_run_guide` for installation or initial use, once per turn.
   Do not repeat it during ordinary reopening, upgrades, repairs, article work or
   image generation. Never acknowledge it on the user's behalf.
   A successful `command_completed=true` result needs no second setup invocation.
   Older releases without `onboarding_pending` still use `first_install`.
9. Open `workbench_url` immediately when it is returned. After first installation,
   tell the user to start a new host conversation only if that host discovers
   Skills at startup.

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
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\wechat-visual-director\visual-director.ps1" doctor --json
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
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\wechat-visual-director\uninstall.ps1"
```

Permanently remove the installed program, tasks, images, and private
configuration only when the user explicitly requests a complete purge:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\wechat-visual-director\uninstall.ps1" -Purge
```

Both modes remove host Skill registrations. Neither mode may delete the Git
source repository supplied by the user.

On macOS use the stable `visual-director` and `uninstall.sh` files under the
Application Support install root. The self-contained Agent installation is the
default path; source checkout is development-only. macOS remains Technical Preview
until the Release package has passed a real-device end-to-end review.
