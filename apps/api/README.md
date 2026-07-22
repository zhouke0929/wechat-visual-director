# Visual Director API

第一轮纵向切片使用规则型规划器建立可重复基线，并通过同一份 VisualPlan 边界预留真实文本模型接入。任务和渲染产物默认保存到 `data/visual-director.db`。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn visual_director.main:app --reload --port 8000
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```
