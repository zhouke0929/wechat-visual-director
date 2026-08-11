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
- `structured_infographic`：模型端到端生成插画型信息图。完整原文保存在事实锚点中；画面默认只绘制标题和逐字来自原文的短标签，短节点才保留完整原文，禁止模型补写说明或新增事实。
- 核心优先调用本机已有的 Tesseract 中文 OCR。OCR 核对的是模型实际被要求绘制的标题和标签；引擎缺失、识别失败或未完整匹配时，候选保持“需人工核对”，运营逐项确认后才能采用。
- 每个候选保存模型原始输出和最终候选。当前端到端链路两者通常一致；确定性保底图会保留空白原始底图与叠字后的最终图，便于质量归因。
- 工作台中的“使用保底信息图”不调用模型，只复制锁定原文并使用确定性布局。它是失败兜底，不是默认设计方案。

## 图片视觉意图 V3

图片槽不再只保存“信息图/氛围图”标签。核心会先生成供应商无关的 `image_visual_intent.v3`，再由 Seedream、Gemini 或 OpenAI Adapter 编译为各自 Prompt：

| 字段 | 作用 |
|---|---|
| `visual_role` | 图片是解释顺序、比较差异、展示演进、说明框架，还是建立章节语境 |
| `learning_objective` | 读者看完图片后应该理解什么；它是生成约束，不是要画进图片的文案 |
| `fact_anchors` | 逐字来自原文块的事实锚点；氛围图必须为空 |
| `layout_family` | 信息关系结构，例如线性进程、二元对比、时间线或结构拆解 |
| `style_treatment` | 触感编辑拼贴、柔和教育插画、干净空间几何或科技编辑拼贴等表现方式 |
| `palette_intent` | 与当前文章主题协调的色板角色，不等于整张图使用同一种底色 |
| `visual_grammar.scene_metaphor` | 用一个完整场景解释信息关系，例如学习路线、知识岛或时间河流 |
| `visual_grammar.spatial_zones` | 标题、核心场景和节点在画布中的空间区域 |
| `visual_grammar.node_visuals` | 每个原文标签对应的具象物体或人物动作，只承担象征作用 |
| `visual_grammar.connector_language` | 道路、桥、时间带或引导线等统一连接方式 |
| `visual_grammar.display_labels` | 逐字截取自事实锚点的短标签，不由模型自由总结 |
| `visual_grammar.text_mode` | 长节点使用 `label_only`，全部较短时使用 `verbatim_full_copy` |
| `visual_grammar.title_mode` | 结构信息图只保留原文语义标题，移除“第二层 / PART 02”等规划脚手架；氛围图不排标题 |
| `visual_grammar.content_occupancy` | 核心内容占画布 70%–85%，避免把防裁切安全区误做成大面积留白 |
| `visual_grammar.edge_treatment` | 纸张毛边、开放插画边缘或干净空间边缘等主题相关表面语言 |

## 文章级 Visual DNA

图片槽之上还有一份整篇共享的 `article_image_art_direction.v0.1`。文章主题与图片风格不再维护成对兼容清单，而是分别声明温度、饱和度、对比度、几何感、触感、空间维度、视觉能量、信息密度和品牌正式度。解析器按以下权重选择新图片的统一美术方向：

- 内容与图片作用适配：35%
- 文章主题 Visual DNA 适配：30%
- 最近五篇视觉新鲜度：25%
- 当前 Provider 稳定性：10%

整篇共享 `style_family`、`palette_variant`、`surface_treatment`、`edge_treatment` 和气质；每个图片槽仍可依据其真实信息关系使用不同 `layout_family`、场景与节点。新增文章主题或图片风格时只注册自己的 Manifest，不修改旧定义。

“未来科技”不再复用理性网格的微缩 3D 舞台。它使用独立的 `editorial_tech_collage`：磨砂半透明信息薄片、连续信号曲线、纸张纤维与克制的 2.5D 层次共同组成不对称编辑跨页。提示词明确禁止路牌/站牌、塑料玩具感、四块等宽小图标和横贯画面的深色道路，并要求主体与信息动线覆盖主要画布、上半部不得形成大面积空白。

冻结时仅保存轻量视觉签名：文章主题、图片风格、色板变体、构图家族、表面处理、边缘处理和场景家族。签名不包含正文、图片内容、Prompt 或凭据，用于最近五篇的确定性避重。

封面不额外调用一轮文本模型。核心直接复用已经确认的全文 `EditorialBrief`，以文章标题、整篇叙事摘要和读者任务确定唯一主视觉隐喻；随后将同一份文章级 Visual DNA 编译为封面专用 Prompt。封面与正文图片共享画材、色板、表面语言和气质，但固定使用“单焦点 + 标题安全区”的 5:4 构图，不生成信息图、多面板或步骤卡。Seedream 路径会显式编译四类风格语言及其禁用项，避免场景模板覆盖当前主题。

宿主 Agent 可以建议视觉作用、学习目标和布局，但本地核心会再次依据原文关系校验：步骤不能被画成对比，普通并列项不能被伪造成时间线，任何事实锚点都必须逐字存在于 `source_block_ids`，短标签也必须是事实锚点的连续原文子串。旧任务缺少 V3 字段时按现有事实引用即时补齐，不要求重建任务。

当前结构库保持精简：`linear_progression`、`binary_comparison`、`comparison_matrix`、`hierarchical_layers`、`hub_spoke`、`structural_breakdown`、`timeline`、`pathway`；氛围图使用 `semantic_scene`。这些是内部自动选择，不要求运营逐项配置。

## 换主题后的图片处理

- 主题始终可以即时切换和回退；已有候选、已采用图片和人工上传图片不会被删除、覆盖或自动重生成。
- 每张新候选保存生成时的文章级美术方向快照。工作台用 Visual DNA 在本地计算它与当前主题的协调度，不调用视觉模型。
- 完全兼容和部分协调时不增加操作提示；只有明显差异时才提供“按新主题再生成”和“回到上个主题”。默认仍保留当前图片，协调度判断不会阻断冻结。
- 只有用户显式点击生成才会调用 Provider。未生成图片槽和后续新增候选使用当前主题；同一主题最多生成三张模型候选，切换主题不会让旧候选占用新主题的三张额度。
- 文章内容决定图片解释什么和使用哪种信息关系；文章主题提供 Visual DNA，解析器从独立图片风格库中选择整篇统一方向，不建立一对一锁定。
- 候选缩略图加载失败时工作台会自动重试一次，仍失败则显示可点击重试入口；文章预览会显示明确加载状态并检测内部图片。连续切换主题时，过期的图片工作区响应不得覆盖当前主题状态。加载提示只代表前端网络状态，不会删除候选或重新调用图片模型。

## 旧 Agnes 配置

Alpha.6 的 `VISUAL_DIRECTOR_IMAGE_PROVIDER=agnes` 与 `AGNES_*` 字段仍会被读取，并映射到 `images_api + extended`。新版本只写入 `IMAGE_API_*` 或 `GEMINI_*` 字段。
