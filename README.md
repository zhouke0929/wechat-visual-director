# WeChat Visual Director

`wechat-visual-director` 是一个本地优先、可由 Agent 调用的微信公众号视觉排版工作台。宿主 Agent 先把主题和资料整理为结构化 Markdown，再复用自己已经配置的模型生成受控 EditorialBrief；本地核心负责严格校验和确定性编译，生成两套可比较的视觉方案。运营在浏览器中确认组件、插图和封面，模型不会自由生成整段 HTML/CSS。

当前版本是 **Alpha**，目标是验证“Markdown → 视觉方案 → 人工确认 → 可选草稿交付”的本地闭环，并作为开源 Skill 发布。它不是 SaaS，也不会自动群发文章。

本项目是独立开源项目，与腾讯或微信官方无隶属或背书关系。

## 当前可用

- 解析 Markdown，并检查标题层级、数据来源与高风险结构；
- 支持 4 类文章、4 套视觉系统和 6 类语义组件；
- 生成结构不同的双方案，支持组件局部换型和撤回；
- 在 390px 移动端画布中实时预览；
- 规划封面与正文图片槽，支持 Mock 候选和人工上传；
- 保存本地任务、方案选择、图片选择和冻结版本；
- 实验性复制公众号富文本、下载含 Markdown/HTML/图片的交付包；
- 可选调用本机 Wenyan CLI，把冻结版本写入微信公众号草稿箱；
- 通过 CLI 启动服务、创建任务、查询状态和打开工作台；
- 复用 OpenClaw、OpenCode、Claude Code 等宿主的现有模型生成 EditorialBrief，无需重复配置文本模型 Key；
- 通过根目录 `SKILL.md` 让 OpenClaw 等宿主 Agent 按统一协议调用。

## Alpha 能力边界

| 能力 | 当前状态 |
|---|---|
| Markdown 预检、双方案、组件与图片确认 | 已实现 |
| 本地任务和确认结果保存 | 已实现 |
| 文本语义规划 | Skill 默认复用宿主 Agent；独立模式支持 Qwen BYOK 或规则兜底 |
| 多模态视觉复核 | 可选路线；不支持看图时继续使用确定性结构和兼容性检查 |
| 生图模型 | Provider 可替换；支持人工上传、Mock、OpenAI/Ark/兼容 Images API 和 Gemini Nano Banana |
| 真实微信公众号草稿创建 | 已实现可选 Wenyan 本地适配器，需本机凭据与 IP 白名单 |
| 富文本一键复制 | 已实现实验入口，图片必须经过公众号保存/重开/手机预览验证 |
| 本地交付包 | 已实现，包含 `article.md`、`article.html`、`assets/` 与清单 |
| 最终群发发布 | **未实现，且必须长期保留人工确认** |

只有界面明确显示真实 Media ID 时，才表示草稿已写入微信公众号后台。冻结版本和下载交付包都不等于已创建微信草稿。

## 架构

```text
宿主 Agent：主题/资料 → 规范 Markdown + EditorialBrief
        ↓
根 Skill + CLI 启动器
        ↓
FastAPI：预检 → Brief 校验/规范化 → 规则兜底 → 确定性渲染
        ↓
Next.js：双方案评审、组件/图片/封面确认
        ↓
本地冻结版本
        ↓
复制正文 / 下载交付包 / 可选 Wenyan 草稿适配器
```

- `SKILL.md`：Agent 触发条件、步骤和安全门禁；
- `scripts/`：安装与统一 CLI 包装脚本；
- `apps/api/`：FastAPI、SQLite、内容解析、规划与渲染；
- `apps/web/`：Next.js 编辑部工作台；
- `references/`：文章协议和 CLI 契约；
- `assets/brand/`：不含真实企业资料的中性示例品牌；
- `samples/`：公开演示与评测样本；
- `docs/`：公开产品决策和验收记录。

真实品牌图、二维码、公司名称、密钥和内部文章不属于公开仓库。私有品牌可以在本机通过 `VISUAL_DIRECTOR_BRAND_PROFILE` 指向独立 JSON 配置；不要把该文件提交到 Git。

## 文本规划模式

作为 Skill 使用时，默认复用宿主 Agent 已经配置的模型：核心先返回只包含文章块、公开品牌规则和最近视觉摘要的安全上下文；宿主生成 `editorial-brief.json` 后，核心执行 Schema 校验、组件合法性检查和确定性编译。该模式不要求第二个文本模型 Key。

`doctor.capabilities.host_agent_text_planning=true` 表示核心可以接收宿主 Brief。任务结果中的 `planner_provider=host_agent`、`fallback_used=false` 才表示本次确实采用了宿主语义规划；若 Brief 不合格，系统会明确标记 `fallback_used=true` 并使用规则方案。

### 可选：独立核心 Qwen

不通过宿主 Agent、直接上传 Markdown 时，零配置安装使用确定性规则规划。需要独立核心自行调用模型时，才在 Git 忽略的 `.env.local` 中由用户手动配置：

```dotenv
VISUAL_DIRECTOR_TEXT_PROVIDER=qwen_max
DASHSCOPE_API_KEY=你的阿里云百炼Key
QWEN_TEXT_MODEL=qwen3.7-max-2026-05-20
```

重启服务后执行 `doctor --json`。只有 `capabilities.ai_text_planning=true` 且 `planners.text.provider=aliyun_qwen` 才表示独立核心正在使用真实文本模型。Key 不会提交到 Git，也不应发送给 Agent。

## 可选：图片来源与真实生成

图片提示词由视觉主编根据文章块、图片作用和品牌约束自动生成，不要求用户填写提示词。打开本地工作台的 `/settings` 页面，可以在四种模式之间切换：

- `manual`：只允许人工上传、沿用原图或跳过，不调用模型；
- `mock`：生成本地确定性占位图，仅用于交互验收；
- `images_api`：连接 OpenAI GPT Image、火山方舟按量/Agent Plan Seedream 或兼容 Images API 的中转服务；
- `gemini`：通过 Google 原生 Interactions API 连接 Nano Banana 系列。

这里没有把所有厂商强行伪装成同一种外部协议：OpenAI Images API 与火山方舟请求结构接近，但仍有字段差异；Google Nano Banana 使用自己的 Interactions API。核心只依赖统一的内部 `generate(prompt, aspect_ratio)` 契约，由 Provider Adapter 翻译请求和响应。这样后续换模型时只替换配置或增加 Adapter，不需要改文章规划、工作台和发布链路。详细配置见 [图片 Provider 说明](references/image-providers.md)。

在设置页填写 API Key 后会保存到安装目录之外的本地私有配置文件并立即生效；页面和 API 只返回“是否已配置”，永远不会回显原值。若配置由进程环境变量托管，设置页会只读，避免覆盖运维配置。OpenAI 官方接口示例：

```dotenv
VISUAL_DIRECTOR_IMAGE_PROVIDER=images_api
IMAGE_API_PROTOCOL=openai
IMAGE_API_ENDPOINT=https://api.openai.com/v1/images/generations
IMAGE_API_MODEL=gpt-image-2
IMAGE_API_SIZE=auto
IMAGE_API_KEY=你的本机Key
```

通过设置页保存时不需要重启；手动改文件或环境变量后需要重启服务并执行 `doctor --json`。只有 `capabilities.image_generation=true` 且警告中没有 `image_generation_mock_only`，才表示真实生图已经启用。设置页只验证本地配置，首次实际生成才会验证账号权限与额度。所有候选都必须由运营逐张确认。

Alpha.6 的 `agnes` 与 `AGNES_*` 配置仍可读取，并会自动映射到 `images_api + extended`，避免无损升级后旧配置立即失效；新配置不再写入旧字段。

## 本地启动

当前 Alpha 以 Windows PowerShell 为首要验证环境，需要 Python 3.11+、Node.js 和 pnpm（或 Corepack）。

```powershell
$existingLauncher = Join-Path $env:LOCALAPPDATA "wechat-visual-director\visual-director.ps1"
if (Test-Path $existingLauncher) {
  powershell -ExecutionPolicy Bypass -File $existingLauncher stop --json
}
$install = powershell -ExecutionPolicy Bypass -File ".\scripts\install.ps1" | ConvertFrom-Json
powershell -ExecutionPolicy Bypass -File $install.launcher doctor --json
powershell -ExecutionPolicy Bypass -File $install.launcher task create --file ".\samples\skill-alpha\canonical-article.md" --open --json
```

默认安装到 `%LOCALAPPDATA%\wechat-visual-director`。`versions/` 保存各程序版本，`data/`、`config/` 和 `runtime/` 分别保存任务与图片、私有配置和运行日志；从新 GitHub Tag 重复执行安装器会切换程序版本，但不会清空这些用户数据。安装器返回的稳定 `launcher` 不依赖最初的临时下载目录，并会同步注册通用用户级 Skill、OpenCode Skill 与 `/wechat-visual-director` 命令。升级后 `doctor` 应同时返回 `installation.persistent=true`、`installation.version_match=true` 和 `capabilities.host_skill_registered=true`；若报告 `core_version_mismatch`，先停止仍占用端口的旧服务再重试；若报告 `host_skill_not_registered`，重新运行当前版本安装器并重启宿主对话。

相同输入默认复用既有任务，避免 Agent 重试产生重复记录；确实需要新版本时增加 `--new-task`。停止由 CLI 启动的服务：

```powershell
powershell -ExecutionPolicy Bypass -File $install.launcher stop --json
```

## 作为 Skill 安装

仓库根目录直接提供 `SKILL.md`。本地来源：

```powershell
openclaw skills install <absolute-repository-path> --as wechat-visual-director
```

从 GitHub 安装：

```text
openclaw skills install git:zhouke0929/wechat-visual-director@v0.1.0-alpha.10
```

首次使用仍需由 Agent 执行 `scripts/install.ps1`，并在后续调用安装结果中的稳定 `launcher`。Alpha.10 安装器会把最小 Skill 入口同时注册到 `~/.agents/skills/wechat-visual-director` 和 `~/.config/opencode/skills/wechat-visual-director`，并为 OpenCode 注册 `/wechat-visual-director` 命令，因此新对话不再依赖最初克隆仓库的上下文。核心 CLI/API 不绑定 OpenClaw，其他支持 Skill 或命令调用的 Agent 也可以复用。

## 可选：发布到微信公众号草稿箱

本地排版不需要公众号凭据。只有使用“保存到微信公众号草稿箱”时才需要：

```powershell
npm install -g @wenyan-md/cli@2.0.11
```

然后由用户在安装结果返回的 `config_file` 中手动填写 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`，并把当前网络的公网出口 IP 加入公众号后台白名单。密钥不会通过前端提交，也不应发送给 Agent。

发布适配器使用 Visual Director 已冻结的内联 HTML 和本地资产；Wenyan 只负责图片上传和草稿传输。当前 Wenyan 2.0.x 不传输工作台中的摘要与“正文显示封面”开关，发布后请在公众号后台复核这些字段。

## 验证

```powershell
.\apps\api\.venv\Scripts\python.exe -m pytest .\apps\api\tests -q
pnpm --dir .\apps\web typecheck
pnpm --dir .\apps\web build
```

已在一台未配置过项目的 Windows 电脑上完成从 GitHub 安装、任务创建与预览测试；真实公众号草稿、电脑端和手机端主链路也已完成人工验收。项目仍保持 Alpha 标记，含正文图片的富文本复制持久化尚待专项验证。

## 安全

- 不要把微信公众号 AppSecret、模型 Key、Cookie 或 Token 写进 `SKILL.md`、文章、提示词或命令行；
- 默认示例不包含真实公司名称、二维码或账号资产；
- 外部模型与微信发布适配器均为可选配置，不是本地排版主链路的前置条件。

## License

本项目采用 [Apache License 2.0](LICENSE)。第三方依赖与外部服务仍分别受其自身许可证和使用条款约束。
