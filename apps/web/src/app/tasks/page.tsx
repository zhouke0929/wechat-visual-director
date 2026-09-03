"use client";

import Link from "@/lib/router";
import { useCallback, useEffect, useState } from "react";
import { ArrowIcon, BackIcon } from "@/components/icons";
import { StatusPill } from "@/components/status-pill";
import { deleteTasks, listTasks } from "@/lib/api";
import type { Task } from "@/lib/types";
import styles from "./tasks.module.css";

const TASK_PAGE_SIZE = 8;

const articleLabels: Record<string, string> = {
  data_policy: "数据与规则解读",
  tutorial_steps: "教程与步骤指南",
  viewpoint_trend: "观点与趋势分析",
  lively_growth: "故事与案例叙事",
};

export default function RecentTasksPage() {
  useEffect(() => { window.scrollTo(0, 0); }, []);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [taskError, setTaskError] = useState("");
  const [manageTasks, setManageTasks] = useState(false);
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [taskNotice, setTaskNotice] = useState("");
  const [taskPage, setTaskPage] = useState(1);
  const [taskTotal, setTaskTotal] = useState(0);
  const [taskTotalPages, setTaskTotalPages] = useState(1);

  const loadTaskPage = useCallback(async (page: number) => {
    setLoading(true);
    try {
      const result = await listTasks(page, TASK_PAGE_SIZE);
      setTasks(result.items);
      setTaskPage(result.page);
      setTaskTotal(result.total);
      setTaskTotalPages(result.total_pages);
      setTaskError("");
    } catch (reason) {
      setTaskError(reason instanceof Error ? reason.message : "读取历史任务失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTaskPage(taskPage);
  }, [loadTaskPage, taskPage]);

  useEffect(() => {
    if (!confirmDelete) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !deleting) setConfirmDelete(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [confirmDelete, deleting]);

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
      const nextTotal = Math.max(0, taskTotal - result.deleted_count);
      const nextTotalPages = Math.max(1, Math.ceil(nextTotal / TASK_PAGE_SIZE));
      const nextPage = Math.min(taskPage, nextTotalPages);
      setSelectedTaskIds(new Set());
      setManageTasks(false);
      setConfirmDelete(false);
      setTaskNotice(
        result.asset_cleanup_warnings.length > 0
          ? `已删除 ${result.deleted_count} 个任务；有少量缓存素材将在维护时继续清理。`
          : `已删除 ${result.deleted_count} 个历史任务。`,
      );
      if (nextPage === taskPage) await loadTaskPage(nextPage);
      else setTaskPage(nextPage);
    } catch (reason) {
      setTaskError(reason instanceof Error ? reason.message : "删除历史任务失败");
      setConfirmDelete(false);
    } finally {
      setDeleting(false);
    }
  }

  function changeTaskPage(nextPage: number) {
    if (nextPage < 1 || nextPage > taskTotalPages || nextPage === taskPage) return;
    setSelectedTaskIds(new Set());
    setConfirmDelete(false);
    setTaskNotice("");
    setTaskError("");
    setTaskPage(nextPage);
  }

  return (
    <main className="desk-page recent-tasks-page">
      <header className={styles.topbar}>
        <Link className={styles.back} href="/"><BackIcon />返回任务台</Link>
        <div className={styles.title}>
          <strong>最近任务</strong>
          <span>RECENT BRIEFS / LOCAL WORKSPACE</span>
        </div>
        <span className={styles.localOnly}>本机任务</span>
      </header>
      <section className="task-section" id="recent-tasks" aria-labelledby="recent-title">
        <div className="section-title-row">
          <div>
            <p className="eyebrow">RECENT BRIEFS</p>
            <h1 id="recent-title">最近任务</h1>
          </div>
          <div className="task-heading-actions">
            <p>Agent 完成规划后，文章会出现在这里。点击继续编辑与审核。</p>
            {taskTotal > 0 && !manageTasks ? (
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
              {selectedTaskIds.size === tasks.length ? "取消全选" : "全选本页"}
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
        {!loading && taskTotal === 0 ? (
          <div className="empty-state">
            <span>01</span>
            <h3>还没有视觉任务</h3>
            <p>回到 Agent 对话，给它一个选题或一篇原稿；完成内容整理与规划后，再来这里确认成稿。</p>
            <Link className="desk-recent-link" href="/">回到首页开始 <span aria-hidden="true">↗</span></Link>
          </div>
        ) : null}
        <div className="task-list">
          {tasks.map((task, index) => {
            const rowContent = (
              <>
                <span className={manageTasks ? (selectedTaskIds.has(task.id) ? "task-check is-selected" : "task-check") : "task-index"}>
                  {manageTasks ? (selectedTaskIds.has(task.id) ? "✓" : "") : String((taskPage - 1) * TASK_PAGE_SIZE + index + 1).padStart(2, "0")}
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
        {!loading && taskTotal > 0 ? (
          <nav className="task-pagination" aria-label="历史任务分页">
            <p>共 {taskTotal} 篇 · 第 {taskPage} / {taskTotalPages} 页</p>
            <div>
              <button
                type="button"
                disabled={taskPage <= 1}
                onClick={() => changeTaskPage(taskPage - 1)}
              >
                上一页
              </button>
              <span aria-current="page">{taskPage}</span>
              <button
                type="button"
                disabled={taskPage >= taskTotalPages}
                onClick={() => changeTaskPage(taskPage + 1)}
              >
                下一页
              </button>
            </div>
          </nav>
        ) : null}
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
