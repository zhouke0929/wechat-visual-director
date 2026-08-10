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
  onCrop: (candidate: CoverCandidate, transform: { scale: number; offsetX: number; offsetY: number }) => Promise<void>;
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

const DEFAULT_CROP_SCALE = 1.15;

function clampOffset(value: number, scale: number) {
  const limit = Math.max(0, (1 - 1 / scale) / 2);
  return Math.max(-limit, Math.min(limit, value));
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
    setCropCandidate(candidate);
    setCropScale(DEFAULT_CROP_SCALE);
    setCropOffset({ x: 0, y: 0 });
  }

  function changeScale(nextScale: number) {
    setCropScale(nextScale);
    setCropOffset((current) => ({
      x: clampOffset(current.x, nextScale),
      y: clampOffset(current.y, nextScale),
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
      x: clampOffset(drag.offsetX + (event.clientX - drag.startX) / bounds.width, cropScale),
      y: clampOffset(drag.offsetY + (event.clientY - drag.startY) / bounds.height, cropScale),
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
        offsetX: -cropOffset.x * cropScale,
        offsetY: -cropOffset.y * cropScale,
      });
      setCropCandidate(null);
    } catch {
      // The task page renders the API error; keep the crop state open for correction or retry.
    }
  }

  if (!review) return <div className="cover-loading">正在读取封面工作台…</div>;
  return (
    <section className="cover-desk" aria-label="封面规划与选择">
      <header className="cover-desk-header">
        <div>
          <span>COVER DIRECTOR / 1080×864</span>
          <h3>封面不是附件，是文章的第一视觉判断</h3>
          <p>{review.cover_brief.narrative}</p>
        </div>
        <b>{review.selected_cover ? "已选封面" : "待选择"}</b>
      </header>

      <div className="cover-brief-ticket">
        <span>全文提炼</span>
        <strong>{review.cover_brief.reader_task}</strong>
        <small>标题安全区：左上与中央 · 模型底图禁止文字、二维码和 Logo</small>
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
            {review.provider_mode === "images_api"
              ? "通用 Images API"
              : review.provider_mode === "gemini"
              ? "Gemini / Nano Banana"
              : review.provider_mode === "mock" ? "Mock 确定性候选" : "不调用图片模型"}
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
          <span>{review.candidates.length ? `${review.candidates.length} 张 · 全部已无损适配为 5:4` : "尚未生成候选"}</span>
        </header>
        {review.candidates.length ? (
          <div>
            {review.candidates.map((candidate) => (
              <article className={candidate.selected ? "selected" : ""} key={candidate.id}>
                <div className="cover-crop-frame">
                  <img alt={`封面候选 ${candidate.candidate_index}`} src={absoluteApiUrl(candidate.content_url)} />
                  <i>标题安全区</i>
                </div>
                <p><span>{String(candidate.candidate_index).padStart(2, "0")}</span><strong>{sourceLabels[candidate.source_type]}</strong></p>
                <div className="cover-candidate-actions">
                  <button disabled={Boolean(busy)} onClick={() => openCrop(candidate)} type="button">调整裁切</button>
                  <button disabled={candidate.selected || Boolean(busy)} onClick={() => void onSelect(candidate)} type="button">
                    {candidate.selected ? "当前封面" : busy === `select:${candidate.id}` ? "采用中…" : "直接采用"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : <p>可生成 AI 候选、复用正文图片、直接上传，或一键使用主题保底封面。</p>}
      </section>

      {cropCandidate && typeof document !== "undefined" ? createPortal((
        <div className="cover-crop-dialog" role="dialog" aria-modal="true" aria-label="调整封面裁切">
          <button className="cover-crop-backdrop" onClick={() => setCropCandidate(null)} type="button" aria-label="关闭裁切窗口" />
          <section className="cover-crop-sheet">
            <header>
              <div><span>COVER CROP / 5:4</span><h3>拖动裁切框，留下最重要的视觉焦点</h3></div>
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
                  <span>最终保留区域</span>
                </div>
              </div>
              <aside>
                <span>缩放画面</span>
                <strong>{Math.round(cropScale * 100)}%</strong>
                <input
                  aria-label="缩放封面"
                  min="1"
                  max="3"
                  step="0.01"
                  type="range"
                  value={cropScale}
                  onChange={(event) => changeScale(Number(event.target.value))}
                />
                <p>{cropScale === 1 ? "当前显示完整原图；使用滚轮或滑条放大后，即可拖动裁切框。" : "鼠标滚轮或滑条缩放；按住白色裁切框可拖到画面边缘。"}</p>
                <button
                  disabled={Boolean(busy)}
                  onClick={() => { setCropScale(DEFAULT_CROP_SCALE); setCropOffset({ x: 0, y: 0 }); }}
                  type="button"
                >重置位置</button>
              </aside>
            </div>
            <footer>
              <p>原始候选不会被覆盖，保存后会生成一张新的受控封面并自动采用。</p>
              <button disabled={Boolean(busy)} onClick={() => void saveCrop()} type="button">
                {busy === `crop:${cropCandidate.id}` ? "保存裁切中…" : "保存裁切并采用"}
              </button>
            </footer>
          </section>
        </div>
      ), document.body) : null}
    </section>
  );
}
