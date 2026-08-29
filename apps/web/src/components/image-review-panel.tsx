"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { absoluteApiUrl } from "@/lib/api";
import { ResilientImage } from "@/components/resilient-image";
import type {
  ImageCandidate,
  ImageSlotList,
  ImageSlotReview,
  VisualPlan,
} from "@/lib/types";

const purposeLabels = {
  atmosphere: "氛围概念图",
  structured_infographic: "轻量结构信息图",
} as const;

const roleLabels = {
  explain_sequence: "解释顺序",
  compare_options: "比较差异",
  show_evolution: "展示演进",
  explain_framework: "说明框架",
  establish_context: "建立语境",
  create_emotional_pause: "情绪停顿",
} as const;

const layoutLabels = {
  semantic_scene: "语义场景",
  linear_progression: "线性进程",
  binary_comparison: "二元对比",
  comparison_matrix: "比较矩阵",
  hierarchical_layers: "层级关系",
  hub_spoke: "中心辐射",
  structural_breakdown: "结构拆解",
  timeline: "时间线",
  pathway: "连续路径",
} as const;

type Props = {
  plan: VisualPlan;
  review: ImageSlotList | null;
  busy: readonly string[];
  onGenerate: (slot: ImageSlotReview) => Promise<void>;
  onAccept: (slot: ImageSlotReview, candidate: ImageCandidate, textVerified: boolean) => Promise<void>;
  onSkip: (slot: ImageSlotReview) => Promise<void>;
  onReplace: (slot: ImageSlotReview, file: File) => Promise<void>;
  onRestoreTheme: () => Promise<void>;
};

type ReviewTarget = {
  slot: ImageSlotReview;
  candidate: ImageCandidate;
};

function candidateLabel(candidate: ImageCandidate, selected: boolean): string {
  if (candidate.provider === "manual_upload") return selected ? "人工替换 · 已采用" : "人工替换";
  if (candidate.provider === "host_agent") return selected ? "当前 Agent · 已采用" : "当前 Agent";
  return selected ? `候选 ${candidate.candidate_index} · 已采用` : `候选 ${candidate.candidate_index}`;
}

function targetKey(target: ReviewTarget): string {
  return `${target.slot.image_slot_id}:${target.candidate.id}`;
}

function reviewStatus(slot: ImageSlotReview): "accepted" | "skipped" | "pending" {
  if (slot.state.selected_candidate_id) return "accepted";
  if (slot.state.status === "skipped") return "skipped";
  return "pending";
}

export function ImageReviewPanel({
  plan,
  review,
  busy,
  onGenerate,
  onAccept,
  onSkip,
  onReplace,
  onRestoreTheme,
}: Props) {
  const [activeTargetKey, setActiveTargetKey] = useState<string | null>(null);
  const knownCandidateIds = useRef<Set<string> | null>(null);
  const knownReviewIdentity = useRef<string | null>(null);

  const allTargets = useMemo<ReviewTarget[]>(
    () =>
      review?.items.flatMap((slot) =>
        slot.state.candidates.map((candidate) => ({ slot, candidate })),
      ) ?? [],
    [review],
  );

  const reviewQueue = useMemo<ReviewTarget[]>(
    () =>
      review?.items.flatMap((slot) => {
        if (reviewStatus(slot) !== "pending") return [];
        const candidate = slot.state.candidates.at(-1);
        return candidate ? [{ slot, candidate }] : [];
      }) ?? [],
    [review],
  );

  const activeTarget =
    allTargets.find((target) => targetKey(target) === activeTargetKey) ?? null;
  const reviewIdentity = review ? `${review.task_id}:${review.plan_id}` : null;
  const anyImageActionBusy = busy.length > 0;

  useEffect(() => {
    const currentIds = new Set(allTargets.map((target) => target.candidate.id));
    if (!reviewIdentity) {
      knownReviewIdentity.current = null;
      knownCandidateIds.current = null;
      setActiveTargetKey(null);
      return;
    }
    if (knownReviewIdentity.current !== reviewIdentity || knownCandidateIds.current === null) {
      knownReviewIdentity.current = reviewIdentity;
      knownCandidateIds.current = currentIds;
      setActiveTargetKey(null);
      return;
    }
    const newTarget = allTargets.find(
      (target) => !knownCandidateIds.current?.has(target.candidate.id),
    );
    knownCandidateIds.current = currentIds;
    if (newTarget) setActiveTargetKey(targetKey(newTarget));
  }, [allTargets, reviewIdentity]);

  useEffect(() => {
    if (!activeTarget) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActiveTargetKey(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [activeTarget]);

  if (!review) {
    return (
      <section className="image-editor image-editor-loading" aria-label="配图确认">
        <span>IMAGE DESK</span>
        <p>正在打开配图工作台…</p>
      </section>
    );
  }

  async function acceptFromViewer(target: ReviewTarget) {
    const textCheck = target.candidate.machine_checks.text_consistency;
    const requiresManualTextConfirmation =
      target.slot.purpose === "structured_infographic" && textCheck?.status !== "passed";
    const currentQueueIndex = reviewQueue.findIndex(
      (item) => targetKey(item) === targetKey(target),
    );
    const nextTarget =
      reviewQueue[currentQueueIndex + 1] ??
      reviewQueue.find((item) => targetKey(item) !== targetKey(target)) ??
      null;

    await onAccept(
      target.slot,
      target.candidate,
      requiresManualTextConfirmation,
    );
    setActiveTargetKey(nextTarget ? targetKey(nextTarget) : null);
  }

  function moveInQueue(direction: -1 | 1) {
    if (!activeTarget || !reviewQueue.length) return;
    const currentIndex = reviewQueue.findIndex(
      (target) => targetKey(target) === targetKey(activeTarget),
    );
    const baseIndex = currentIndex < 0 ? 0 : currentIndex;
    const nextIndex = (baseIndex + direction + reviewQueue.length) % reviewQueue.length;
    setActiveTargetKey(targetKey(reviewQueue[nextIndex]));
  }

  return (
    <section className="image-editor" aria-label={`${plan.plan_name} 配图确认`}>
      {review.items.length ? (
        <div className="image-slot-list">
          {review.items.map((slot, slotIndex) => {
            const modelCandidates = slot.state.candidates.filter(
              (candidate) =>
                candidate.provider !== "manual_upload" &&
                candidate.provider !== "deterministic_fallback",
            );
            const currentVisualSystem = plan.visual_system ?? plan.style_mode;
            const currentThemeCandidates = modelCandidates.filter((candidate) => {
              const snapshot = candidate.machine_checks.art_direction_snapshot;
              return !snapshot || snapshot.visual_system === currentVisualSystem;
            });
            const compatibilityCandidate =
              slot.state.candidates.find(
                (candidate) => candidate.id === slot.state.selected_candidate_id,
              ) ?? slot.state.candidates.at(-1);
            const compatibility = compatibilityCandidate?.theme_compatibility;
            const slotBusy = busy.some((key) => key.startsWith(`${slot.image_slot_id}:`));
            const status = reviewStatus(slot);
            return (
              <article
                className={`image-slot-card image-slot-${status}`}
                id={`control-${slot.image_slot_id}`}
                key={slot.image_slot_id}
              >
                <div className="image-slot-brief">
                  <span className="image-slot-number">
                    {String(slotIndex + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <div className="image-slot-title-row">
                      <strong>{purposeLabels[slot.purpose]}</strong>
                      <span>{slot.aspect_ratio}</span>
                      <span className={`slot-status slot-status-${status}`}>
                        {status === "accepted" ? "已采用" : status === "skipped" ? "已跳过" : "待处理"}
                      </span>
                    </div>
                    <details className="image-slot-intent">
                      <summary>查看配图意图</summary>
                      <p>{slot.reason}</p>
                      <small>
                        图片目标：{roleLabels[slot.visual_intent.visual_role]} · {layoutLabels[slot.visual_intent.layout_family]}
                      </small>
                      <small>{slot.visual_intent.learning_objective}</small>
                      {slot.purpose === "structured_infographic" ? (
                        <small>
                          视觉脚本：{slot.visual_intent.visual_grammar?.scene_metaphor ?? "兼容版语义场景"} ·
                          {slot.visual_intent.visual_grammar?.text_mode === "verbatim_full_copy"
                            ? "原文短句"
                            : "短标签插画"}
                        </small>
                      ) : null}
                      <small>插入位置：{slot.anchor_block_id} 之后</small>
                    </details>
                  </div>
                </div>

                {compatibility?.level === "incompatible" ? (
                  <div className={`image-theme-compatibility image-theme-${compatibility.level}`} role="status">
                    <div>
                      <strong>图片与新主题差异较大</strong>
                      <p>{compatibility.message} 默认继续保留，不会自动重生成或产生费用。</p>
                    </div>
                    <div>
                      <button
                        disabled={slotBusy}
                        onClick={() => void onGenerate(slot)}
                        type="button"
                      >按新主题抽一张</button>
                      {(plan.undo_stack ?? []).length ? (
                        <button disabled={anyImageActionBusy} onClick={() => void onRestoreTheme()} type="button">
                          回到上个主题
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {slot.state.last_error ? (
                  <div className="image-slot-error" role="status">
                    <div>
                      <strong>本次生成未完成</strong>
                      <p>{slot.state.last_error.message}</p>
                    </div>
                    <span>
                      {slot.state.last_error.retryable
                        ? "可重新生成"
                        : "请检查配置或上传替换"}
                    </span>
                  </div>
                ) : null}

                {slot.state.candidates.length ? (
                  <div className="candidate-contact-sheet">
                    {slot.state.candidates.map((candidate) => {
                      const selected =
                        slot.state.selected_candidate_id === candidate.id;
                      const textCheck = candidate.machine_checks.text_consistency;
                      return (
                        <div
                          className={`candidate-card ${selected ? "candidate-selected" : ""}`}
                          key={candidate.id}
                        >
                          <button
                            className="candidate-image-wrap candidate-preview-button"
                            onClick={() =>
                              setActiveTargetKey(targetKey({ slot, candidate }))
                            }
                            type="button"
                          >
                            <ResilientImage
                              src={absoluteApiUrl(candidate.content_url)}
                              alt={`${purposeLabels[slot.purpose]}候选 ${candidate.candidate_index}`}
                            />
                            <span>{candidateLabel(candidate, selected)}</span>
                            <i>点击放大审核</i>
                          </button>
                          <div className="candidate-meta">
                            <span>{candidate.width}×{candidate.height}</span>
                            <span>
                              {candidate.provider === "mock"
                                ? "本地 Mock"
                                : candidate.model}
                            </span>
                            <span>
                              {textCheck?.status === "passed"
                                ? "OCR 已核对"
                                : slot.purpose === "structured_infographic"
                                  ? "需人工核对文字"
                                  : "无锁定文字"}
                            </span>
                          </div>
                          <button
                            className={
                              selected
                                ? "candidate-accepted-button"
                                : "candidate-accept-button"
                            }
                            disabled={slotBusy}
                            onClick={() =>
                              setActiveTargetKey(targetKey({ slot, candidate }))
                            }
                            type="button"
                          >
                            {selected ? "查看已采用图片" : "放大并审核"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="image-empty-contact">
                    <span>READY TO GENERATE</span>
                    <p>位置和用途已规划好，请为这一处单独生成、上传图片，或选择跳过。</p>
                  </div>
                )}

                <div className="image-slot-actions">
                  <button
                    className="image-generate-button"
                    disabled={
                      review.provider_mode === "manual" ||
                      slotBusy
                    }
                    onClick={() => void onGenerate(slot)}
                    type="button"
                  >
                    {review.provider_mode === "manual"
                      ? "人工模式：请上传图片"
                      : busy.includes(`${slot.image_slot_id}:generate`)
                        ? "图片生成中…"
                        : modelCandidates.length
                          ? currentThemeCandidates.length
                            ? `再抽一张（本主题已有 ${currentThemeCandidates.length} 张）`
                            : "按当前主题抽一张"
                          : "生成图片"}
                  </button>
                  <label
                    className={
                      slotBusy
                        ? "image-upload-button disabled"
                        : "image-upload-button"
                    }
                  >
                    上传替换
                    <input
                      accept="image/png,image/jpeg,image/webp"
                      disabled={slotBusy}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) void onReplace(slot, file);
                        event.target.value = "";
                      }}
                      type="file"
                    />
                  </label>
                  <button
                    className="image-skip-button"
                    disabled={slotBusy || status === "skipped"}
                    onClick={() => void onSkip(slot)}
                    type="button"
                  >
                    {status === "skipped" ? "已跳过" : "本篇不配图"}
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

      {activeTarget && typeof document !== "undefined" ? createPortal((
        <div
          aria-label="图片大图审核"
          aria-modal="true"
          className="image-review-modal"
          role="dialog"
        >
          <button
            aria-label="关闭图片审核"
            className="image-review-backdrop"
            onClick={() => setActiveTargetKey(null)}
            type="button"
          />
          <div className="image-review-dialog">
            <header className="image-review-dialog-header">
              <div>
                <span>FULL FRAME REVIEW</span>
                <strong>
                  {purposeLabels[activeTarget.slot.purpose]} · 候选{" "}
                  {activeTarget.candidate.candidate_index}
                </strong>
              </div>
              <div className="image-review-dialog-tools">
                <button onClick={() => setActiveTargetKey(null)} type="button">关闭</button>
              </div>
            </header>

            <div className="image-review-dialog-body">
              <div className="image-review-canvas">
                <div className="image-review-canvas-scroll">
                  <ResilientImage
                    src={absoluteApiUrl(activeTarget.candidate.content_url)}
                    alt={`${purposeLabels[activeTarget.slot.purpose]}审核大图`}
                  />
                </div>
                <div className="image-review-canvas-caption">
                  <span>
                    {activeTarget.candidate.width}×{activeTarget.candidate.height}
                  </span>
                  <span>{activeTarget.candidate.model}</span>
                  {activeTarget.candidate.raw_content_url ? (
                    <a
                      href={absoluteApiUrl(activeTarget.candidate.raw_content_url)}
                      rel="noreferrer"
                      target="_blank"
                    >
                      查看模型原始输出
                    </a>
                  ) : null}
                </div>
              </div>

              <aside className="image-review-inspector">
                <span>EDITOR CHECK</span>
                <h4>先看整体，再核对文字</h4>
                <p>{activeTarget.slot.reason}</p>
                <p>
                  {roleLabels[activeTarget.slot.visual_intent.visual_role]} · {layoutLabels[activeTarget.slot.visual_intent.layout_family]}：{activeTarget.slot.visual_intent.learning_objective}
                </p>

                {activeTarget.slot.purpose === "structured_infographic" ? (
                  <section className="image-review-locked-copy">
                    <div>
                      <strong>必须与图片一致的原文</strong>
                      <i>
                        {activeTarget.candidate.machine_checks.text_consistency?.status ===
                        "passed"
                          ? "OCR 已通过"
                          : "需人工核对"}
                      </i>
                    </div>
                    <ol>
                      {(activeTarget.candidate.machine_checks.locked_copy ?? []).map(
                        (value) => <li key={value}>{value}</li>,
                      )}
                    </ol>
                    {activeTarget.candidate.machine_checks.text_consistency?.status !==
                    "passed" ? (
                      <small>
                        点击“文字无误，采用此图”即代表你已逐项确认，不需要再勾选一次。
                      </small>
                    ) : null}
                  </section>
                ) : (
                  <section className="image-review-no-copy">
                    <strong>本图没有锁定文字</strong>
                    <p>只需判断画面是否符合文章语义、风格和阅读节奏。</p>
                  </section>
                )}

                <details>
                  <summary>查看脱敏提示词</summary>
                  <p>{activeTarget.candidate.provider_prompt}</p>
                </details>

                <div className="image-review-primary-actions">
                  <button
                    className="image-review-accept"
                    disabled={
                      anyImageActionBusy ||
                      activeTarget.slot.state.selected_candidate_id ===
                        activeTarget.candidate.id
                    }
                    onClick={() => void acceptFromViewer(activeTarget)}
                    type="button"
                  >
                    {activeTarget.slot.state.selected_candidate_id ===
                    activeTarget.candidate.id
                      ? "这张图片已采用"
                      : activeTarget.slot.purpose === "structured_infographic" &&
                          activeTarget.candidate.machine_checks.text_consistency
                            ?.status !== "passed"
                        ? "文字无误，采用此图"
                        : "采用此图"}
                  </button>
                  <button
                    disabled={anyImageActionBusy}
                    onClick={() => {
                      setActiveTargetKey(null);
                      void onSkip(activeTarget.slot);
                    }}
                    type="button"
                  >
                    本篇不配这张图
                  </button>
                </div>
              </aside>
            </div>

            {reviewQueue.length > 1 ? (
              <footer className="image-review-dialog-footer">
                <button onClick={() => moveInQueue(-1)} type="button">← 上一张待审核</button>
                <span>{reviewQueue.length} 张图片等待决定</span>
                <button onClick={() => moveInQueue(1)} type="button">下一张待审核 →</button>
              </footer>
            ) : null}
          </div>
        </div>
      ), document.body) : null}
    </section>
  );
}
