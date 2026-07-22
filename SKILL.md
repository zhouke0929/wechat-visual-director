---
name: wechat-visual-director
description: 将公众号主题、资料或 Markdown 初稿整理为 wechat_article.v1，调用本地视觉主编生成双方案，并打开人工评审工作台。Use when an operator asks to create, structure, visually typeset, review, or prepare a WeChat Official Account article from a topic, source material, or .md file; also use when resuming an existing visual-director task. Do not use for final mass publishing without explicit human confirmation.
---

# WeChat Visual Director

把宿主 Agent 作为内容编辑，把本仓库 CLI 作为确定性视觉编译入口。不要自行生成整段 HTML/CSS，也不要把公众号密钥放进文章、提示词或命令行。

## 首次使用

1. 将本 Skill 所在目录记为 `{baseDir}`。若运行环境不展开该占位符，先解析当前 `SKILL.md` 的绝对目录。
2. 在 Windows PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File "{baseDir}/scripts/install.ps1"
```

3. 安装失败时只报告脚本给出的缺失依赖或修复动作；不要绕过版本检查，也不要自行下载不明二进制。

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
- 当前 Alpha 只保存本地冻结版本和 Mock 草稿记录，不具备真实公众号草稿、富文本复制或最终群发能力。
- 未来接入发布适配器后，未经用户明确确认也不得创建公众号草稿；最终群发始终由人工完成。
- 图片模型不可用时允许用户上传、沿用已有图片或跳过，不用无关占位图冒充成稿。
