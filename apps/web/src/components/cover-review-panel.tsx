"use client";

import { useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";
import { createPortal } from "react-dom";
import { absoluteApiUrl } from "@/lib/api";
import type { CoverCandidate, CoverReuseSource, CoverWorkspace } from "@/lib/types";

type Props = {
  busy: string;
  review: CoverWorkspace | null;
  onGenerate: () => Promise<void>;
  onFallback: () => Promise<void>;
  onCrop: (
    candidate: CoverCandidate,
    transform: { scale: number; offsetX: number; offsetY: number },
  ) => Promise<void>;
  onReuse: (source: CoverReuseSource) => Promise<void>;
  onSelect: (candidate: CoverCandidate) => Promise<void>;
  onUpload: (file: File) => Promise<void>;
};

const sourceLabels: Record<CoverCandidate["source_type"], string> = {
  ai_generated: "AI 全文生成",
  accepted_body_image: "正文配图复用",
  controlled_source_image: "原稿图片复用",
  theme_fallback: "主题保底封面",
  custom_crop: "人工裁切封面",
};

const DEFAULT_CROP_SCALE = 1;
const COVER_MASTER_ASPECT = 5 / 4;
const WECHAT_HEADLINE_ASPECT = 900 / 383;

type CoverDisplayTransform = { scale: number; offsetX: number; offsetY: number };

function displayFrameSize(scale: number) {
  const width = 1 / scale;
  return { width, height: width * COVER_MASTER_ASPECT / WECHAT_HEADLINE_ASPECT };
}

function clampOffset(value: number, scale: number, axis: "x" | "y") {
  const frame = displayFrameSize(scale);
  const limit = Math.max(0, (1 - (axis === "x" ? frame.width : frame.height)) / 2);
  return Math.max(-limit, Math.min(limit, value));
}

function savedDisplayTransform(candidate: CoverCandidate): CoverDisplayTransform {
  const stored = candidate.machine_checks.crop_transform as Record<string, unknown> | undefined;
  const scale = Math.max(1, Math.min(3, Number(stored?.scale) || DEFAULT_CROP_SCALE));
  return {
    scale,
    offsetX: clampOffset(Number(stored?.offset_x) || 0, scale, "x"),
    offsetY: clampOffset(Number(stored?.offset_y) || 0, scale, "y"),
  };
}

function displayAreaStyle(transform: CoverDisplayTransform) {
  return {
    "--cover-display-width": `${100 / transform.scale}%`,
    "--cover-display-x": `${transform.offsetX * 100}%`,
    "--cover-display-y": `${transform.offsetY * 100}%`,
  } as CSSProperties;
}

export function CoverReviewPanel({ busy, review, onGenerate, onFallback, onCrop, onReuse, onSelect, onUpload }: Props) {
  const [cropCandidate, setCropCandidate] = useState<CoverCandidate | null>(null);
  const [cropScale, setCropScale] = useState(DEFAULT_CROP_SCALE);
  const [cropOffset, setCropOffset] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);

  function openCrop(candidate: CoverCandidate) {
    const saved = savedDisplayTransform(candidate);
    setCropCandidate(candidate);
    setCropScale(saved.scale);
    setCropOffset({ x: saved.offsetX, y: saved.offsetY });
  }

  function changeScale(nextScale: number) {
    setCropScale(nextScale);
    setCropOffset((current) => ({
      x: clampOffset(current.x, nextScale, "x"),
      y: clampOffset(current.y, nextScale, "y"),
    }));
  }

  function startDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (!cropCandidate) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      offsetX: cropOffset.x,
      offsetY: cropOffset.y,
    };
  }

  function moveDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const bounds = event.currentTarget.parentElement?.getBoundingClientRect() ?? event.currentTarget.getBoundingClientRect();
    setCropOffset({
      x: clampOffset(drag.offsetX + (event.clientX - drag.startX) / bounds.width, cropScale, "x"),
      y: clampOffset(drag.offsetY + (event.clientY - drag.startY) / bounds.height, cropScale, "y"),
    });
  }

  function stopDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function zoomWithWheel(event: ReactWheelEvent<HTMLDivElement>) {
    event.preventDefault();
    const step = event.deltaY < 0 ? 0.1 : -0.1;
    changeScale(Math.max(1, Math.min(3, Number((cropScale + step).toFixed(2)))));
  }

  async function saveCrop() {
    if (!cropCandidate) return;
    try {
      await onCrop(cropCandidate, {
        scale: cropScale,
        offsetX: cropOffset.x,
        offsetY: cropOffset.y,
      });
      setCropCandidate(null);
    } catch {
      // The task page renders the API error; keep the crop state open for correction or retry.
    }
  }

  if (!review) return <div className="cover-loading">正在读取封面工作台…</div>;
  return (
    <section className="cover-desk" aria-label="封面规划与选择">
      <div className="cover-brief-ticket">
        <span>全文提炼</span>
        <strong>{review.cover_brief.reader_task}</strong>
      </div>

      <div className="cover-actions-grid">
        <button disabled={review.provider_mode === "manual" || Boolean(busy)} onClick={onGenerate} type="button">
          <span>01</span>
          <strong>
            {review.provider_mode === "manual"
              ? "人工模式：请上传或复用封面"
              : busy === "generate" ? "生成中…" : "AI 总结全文生成封面"}
          </strong>
          <small>
            {review.provider_mode === "manual"
              ? "从正文候选或本机图片中选择"
              : "根据全文与当前主题生成"}
          </small>
        </button>
        <label className={busy ? "disabled" : ""}>
          <input
            accept="image/png,image/jpeg,image/webp"
            disabled={Boolean(busy)}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void onUpload(file);
              event.currentTarget.value = "";
            }}
            type="file"
          />
          <span>02</span><strong>{busy === "upload" ? "上传中…" : "上传自己的封面"}</strong><small>人工兜底 · 自动进入受控资产</small>
        </label>
        <button disabled={Boolean(busy)} onClick={onFallback} type="button">
          <span>03</span>
          <strong>{busy === "fallback" ? "正在制作…" : "跳过生图，使用主题保底封面"}</strong>
          <small>不调用模型 · 无需准备图片 · 自动采用</small>
        </button>
      </div>

      {review.reuse_sources.length ? (
        <section className="cover-source-strip">
          <header><strong>从正文中挑选</strong><span>完整保留正文原图，用柔化背景适配 5:4</span></header>
          <div>
            {review.reuse_sources.map((source) => (
              <button disabled={Boolean(busy)} key={`${source.source_type}:${source.source_id}`} onClick={() => void onReuse(source)} type="button">
                <img alt={source.label} src={absoluteApiUrl(source.content_url)} />
                <span>{source.label}</span>
              </button>
            ))}
          </div>
        </section>
      ) : (
        <p className="cover-source-empty">采纳一张正文配图后，这里会出现“复用为封面”的候选入口。</p>
      )}

      <section className="cover-contact-sheet">
        <header>
          <strong>封面候选</strong>
          <span>{review.candidates.length ? `${review.candidates.length} 张 5:4 原图 · 可调整 2.35:1 头图范围` : "尚未生成候选"}</span>
        </header>
        {review.candidates.length ? (
          <div>
            {review.candidates.map((candidate) => {
              const displayTransform = savedDisplayTransform(candidate);
              return (
                <article className={candidate.selected ? "selected" : ""} key={candidate.id}>
                  <div className="cover-crop-frame">
                    <img alt={`封面候选 ${candidate.candidate_index}`} src={absoluteApiUrl(candidate.content_url)} />
                    <div className="cover-display-area" style={displayAreaStyle(displayTransform)}><i>封面显示区</i></div>
                  </div>
                  <p><span>{String(candidate.candidate_index).padStart(2, "0")}</span><strong>{sourceLabels[candidate.source_type]}</strong></p>
                  <div className="cover-candidate-actions">
                    <button disabled={Boolean(busy)} onClick={() => openCrop(candidate)} type="button">调整封面显示区</button>
                    <button
                      disabled={candidate.selected || Boolean(busy)}
                      onClick={() => void onSelect(candidate)}
                      type="button"
                    >
                      {candidate.selected
                        ? "当前封面"
                        : busy === `select:${candidate.id}`
                          ? "采用中…"
                          : "直接采用"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : <p>可生成 AI 候选、复用正文图片、直接上传，或一键使用主题保底封面。</p>}
      </section>

      {cropCandidate && typeof document !== "undefined" ? createPortal((
        <div className="cover-crop-dialog" role="dialog" aria-modal="true" aria-label="调整封面显示区">
          <button className="cover-crop-backdrop" onClick={() => setCropCandidate(null)} type="button" aria-label="关闭封面显示区窗口" />
          <section className="cover-crop-sheet">
            <header>
              <div><span>COVER DISPLAY / 2.35:1</span><h3>在原图中调整公众号头图的显示范围</h3></div>
              <button disabled={Boolean(busy)} onClick={() => setCropCandidate(null)} type="button">关闭</button>
            </header>
            <div className="cover-crop-workspace">
              <div className="cover-crop-viewport" onWheel={zoomWithWheel}>
                <img
                  alt="封面裁切预览"
                  draggable={false}
                  src={absoluteApiUrl(cropCandidate.content_url)}
                />
                <div
                  className="cover-crop-selection"
                  onPointerCancel={stopDrag}
                  onPointerDown={startDrag}
                  onPointerMove={moveDrag}
                  onPointerUp={stopDrag}
                  style={{
                    "--crop-frame-size": `${100 / cropScale}%`,
                    "--crop-frame-x": `${cropOffset.x * 100}%`,
                    "--crop-frame-y": `${cropOffset.y * 100}%`,
                  } as CSSProperties}
                >
                  <div className="cover-crop-grid" aria-hidden="true"><i /><i /><i /><i /></div>
                  <span>封面显示区</span>
                </div>
              </div>
              <aside>
                <span>显示范围</span>
                <strong>{cropScale === 1 ? "完整宽度" : `聚焦 ${Math.round(100 / cropScale)}%`}</strong>
                <input
                  aria-label="调整封面显示区大小"
                  min="1"
                  max="3"
                  step="0.01"
                  type="range"
                  value={cropScale}
                  onChange={(event) => changeScale(Number(event.target.value))}
                />
                <p>{cropScale === 1 ? "当前显示区已占满原图宽度；上下拖动可选择头图保留位置。" : "使用滚轮或滑条调整范围，再拖动白色显示区选择画面重点。"}</p>
                <button
                  disabled={Boolean(busy)}
                  onClick={() => { setCropScale(DEFAULT_CROP_SCALE); setCropOffset({ x: 0, y: 0 }); }}
                  type="button"
                >恢复完整宽度</button>
              </aside>
            </div>
            <footer>
              <p>只保存 2.35:1 头图的显示位置并自动采用；5:4 候选原图不会被裁掉或覆盖。</p>
              <button disabled={Boolean(busy)} onClick={() => void saveCrop()} type="button">
                {busy === `crop:${cropCandidate.id}` ? "保存显示区中…" : "保存显示区并采用"}
              </button>
            </footer>
          </section>
        </div>
      ), document.body) : null}
    </section>
  );
}
