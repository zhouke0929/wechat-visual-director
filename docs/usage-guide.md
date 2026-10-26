# 安装、配置与日常维护

[返回产品介绍](../README.md) · [Agent 完整安装协议](../INSTALL_FOR_AGENT.md)

这份指南面向已经准备使用公众号视觉主编的用户。第一次接触产品，建议先复制 README 中的安装提示词，把安装和启动交给 Agent；这里保留手动命令、配置说明与排障方法。

## 手动安装与升级

普通安装下载包含 Python、依赖和工作台的自包含 Release 包，不需要克隆源码或额外安装 Node.js、Git、Homebrew。

下面两个入口都从 `main/VERSION` 读取目标版本，再下载对应已发布资产并校验 SHA-256，不把版本写在命令中。只打开已有工作台时不必重装；明确升级时重新执行安装入口。若下载或校验失败，应停止并报告，不改装历史版本。只有用户明确指定版本时才使用 `-Version`（Windows）或 `--version`（macOS）。

### Windows x64

在 PowerShell 中执行：

```powershell
$installer = Join-Path $env:TEMP "wechat-visual-director-install.ps1"
Invoke-WebRequest "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/scripts/install-release.ps1" -OutFile $installer
powershell -NoProfile -ExecutionPolicy Bypass -File $installer
```

安装成功后，用稳定入口检查状态，再在浏览器打开安装结果返回的 `workbench_url`：

```powershell
$launcher = Join-Path $env:LOCALAPPDATA "wechat-visual-director\visual-director.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File $launcher doctor --json
```

### macOS：Apple Silicon / Intel

macOS 自包含包目前为 Technical Preview。

```bash
installer="$(mktemp -t wechat-visual-director-install.XXXXXX)"
curl -fsSL "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/scripts/install-release.sh" -o "$installer"
bash "$installer"
```

安装成功后检查状态，再在浏览器打开安装结果返回的 `workbench_url`：

```bash
launcher="$HOME/Library/Application Support/wechat-visual-director/visual-director"
"$launcher" doctor --json
```

Agent 应核对实际安装版本与本次目标版本相同，再检查最终结果中的 `ok=true`、`installation.persistent=true`、`installation.version_match=true`、`installation.runtime_match=true` 和 `capabilities.host_skill_registered=true`，不能只因文件已复制或端口可访问就报告成功。完整协议见 [INSTALL_FOR_AGENT.md](../INSTALL_FOR_AGENT.md#version-selection-do-not-inherit-a-stale-documentation-pin)。

安装后如果宿主未自动打开工作台，直接告诉它“打开公众号工作台”；若宿主确实只在启动时发现 Skill，再重启宿主或新开对话，无需重复下载源码。

## 第一次打开后做什么

把选题、资料或现成的纯文本 / Markdown 交给 Agent，它完成内容整理与语义规划后返回具体任务页。首页提供可复制的指令和简短流程；“最近任务”可按标题关键词搜索完整历史并继续之前的文章。也可以让 Agent 查找已有任务；有多个匹配时先确认，不必重新创建文章。

工作台负责原文编辑、主题切换、配图与封面审核，以及预览和交付，不提供绕过 Agent 规划的手动 Markdown 上传入口。内容校对自动保存；手机预览用于检查修改后的阅读效果。

本地设置属于这台电脑，不属于某个对话，不必在每个 Agent 窗口中重新填写。

## 图片与封面

### 三种使用方式

- **上传自己的图片：** 无需图片 Key。可以人工上传、替换或复用图片，不需要配图的位置可以跳过。
- **宿主 Agent 原生生图：** 宿主必须有可调用的原生生图工具。确认主题后，可展开正文配图或封面区域的“也可以让 Agent 生成”，复制带当前任务链接的指令回对话；Agent 按任务请求生成并导入待审核候选。消耗宿主自身额度，不会因为没有原生工具而静默改用收费 API，复制指令本身不会生成或采用图片。
- **工作台图片 API：** 在本地设置选择“图片模型 API”，填写服务商提供的完整 Endpoint、模型 ID、API Key，并选择图片清晰度。服务支持与适配边界见[图片 Provider 协议](../skills/wechat-visual-director/references/image-providers.md)，不要只凭模型品牌名判断任意接口都兼容。

`Mock` 仅生成本地占位图，供测试交互使用，不作为发布素材。若设置显示“当前由启动环境管理”，该选项被启动环境变量锁定；应检查启动方式，不是继续点击就能切换。

### 图片不会随换主题自动重画

新生成的正文图片与封面使用文章级视觉方向。切换主题会保留已有候选与采用图片，不自动再次计费；需要新风格时再主动生成。图片生成可能出现文字或事实错误，尤其是结构信息图，采用前必须逐项核对。

封面编辑器通过可移动的“封面显示区”调整展示位置，保留候选母图。不同展示入口可能截取不同范围，建议把关键主体放在中央安全区域，并在实际手机端检查。

## 复制图文：不必先配置微信 API

最终交付区的复制功能会把正文、已采用的正文图片和主题装饰一起准备进富文本剪贴板。AI 配图与人工上传的正文图片都适用；不需要先配置 AppID / AppSecret，也不依赖公众号后台访问本机图片地址。

1. 确认正文与图片，保存最终版本后复制图文。
2. 粘贴到公众号后台正文编辑区，等待图片处理完成。公众号封面、标题等发布信息仍需在后台设置。
3. 保存草稿、重新打开，并检查手机预览；粘贴瞬间正常不代表保存后的效果一定一致。

浏览器需支持富文本剪贴板并允许复制。当前本地保护上限为单张图片 8 MiB、最终剪贴板 HTML 24 MiB、100 处图片（含主题装饰）；这是本产品的保护阈值，不是微信官方额度，编码后的大小也不等于原图片文件大小。图片较多时可能变慢，超过上限会提示未复制；可压缩图片或减少图片后重试，也可下载交付包。配置了微信连接时也可选择 API 交付。

## 保存到微信公众号草稿箱

没有微信连接也能复制全文、下载交付包。需要直接创建草稿时，在本地设置中选择“完整交付”，按页面引导：

1. 确认公众号具有所需接口权限，准备 AppID 与 AppSecret。
2. 检测当前公网出口 IP，并将其加入微信后台的开发接口 IP 白名单。不要填写 `192.168.x.x` 等局域网地址。
3. 仅在本地设置页填写凭据，不粘贴进 Agent 对话。
4. 保存并点击“检测连接（不建草稿）”。
5. 连接通过后，完成文章、图片与封面的确认，在最终交付页主动创建草稿。

内置发布器直接连接微信官方 API，不需要额外安装 Wenyan 或全局 npm 发布工具。只有返回真实 Media ID 才表示已创建草稿，最终群发仍需在微信中操作。

如果结果为“未知”，**先检查公众号草稿箱，不要立即重试**。后台找到草稿就按页面确认；确认没有后再解除锁定重试，以免重复创建。复制全文与下载交付包不会再次调用微信创建草稿。

## 遇到问题时

先让 Agent 使用正式安装目录的稳定启动器运行 `doctor --json`。不要手工同时启动多个 API / Web 服务，也不要用源码测试服务冒充正式安装。

| 现象 | 优先检查 |
|---|---|
| 只回复“Skill 已安装”，没有工作台 | 让 Agent 读取已安装 Skill，接续首次使用准备入口；返回真实工作台链接与检查结果 |
| 安装了旧版 | 核对实际版本、`main/VERSION` 和对应 Release；不要复用旧安装脚本或历史说明中的固定链接 |
| 工作台打不开 | 查看 doctor 的错误与下一步操作，核对端口是否被其他程序或源码服务占用 |
| `core_runtime_mismatch` | 占用端口的服务不属于当前正式运行环境，先查明来源；不要把测试库识别成正式库 |
| 图片模型 API 无法切换 | 查看是否被启动环境变量管理，以及页面给出的锁定原因 |
| `publishers.wechat.ready=false` | 检查本地凭据、账号权限和连接检测结果 |
| 微信连接检测提示 IP 错误 | 重新检测公网出口 IP，检查微信白名单；网络变化可能改变出口 |
| 复制提示不支持或被拒绝 | 使用支持富文本剪贴板的浏览器并允许复制；不要把普通文字复制当作图文复制成功 |
| 复制后缺图或处理缓慢 | 等待微信处理图片，再保存并重开检查；核对最终版本是否已采用图片，必要时压缩图片后重试或下载交付包 |

提交反馈时提供实际版本、错误代码、主题名、复现步骤和脱敏截图。不要附原始私密配置、凭据或完整任务数据库。

## 升级卸载与数据保留

### 数据存在哪里

Windows 程序默认位于 `%LOCALAPPDATA%\wechat-visual-director`（部分宿主会重定向这个目录），但升级后的正式安装把共享历史固定放在 `%USERPROFILE%\.wechat-visual-director`。换 Agent 时优先打开共享登记中的工作台，不再各建一份历史。macOS 仍使用 `~/Library/Application Support/wechat-visual-director`。

Windows 程序目录中的 `versions/` 保存程序与内置运行环境；共享用户目录保存以下内容（macOS 仍在原安装目录内）：

```text
data/        任务、正文图片、交付资产与自定义主题
config/      本机私有配置
backups/     数据恢复前的备份
runtime/     进程信息与运行日志
profile.json 共享历史与当前程序的登记（Windows）
```

正常升级保留任务、图片与私有配置。Windows 从旧版升级时，会核验并复制选定旧安装的数据到共享目录，原来源保留；有两份不同历史则先确认，不自动合并。登记过的数据库缺失会停止，不悄悄新建空库。正式安装不自动导入源码测试库；源码与正式数据分离。日常再次打开复用现有安装，只有明确升级才下载新版。

### 卸载

默认卸载保留任务、图片与本机配置，方便以后继续。它会移除程序及宿主 Skill 注册，不删除你自己的开发仓库。

Windows：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\wechat-visual-director\uninstall.ps1"
```

macOS：

```bash
bash "$HOME/Library/Application Support/wechat-visual-director/uninstall.sh"
```

只有明确要永久删除任务、图片、配置与安装内备份时，才在 Windows 命令末尾加 `-Purge`，或 macOS 命令末尾加 `--purge`。这适用于模拟完全首次安装，但数据不可继续使用；执行前先确认是否另有需要保留的备份。

### 重装后找不到旧任务

不要只复制 SQLite 文件。先停止服务，用 `data scan --json` 只读扫描；知道旧位置时加 `--candidate <旧数据根目录>`。数据集包含数据库、`image-assets`、`publication-assets` 与 `theme-packs`，需要一起核对。

需要恢复时，由用户确认来源与目标后，再执行 `data recover --from <数据根目录> --activate --yes`。程序会先做备份；不要把源码测试数据误恢复到正式库。

本地存储不代表数据不会离开电脑：交给宿主 Agent、图片服务或微信的内容，仍会发送到对应服务。只发送完成任务所需的信息，凭据始终留在本地设置中。
