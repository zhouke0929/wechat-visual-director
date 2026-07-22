# WeChat Visual Director

`wechat-visual-director` 是一个本地优先、可由 Agent 调用的微信公众号视觉排版工作台。它把结构化 Markdown 转为两套可比较的视觉方案，让运营在浏览器中确认组件、插图和封面，同时用确定性渲染降低自由生成 HTML/CSS 带来的不稳定性。

当前版本是 **Alpha**，目标是先验证“Markdown → 视觉方案 → 人工确认”的内部闭环，并作为开源 Skill 发布。它不是 SaaS，也不是完整的微信公众号发布工具。

本项目是独立开源项目，与腾讯或微信官方无隶属或背书关系。

## 当前可用

- 解析 Markdown，并检查标题层级、数据来源与高风险结构；
- 支持 4 类文章、4 套视觉系统和 6 类语义组件；
- 生成结构不同的双方案，支持组件局部换型和撤回；
- 在 390px 移动端画布中实时预览；
- 规划封面与正文图片槽，支持 Mock 候选和人工上传；
- 保存本地任务、方案选择、图片选择和冻结版本；
- 通过 CLI 启动服务、创建任务、查询状态和打开工作台；
- 通过根目录 `SKILL.md` 让 OpenClaw 等宿主 Agent 按统一协议调用。

## Alpha 能力边界

| 能力 | 当前状态 |
|---|---|
| Markdown 预检、双方案、组件与图片确认 | 已实现 |
| 本地任务和确认结果保存 | 已实现 |
| 真实文本/生图模型 | Provider 接口已保留，默认不需要 Key |
| 真实微信公众号草稿创建 | **未实现** |
| 富文本一键复制 | **未实现** |
| 最终群发发布 | **未实现，且必须长期保留人工确认** |

界面中的“冻结版本”或 Mock 草稿只代表本地流程状态，不等于已经写入微信公众号后台。请勿据此宣称端到端发布已打通。

## 架构

```text
宿主 Agent / 用户 Markdown
        ↓
根 Skill + CLI 启动器
        ↓
FastAPI：预检、视觉规划、状态与确定性渲染
        ↓
Next.js：双方案评审、组件/图片/封面确认
        ↓
本地冻结版本（Alpha 当前终点）
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

## 本地启动

当前 Alpha 以 Windows PowerShell 为首要验证环境，需要 Python 3.11+、Node.js 和 pnpm（或 Corepack）。

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install.ps1"
powershell -ExecutionPolicy Bypass -File ".\scripts\visual-director.ps1" doctor --json
powershell -ExecutionPolicy Bypass -File ".\scripts\visual-director.ps1" task create --file ".\samples\skill-alpha\canonical-article.md" --open --json
```

相同输入默认复用既有任务，避免 Agent 重试产生重复记录；确实需要新版本时增加 `--new-task`。停止由 CLI 启动的服务：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\visual-director.ps1" stop --json
```

## 作为 Skill 安装

仓库根目录直接提供 `SKILL.md`。本地来源：

```powershell
openclaw skills install <absolute-repository-path> --as wechat-visual-director
```

GitHub 仓库建立后：

```text
openclaw skills install git:<owner>/wechat-visual-director@main
```

Git 安装只会让宿主发现 Skill；首次使用仍需由 Agent 执行 `scripts/install.ps1` 安装核心程序依赖。核心 CLI/API 不绑定 OpenClaw，其他支持 Skill 或命令调用的 Agent 也可以复用。

## 验证

```powershell
.\apps\api\.venv\Scripts\python.exe -m pytest .\apps\api\tests -q
pnpm --dir .\apps\web typecheck
pnpm --dir .\apps\web build
```

发布前还需要在一台未配置过项目的 Windows 电脑上完成从 GitHub 安装测试；在该测试完成前，本项目保持 Alpha 标记。

## 安全

- 不要把微信公众号 AppSecret、模型 Key、Cookie 或 Token 写进 `SKILL.md`、文章、提示词或命令行；
- 默认示例不包含真实公司名称、二维码或账号资产；
- 外部模型与微信发布适配器未来均采用可选配置，不是本地排版主链路的前置条件。

## License

本项目采用 [Apache License 2.0](LICENSE)。第三方依赖与外部服务仍分别受其自身许可证和使用条款约束。
