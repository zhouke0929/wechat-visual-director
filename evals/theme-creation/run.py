"""Freeze raw evaluation inputs and build a local calibration board; no model calls."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    allowed = (root / "artifacts").resolve(), (root / "evals/theme-creation/fixtures").resolve()
    if not any(path.is_relative_to(base) for base in allowed):
        raise ValueError(f"Source outside evaluation material: {relative}")
    return path


def validate_suite(suite: dict) -> None:
    if suite.get("schema_version") != "theme_creation_eval.v1":
        raise ValueError("Unsupported suite version")
    ids: set[str] = set()
    for case in suite["cases"]:
        if case["id"] in ids or not re.fullmatch(r"[a-z0-9-]+", case["id"]):
            raise ValueError("Invalid or repeated case id")
        ids.add(case["id"])
        names = [item["name"] for item in case["inputs"]]
        if len(names) != len(set(names)) or "article.md" not in names:
            raise ValueError("Case needs unique input names and article.md")
        for item in case["inputs"]:
            if Path(item["name"]).name != item["name"] or "\\" in item["name"]:
                raise ValueError("Input names must be plain filenames")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", item["sha256"]):
                raise ValueError("Input needs SHA256")


def checked(root: Path, items: list[dict]) -> list[tuple[dict, Path]]:
    result = []
    for item in items:
        path = source(root, item["path"])
        if not path.is_file():
            raise ValueError(f"Missing local evidence: {item['path']}")
        if digest(path) != item["sha256"].lower():
            raise ValueError(f"Evidence hash changed: {item['path']}")
        result.append((item, path))
    return result


def destination(root: Path, out: Path) -> Path:
    out = out.resolve()
    if not any(out.is_relative_to((root / name).resolve()) and out != (root / name).resolve()
               for name in ("artifacts", ".tmp")):
        raise ValueError("Output must be a new subdirectory of artifacts or .tmp")
    if out.exists():
        raise ValueError("Output already exists; preserve previous evidence")
    return out


def inspect(root: Path, suite: dict) -> dict:
    result = []
    for case in suite["cases"]:
        try:
            checked(root, case["inputs"])
            available, error = True, None
        except ValueError as exc:
            available, error = False, str(exc)
        result.append({"id": case["id"], "status": case["status"],
                       "inputs_available": available, "error": error})
    return {"cases": result, "model_calls": 0, "visual_result": "not_reviewed"}


def prepare(root: Path, suite: dict, case_id: str, out: Path, port: int) -> dict:
    case = next((c for c in suite["cases"] if c["id"] == case_id), None)
    if case is None:
        raise ValueError("Unknown case")
    if not 1024 <= port <= 65535 or port == 8000:
        raise ValueError("Choose a non-production local port")
    inputs = checked(root, case["inputs"])
    out = destination(root, out)
    skill = root / "skills/wechat-visual-director"
    files = [(p, p.relative_to(skill)) for p in sorted(skill.rglob("*"))
             if p.is_file() and not {"evals", "__pycache__"}.intersection(p.relative_to(skill).parts)]
    if not (skill / "SKILL.md").is_file():
        raise ValueError("Repository Skill is missing")
    out.mkdir(parents=True)
    (out / "input").mkdir()
    runtime = out / "output/runtime"
    runtime.mkdir(parents=True)
    for item, path in inputs:
        shutil.copy2(path, out / "input" / item["name"])
    snapshot_hashes = {}
    for path, relative in files:
        target = out / "skill-snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        snapshot_hashes[relative.as_posix()] = digest(target)
    shutil.copy2(HERE / "runtime_cli.py", out / "output/isolated_cli.py")
    (runtime / "empty.env").write_text("", encoding="utf-8")
    (runtime / "brand.json").write_text(json.dumps({"name": "隔离主题试样", "fixed_footer": {"enabled": False}}, ensure_ascii=False), encoding="utf-8")
    (out / "output/runtime-config.json").write_text(json.dumps({"repository": str(root), "port": port}), encoding="utf-8")
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False).stdout.strip() or "unknown"
        state = subprocess.run(["git", "status", "--porcelain", "--", "skills/wechat-visual-director"], cwd=root, capture_output=True, text=True, check=False)
        skill_dirty = bool(state.stdout.strip()) if state.returncode == 0 else None
    except OSError:
        revision = "unknown"
        skill_dirty = None
    lock = {"schema_version": "theme_eval_run.v1", "case_id": case_id,
            "suite_revision": suite["revision"], "case_status_at_prepare": case["status"],
            "skill_commit": revision, "skill_dirty": skill_dirty, "port": port,
            "input_sha256": {i["name"]: i["sha256"].lower() for i, _ in inputs},
            "skill_sha256": snapshot_hashes,
            "visual_result": "not_reviewed", "wechat_result": "not_verified"}
    (out / "run-lock.json").write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
    assessment = read_json(HERE / "assessment-template.json")
    assessment.update({"case_id": case_id, "skill_commit": revision,
                       "suite_revision": suite["revision"]})
    (out / "assessment.json").write_text(json.dumps(assessment, ensure_ascii=False, indent=2), encoding="utf-8")
    prompt = f"""请使用 {out.as_posix()}/skill-snapshot/SKILL.md 中指定版本的 wechat-visual-director Skill 完成需求，不使用机器上旧的同名副本。

{case['request']}

原始输入目录：{out.as_posix()}/input
唯一输出目录：{out.as_posix()}/output

这是隔离的新会话验证。只读取本次输入、指定 Skill 及按需引用；可以读取必要的工具操作与安全说明，以及生产源码、Schema 和字段模板了解接口。不要读取其它 artifacts、评测目录、旧对话、审计、预期答案或已有自定义主题成品，不从官方主题挑外观零件。不改源码、Skill、原稿或参考，不提交/推送 Git。

output/isolated_cli.py 负责清除继承的业务配置，把数据库、主题库与缓存限定在本次 output；本地服务仅用 127.0.0.1:{port}，需要时用当前 Python 调用此入口的 serve-isolated。端口冲突就报告，不复用未知服务。不要运行安装/升级/准备脚本，不连接正式工作台、微信或付费图片服务，不读取密钥或私有配置。正常文章走生产解析、Brief、编译/规划、渲染链，不手写 HTML 文章冒充；导航可手写。

按指定 Skill 完成，本轮自行看图自审，不委派、不再开对话。保留首次完整版和真实修订证据。交付完整 JSON/.vdtheme、正常文章与全组件入口、绑定定版的简短检查和评审回执；如实记录未测项，不编造分数、成功率、token 或费用。
"""
    (out / "task-prompt.md").write_text(prompt, encoding="utf-8")
    return {"prepared": True, "case_id": case_id, "prompt": str(out / "task-prompt.md"),
            "model_calls": 0, "visual_result": "not_reviewed"}


def verify(run: Path) -> dict:
    run = run.resolve()
    lock = read_json(run / "run-lock.json")
    if lock.get("schema_version") != "theme_eval_run.v1":
        raise ValueError("Unsupported run lock")
    changed = []
    for folder, field in (("input", "input_sha256"), ("skill-snapshot", "skill_sha256")):
        base = run / folder
        expected = lock[field]
        for name, expected_hash in expected.items():
            path = (base / name).resolve()
            if not path.is_relative_to(base.resolve()):
                raise ValueError("Unsafe run lock path")
            if not path.is_file() or digest(path) != expected_hash:
                changed.append(f"{folder}/{name}")
        extras = {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()} - set(expected)
        changed.extend(f"{folder}/{name}" for name in sorted(extras))
    return {"inputs_and_skill_unchanged": not changed, "changed": changed,
            "visual_result": "not_reviewed", "wechat_result": "not_verified"}


def board(root: Path, suite: dict, out: Path) -> dict:
    assets = checked(root, suite["anchors"])
    out = destination(root, out)
    out.mkdir(parents=True)
    (out / "assets").mkdir()
    cards = []
    entries = []
    for index, (anchor, path) in enumerate(assets, 1):
        filename = f"anchor-{index}.png"
        shutil.copy2(path, out / "assets" / filename)
        esc = html.escape
        cards.append(f'''<article data-anchor="{esc(anchor['id'])}"><header><span>0{index} / {esc(anchor['role'])}</span><h2>{esc(anchor['title'])}</h2></header><div class="image"><img src="assets/{filename}" alt="{esc(anchor['title'])}" width="357"></div><details><summary>展开暂定定位与依据</summary><p class="label">{esc(anchor['label'])} · 尚待产品负责人确认</p><p>{esc(anchor['reason'])}</p><p class="boundary">{esc(anchor['boundary'])}</p></details><label>你的校准<select><option value="pending">待确认</option><option value="agree">同意此定位</option><option value="adjust">需要调整定位</option></select></label><label>补充理由<textarea rows="2" placeholder="如果不同意，说明哪处画面改变了你的判断"></textarea></label></article>''')
        entries.append({"id": anchor["id"], "source_sha256": anchor["sha256"], "provisional_label": anchor["label"]})
    data = json.dumps(entries, ensure_ascii=False).replace("<", "\\u003c")
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>主题评测 · 校准四个判断</title><style>
    :root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f4f2ed;color:#172e28;font:15px/1.8 "Microsoft YaHei",sans-serif}main{max-width:1040px;margin:0 auto;padding:44px 24px 64px}.eyebrow{font:12px Consolas,monospace;letter-spacing:2px;color:#63756c}h1{font:36px/1.35 "SimSun",serif;margin:16px 0}main>p{max-width:720px;color:#53665e}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px;margin-top:32px}article{background:white;padding:24px;border-top:3px solid #244f43;min-width:0}header span{font:12px Consolas,monospace;color:#63756c}h2{font:22px/1.5 "SimSun",serif;margin:12px 0 20px}.image{overflow:auto;border-bottom:1px solid #e7ebe6;padding-bottom:20px}.image img{display:block;max-width:none;width:357px;height:auto}details{margin:18px 0;border-bottom:1px solid #e7ebe6;padding-bottom:16px}summary{cursor:pointer;color:#244f43}.label{font-weight:bold}.boundary{color:#6c7067;font-size:13px}label{display:block;font-size:13px;margin-top:12px}select,textarea{display:block;width:100%;font:inherit;font-size:14px;line-height:1.7;color:#172e28;padding:9px;border:1px solid #cdd8cf;background:#fcfdfb;margin-top:6px}button{font:15px "Microsoft YaHei",sans-serif;background:#244f43;color:white;border:0;padding:14px 22px;margin-top:24px;cursor:pointer}:focus-visible{outline:3px solid #bf8a35;outline-offset:3px}footer{margin-top:24px;color:#63756c;font-size:13px}@media(max-width:850px){.grid{grid-template-columns:1fr}main{padding:28px 16px}h1{font-size:29px}article{padding:18px}}
    </style><main><div class="eyebrow">VISUAL DIRECTOR / EVALUATION CALIBRATION</div><h1>先校准判断，再继续盲测。</h1><p>这里只看四个局部样本：哪些值得保留，哪些只是可用，哪些仍需改善。先看图，再展开暂定定位；它们不是客观美观分，也不代表整套主题通过。图片保持手机正文原生 357px，窄屏可在图内横向查看。</p><div class="grid">''' + "".join(cards) + '''</div><button id="export">导出校准意见</button><p id="status" role="status"></p><footer>意见只在本页填写，点击导出后下载 JSON；没有网络请求，不会自动保存或修改项目。保留未确认项，不推断整体通过或成功率。</footer></main><script>const anchors=''' + data + ''';document.querySelector('#export').addEventListener('click',()=>{const items=[...document.querySelectorAll('article')].map((card,i)=>({...anchors[i],decision:card.querySelector('select').value,reason:card.querySelector('textarea').value}));const result={schema_version:'theme_owner_calibration.v1',status:'human_calibration',created_at:new Date().toISOString(),items};const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='theme-owner-calibration.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);document.querySelector('#status').textContent='已导出；待确认项保持未确认。';});</script></html>'''
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "evidence-lock.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"page": str(out / "index.html"), "anchors": len(entries), "owner_confirmation": "pending", "model_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    p = sub.add_parser("prepare")
    p.add_argument("--case", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--port", type=int, required=True)
    p = sub.add_parser("verify")
    p.add_argument("--run", type=Path, required=True)
    p = sub.add_parser("board")
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        suite = read_json(HERE / "suite.json")
        validate_suite(suite)
        if args.command == "inspect":
            result = inspect(ROOT, suite)
        elif args.command == "prepare":
            result = prepare(ROOT, suite, args.case, args.out, args.port)
        elif args.command == "verify":
            result = verify(args.run)
        else:
            result = board(ROOT, suite, args.out)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("inputs_and_skill_unchanged") is False else 0
    except (ValueError, OSError, KeyError, StopIteration) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
