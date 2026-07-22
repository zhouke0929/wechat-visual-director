"use client";

import { useEffect, useRef, useState } from "react";
import { absoluteApiUrl } from "@/lib/api";
import type {
  DraftOperation,
  PublicationMetadata,
  PublicationReadiness,
  PublicationRevision,
  Task,
} from "@/lib/types";

type PublicationPanelProps = {
  busy: string;
  operation: DraftOperation | null;
  readiness: PublicationReadiness | null;
  revision: PublicationRevision | null;
  task: Task;
  onAutosave: (metadata: PublicationMetadata) => Promise<void>;
  onContinueEditing: () => Promise<void>;
  onRetry: () => Promise<void>;
  onSaveAndSync: (metadata: PublicationMetadata) => Promise<void>;
};

const checkLabels: Record<string, string> = {
  plan_selected: "视觉方案",
  preflight_resolved: "内容风险",
  assets_complete: "发布素材",
  image_slots_decided: "配图决定",
  compatibility: "微信兼容",
  draft_operation_clear: "草稿状态",
};

export function PublicationPanel({
  busy,
  operation,
  readiness,
  revision,
  task,
  onAutosave,
  onContinueEditing,
  onRetry,
  onSaveAndSync,
}: PublicationPanelProps) {
  const [metadata, setMetadata] = useState<PublicationMetadata>(task.publication_draft_metadata);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("saved");
  const autosaveRef = useRef(onAutosave);

  useEffect(() => {
    autosaveRef.current = onAutosave;
  }, [onAutosave]);

  useEffect(() => {
    setMetadata(task.publication_draft_metadata);
    setSaveState("saved");
  }, [task.id, task.publication_draft_metadata]);

  useEffect(() => {
    if (revision) return;
    if (JSON.stringify(metadata) === JSON.stringify(task.publication_draft_metadata)) return;
    setSaveState("saving");
    const timer = window.setTimeout(() => {
      void autosaveRef.current(metadata)
        .then(() => setSaveState("saved"))
        .catch(() => setSaveState("error"));
    }, 650);
    return () => window.clearTimeout(timer);
  }, [metadata, revision, task.publication_draft_metadata]);

  if (revision) {
    const succeeded = operation?.status === "succeeded";
    const failed = operation?.status === "failed";
    const unknown = operation?.status === "unknown";
    return (
      <section className="publication-console publication-console-frozen" aria-label="本地冻结版本与模拟草稿结果">
        <header className="mock-warning-band">
          <strong>MOCK MODE</strong>
          <span>当前为联调环境，不会写入真实微信公众号</span>
          <i>NO REAL DRAFT</i>
        </header>

        <div className="publication-final-grid">
          <section className="publication-proof-sheet publication-result-card">
            <div className="proof-eyebrow">
              <span>WECHAT DRAFT / R{String(revision.revision_number).padStart(2, "0")}</span>
              <b>{succeeded ? "已保存" : failed ? "需重试" : unknown ? "待核对" : "处理中"}</b>
            </div>
            <h2>{succeeded ? "文章已保存并完成模拟同步" : "这次同步还没有完成"}</h2>
            <p className="proof-intro">
              {succeeded
                ? "网站保留了这份最终稿，并生成了一条 Mock 公众号草稿记录。"
                : "最终稿已经安全保留，可以在这里重试，不需要重新排版。"}
            </p>

            <dl className="publication-metadata-ledger">
              <div><dt>标题</dt><dd>{revision.title}</dd></div>
              <div><dt>作者</dt><dd>{revision.metadata.author || "未填写"}</dd></div>
              <div><dt>摘要</dt><dd>{revision.metadata.digest || "未填写"}</dd></div>
              <div><dt>草稿序号</dt><dd>{operation?.draft_slot ?? revision.suggested_draft_slot}</dd></div>
            </dl>

            {operation ? (
              <section className={`draft-receipt draft-receipt-${operation.status}`}>
                <span>SYNC RECEIPT</span>
                {succeeded ? (
                  <>
                    <h3>模拟公众号草稿已创建</h3>
                    <code>{operation.media_id}</code>
                    <p>这是联调用的 Mock Media ID；接入真实微信发布器后，这里将显示真实草稿结果。</p>
                  </>
                ) : null}
                {failed ? (
                  <>
                    <h3>同步明确失败</h3>
                    <p>{operation.last_error?.message ?? "当前操作可以安全重试。"}</p>
                    <button disabled={Boolean(busy)} onClick={onRetry} type="button">
                      {busy === "retry" ? "重试中…" : "重试同步"}
                    </button>
                  </>
                ) : null}
                {unknown ? <><h3>同步结果待核对</h3><p>为避免重复草稿，需先核对公众号后台，再决定后续动作。</p></> : null}
              </section>
            ) : <p className="gate-ready-note">正在准备同步记录，请稍候刷新。</p>}

            {!unknown ? (
              <button className="continue-editing-button" disabled={Boolean(busy)} onClick={onContinueEditing} type="button">
                {busy === "continue" ? "正在打开工作稿…" : "继续修改并另存为新草稿"}
              </button>
            ) : null}
          </section>

          <section className="frozen-preview-workspace">
            <header>
              <div><span>FINAL MOBILE PREVIEW</span><strong>已保存版本</strong></div>
              <p>390px · 微信兼容检查 {revision.compatibility_status === "pass" ? "通过" : "未通过"}</p>
            </header>
            <div className="phone-stage">
              <div className="phone-label"><span>390</span><i />MOBILE CONTENT WIDTH</div>
              <iframe className="preview-frame" src={absoluteApiUrl(revision.preview_url)} title={`${revision.title} 最终移动端预览`} />
            </div>
          </section>
        </div>
      </section>
    );
  }

  const blockerCount = readiness?.blockers.length ?? 0;
  return (
    <section className="publication-console publication-dock" aria-label="保存本地冻结版本并生成模拟草稿记录">
      <div className="publication-dock-main">
        <div className="publication-dock-copy">
          <span>DELIVERY DOCK / {task.publication_mode.toUpperCase()}</span>
          <h2>完成后，保存本地冻结版本</h2>
          <p>
            {readiness?.ready
              ? "当前方案已通过发布检查。工作稿会自动保存在网站中。"
              : `还有 ${blockerCount} 项需要处理，完成后即可同步。`}
          </p>
          <small className={`autosave-state autosave-${saveState}`} aria-live="polite">
            {saveState === "saving" ? "正在自动保存…" : saveState === "error" ? "自动保存失败，将在提交时重试" : "工作稿已自动保存"}
          </small>
        </div>

        <button
          className="publication-primary-action"
          disabled={!readiness?.ready || Boolean(busy)}
          onClick={() => void onSaveAndSync(metadata)}
          type="button"
        >
          {busy === "sync" ? "正在保存本地版本…" : "保存并生成 Mock 草稿记录"}
        </button>
      </div>

      {readiness?.blockers.length ? (
        <div className="gate-blockers publication-dock-blockers">
          <strong>同步前需要处理</strong>
          <ul>{readiness.blockers.map((item) => <li key={`${item.code}:${item.resource_id ?? "root"}`}>{item.message}</li>)}</ul>
        </div>
      ) : null}

      <details className="publication-details">
        <summary>发布信息与检查详情</summary>
        <div className="publication-details-grid">
          <div className="publication-metadata-form">
            <label>作者（最多 8 个字符）<input maxLength={8} onChange={(event) => setMetadata({ ...metadata, author: event.target.value })} value={metadata.author} /></label>
            <label>摘要<textarea maxLength={120} onChange={(event) => setMetadata({ ...metadata, digest: event.target.value })} placeholder="可选" rows={3} value={metadata.digest} /></label>
            <label>原文链接<input onChange={(event) => setMetadata({ ...metadata, content_source_url: event.target.value })} placeholder="可选" type="url" value={metadata.content_source_url} /></label>
            <label className="cover-policy"><input checked={metadata.show_cover_pic} onChange={(event) => setMetadata({ ...metadata, show_cover_pic: event.target.checked })} type="checkbox" /><span>在正文中显示封面图</span></label>
          </div>
          <div className="gate-check-cards">
            {Object.entries(readiness?.checks ?? {}).map(([key, status]) => (
              <div className={`gate-check gate-check-${status}`} key={key}>
                <span>{status === "pass" ? "✓" : status === "blocking" ? "!" : "·"}</span>
                <div><strong>{checkLabels[key] ?? key}</strong><small>{status === "pass" ? "已通过" : status === "blocking" ? "待处理" : "等待检查"}</small></div>
              </div>
            ))}
          </div>
        </div>
      </details>
    </section>
  );
}
