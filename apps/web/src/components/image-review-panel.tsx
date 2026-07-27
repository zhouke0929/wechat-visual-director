"use client";

import { absoluteApiUrl } from "@/lib/api";
import type { ImageCandidate, ImageSlotList, ImageSlotReview, VisualPlan } from "@/lib/types";

const purposeLabels = {
  atmosphere: "氛围概念图",
  structured_infographic: "轻量结构信息图",
} as const;

const providerLabels = {
  manual: ["MANUAL", "人工上传，不调用模型"],
  mock: ["MOCK", "交互验证，不消耗额度"],
  agnes: ["AGNES", "真实模型，图片需人工确认"],
} as const;

type Props = {
  plan: VisualPlan;
  review: ImageSlotList | null;
  busy: string;
  onGenerate: (slot: ImageSlotReview) => void;
  onAccept: (slot: ImageSlotReview, candidate: ImageCandidate) => void;
  onSkip: (slot: ImageSlotReview) => void;
  onReplace: (slot: ImageSlotReview, file: File) => void;
};

function candidateLabel(candidate: ImageCandidate, selected: boolean): string {
  if (candidate.provider === "manual_upload") return selected ? "人工替换 · 已采用" : "人工替换";
  return selected ? `候选 ${candidate.candidate_index} · 已采用` : `候选 ${candidate.candidate_index}`;
}

export function ImageReviewPanel({
  plan,
  review,
  busy,
  onGenerate,
  onAccept,
  onSkip,
  onReplace,
}: Props) {
  if (!review) {
    return (
      <section className="image-editor image-editor-loading" aria-label="配图确认">
        <span>IMAGE DESK</span>
        <p>正在打开配图工作台…</p>
      </section>
    );
  }

  return (
    <section className="image-editor" aria-label={`${plan.plan_name} 配图确认`}>
      <header className="image-editor-header">
        <div>
          <span>IMAGE DESK / SELECTED PLAN</span>
          <h3>配图确认 · {review.items.length} 个图片槽</h3>
          <p>只处理已选方案；生成成功后仍需逐张确认。</p>
        </div>
        <div className="provider-stamp">
          <strong>{providerLabels[review.provider_mode][0]}</strong>
          <small>{providerLabels[review.provider_mode][1]}</small>
        </div>
      </header>

      {review.items.length ? (
        <div className="image-slot-list">
          {review.items.map((slot, slotIndex) => {
            const modelCandidates = slot.state.candidates.filter((candidate) => candidate.provider !== "manual_upload");
            const slotBusy = busy.startsWith(`${slot.image_slot_id}:`);
            return (
              <article className="image-slot-card" id={`control-${slot.image_slot_id}`} key={slot.image_slot_id}>
                <div className="image-slot-brief">
                  <span className="image-slot-number">{String(slotIndex + 1).padStart(2, "0")}</span>
                  <div>
                    <div className="image-slot-title-row">
                      <strong>{purposeLabels[slot.purpose]}</strong>
                      <span>{slot.aspect_ratio}</span>
                      <span>R{String(slot.state.image_revision).padStart(2, "0")}</span>
                    </div>
                    <p>{slot.reason}</p>
                    <small>插入位置：{slot.anchor_block_id} 之后 · 可跳过</small>
                  </div>
                </div>

                {slot.state.last_error ? (
                  <div className="image-slot-error" role="status">
                    <div>
                      <strong>本次生成未完成</strong>
                      <p>{slot.state.last_error.message}</p>
                    </div>
                    <span>{slot.state.last_error.retryable ? "可重新生成" : "请检查配置或上传替换"}</span>
                  </div>
                ) : null}

                {slot.state.candidates.length ? (
                  <div className="candidate-contact-sheet">
                    {slot.state.candidates.map((candidate) => {
                      const selected = slot.state.selected_candidate_id === candidate.id;
                      return (
                        <div className={`candidate-card ${selected ? "candidate-selected" : ""}`} key={candidate.id}>
                          <div className="candidate-image-wrap">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={absoluteApiUrl(candidate.content_url)} alt={`${purposeLabels[slot.purpose]}候选 ${candidate.candidate_index}`} />
                            <span>{candidateLabel(candidate, selected)}</span>
                          </div>
                          <div className="candidate-meta">
                            <span>{candidate.width}×{candidate.height}</span>
                            <span>{candidate.provider === "mock" ? "本地 Mock" : candidate.model}</span>
                            <span>风险项待人工确认</span>
                          </div>
                          <details>
                            <summary>查看脱敏提示词</summary>
                            <p>{candidate.provider_prompt}</p>
                          </details>
                          <button
                            className={selected ? "candidate-accepted-button" : "candidate-accept-button"}
                            disabled={slotBusy || selected}
                            onClick={() => onAccept(slot, candidate)}
                            type="button"
                          >
                            {selected ? "已采用" : "接受这张"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="image-empty-contact">
                    <span>EMPTY CONTACT SHEET</span>
                    <p>当前只有位置与用途规划，还没有生成图片候选。</p>
                  </div>
                )}

                <div className="image-slot-actions">
                  <button
                    className="image-generate-button"
                    disabled={review.provider_mode === "manual" || slotBusy || modelCandidates.length >= 3}
                    onClick={() => onGenerate(slot)}
                    type="button"
                  >
                    {review.provider_mode === "manual"
                      ? "人工模式：请上传图片"
                      : busy === `${slot.image_slot_id}:generate`
                      ? review.provider_mode === "agnes" ? "Agnes 生成中…" : "生成中…"
                      : modelCandidates.length
                        ? `重生成候选 ${modelCandidates.length + 1}`
                        : "生成第一张"}
                  </button>
                  <label className={slotBusy ? "image-upload-button disabled" : "image-upload-button"}>
                    上传替换
                    <input
                      accept="image/png,image/jpeg,image/webp"
                      disabled={slotBusy}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) onReplace(slot, file);
                        event.target.value = "";
                      }}
                      type="file"
                    />
                  </label>
                  <button
                    className="image-skip-button"
                    disabled={slotBusy || slot.state.status === "skipped"}
                    onClick={() => onSkip(slot)}
                    type="button"
                  >
                    {slot.state.status === "skipped" ? "已跳过" : "本篇跳过"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="image-plan-empty">
          <strong>这篇文章不需要自动配图</strong>
          <p>系统主动保留纯排版方案；固定小程序 CTA 不计入图片槽。</p>
        </div>
      )}
    </section>
  );
}
