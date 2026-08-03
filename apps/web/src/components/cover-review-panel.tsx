"use client";

import { absoluteApiUrl } from "@/lib/api";
import type { CoverCandidate, CoverReuseSource, CoverWorkspace } from "@/lib/types";

type Props = {
  busy: string;
  review: CoverWorkspace | null;
  onGenerate: () => Promise<void>;
  onReuse: (source: CoverReuseSource) => Promise<void>;
  onSelect: (candidate: CoverCandidate) => Promise<void>;
  onUpload: (file: File) => Promise<void>;
};

const sourceLabels: Record<CoverCandidate["source_type"], string> = {
  ai_generated: "AI 全文生成",
  accepted_body_image: "正文配图复用",
  controlled_source_image: "原稿图片复用",
};

export function CoverReviewPanel({ busy, review, onGenerate, onReuse, onSelect, onUpload }: Props) {
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
                <button disabled={candidate.selected || Boolean(busy)} onClick={() => void onSelect(candidate)} type="button">
                  {candidate.selected ? "当前封面" : busy === `select:${candidate.id}` ? "采用中…" : "采用这张封面"}
                </button>
              </article>
            ))}
          </div>
        ) : <p>先生成 AI 候选、复用正文图片，或直接上传封面。</p>}
      </section>
    </section>
  );
}
