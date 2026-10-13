# 图片 Provider 配置

视觉主编只向用户展示一个图片模型 API 入口：完整 Endpoint、Model ID、API Key 和图片清晰度。Endpoint 会原样保存和请求，不自动追加 `/images/generations` 或其他后缀。外部厂商协议差异由本地隐藏 Adapter 处理。

## 工作台模式

| 模式 | 用途 | 是否需要 Key |
|---|---|---|
| `manual` | 人工上传、沿用原图或跳过 | 否 |
| `mock` | 本地占位图和交互验收 | 否 |
| `images_api` | GPT Image、Nano Banana、Seedream、通义万相与兼容中转站 | 是 |

## 当前宿主 Agent 的原生生图（可选）

实际执行读取请求、调用工具、绑定导入时先读 [宿主生图桥接](host-images.md)。本节说明能力边界，不代替绑定命令。

宿主原生生图不是第五种持久 Provider，也不会替换工作台里的 API、上传和跳过能力。它是一条由用户在原 Agent 对话中显式提出的异步桥接链路：用户先在工作台确认文章主题，再要求 Agent 为当前任务生成并插入正文配图或封面；Agent 读取主题绑定的受控 Prompt，使用宿主已经提供的原生生图工具生成文件，并把文件导回工作台作为待审核候选。

- Codex 等确实暴露原生生图工具的宿主可以使用；是否占用订阅额度由宿主产品决定，不等同于“免费 API”。
- Claude Code、OpenCode、Trae、WorkBuddy、OpenClaw 等如果没有可调用的图片工具，就明确报告不可用，继续使用工作台 Provider、人工上传、沿用原图或跳过。
- 工作台不会假设所有 Agent 都能生图，也不会从浏览器直接调用宿主；可见界面不提供复制指令或等待回传按钮，底层 CLI/API 只供 Agent 在用户明确要求后调用。
- 正文请求绑定任务、生成时的主题 revision、图片槽 revision 和 Prompt 哈希；封面请求绑定方案 revision、候选计数和 Prompt 哈希。生成期间换主题后，旧图仍可作为候选导入。只有正文语义、封面语义或对应候选 revision 真正变化时才拒绝导入。
- 已经采用或替换的正文槽仍可继续使用宿主抽卡，导入后保留当前采用图片，只追加一张待审核候选。正文与封面都不设置候选数量上限。
- `requests=[]` 是硬停止状态；Agent 不得自拟 Prompt，也不得把宿主生成结果伪装成普通人工上传。
- 宿主生成的文件仍执行格式、尺寸、比例和结构信息图文字核验；导入后必须人工查看大图并采用，不会自动写入文章。
- 这条链路不得静默降级到付费图片 API，也不得读取工作台已经保存的图片 Key。

## 统一图片模型 API

设置页不再要求用户选择协议。核心只进行一次确定性 Adapter 判定，不会为了“猜协议”把同一个付费请求轮流发送给多个接口：

- 火山方舟官方域名与路径 → Ark / Agent Plan Adapter；
- 阿里云 DashScope / Model Studio 官方域名 → DashScope Adapter；
- Agnes 已知域名 → Extended Adapter；
- Google 的 OpenAI 兼容 Endpoint、OpenAI 官方接口以及其他未知 Endpoint → 标准 OpenAI Images JSON。

未知中转站必须由服务商明确声明兼容 OpenAI Images 请求与响应格式。只兼容 Chat Completions 不代表兼容生图。

### OpenAI

- Endpoint：`https://api.openai.com/v1/images/generations`
- Model：`gpt-image-2`
- 清晰度：建议 `1K`

OpenAI 的横向输出与文章要求的 4:3、16:9 不完全一致时，核心会做确定性的居中裁切，不把尺寸差异泄漏到渲染器。

### 火山方舟 / Seedream

- Endpoint：`https://ark.cn-beijing.volces.com/api/v3/images/generations`
- Model：从用户自己的火山方舟控制台复制当前可用 Model ID，不在 Skill 中长期硬编码。
- 清晰度：建议先用 `1K`，确认质量后再选 `2K`

订阅火山方舟 Agent Plan 时改用：

- Endpoint：`https://ark.cn-beijing.volces.com/api/plan/v3/images/generations`
- 默认 Model：`doubao-seedream-5.0-lite`
- 清晰度：`1K` 或 `2K`

两个协议的图片请求字段一致，但计费/订阅路由不同，不能互相替换。

Seedream 是图片模型；Seedance 是视频模型，不应出现在图片 Provider 的模型列表中。

### Google Gemini / Nano Banana

- Endpoint：`https://generativelanguage.googleapis.com/v1beta/openai/images/generations`
- Model：填写 Google 当前提供的可生图模型名
- 清晰度：建议 `1K`

这里使用 Google 官方 OpenAI 兼容生图 Endpoint，因此和其他模型共用同一个入口，不再要求用户切换到单独的 Gemini 卡片。

### 阿里云百炼 / 通义万相 / Qwen Image

- Endpoint：从阿里云 Model Studio 文档或控制台复制完整官方请求地址；
- Model：填写当前可用模型名；
- 清晰度：建议 `1K`。

阿里云官方接口采用 DashScope 原生请求结构，本地核心会根据官方域名选择隐藏 Adapter。不要把 Chat Completions 的 Endpoint 填进图片设置。

### 中转服务

直接填写服务商提供的完整生图 Endpoint。未知域名按标准 OpenAI Images JSON 请求；如果服务商使用自定义字段且不属于已内置官方 Adapter，当前版本不会自动试错或重复计费。

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
- 每个候选保存模型原始输出和最终候选，便于核对图片服务的真实返回与工作台最终展示。

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

封面不额外调用一轮文本模型。核心复用已经确认的全文 `EditorialBrief`，并优先取当前文章第一条氛围图意图作为具体场景锚点；没有氛围图时才回退到文章标题和读者任务。文章决定人物、物体、环境与动作，主题只决定画材、色板、气质和空间节奏。HTML 主题中的栏目、索引、报告、表格、坐标轴、海报文字或界面组件不会原样进入封面 Prompt，而会被封面专用编译器转换为无字的材质、光线、留白和物体关系，避免模型把排版语言误画成伪文字。模型生成“单焦点 + 中央安全主体”的 5:4 无字母图；工作台在不修改母图的前提下记录 2.35:1 头图显示区，并确定性输出 900×383 发布资产，不生成信息图、多面板或步骤卡。Seedream 路径仍使用独立的简洁风格编译，不以固定行业场景覆盖当前文章。

AI 封面生成后可以执行本机 OCR 无字检查，但结果只保存在候选诊断数据中，不在工作台展示红色警告，也不阻断直接采用或保存显示区。OCR 对艺术字体、伪文字和缺少中文识别引擎的环境都可能不确定；产品因此保留普通的“调整封面显示区 / 直接采用”视觉审核流程，由用户查看实际候选后决定。

宿主 Agent 可以建议视觉作用、学习目标和布局，但本地核心会再次依据原文关系校验：步骤不能被画成对比，普通并列项不能被伪造成时间线，任何事实锚点都必须逐字存在于 `source_block_ids`，短标签也必须是事实锚点的连续原文子串。旧任务缺少 V3 字段时按现有事实引用即时补齐，不要求重建任务。

当前结构库保持精简：`linear_progression`、`binary_comparison`、`comparison_matrix`、`hierarchical_layers`、`hub_spoke`、`structural_breakdown`、`timeline`、`pathway`；氛围图使用 `semantic_scene`。这些是内部自动选择，不要求运营逐项配置。

## 换主题后的图片处理

- 主题始终可以即时切换和回退；已有候选、已采用图片和人工上传图片不会被删除、覆盖或自动重生成。
- 每张新候选保存生成时的文章级美术方向快照。工作台用 Visual DNA 在本地计算它与当前主题的协调度，不调用视觉模型。
- 完全兼容和部分协调时不增加操作提示；只有明显差异时才提供“按新主题再生成”和“回到上个主题”。默认仍保留当前图片，协调度判断不会阻断冻结。
- 只有用户显式点击生成才会调用 Provider。每次点击都会为当前图片槽追加一张候选，不覆盖旧候选或已采用图片，也不限制同一主题的抽卡次数；切换主题后，新候选使用当前主题，旧候选继续保留并显示协调度。
- 文章内容决定图片解释什么和使用哪种信息关系；文章主题提供 Visual DNA，解析器从独立图片风格库中选择整篇统一方向，不建立一对一锁定。
- 候选缩略图加载失败时工作台会自动重试一次，仍失败则显示可点击重试入口；文章预览会显示明确加载状态并检测内部图片。连续切换主题时，过期的图片工作区响应不得覆盖当前主题状态。加载提示只代表前端网络状态，不会删除候选或重新调用图片模型。

## 旧 Agnes 配置

旧版 `agnes` 与独立 `gemini` 配置仍会被读取。旧 `IMAGE_API_PROTOCOL` 不再决定新请求；核心会按完整 Endpoint 重新解析，用户下一次在设置页保存后会迁移为统一的 `IMAGE_API_ENDPOINT`、`IMAGE_API_MODEL`、`IMAGE_API_RESOLUTION` 与隐藏 `IMAGE_API_ADAPTER`。
