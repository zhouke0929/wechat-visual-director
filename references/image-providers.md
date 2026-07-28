# 图片 Provider 配置

视觉主编使用统一的内部生图契约，外部厂商协议由 Adapter 处理。不要因为某个中转站宣称“OpenAI 兼容”就默认所有字段兼容；必须选择正确协议并执行一次真实生图验收。

## 工作台模式

| 模式 | 用途 | 是否需要 Key |
|---|---|---|
| `manual` | 人工上传、沿用原图或跳过 | 否 |
| `mock` | 本地占位图和交互验收 | 否 |
| `images_api` | OpenAI GPT Image、火山方舟 Seedream、兼容中转站 | 是 |
| `gemini` | Google Nano Banana 原生 Interactions API | 是 |

## 通用 Images API

### OpenAI

- 协议：`openai`
- Endpoint：`https://api.openai.com/v1/images/generations`
- Model：`gpt-image-2`
- Size：`auto`

OpenAI 的横向输出与文章要求的 4:3、16:9 不完全一致时，核心会做确定性的居中裁切，不把尺寸差异泄漏到渲染器。

### 火山方舟 / Seedream

- 标准按量协议：`ark`
- Endpoint：`https://ark.cn-beijing.volces.com/api/v3/images/generations`
- Model：从用户自己的火山方舟控制台复制当前可用 Model ID，不在 Skill 中长期硬编码。
- Size：建议先用 `2K`

订阅火山方舟 Agent Plan 时改用：

- 协议：`ark_plan`
- Endpoint：`https://ark.cn-beijing.volces.com/api/plan/v3/images/generations`
- 默认 Model：`doubao-seedream-5.0-lite`
- Size：`2K`

两个协议的图片请求字段一致，但计费/订阅路由不同，不能互相替换。

Seedream 是图片模型；Seedance 是视频模型，不应出现在图片 Provider 的模型列表中。

### 中转服务

- 严格兼容 OpenAI Images API 时选 `openai`。
- 支持火山方舟字段时选 `ark`。
- 仍使用旧 `ratio`、`extra_body` 结构时选 `extended`。

不要仅凭 URL 或模型名自动猜协议。中转服务的权限、价格、数据处理与可用性由用户自行核实。

## Google Gemini / Nano Banana

- 模式：`gemini`
- Endpoint：`https://generativelanguage.googleapis.com/v1beta/interactions`
- 默认 Model：`gemini-3.1-flash-image`
- Size：`1K`；需要更高质量时可选 `2K` 或 `4K`

Google 使用 `x-goog-api-key` 和 Interactions 原生请求结构，不能无损地塞进 OpenAI Images API。核心为它保留独立 Adapter。

## 密钥与验收

- Key 只能由用户在本地设置页或安装器返回的私有 `config_file` 中填写。
- Agent 不读取、不回显、不写入 Key。
- 设置保存只代表本地格式有效；首次真实生成才验证模型权限、额度和上游响应。
- 真实候选必须人工确认，失败时仍可切回人工上传，不阻塞文章排版与发布。
- 自定义 Endpoint 必须使用 HTTPS，且不得指向本机或局域网地址。

## 配图与信息图是两条链路

- `atmosphere`：模型生成无文字语义插画。提示词传递 EditorialBrief 的视觉隐喻、风格家族、色板与气质，但禁止文字、二维码、Logo 和水印。
- `structured_infographic`：模型端到端生成最终信息图。标题和 2–4 个原文节点以锁定文案传入，禁止模型改写、遗漏或新增事实。
- 核心优先调用本机已有的 Tesseract 中文 OCR。OCR 引擎缺失、识别失败或未完整匹配时，候选保持“需人工核对”，运营逐项确认原文后才能采用。
- 每个候选保存模型原始输出和最终候选。当前端到端链路两者通常一致；确定性保底图会保留空白原始底图与叠字后的最终图，便于质量归因。
- 工作台中的“使用保底信息图”不调用模型，只复制锁定原文并使用确定性布局。它是失败兜底，不是默认设计方案。

## 旧 Agnes 配置

Alpha.6 的 `VISUAL_DIRECTOR_IMAGE_PROVIDER=agnes` 与 `AGNES_*` 字段仍会被读取，并映射到 `images_api + extended`。新版本只写入 `IMAGE_API_*` 或 `GEMINI_*` 字段。
