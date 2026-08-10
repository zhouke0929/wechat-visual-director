"use client";

import Link, { useRouter } from "@/lib/router";
import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowIcon, UploadIcon } from "@/components/icons";
import { StatusPill } from "@/components/status-pill";
import { createTask, deleteTasks, getApplicationVersion, listTasks } from "@/lib/api";
import type { Task } from "@/lib/types";

const articleTypes = [
  ["", "自动识别"],
  ["data_policy", "数据 / 政策"],
  ["viewpoint_trend", "观点 / 趋势"],
  ["tutorial_steps", "教程 / 步骤"],
  ["lively_growth", "活动 / 成长"],
];

const articleLabels: Record<string, string> = {
  data_policy: "数据 / 政策",
  viewpoint_trend: "观点 / 趋势",
  tutorial_steps: "教程 / 步骤",
  lively_growth: "活动 / 成长",
};

export default function EditorialDeskPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [articleType, setArticleType] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [taskError, setTaskError] = useState("");
  const [appVersion, setAppVersion] = useState("ALPHA");
  const [manageTasks, setManageTasks] = useState(false);
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [taskNotice, setTaskNotice] = useState("");

  useEffect(() => {
    listTasks()
      .then(setTasks)
      .catch((reason: Error) => setTaskError(reason.message))
      .finally(() => setLoading(false));
    getApplicationVersion().then(setAppVersion).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!confirmDelete) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !deleting) setConfirmDelete(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [confirmDelete, deleting]);

  async function chooseValidationSample() {
    setError("");
    try {
      const response = await fetch("/sample-tutorial.md");
      if (!response.ok) throw new Error("验收样本暂时无法读取");
      const content = await response.text();
      setFile(new File([content], "sample-tutorial.md", { type: "text/markdown" }));
      setArticleType("tutorial_steps");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "验收样本暂时无法读取");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("请先选择一份 Markdown 文件");
      inputRef.current?.focus();
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const task = await createTask(file, articleType);
      router.push(`/tasks/${task.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建任务失败");
      setSubmitting(false);
    }
  }

  function toggleTaskSelection(taskId: string) {
    setSelectedTaskIds((current) => {
      const next = new Set(current);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  function closeManageMode() {
    setManageTasks(false);
    setSelectedTaskIds(new Set());
    setTaskNotice("");
    setTaskError("");
  }

  async function confirmTaskDeletion() {
    const ids = Array.from(selectedTaskIds);
    if (ids.length === 0) return;
    setDeleting(true);
    setTaskError("");
    try {
      const result = await deleteTasks(ids);
      const deleted = new Set(result.deleted_task_ids);
      setTasks((current) => current.filter((task) => !deleted.has(task.id)));
      setSelectedTaskIds(new Set());
      setManageTasks(false);
      setConfirmDelete(false);
      setTaskNotice(
        result.asset_cleanup_warnings.length > 0
          ? `已删除 ${result.deleted_count} 个任务；有少量缓存素材将在维护时继续清理。`
          : `已删除 ${result.deleted_count} 个历史任务。`,
      );
    } catch (reason) {
      setTaskError(reason instanceof Error ? reason.message : "删除历史任务失败");
      setConfirmDelete(false);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="desk-page">
      <header className="topbar">
        <Link className="wordmark" href="/" aria-label="返回视觉主编任务台">
          <span className="wordmark-cn">视觉主编</span>
          <span className="wordmark-en">WECHAT VISUAL DIRECTOR</span>
        </Link>
        <div className="topbar-actions">
          <Link className="gallery-link" href="/theme-gallery">主题样本册</Link>
          <Link className="gallery-link settings-link" href="/settings">本地设置</Link>
          <span className="baseline-badge">LOCAL · {appVersion}</span>
        </div>
      </header>

      <section className="hero-grid" aria-labelledby="page-title">
        <div className="hero-copy">
          <p className="eyebrow">CONTENT OPERATIONS / 01</p>
          <h1 id="page-title">让每篇文章拥有自己的视觉节奏。</h1>
          <p>
            导入 Markdown 后先检查标题、层级、来源和占位资产；确认没有生成前阻断，再基于品牌约束与最近 5 篇历史编译两套视觉系统。
          </p>
          <dl className="hero-metrics">
            <div><dt>智能规划</dt><dd>1 次</dd></div>
            <div><dt>历史窗口</dt><dd>5 篇</dd></div>
            <div><dt>预览宽度</dt><dd>390 px</dd></div>
          </dl>
        </div>

        <form className="import-panel" onSubmit={handleSubmit} aria-labelledby="import-title">
          <div className="panel-heading">
            <span>NEW BRIEF</span>
            <h2 id="import-title">创建视觉方案</h2>
          </div>
          <label className="file-drop" htmlFor="markdown-file">
            <UploadIcon />
            <span className="file-drop-copy">
              <strong>{file?.name ?? "选择 Markdown 初稿"}</strong>
              <small>{file ? `${Math.max(1, Math.round(file.size / 1024))} KB · UTF-8` : "支持 .md / .markdown，最大 2MB"}</small>
            </span>
            <span className="file-action">浏览文件</span>
          </label>
          <input
            ref={inputRef}
            className="visually-hidden"
            id="markdown-file"
            type="file"
            accept=".md,.markdown,text/markdown"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />

          <div className="form-row">
            <label htmlFor="article-type">文章类型（可选）</label>
            <select id="article-type" value={articleType} onChange={(event) => setArticleType(event.target.value)}>
              {articleTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <p className="form-hint">默认自动识别；它只影响主题、组件样式和配图方向，不会改写文章内容。</p>

          {error ? <p className="form-error" role="alert">{error}</p> : null}

          <div className="form-actions">
            <button className="text-button" type="button" onClick={chooseValidationSample} disabled={submitting}>
              使用验收样本
            </button>
            <button className="primary-button" type="submit" disabled={submitting}>
              <span>{submitting ? "正在检查初稿…" : "创建任务并预检"}</span>
              <ArrowIcon />
            </button>
          </div>
        </form>
      </section>

      <section className="task-section" aria-labelledby="recent-title">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">RECENT BRIEFS</p>
            <h2 id="recent-title">最近任务</h2>
          </div>
          <div className="task-heading-actions">
            <p>任务创建时会冻结品牌版本、历史窗口和 CTA 版本。</p>
            {tasks.length > 0 && !manageTasks ? (
              <button className="task-manage-button" type="button" onClick={() => { setManageTasks(true); setTaskNotice(""); setTaskError(""); }}>
                管理历史任务
              </button>
            ) : null}
          </div>
        </div>

        {manageTasks ? (
          <div className="task-manage-toolbar" aria-label="历史任务批量管理">
            <button
              className="task-select-all"
              type="button"
              onClick={() => setSelectedTaskIds(
                selectedTaskIds.size === tasks.length ? new Set() : new Set(tasks.map((task) => task.id)),
              )}
            >
              <span className={selectedTaskIds.size === tasks.length ? "task-check is-selected" : "task-check"} aria-hidden="true">
                {selectedTaskIds.size === tasks.length ? "✓" : ""}
              </span>
              {selectedTaskIds.size === tasks.length ? "取消全选" : "全选当前任务"}
            </button>
            <span className="task-selected-count" aria-live="polite">已选 {selectedTaskIds.size} 项</span>
            <div className="task-manage-toolbar-actions">
              <button className="task-cancel-button" type="button" onClick={closeManageMode}>退出管理</button>
              <button
                className="task-delete-button"
                type="button"
                disabled={selectedTaskIds.size === 0}
                onClick={() => setConfirmDelete(true)}
              >
                删除所选
              </button>
            </div>
          </div>
        ) : null}

        {taskNotice ? <p className="task-notice" role="status">{taskNotice}</p> : null}
        {taskError ? <p className="task-notice task-notice-error" role="alert">{taskError}</p> : null}

        {loading ? <div className="loading-line" role="status">正在读取任务…</div> : null}
        {!loading && tasks.length === 0 ? (
          <div className="empty-state">
            <span>01</span>
            <h3>还没有视觉任务</h3>
            <p>从上方导入验收样本，约数秒后即可对比第一组方案。</p>
          </div>
        ) : null}
        <div className="task-list">
          {tasks.map((task, index) => {
            const rowContent = (
              <>
                <span className={manageTasks ? (selectedTaskIds.has(task.id) ? "task-check is-selected" : "task-check") : "task-index"}>
                  {manageTasks ? (selectedTaskIds.has(task.id) ? "✓" : "") : String(index + 1).padStart(2, "0")}
                </span>
                <div className="task-main">
                  <h3>{task.title}</h3>
                  <p>{articleLabels[task.article_type ?? ""] ?? "待识别"} · 历史 {task.history_window} 篇 · {new Date(task.updated_at).toLocaleString("zh-CN")}</p>
                </div>
                <StatusPill status={task.status} />
                {manageTasks ? <span className="task-selection-state">{selectedTaskIds.has(task.id) ? "已选择" : "选择"}</span> : <ArrowIcon className="task-arrow" />}
              </>
            );
            return manageTasks ? (
              <button
                aria-checked={selectedTaskIds.has(task.id)}
                className="task-row task-select-row"
                key={task.id}
                role="checkbox"
                type="button"
                onClick={() => toggleTaskSelection(task.id)}
              >
                {rowContent}
              </button>
            ) : (
              <Link className="task-row" href={`/tasks/${task.id}`} key={task.id}>{rowContent}</Link>
            );
          })}
        </div>
      </section>

      {confirmDelete ? (
        <div className="task-delete-modal" role="presentation" onMouseDown={(event) => {
          if (event.currentTarget === event.target && !deleting) setConfirmDelete(false);
        }}>
          <section className="task-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-task-title">
            <p className="eyebrow">LOCAL DATA / CLEANUP</p>
            <h2 id="delete-task-title">删除 {selectedTaskIds.size} 个历史任务？</h2>
            <p>
              将清理这些任务的本地正文、预览、生成图片和冻结交付资产。曾完成最终冻结的任务仍会保留不含正文和图片的轻量视觉记录，用于最近 5 篇主题避重。公众号后台已有草稿和已发布文章不会受影响。
            </p>
            <ul>
              {tasks.filter((task) => selectedTaskIds.has(task.id)).slice(0, 3).map((task) => <li key={task.id}>{task.title}</li>)}
              {selectedTaskIds.size > 3 ? <li>以及另外 {selectedTaskIds.size - 3} 个任务</li> : null}
            </ul>
            <div className="task-delete-dialog-actions">
              <button className="task-cancel-button" type="button" disabled={deleting} onClick={() => setConfirmDelete(false)}>保留任务</button>
              <button className="task-delete-button" type="button" disabled={deleting} onClick={confirmTaskDeletion}>
                {deleting ? "正在删除…" : "确认永久删除"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
