"use client";

import { useEffect, useRef, useState } from "react";
import { absoluteApiUrl } from "@/lib/api";
import { ArticlePreviewViewport } from "@/components/article-preview-viewport";
import { ResilientPreviewFrame } from "@/components/resilient-preview-frame";
import type {
  DraftOperation,
  PublicationBlocker,
  PublicationMetadata,
  PublicationReadiness,
  PublicationRevision,
  Task,
  WechatPublisherStatus,
} from "@/lib/types";

type BlockerTarget = "cover" | "images" | "preflight";

type PublicationPanelProps = {
  busy: string;
  copyFallbackAvailable?: boolean;
  bundleUrl: string | null;
  operation: DraftOperation | null;
  publisher: WechatPublisherStatus | null;
  readiness: PublicationReadiness | null;
  revision: PublicationRevision | null;
  task: Task;
  onAutosave: (metadata: PublicationMetadata) => Promise<void>;
  onContinueEditing: () => Promise<void>;
  onCopy: (uploadImages?: boolean) => Promise<void>;
  onFreeze: (metadata: PublicationMetadata) => Promise<void>;
  onReviewBlocker?: (target: BlockerTarget) => void;
  onPublish: () => Promise<void>;
  onRetry: () => Promise<void>;
  onResolveUnknown: (outcome: "confirmed_succeeded" | "confirmed_not_created") => Promise<void>;
};

const blockerActions: Record<BlockerTarget, string> = {
  cover: "去选封面",
  images: "去确认配图",
  preflight: "查看原稿检查",
};

const blockerWorkflowOrder = ["source_image_not_controlled", "image_slot_pending", "cover_asset_not_controlled"];

function describeBlockers(blockers: PublicationBlocker[]) {
  const groups = new Map<string, PublicationBlocker[]>();
  for (const blocker of blockers) {
    const key = blockerWorkflowOrder.includes(blocker.code)
      ? blocker.code
      : `${blocker.action}:${blocker.message}`;
    const group = groups.get(key) ?? [];
    group.push(blocker);
    groups.set(key, group);
  }
  const orderedKeys = [...blockerWorkflowOrder.filter((key) => groups.has(key)), ...Array.from(groups.keys()).filter((key) => !blockerWorkflowOrder.includes(key))];
  return orderedKeys.map((key) => {
    const group = groups.get(key)!;
    const first = group[0];
    switch (first.code) {
      case "cover_asset_not_controlled":
        return { key, title: "还没选封面", detail: "选一张封面，也可以直接使用主题保底封面。", target: "cover" as const };
      case "image_slot_pending":
        return { key, title: `还有 ${group.length} 处配图待确认`, detail: "采用一张图，或跳过不需要的配图。", target: "images" as const };
      case "source_image_not_controlled":
        return { key, title: `还有 ${group.length} 张原稿图片未导入`, detail: "补传原图，避免交付后漏图。", target: "preflight" as const, actionLabel: "去导入原图" };
      case "preflight_finding_unresolved":
        return { key, title: first.message, target: "preflight" as const };
      case "draft_operation_unknown":
        return { key, title: "上一次草稿结果待确认", detail: "先到公众号后台核对，不要重复创建草稿。" };
      case "draft_operation_in_progress":
        return { key, title: "公众号草稿正在保存", detail: "等本次保存完成后再操作。" };
      default:
        return { key, title: first.message, target: first.action === "review_image_slot" ? "images" as const : undefined };
    }
  });
}

export function PublicationPanel({
  busy,
  copyFallbackAvailable = false,
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
  onReviewBlocker,
  onPublish,
  onRetry,
  onResolveUnknown,
}: PublicationPanelProps) {
  const [metadata, setMetadata] = useState<PublicationMetadata>(task.publication_draft_metadata);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("saved");
  const autosaveRef = useRef(onAutosave);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

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
                : "可以直接保存到公众号草稿箱，也可以复制图文后到公众号后台粘贴。"}
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
                  <strong>{unknown || failed ? "其他交付方式" : "复制与下载"}</strong>
                  <p>正文、配图与主题装饰一起复制，粘贴后仍可编辑文字。</p>
                  <div className="delivery-action-row">
                    <button disabled={Boolean(busy)} onClick={() => onCopy(false)} type="button">
                      {busy === "copy" ? "正在准备剪贴板…" : "复制图文"}
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
                  <button disabled={Boolean(busy)} onClick={() => onCopy(false)} type="button">
                    {busy === "copy" ? "正在准备剪贴板…" : "复制图文"}
                  </button>
                  {bundleUrl ? <a download href={bundleUrl}>下载交付包</a> : null}
                </div>
                <p className="publisher-readiness-note">
                  {publisher?.ready
                    ? "内置微信官方 API · 本机凭据已配置 · 微信接口会再次校验当前出口 IP"
                    : publisher?.warnings[0] ?? "正在检查微信官方 API 配置…"}
                </p>
                <small>正文与图片一起复制。粘贴后请保存、重新打开并检查手机预览。</small>
              </div>
            )}

            {copyFallbackAvailable ? (
              <div className="delivery-action-stack delivery-fallback-stack" role="region" aria-label="复制备用方式">
                <strong>复制遇到问题？</strong>
                <p>请先根据错误提示检查浏览器剪贴板权限或图片大小。浏览器需允许图文复制；下载交付包不依赖剪贴板权限。</p>
                <p>{publisher?.ready
                  ? "如果需要改用公众号图片地址，可以先上传图片再复制。这会使用已配置的公众号连接，不会创建草稿；仍需浏览器允许图文复制。"
                  : "如果图片过大，可以缩小图片后重试，或下载交付包后分别导入正文与图片。"}</p>
                {publisher?.ready ? (
                  <div className="delivery-action-row">
                    <button disabled={Boolean(busy)} onClick={() => onCopy(true)} type="button">上传图片后复制</button>
                  </div>
                ) : null}
              </div>
            ) : null}

            <button className="continue-editing-button" disabled={Boolean(busy) || unknown} onClick={onContinueEditing} type="button">
              {unknown ? "先核对后台并处置结果" : busy === "continue" ? "正在恢复工作稿…" : "返回工作台继续修改"}
            </button>
          </section>

          <section className="frozen-preview-workspace">
            <header>
              <div><span>FINAL MOBILE PREVIEW</span><strong>冻结版本</strong></div>
              <p>双视口 · 微信兼容检查 {revision.compatibility_status === "pass" ? "通过" : "未通过"}</p>
            </header>
            <ArticlePreviewViewport>
              <ResilientPreviewFrame
                src={absoluteApiUrl(revision.preview_url)}
                title={`${revision.title} 最终移动端预览`}
              />
            </ArticlePreviewViewport>
          </section>
        </div>
      </section>
    );
  }

  const blockers = describeBlockers(readiness?.blockers ?? []);
  const blocked = readiness !== null && !readiness.ready;
  const blockedHint = blockers.length ? blockers.map((item) => item.title).join("；") : "还有交付条件未完成";
  const statusText = readiness === null
    ? "正在检查交付条件…"
    : blocked
      ? `待处理：${blockedHint}`
      : "交付检查已通过";
  const actionTitle = publisher?.ready ? "创建公众号草稿" : "保存最终版本";
  return (
    <div className={`publication-toolbar${readiness?.ready ? " is-ready" : ""}`} aria-label="草稿交付">
      <div className="publication-toolbar-action" title={statusText}>
        <button
          aria-describedby="publication-toolbar-hint"
          aria-controls={blocked ? "publication-toolbar-popover" : undefined}
          aria-expanded={blocked ? detailsOpen : undefined}
          className={blocked ? "publication-action-blocked" : undefined}
          disabled={readiness === null || Boolean(busy)}
          onClick={() => {
            if (readiness?.ready) {
              void onFreeze(metadata);
            } else if (blocked && detailsRef.current) {
              detailsRef.current.open = !detailsRef.current.open;
            }
          }}
          type="button"
        >
          <strong>
            {busy === "freeze"
              ? "正在保存…"
              : busy === "publish"
                ? "正在创建草稿…"
                : actionTitle}
          </strong>
          {blocked ? <small>{blockers.length ? `${blockers.length} 项待处理 · 查看` : "查看待处理项"}</small> : null}
        </button>
        <span className="visually-hidden" id="publication-toolbar-hint">{statusText}</span>
      </div>
      <details className="publication-toolbar-details" ref={detailsRef} onToggle={(event) => setDetailsOpen(event.currentTarget.open)}>
        <summary aria-label="展开发布详情" title="发布详情">
          <span className="visually-hidden">发布详情</span>
        </summary>
        <div className="publication-toolbar-popover" id="publication-toolbar-popover">
          <header>
            <div>
              <span>DELIVERY CHECK</span>
              <strong>交付检查</strong>
            </div>
            <small className={`autosave-state autosave-${saveState}`} aria-live="polite">
              {saveState === "saving" ? "信息保存中…" : saveState === "error" ? "信息未保存" : ""}
            </small>
          </header>
          <p aria-live="polite" className={readiness?.ready ? "publication-toolbar-readiness is-ready" : "publication-toolbar-readiness"}>
            {blocked && blockers.length ? `还有 ${blockers.length} 项待处理，完成后即可${actionTitle}。` : statusText}
          </p>
          {blocked && blockers.length > 0 ? (
            <ul className="publication-blockers">
              {blockers.map(({ key, title, detail, target, actionLabel }) => (
                <li key={key}>
                  <div><strong>{title}</strong>{detail ? <p>{detail}</p> : null}</div>
                  {target && onReviewBlocker ? (
                    <button
                      type="button"
                      onClick={() => {
                        if (detailsRef.current) detailsRef.current.open = false;
                        onReviewBlocker(target);
                      }}
                    >{actionLabel ?? blockerActions[target]}</button>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          <details className="publication-optional-details">
            <summary>可选：公众号草稿信息</summary>
            <div className="publication-metadata-form">
              <p>仅用于保存到公众号草稿箱。可留空，也可以到公众号后台再填；复制图文不包含这些信息。</p>
              <label>作者（最多 8 个字符）<input maxLength={8} onChange={(event) => setMetadata({ ...metadata, author: event.target.value })} value={metadata.author} /></label>
              <label>摘要<textarea maxLength={120} onChange={(event) => setMetadata({ ...metadata, digest: event.target.value })} rows={2} value={metadata.digest} /></label>
              <label>原文链接<input onChange={(event) => setMetadata({ ...metadata, content_source_url: event.target.value })} type="url" value={metadata.content_source_url} /></label>
              <label className="cover-policy"><input checked={metadata.show_cover_pic} onChange={(event) => setMetadata({ ...metadata, show_cover_pic: event.target.checked })} type="checkbox" /><span>在正文中显示封面图（草稿设置）</span></label>
            </div>
          </details>
        </div>
      </details>
    </div>
  );
}
