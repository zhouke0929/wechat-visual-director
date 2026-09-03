# CLI 调用契约

首次使用先运行 Skill 内 `scripts/ensure-workbench.ps1` 或 `scripts/ensure-workbench.sh`：缺失时安装正式包，已有时启动检查；成功 JSON 的 `launcher` 为后续稳定入口，`workbench_url` 为用户入口。失败或显式安装恢复时读取同目录的 `install.md`。不要手动启动系统 Python、uvicorn、Next.js 或 Vite。

## 常用命令

```powershell
# 环境和服务状态
& "{launcher}" doctor --json

# 创建任务，自动规划并打开工作台
& "{launcher}" task create --file C:\path\article.md --open --json

# Skill 默认流程：创建任务后复用宿主 Agent 生成 Brief
& "{launcher}" task create --file C:\path\article.md --no-plan --json
& "{launcher}" task context <task-id> --json
& "{launcher}" task plan <task-id> --brief C:\path\editorial-brief.json --expected-task-version <version> --host-model host_managed --open --json

# 同一原稿显式另建任务
& "{launcher}" task create --file C:\path\article.md --new-task --open --json

# 查询和打开任务
& "{launcher}" task status <task-id> --json
& "{launcher}" task open <task-id> --json

# 用户确认主题后，读取当前宿主可执行的受控配图请求
& "{launcher}" image context <task-id> --json

# 用户明确要求宿主生成封面时，只读取封面请求
& "{launcher}" image context <task-id> --asset-type cover --json

# 宿主原生生图完成后，把文件导回工作台作为待审核候选
& "{launcher}" image import <task-id> --plan-id <plan-id> --slot-id <image-slot-id> --request-id <request-id> --expected-plan-revision <plan-revision> --expected-image-revision <image-revision> --file C:\path\image.png --host-name codex --host-model gpt-image-2 --json

# 宿主封面完成后，按封面候选计数绑定导回工作台
& "{launcher}" image import <task-id> --asset-type cover --plan-id <plan-id> --request-id <request-id> --expected-plan-revision <plan-revision> --expected-cover-candidate-count <count> --file C:\path\cover.png --host-name codex --host-model gpt-image-2 --json

# 安全停止本 CLI 启动的服务
& "{launcher}" stop --json

# 只读盘点当前及旧数据目录
& "{launcher}" data scan --candidate C:\path\to\old\apps\api\data --json

# 服务停止后，把旧数据迁移到空目标；非空目标还必须显式增加 --activate --yes
& "{launcher}" data recover --from C:\path\to\old\apps\api\data --json
```

## 关键输出

- `command_completed=true`：当前 CLI 命令已经完成；后台服务是独立进程，不得继续等待其退出。
- `background=true`、`process_mode=detached`：`serve`/`bootstrap` 已在无控制台后台模式启动或复用服务，宿主终端可以立即结束。
- `status=plans_ready`：双方案已经生成，可以评审。
- `next_action=fix_source`：读取同一 JSON 中未解决的 `findings`，只修复明确的 Markdown 问题；`source_structure_too_flat` 只允许整理原稿已有关系。
- `next_action=generate_editorial_brief`：读取 `task context`，由当前宿主 Agent 或可选子智能体生成 Brief。
- `next_action=human_review`：把 `review_url` 交给用户，暂停 Agent 自主操作。
- `next_action=generate_images_with_host`：仅当当前宿主暴露原生生图工具时，逐条执行 `requests[]` 并用 `image import` 回传；否则返回 `host_image_generation_unavailable`。
- `next_action=host_image_handoff_blocked`：当前没有可执行请求；读取 `blocked_targets` 后停止，禁止自行补写 Prompt、生图或改走普通上传。
- 已采用、已替换或已有多个候选的正文图片槽仍可继续获得请求；新图只追加为候选，不覆盖当前采用结果。正文和封面候选都不设置抽卡数量上限。
- 生成期间只切换主题不会使请求失效；旧图仍导入为候选，并按当前主题返回 `theme_compatibility`，由用户人工决定是否采用。
- `host_image_request_stale`、`host_image_semantic_context_changed`、`host_image_revision_changed`：历史请求不存在、正文锚点/图片任务已改变，或请求发出后图片槽又发生变化；重新读取上下文，不要覆盖当前候选。
- `host_cover_request_stale`、`host_cover_semantic_context_changed`、`host_cover_revision_changed`：封面历史请求不存在、文章封面语义已变化或候选列表已变化；重新读取封面上下文。
- `planner_provider=host_agent`：本次使用了宿主提交的 Brief，核心没有再次调用文本模型。
- `fallback_used=true`：宿主 Brief 无效或无法编译，方案已透明降级为规则规划。
- `normalization_count>0`：核心对 Brief 做了不改变事实的安全规范化。
- `idempotency_replayed=true`：相同输入已存在，返回原任务。
- `opened=false`：浏览器自动打开失败，但任务仍成功；直接提供 `review_url`。
- `doctor.capabilities.ai_text_planning=true`：核心已配置真实文本规划模型。
- `doctor.capabilities.host_agent_text_planning=true`：核心支持接收宿主 Agent Brief，不代表当前任务已成功采用。
- `doctor.capabilities.host_skill_registered=true`：用户级 Skill 已注册；同时可从 `doctor.host_integrations.skill` 检查通用目录、OpenCode 目录与斜杠命令。
- `doctor.capabilities.rule_text_planning=true`：当前使用确定性规则兜底；可以排版，但不得宣称调用了 AI 文本规划。
- `doctor.capabilities.wechat_draft=true`：内置微信官方 API 发布器与公众号凭据已就绪，但仍需人工确认公网出口 IP 已加入白名单。
- `doctor.capabilities.rich_copy=true`：工作台提供实验性富文本复制；粘贴后必须保存、重开并在手机端检查图片。
- `doctor.capabilities.bundle_export=true`：冻结版本可以下载为本地交付包。
- `doctor.installation.persistent=true`：当前使用固定安装目录；同时核对 `version`、`app_root` 和 `data_root`。
- `doctor.installation.version_match=true`：当前 API 进程与已安装版本一致；`core_version_mismatch` 时不得继续创建任务，先停止旧服务并重新启动。
- `workbench_build_missing`：当前 FastAPI 版本没有匹配的静态工作台；重新运行安装器，不要另起前端开发服务器。
- `target_has_tasks`：恢复目标已有任务，必须先人工核对扫描结果；需要切换时显式使用 `--activate --yes`，系统会先备份。

退出码：`0` 成功；`2` 输入/配置错误；`3` 本地服务不可用；`4` Preflight 阻断；`5` 规划或 Provider 失败；`6` 安全停止拒绝；`10` 未知内部错误。

不要解析人类可读文案，不要从 stderr 提取任务信息。需要审计实现时再查看源码仓库中的 [完整技术契约](https://github.com/zhouke0929/wechat-visual-director/blob/main/docs/V1.0-Agent调用与CLI契约.md)；普通使用不需要克隆源码。
