# 宿主生图桥接

仅在用户确认文章主题后明确要求宿主生成正文图片或封面时读取。不要求用户复制任务 ID，不替换工作台 API、上传、沿用和跳过能力。`{launcher}` 来自主 Skill 的准备回执。

- 用户在工作台确认当前主题后，可直接在对话要求生图，也可从配图/封面区域复制带当前任务链接的指令。先核对任务状态，再检查当前会话实际暴露的生图工具；不能凭“Codex/某宿主支持生图”、工作台 API 未配置或旧回执判断当前工具可用性。无法定位任务时按[任务继续与交付](delivery.md)检索。宿主确有工具时执行下面的读取与导入，不要求用户手填任务 ID 或命令：

```powershell
& "{launcher}" image context <task-id> --json
```

  已采用、已替换或已有任意数量候选的正文图片槽仍会返回新的宿主请求；宿主导入只追加候选并保留当前采用结果。若用户明确要求宿主生成封面，改为执行 `image context <task-id> --asset-type cover --json`；正文和封面都明确要求时可使用 `--asset-type all`。

  只有 `next_action=generate_images_with_host` 且 `requests[]` 非空时才允许调用生图工具。`next_action=host_image_handoff_blocked` 或 `request_count=0` 是硬停止：必须报告 `blocked_targets`，禁止自行编写 Prompt、生图，或通过普通人工上传冒充宿主导入。

  对每条 `requests[]` 必须原样使用 `prompt` 调用当前宿主的原生生图工具，并把结果保存为 PNG、JPEG 或 WebP 本地文件。Codex 可使用会话中的 `$imagegen`；其他宿主只有在存在等价可调用工具时才执行。正文图片生成完成后，严格使用同一条请求返回的绑定字段导入：

```powershell
& "{launcher}" image import <task-id> --plan-id <plan-id> --slot-id <image-slot-id> --request-id <request-id> --expected-plan-revision <plan-revision> --expected-image-revision <image-revision> --file "<absolute-image-path>" --host-name "<actual-host>" --host-model "<actual-image-model-or-host_managed>" --json
```

  封面请求使用专用绑定字段导入，不传 `--slot-id` 或正文 revision：

```powershell
& "{launcher}" image import <task-id> --asset-type cover --plan-id <plan-id> --request-id <request-id> --expected-plan-revision <plan-revision> --expected-cover-candidate-count <cover-candidate-count> --file "<absolute-image-path>" --host-name "<actual-host>" --host-model "<actual-image-model-or-host_managed>" --json
```

  正文和封面导入都只会新增待审核候选，绝不自动采用，也不覆盖当前采用结果。生成期间只切换主题（包括切走后切回）不会拒绝导入：正文保留生成时的 Visual DNA 快照并按当前主题给出兼容度提示；封面保留生成时主题与宿主回执。若返回 `host_image_request_stale`、`host_image_semantic_context_changed`、`host_image_revision_changed`、`host_cover_request_stale`、`host_cover_semantic_context_changed` 或 `host_cover_revision_changed`，说明历史请求不存在、文章/图片任务已改变，或候选状态已变化；此时重新执行对应的 `image context`，不得强制导入。宿主没有原生生图能力时明确返回 `host_image_generation_unavailable`，继续允许工作台 API 生图、人工上传、沿用原图或跳过；不得静默调用收费图片 API，也不得要求用户为了这条可选路径再配置 Key。

结构信息图须人工核对锁定文字后采用；普通配图与封面按大图审核。主题切换不删除或自动重生成已采用图片。配图方向、API 配置和封面显示区需要时读 [图片 Provider](image-providers.md)，异常状态查 [CLI 契约](cli-contract.md)。
