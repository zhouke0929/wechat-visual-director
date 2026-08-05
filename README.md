# WeChat Visual Director

把公众号主题、资料或 Markdown 初稿，转换成可人工确认、可写入微信公众号草稿箱的视觉文章。

`wechat-visual-director` 是一个本地优先的开源 Skill + 工作台。宿主 Agent 负责理解内容并输出受控的 `EditorialBrief`，本地核心负责结构校验、主题选择、组件编译和微信兼容渲染。运营只需在浏览器里确认方案、图片与封面，不需要让模型自由编写整段 HTML/CSS。

当前版本：**v0.1.0-alpha.13**。项目仍处于 Alpha 阶段，不是 SaaS，也不会自动群发文章。

本项目与腾讯、微信官方无隶属或背书关系。

## 它解决什么问题

- 固定 Markdown 主题长期使用后，标题、卡片和点缀高度同质化；
- 图片与文章章节关联弱，需要运营逐张复制内容、生成和插入；
- 弱模型可能漏选组件、误判标题层级或破坏正文结构；
- 排版完成后仍需在多个编辑器之间来回复制；
- API Key、公众号密钥和历史任务不适合交给远程 Agent 托管。

Visual Director 将这些问题拆成两层：

1. **Agent 理解语义**：把真实内容整理为规范 Markdown，并生成结构化视觉意图；
2. **本地核心确定性执行**：只使用经过验证的主题、组件和内联样式完成渲染与交付。

## 当前能力

- 4 类文章：数据政策、教程步骤、观点趋势、活力成长；
- 6 套视觉系统：轻盈阅读、温暖人文、编辑对比、理性网格、青春校园、未来科技；
- 12 类语义组件，并支持同一主题内的局部换型与撤回；
- 连续概念词条组、长清单、真实对比段和长文组件节奏识别；
- 双视觉方案与 390px 移动端预览；
- 正文配图、结构信息图、人工上传与封面候选；
- 人工、Mock、OpenAI/Ark/兼容 Images API、Gemini Nano Banana 图片 Provider；
- 本地任务、历史方案、图片选择与冻结版本持久化；
- 富文本复制、Markdown/HTML/图片交付包；
- 可选 Wenyan 适配器写入微信公众号草稿箱；
- OpenClaw、OpenCode、Claude Code、Trae 等宿主可复用现有文本模型，不要求再配置一份文本模型 Key；
- Windows 持久安装、升级保留数据、通用 Skill 注册和 OpenCode 命令注册。

> 能力口径：`mock` 只用于自动化回归和演示，不是正常发布路径。只要 `doctor --json` 返回
> `capabilities.wechat_draft=true` 且 `publishers.wenyan.ready=true`，工作台就会调用本机 Wenyan
> 创建真实公众号草稿；Alpha 标识不代表该能力仍是 Mock。

## 工作流

```text
运营提出主题或提供资料
        ↓
宿主 Agent 生成规范 Markdown + EditorialBrief
        ↓
本地 FastAPI 校验事实、标题层级和组件绑定
        ↓
确定性组件库生成两套视觉方案
        ↓
运营在 Next.js 工作台确认主题、组件、图片和封面
        ↓
冻结版本
        ↓
复制正文 / 下载交付包 / 写入微信公众号草稿箱
```

H1/H2、数字、来源和事实关系始终受保护。组件只能绑定原文已经存在的语义，不会为了视觉效果补造概念、比较、结论或数据。

## 快速开始

### 方式一：交给支持 Skill 的 Agent

把下面这段话发给 OpenCode、Claude Code、Trae 或其他具备终端能力的 Agent：

```text
请从以下固定版本安装或升级 wechat-visual-director，执行项目安装器和 doctor 检查，然后用仓库样例创建任务并打开本地评审工作台。不要读取或回显任何 API Key、AppSecret 或 Cookie。

https://github.com/zhouke0929/wechat-visual-director/tree/v0.1.0-alpha.13
```

安装器会把最小 Skill 入口注册到通用 Agent 目录和 OpenCode 目录。安装完成后请重启宿主对话，使新会话能够自动发现 Skill。

### 方式二：Windows PowerShell

需要 Python 3.11+、Node.js，以及 pnpm 或 Corepack。

```powershell
git clone --branch v0.1.0-alpha.13 --depth 1 https://github.com/zhouke0929/wechat-visual-director.git
Set-Location .\wechat-visual-director

$install = powershell -ExecutionPolicy Bypass -File ".\scripts\install.ps1" | ConvertFrom-Json
powershell -ExecutionPolicy Bypass -File $install.launcher doctor --json
powershell -ExecutionPolicy Bypass -File $install.launcher task create --file ".\samples\skill-alpha\canonical-article.md" --open --json
```

默认安装位置为 `%LOCALAPPDATA%\wechat-visual-director`：

```text
wechat-visual-director/
├── versions/   # 各程序版本
├── data/       # 任务、图片和冻结产物
├── config/     # 本地私有配置
├── runtime/    # PID 与运行日志
├── visual-director.ps1
└── visual-director.cmd     # CMD/桌面 Agent 兼容入口
```

升级不会清空 `data/`、`config/` 或 `runtime/`。`doctor --json` 应返回：

```text
core_ready=true
workbench_ready=true
persistent=true
version_match=true
host_skill_registered=true
```

## 文本规划

作为 Skill 使用时，默认复用宿主 Agent 已经配置的文本模型。核心只向宿主提供文章块、公开品牌规则和最近视觉摘要；宿主返回 `EditorialBrief` 后，本地核心执行 Schema 校验、结构规范化和确定性编译。

任务结果满足以下条件，才表示本次确实使用了宿主规划：

```text
planner_provider=host_agent
fallback_used=false
```

若宿主输出不合法，系统会标记 `fallback_used=true`，并退回只使用原稿事实的规则方案。

不通过宿主 Agent、只把 Markdown 上传到工作台时，可以零配置使用规则规划；如需独立核心调用 Qwen，再在本地私有配置中填写：

```dotenv
VISUAL_DIRECTOR_TEXT_PROVIDER=qwen_max
DASHSCOPE_API_KEY=你的本机Key
QWEN_TEXT_MODEL=qwen3.7-max-2026-05-20
```

## 图片 Provider

工作台 `/settings` 支持四种模式：

| 模式 | 用途 | 是否需要 Key |
|---|---|---|
| `manual` | 人工上传、沿用原图或跳过 | 否 |
| `mock` | 本地占位图与交互验收 | 否 |
| `images_api` | OpenAI GPT Image、火山方舟 Seedream、兼容中转站 | 是 |
| `gemini` | Google Nano Banana 原生 Interactions API | 是 |

Key 由用户在本地设置页填写，保存到仓库之外的私有配置文件；页面和 API 只返回“是否已配置”，不会回显原值。首次真实生成才会验证模型权限与额度。

Seedream 5.0 信息图会使用安全区、纵向阅读动线和锁定原文提示；封面复用正文横图时，使用柔化背景适配 5:4，不再直接中心裁掉两侧内容。详细协议与配置见 [图片 Provider 说明](references/image-providers.md)。

## 写入微信公众号草稿箱

本地排版不需要公众号凭据。只有点击“保存到微信公众号草稿箱”时才需要：

```powershell
npm install -g @wenyan-md/cli@2.0.11
```

随后在安装器返回的本地 `config_file` 中手动填写：

```dotenv
WECHAT_APP_ID=
WECHAT_APP_SECRET=
```

还需要把当前网络的公网出口 IP 加入公众号后台白名单。Visual Director 负责冻结文章和生成内联 HTML；Wenyan 只负责图片上传与草稿传输。只有界面返回真实 Media ID，才表示草稿已写入公众号后台。

当前不会自动执行最终群发，微信公众号后台仍必须人工复核标题、封面、摘要、图片和手机端效果。

如果页面显示“结果未知”，表示 Wenyan 已被调用，但本地没有拿到可确认的 Media ID；此时先到公众号
草稿箱核对，不要重复推送。无论发布成功、失败还是结果未知，冻结页都会继续提供“复制全文到剪贴板”
和“下载交付包”，这两项不会再次调用微信接口。

## 数据与安全边界

- `.env.local`、本地配置、任务数据库、图片、诊断产物和内部文章均被 Git 忽略；
- 不要把 AppSecret、API Key、Cookie 或 Token 发给 Agent；
- 真实品牌图、二维码、公司名称与内部评测材料不进入公开仓库；
- 图片候选必须经过人工确认；
- 同一输入默认复用既有任务，避免 Agent 重试制造重复草稿；
- 最终群发始终保留人工门禁。

## 仓库结构

```text
├── SKILL.md                 # Agent 触发条件、工作流与安全门禁
├── agents/openai.yaml       # Skill UI 元数据
├── scripts/                 # 安装器、稳定启动器和公开验证脚本
├── apps/api/                # FastAPI、SQLite、规划、组件与发布适配器
├── apps/web/                # Next.js 本地评审工作台
├── references/              # 文章协议、CLI 契约、图片 Provider 说明
├── samples/                 # 中性公开样例与回归样本
├── contracts/               # EditorialBrief、OpenAPI 等契约
├── assets/brand/            # 不含真实企业资料的示例品牌
└── docs/                    # 公开产品决策、质量基线与发布记录
```

## 开发验证

```powershell
$env:PYTHONPATH="apps/api/src"
python -m pytest apps/api/tests -q
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
```

Alpha.13 已完成 API 全量测试、Next.js 生产构建，以及真实 Markdown → 双方案 → 图片/封面确认 → 微信公众号草稿箱的人工端到端验证。工作台与 API 现在都会校验运行版本，桌面 Agent 不应再用旧源码或系统 Python 绕过稳定入口。下一阶段优先观察真实文章中的默认主题采用率、组件修改位置、图片采纳率和人工处理时间，而不是继续无边界扩充主题。

运营观察模板见 [真实运营观察表](docs/真实运营观察表.md)。

## License

本项目采用 [Apache License 2.0](LICENSE)。第三方依赖和外部服务仍分别受其自身许可证与使用条款约束。
