# 完整产品安装与恢复

wechat-visual-director 支持完整安装和先添加 Skill、首次使用时准备工作台两条路径。用户要求安装产品时，以「Skill + 工作台就绪 + 上手回执」为完成标准；通用安装器复制文件后继续准备，不修改宿主系统安装器。用户明确只下载文件或当前无法执行时，说明仅完成文件安装，并保留下一步入口：

> 公众号视觉主编 Skill 已添加；工作台尚未启动。直接说「打开公众号工作台」或「帮我写一篇关于××的公众号文章」。
> 第一次使用会自动准备工作台；也可给参考图或风格描述，让 Agent 创作一整套新主题。
> 如果当前 Agent 支持生图，确认主题后可生成正文配图与封面候选。

未实际添加文件不报已添加；准备失败说明具体步骤和重试动作，不用“缺少运行时”作为没有下一步的结束语。

## 用户开始使用与准备回执

1. 将本 Skill 所在目录记为 `{baseDir}`。若运行环境不展开该占位符，先解析当前 `SKILL.md` 的绝对目录。
2. 用户要求安装本产品、打开工作台、写作或排版时，先运行随 Skill 分发的准备入口。通过宿主通用安装器复制文件后接续此步骤，不把「下一轮可用」作为完整安装回执。如果用户明确只下载文件，不自动启动；若宿主权限阻止执行则如实告知。Windows：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "{baseDir}/scripts/ensure-workbench.ps1"
```

macOS：

```bash
bash "{baseDir}/scripts/ensure-workbench.sh"
```

3. 准备入口只在稳定启动器缺失时下载校验过的正式 Release；已有安装直接启动并运行 doctor，不自动升级。用户明确要求升级时传 `-Upgrade` / `--upgrade`。马上要打开文章任务时可传 `-NoOpen` / `--no-open`，避免先打开空工作台。脚本不需要系统 Python、Node.js 或 Git；异常按本文后续说明处理。
4. 只解析 stdout 的最终 JSON。`ok=true` 且 `workbench_ready=true` 后，把绝对 `launcher` 记为 `{launcher}`，后续调用这个稳定入口。未主动使用 `NoOpen` 而 `browser_opened=false` 时，由宿主打开 `workbench_url`；为创建文章使用 `NoOpen` 时先继续文章流程，之后打开具体任务。用户只要求安装或打开工作台时，返回链接和适用的简短引导，不额外生成文章。用户要求文章时不停在安装成功。返回 `command_completed=true` 表示命令已结束，后台 API 独立运行，不要等待 API 进程退出，也不要为确认成功再次执行相同准备命令。
5. 准备入口会校验 `installation.persistent`、`version_match`、`runtime_match` 与 `capabilities.host_skill_registered`；失败时不得继续创建任务或声称工作台就绪。升级还须按下节核对数据延续：版本一致不代表原任务仍在。不要自行改用源码/测试服务。程序版本位于 `versions/`，任务、图片、配置和日志位于版本目录之外。
6. `capabilities.image_generation=false` 时仍可完成排版；允许跳过、沿用原图或人工上传。用户明确要求配置真实生图时，引导其本人打开 `{settings_url}` 填写，不得读取、代填或要求用户把 API Key 粘贴进对话。
7. 用户要求安装、开始使用或初次打开工作台时，参考 `first_run_guide` 返回不超过五行的简短上手说明（同一轮只讲一次）。首页常显简要流程，不再需要「我已了解」按钮；不要要求确认或代调用已读接口。`first_install` 只表示这次是否新装，`onboarding_pending` 是兼容字段，不作为反复讲教程的条件。普通再次打开、文章续写、生图、升级、诊断不主动重复整段教程；需要时提醒首页有简要流程，已有文章可从「最近任务」进入。只有宿主明确要求重新加载时才提示重启，不默认要求新开对话。
8. 下文 PowerShell 示例在 macOS 上应改为直接执行 `"{launcher}" <args>`，参数语义完全相同。

## 安装或升级

只要求更新 Skill 文件时，同步 Skill，不顺带更换工作台或数据来源；需要升级工作台时说明并取得用户授权。升级前先用 `doctor --json` 记录实际运行的 `running_data_root`、`running_task_count`，并以 `data scan` 盘点当前及已知旧数据目录（例如用户提供的源码目录），只读目录、计数与健康状态，不读取正文或私密配置。不要递归搜盘后自动选择“任务最多”的库。

新版安装流程先备份正式安装自己的非空数据集，返回 `data_continuity.checked=true`、`preserved=true` 与 `backup_root`，核对任务 ID 与配套资产，而非只检查数量。默认安装不扫描当前对话工作目录，也不导入独立源码库或其私密配置；显式发现的其他数据集只作为 `migration_candidates` 和 `optional_data_migration_available` 提示。用户选择不迁移时继续独立安装，来源保持不动；正式目录已有数据则原样保留，不能为了“全新安装”清空它。

`upgrade_data_root_changed` 表示安装记录证明数据目录将改变，应停止并请用户确认来源；只有用户授权迁移才执行 `data recover`，数据库与配套资产整体恢复。`upgrade_runtime_conflict` 则表示另一套工作台占用了安装地址，处理服务或端口冲突，不把迁移数据作为解决办法，也不自动停止无关服务。旧安装包的 `upgrade_data_migration_required` 须先核对来源归属，不能把拒绝独立开发库迁移理解成取消安装；包不支持独立安装时说明限制，不能擅自迁移、删库或声称完成。

旧安装包没有数据延续字段时，宿主仍须比较升级前后实际数据目录、任务数及资产盘点；同一安装原有任务意外变为空库不得报告成功，也不得继续创建任务掩盖问题。独立开发库与用户明确选择的空安装不属于这种数据丢失；恢复后重新检查，再交付工作台。

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
5. 安装结果提供 `workbench_url` 时立即打开。安装或初次使用时参考 `first_run_guide` 返回不超过五行的教程，同轮不重复。普通再次打开、升级、修复和任务检查不主动重复教程，不以 `onboarding_pending` 决定重复提醒。工作台首页常显简要流程，顶部「最近任务」进入独立任务页；Agent 不调用已读接口代用户确认。
6. 普通安装不得安装 Git、Homebrew、系统 Python、Node.js、pnpm 或 Wenyan，也不得手动启动 `uvicorn`、Vite 或源码开发服务。

只有用户明确要求源码开发或审计，并已经提供独立源码检出时，才运行该源码根目录的 `scripts/bootstrap.ps1` 或 `scripts/bootstrap.sh`。当前 Skill 目录永远不视为源码仓库。

## 私密配置

图片 API 与微信公众号凭据只允许用户本人在安装结果返回的 `settings_url` 中填写。不要读取、回显或要求用户把 API Key、AppSecret、Cookie 或 Token 粘贴到对话。

## 卸载

只有用户明确要求时才卸载。默认卸载保留任务、图片与私密配置；彻底清理必须额外得到用户明确要求并使用 `-Purge`（Windows）或 `--purge`（macOS）。卸载必须同时移除 Codex、通用 Agent 和 OpenCode 的 Skill 注册，且不得删除用户提供的源码仓库。
