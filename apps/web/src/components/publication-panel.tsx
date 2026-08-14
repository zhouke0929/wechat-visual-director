"use client";

import { useEffect, useRef, useState } from "react";
import { absoluteApiUrl } from "@/lib/api";
import type {
  DraftOperation,
  PublicationMetadata,
  PublicationReadiness,
  PublicationRevision,
  Task,
  WechatPublisherStatus,
} from "@/lib/types";

type PublicationPanelProps = {
  busy: string;
  bundleUrl: string | null;
  operation: DraftOperation | null;
  publisher: WechatPublisherStatus | null;
  readiness: PublicationReadiness | null;
  revision: PublicationRevision | null;
  task: Task;
  onAutosave: (metadata: PublicationMetadata) => Promise<void>;
  onContinueEditing: () => Promise<void>;
  onCopy: () => Promise<void>;
  onFreeze: (metadata: PublicationMetadata) => Promise<void>;
  onPublish: () => Promise<void>;
  onRetry: () => Promise<void>;
  onResolveUnknown: (outcome: "confirmed_succeeded" | "confirmed_not_created") => Promise<void>;
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
  bundleUrl,
  operation,
  publisher,
  readiness,
  revision,
  task,
  onAutosave,
  onContinueEditing,
  onCopy,
  onFreeze,
  onPublish,
  onRetry,
  onResolveUnknown,
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
    const realOperation = operation?.provider === "wechat_api";
    const realSucceeded = succeeded && realOperation;
    return (
      <section className="publication-console publication-console-frozen" aria-label="冻结版本与交付操作">
        <header className={`delivery-status-band ${succeeded && realOperation ? "delivery-status-live" : ""}`}>
          <strong>{succeeded && realOperation ? "WECHAT DRAFT" : "DELIVERY READY"}</strong>
          <span>
            {succeeded && realOperation
              ? "已写入微信公众号草稿箱，最终群发仍需人工确认"
              : "最终视觉版本已冻结，可选择一种交付方式"}
          </span>
          <i>{realOperation ? "WECHAT OFFICIAL API" : "LOCAL REVISION"}</i>
        </header>

        <div className="publication-final-grid">
          <section className="publication-proof-sheet publication-result-card">
            <div className="proof-eyebrow">
              <span>FINAL REVISION / R{String(revision.revision_number).padStart(2, "0")}</span>
              <b>{realSucceeded ? "已送达" : succeeded ? "仅本地模拟" : failed ? "需要处理" : unknown ? "待人工核对" : "待选择出口"}</b>
            </div>
            <h2>{realSucceeded ? "公众号草稿已经创建" : succeeded ? "旧版模拟记录，不代表真实草稿" : "选择这份文章的交付方式"}</h2>
            <p className="proof-intro">
              {realSucceeded
                ? "系统已保存本地冻结版本和真实 Media ID。请到公众号后台完成最终检查与发布。"
                : succeeded
                  ? "这是早期测试流程留下的模拟结果，没有调用微信接口；返回工作台后可使用真实交付出口。"
                : "发布到微信会调用内置官方 API；复制和下载不会使用 AppID 或 AppSecret。"}
            </p>

            <dl className="publication-metadata-ledger">
              <div><dt>标题</dt><dd>{revision.title}</dd></div>
              <div><dt>作者</dt><dd>{revision.metadata.author || "未填写"}</dd></div>
              <div><dt>摘要</dt><dd>{revision.metadata.digest || "由公众号后台自动处理"}</dd></div>
              <div><dt>版本</dt><dd>R{String(revision.revision_number).padStart(2, "0")} · {revision.frozen_html_hash.slice(0, 10)}</dd></div>
            </dl>

            {operation ? (
              <>
                <section className={`draft-receipt draft-receipt-${operation.status}`}>
                  <span>{realOperation ? "WECHAT SYNC RECEIPT" : "LOCAL TEST RECEIPT"}</span>
                  {succeeded ? (
                    <>
                      <h3>{realOperation ? "真实公众号草稿已创建" : "本地模拟记录已创建"}</h3>
                      {operation.media_id ? <code>{operation.media_id}</code> : null}
                      {realOperation && !operation.media_id ? <p>已由你在公众号后台人工确认草稿存在；接口未返回可记录的 Media ID。</p> : null}
                      <p>请在公众号后台核对标题、封面、正文图片和手机端样式。</p>
                    </>
                  ) : null}
                  {failed ? (
                    <>
                      <h3>草稿创建失败</h3>
                      <p>{operation.last_error?.message ?? "发布器返回了明确失败结果。"}</p>
                      {realOperation ? (
                        <button disabled={!publisher?.ready || Boolean(busy)} onClick={onRetry} type="button">
                          {busy === "retry" ? "正在重新写入…" : "修正后重试"}
                        </button>
                      ) : null}
                    </>
                  ) : null}
                  {unknown ? (
                    <>
                      <h3>结果未知，请先核对公众号后台</h3>
                      <p>{operation.last_error?.message ?? "请先到公众号后台核对是否已经生成草稿。"}</p>
                      <small>诊断码：{operation.last_error?.code ?? "wechat_draft_result_unknown"}</small>
                      <div className="unknown-resolution-actions">
                        <button
                          disabled={Boolean(busy)}
                          onClick={() => onResolveUnknown("confirmed_succeeded")}
                          type="button"
                        >{busy === "resolve-unknown" ? "正在记录…" : "后台已找到草稿"}</button>
                        <button
                          className="unknown-resolution-secondary"
                          disabled={Boolean(busy)}
                          onClick={() => onResolveUnknown("confirmed_not_created")}
                          type="button"
                        >{busy === "resolve-unknown" ? "正在解除…" : "后台确认无草稿，解除锁定"}</button>
                      </div>
                      <p>只有确认后台没有草稿后才解除锁定；解除后会出现重新保存按钮。</p>
                    </>
                  ) : null}
                </section>
                <div className="delivery-action-stack delivery-fallback-stack">
                  <strong>{unknown || failed ? "仍可使用安全的手动交付" : "保留一份可编辑的本地副本"}</strong>
                  <p>下面两项不会再次调用微信接口，也不会重复创建草稿。</p>
                  <div className="delivery-action-row">
                    <button disabled={Boolean(busy)} onClick={onCopy} type="button">
                      {busy === "copy" ? "正在复制…" : "复制全文到剪贴板"}
                    </button>
                    {bundleUrl ? <a download href={bundleUrl}>下载交付包</a> : null}
                  </div>
                  <small>粘贴到公众号后台后，请保存、重新打开并用手机预览，重点检查图片和样式。</small>
                </div>
              </>
            ) : (
              <div className="delivery-action-stack">
                <button
                  className="delivery-action-primary"
                  disabled={!publisher?.ready || Boolean(busy)}
                  onClick={onPublish}
                  type="button"
                >
                  {busy === "publish" ? "正在写入公众号草稿箱…" : "保存到微信公众号草稿箱"}
                </button>
                <div className="delivery-action-row">
                  <button disabled={Boolean(busy)} onClick={onCopy} type="button">
                    {busy === "copy" ? "正在复制…" : "复制全文到剪贴板"}
                  </button>
                  {bundleUrl ? <a download href={bundleUrl}>下载交付包</a> : null}
                </div>
                <p className="publisher-readiness-note">
                  {publisher?.ready
                    ? "内置微信官方 API · 本机凭据已配置 · 微信接口会再次校验当前出口 IP"
                    : publisher?.warnings[0] ?? "正在检查微信官方 API 配置…"}
                </p>
                <small>复制正文后必须在公众号后台保存、重新打开并用手机预览，重点检查图片。</small>
              </div>
            )}

            <button className="continue-editing-button" disabled={Boolean(busy) || unknown} onClick={onContinueEditing} type="button">
              {unknown ? "先核对后台并处置结果" : busy === "continue" ? "正在恢复工作稿…" : "返回工作台继续修改"}
            </button>
          </section>

          <section className="frozen-preview-workspace">
            <header>
              <div><span>FINAL MOBILE PREVIEW</span><strong>冻结版本</strong></div>
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
  const blockerMessages = Array.from(new Set(readiness?.blockers.map((item) => item.message) ?? []));
  const blockerHint = readiness === null
    ? "正在检查交付条件…"
    : readiness.ready
      ? publisher?.ready
        ? "所有必选项已完成，可以保存并创建公众号草稿。"
        : "所有必选项已完成，可以保存最终版本。"
      : `未完成：${blockerMessages.slice(0, 2).join("；")}${blockerMessages.length > 2 ? `；另有 ${blockerMessages.length - 2} 项` : ""}`;
  return (
    <section className="publication-console publication-dock" aria-label="确认最终视觉版本">
      <div className="publication-dock-main">
        <div className="publication-dock-copy">
          <span>DELIVERY DOCK / LOCAL</span>
          <h2>{publisher?.ready ? "确认后，直接创建公众号草稿" : "保存最终版本"}</h2>
          <p>
            {readiness?.ready
              ? publisher?.ready
                ? "当前方案已通过检查；一次点击完成本地保存并写入微信公众号草稿箱。"
                : "当前方案已通过检查；保存后可以复制正文或下载交付包。"
              : blockerCount
                ? "请先完成工作台中的必选项，按钮会自动解锁。"
                : "正在检查当前方案是否可以交付。"}
          </p>
          <small className={`autosave-state autosave-${saveState}`} aria-live="polite">
            {saveState === "saving" ? "正在自动保存…" : saveState === "error" ? "自动保存失败，确认时将再次保存" : "工作稿已自动保存"}
          </small>
        </div>

        <div className="publication-primary-stack" title={blockerHint}>
          <button
            aria-describedby="publication-primary-hint"
            className="publication-primary-action"
            disabled={!readiness?.ready || Boolean(busy)}
            onClick={() => void onFreeze(metadata)}
            type="button"
          >
            {busy === "freeze"
              ? "正在保存最终版本…"
              : busy === "publish"
                ? "正在创建公众号草稿…"
                : publisher?.ready
                  ? "保存并创建公众号草稿"
                  : "保存最终版本"}
          </button>
          <small className={readiness?.ready ? "publication-primary-hint hint-ready" : "publication-primary-hint"} id="publication-primary-hint">
            {blockerHint}
          </small>
        </div>
      </div>

      <details className="publication-details">
        <summary>发布信息与检查详情</summary>
        <div className="publication-details-grid">
          <div className="publication-metadata-form">
            <label>作者（最多 8 个字符）<input maxLength={8} onChange={(event) => setMetadata({ ...metadata, author: event.target.value })} value={metadata.author} /></label>
            <label>摘要<textarea maxLength={120} onChange={(event) => setMetadata({ ...metadata, digest: event.target.value })} placeholder="可选；将通过微信官方 API 写入草稿" rows={3} value={metadata.digest} /></label>
            <label>原文链接<input onChange={(event) => setMetadata({ ...metadata, content_source_url: event.target.value })} placeholder="可选" type="url" value={metadata.content_source_url} /></label>
            <label className="cover-policy"><input checked={metadata.show_cover_pic} onChange={(event) => setMetadata({ ...metadata, show_cover_pic: event.target.checked })} type="checkbox" /><span>在正文中显示封面图（本地记录）</span></label>
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
