# CLI 调用契约

入口脚本：`{baseDir}/scripts/visual-director.ps1`。

## 常用命令

```powershell
# 环境和服务状态
./scripts/visual-director.ps1 doctor --json

# 创建任务，自动规划并打开工作台
./scripts/visual-director.ps1 task create --file C:\path\article.md --open --json

# Skill 默认流程：创建任务后复用宿主 Agent 生成 Brief
./scripts/visual-director.ps1 task create --file C:\path\article.md --no-plan --json
./scripts/visual-director.ps1 task context <task-id> --json
./scripts/visual-director.ps1 task plan <task-id> --brief C:\path\editorial-brief.json --expected-task-version <version> --host-model host_managed --open --json

# 同一原稿显式另建任务
./scripts/visual-director.ps1 task create --file C:\path\article.md --new-task --open --json

# 查询和打开任务
./scripts/visual-director.ps1 task status <task-id> --json
./scripts/visual-director.ps1 task open <task-id> --json

# 安全停止本 CLI 启动的服务
./scripts/visual-director.ps1 stop --json
```

## 关键输出

- `status=plans_ready`：双方案已经生成，可以评审。
- `next_action=fix_source`：修复明确的 Markdown 问题。
- `next_action=generate_editorial_brief`：读取 `task context`，由当前宿主 Agent 或可选子智能体生成 Brief。
- `next_action=human_review`：把 `review_url` 交给用户，暂停 Agent 自主操作。
- `planner_provider=host_agent`：本次使用了宿主提交的 Brief，核心没有再次调用文本模型。
- `fallback_used=true`：宿主 Brief 无效或无法编译，方案已透明降级为规则规划。
- `normalization_count>0`：核心对 Brief 做了不改变事实的安全规范化。
- `idempotency_replayed=true`：相同输入已存在，返回原任务。
- `opened=false`：浏览器自动打开失败，但任务仍成功；直接提供 `review_url`。
- `doctor.capabilities.ai_text_planning=true`：核心已配置真实文本规划模型。
- `doctor.capabilities.host_agent_text_planning=true`：核心支持接收宿主 Agent Brief，不代表当前任务已成功采用。
- `doctor.capabilities.rule_text_planning=true`：当前使用确定性规则兜底；可以排版，但不得宣称调用了 AI 文本规划。
- `doctor.capabilities.wechat_draft=true`：本机 Wenyan 与公众号凭据已就绪，但仍需人工确认公网出口 IP 已加入白名单。
- `doctor.capabilities.rich_copy=true`：工作台提供实验性富文本复制；粘贴后必须保存、重开并在手机端检查图片。
- `doctor.capabilities.bundle_export=true`：冻结版本可以下载为本地交付包。

退出码：`0` 成功；`2` 输入/配置错误；`3` 本地服务不可用；`4` Preflight 阻断；`5` 规划或 Provider 失败；`6` 安全停止拒绝；`10` 未知内部错误。

不要解析人类可读文案，不要从 stderr 提取任务信息。完整技术契约见 `{baseDir}/docs/V1.0-Agent调用与CLI契约.md`。
