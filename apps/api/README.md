# Visual Director API

FastAPI 本地核心负责 Markdown 解析、预检、EditorialBrief 校验与规范化、视觉方案编译、内联 HTML 渲染、图片候选、任务持久化和可选微信公众号草稿适配。

日常用户应把仓库根目录的 `INSTALL_FOR_AGENT.md` 链接交给 Agent，由它安装带内置运行时的正式 Release，并同时注册轻量 Skill；本目录和 `scripts/install.ps1` 主要供源码开发、发行构建与测试使用。

## 开发启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m uvicorn visual_director.main:app --reload --port 8000
```

默认数据库位于 `data/visual-director.db`。该目录、`.env.local`、运行日志和图片产物均不应提交到 Git。

## 测试

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -m pytest tests -q
```

API 基础地址：`http://127.0.0.1:8000/api/v1`。面向宿主 Agent 的稳定调用方式与状态机见仓库中的 `skills/wechat-visual-director/references/cli-contract.md` 和 `skills/wechat-visual-director/SKILL.md`。
