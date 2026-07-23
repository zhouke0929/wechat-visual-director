---
name: wechat-visual-director
description: 将公众号主题、资料或 Markdown 初稿整理为 wechat_article.v1，调用本地视觉主编生成双方案，并打开人工评审工作台。Use when an operator asks to create, structure, visually typeset, review, or prepare a WeChat Official Account article from a topic, source material, or .md file; also use when resuming an existing visual-director task. Do not use for final mass publishing without explicit human confirmation.
---

# WeChat Visual Director

把宿主 Agent 作为内容编辑，把本仓库 CLI 作为视觉规划与确定性编译入口。宿主 Agent 负责把主题和资料整理成规范 Markdown；配置文本模型后，由核心规划器理解全文并输出受控 EditorialBrief，确定性编译器再完成组件选择与渲染。未配置模型时使用规则规划作为零成本兜底。不要自行生成整段 HTML/CSS，也不要把公众号密钥或模型 Key 放进文章、提示词或命令行。

## 首次使用

1. 将本 Skill 所在目录记为 `{baseDir}`。若运行环境不展开该占位符，先解析当前 `SKILL.md` 的绝对目录。
2. 在 Windows PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File "{baseDir}/scripts/install.ps1"
```

3. 执行 `doctor --json`。`ai_text_planning=true` 表示核心会调用已配置的文本模型；`rule_text_planning=true` 表示当前使用确定性规则兜底。两种模式都能生成方案，但不得把规则模式描述为真实 AI 规划。
4. 安装失败时只报告脚本给出的缺失依赖或修复动作；不要绕过版本检查，也不要自行下载不明二进制。

## 创建文章任务

1. 读取用户主题、资料和明确约束。已有 Markdown 时保留其事实、数字、来源、观点与结论。
2. 写作或整理前读取 [文章协议](references/article-protocol.md)。需要处理 CLI 状态或错误时再读取 [CLI 契约](references/cli-contract.md)。
3. 将最终稿保存为 UTF-8 `.md` 临时文件。正文只能有一个 H1；H2 是主章节；H3 是章节内小主题。不要用 HTML/CSS 指定视觉效果。
4. 执行：

```powershell
powershell -ExecutionPolicy Bypass -File "{baseDir}/scripts/visual-director.ps1" task create --file "<absolute-article-path>" --open --json
```

5. 只解析 stdout 中的 JSON：
   - `next_action=fix_source`：只修复明确 finding，再用同一幂等语义重试；不得补造事实。
   - `next_action=human_review`：把 `review_url` 告知用户并停止自主操作，等待其在工作台选择方案、组件、图片与封面。
   - `idempotency_replayed=true`：说明复用了同一输入的既有任务，不要再创建副本。
6. 用户明确要求“重新开一篇/另建版本”时，才在创建命令增加 `--new-task`。

## 人工确认与交付

- 收到 `next_action=human_review` 后，把工作台链接交给用户并暂停；不得替用户选择方案或点击发布。
- 工作台可以冻结最终版本、实验性复制富文本、下载交付包；本机配置 Wenyan 后还可以创建微信公众号草稿。
- Wenyan 配置只允许来自本机进程环境或 Git 忽略的 `.env.local`。不要要求用户把 AppID、AppSecret 粘贴进对话。
- 草稿结果为 `unknown` 时，先让用户去公众号后台核对；不得自动重试，以免产生重复草稿。
- “创建公众号草稿”不等于最终发布；群发操作始终由用户在公众号后台完成。

## 继续已有任务

查询状态：

```powershell
powershell -ExecutionPolicy Bypass -File "{baseDir}/scripts/visual-director.ps1" task status <task-id> --json
```

重新打开：

```powershell
powershell -ExecutionPolicy Bypass -File "{baseDir}/scripts/visual-director.ps1" task open <task-id> --json
```

服务异常时先执行 `doctor --json`；仅停止由本 CLI 启动且身份校验通过的进程：

```powershell
powershell -ExecutionPolicy Bypass -File "{baseDir}/scripts/visual-director.ps1" stop --json
```

## 安全门禁

- 不读取、回显或写入 AppSecret、API Key、Cookie、Token。
- 不把上一篇文章的主题、事实或临时资料混入当前稿件。
- 不为触发组件而制造概念、结论、因果、案例或数据。
- 不自行确认 Preflight finding，不自行选择视觉方案。
- 当前 Alpha 支持本地冻结版本、实验性富文本复制、交付包下载，以及可选的本地 Wenyan 草稿适配器。
- 未经用户在工作台明确确认不得创建公众号草稿；最终群发始终由人工完成。
- 图片模型不可用时允许用户上传、沿用已有图片或跳过，不用无关占位图冒充成稿。
- 模型 Key 只允许由用户在 Git 忽略的 `.env.local` 或独立私有环境文件中配置；不得要求用户粘贴到对话。
