"use client";

import Link from "@/lib/router";
import { useMemo, useState } from "react";
import { absoluteApiUrl, getBlindReviewSet, submitBlindReview } from "@/lib/api";
import type {
  BlindDimensionRating,
  BlindReviewDimensionKey,
  BlindReviewSet,
  BlindReviewSubmission,
} from "@/lib/types";
import styles from "./blind-review.module.css";

const EVAL_SET_ID = "v0.6-visual-contrast-20260717";
const reviewerOptions = [
  { id: "product_owner" as const, label: "产品负责人", note: "独立完成" },
  { id: "operator" as const, label: "运营评审者", note: "运营同事独立完成" },
];

const articleLabels: Record<string, string> = {
  data_policy: "数据 / 政策",
  viewpoint_trend: "观点 / 趋势",
  tutorial_steps: "教程 / 步骤",
  lively_growth: "活动 / 成长",
};

const styleLabels: Record<string, string> = {
  editorial_paper_cut: "编辑纸感",
  soft_flat_illustration: "柔和平面插画",
  clean_3d_geometry: "简洁三维几何",
};

type ReviewerId = "product_owner" | "operator";
type Position = "left" | "right";

function emptyRatings(dimensions: BlindReviewSet["dimensions"]): BlindReviewSubmission["scores"] {
  return Object.fromEntries(
    dimensions.map((dimension) => [dimension.key, { left: 0, right: 0, reason: "" }]),
  ) as BlindReviewSubmission["scores"];
}

function ScorePicker({
  value,
  onChange,
  label,
}: {
  value: number;
  onChange: (value: number) => void;
  label: string;
}) {
  return (
    <fieldset className={styles.scorePicker} aria-label={label}>
      {[1, 2, 3, 4, 5].map((score) => (
        <label className={value === score ? styles.scoreActive : ""} key={score}>
          <input
            checked={value === score}
            name={label}
            onChange={() => onChange(score)}
            type="radio"
            value={score}
          />
          <span>{score}</span>
        </label>
      ))}
    </fieldset>
  );
}

export default function BlindReviewPage() {
  const [reviewerId, setReviewerId] = useState<ReviewerId | null>(null);
  const [reviewSet, setReviewSet] = useState<BlindReviewSet | null>(null);
  const [sampleIndex, setSampleIndex] = useState(0);
  const [ratings, setRatings] = useState<BlindReviewSubmission["scores"] | null>(null);
  const [preference, setPreference] = useState<Position | "tie" | "">("");
  const [preferenceReason, setPreferenceReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [validationAttempted, setValidationAttempted] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const sample = reviewSet?.samples[sampleIndex] ?? null;
  const allComplete = Boolean(reviewSet && reviewSet.progress.completed === reviewSet.progress.total);

  const missingItems = useMemo(() => {
    if (!reviewSet || !ratings) return [] as Array<{ label: string; targetId: string }>;
    const missing: Array<{ label: string; targetId: string }> = [];
    reviewSet.dimensions.forEach((dimension) => {
      const rating = ratings[dimension.key];
      const fields = [
        rating.left <= 0 ? "方案 A 分数" : null,
        rating.right <= 0 ? "方案 B 分数" : null,
        rating.reason.trim().length < 2 ? "比较理由" : null,
      ].filter(Boolean);
      if (fields.length) {
        missing.push({
          label: `${dimension.label}：${fields.join("、")}`,
          targetId: `dimension-${dimension.key}`,
        });
      }
    });
    if (!preference) missing.push({ label: "最终偏好", targetId: "final-preference" });
    if (preferenceReason.trim().length < 2) {
      missing.push({ label: "最终选择理由", targetId: "final-preference" });
    }
    return missing;
  }, [preference, preferenceReason, ratings, reviewSet]);
  const formComplete = missingItems.length === 0;

  async function chooseReviewer(nextReviewer: ReviewerId) {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const nextSet = await getBlindReviewSet(EVAL_SET_ID, nextReviewer);
      setReviewerId(nextReviewer);
      setReviewSet(nextSet);
      const nextIndex = Math.max(0, nextSet.samples.findIndex((item) => !item.submitted));
      setSampleIndex(nextIndex);
      setRatings(emptyRatings(nextSet.dimensions));
      setPreference("");
      setPreferenceReason("");
      setValidationAttempted(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "盲评集合加载失败");
    } finally {
      setLoading(false);
    }
  }

  function updateRating(key: BlindReviewDimensionKey, patch: Partial<BlindDimensionRating>) {
    setRatings((current) => current ? { ...current, [key]: { ...current[key], ...patch } } : current);
  }

  function goToSample(index: number) {
    if (!reviewSet) return;
    setSampleIndex(index);
    setRatings(emptyRatings(reviewSet.dimensions));
    setPreference("");
    setPreferenceReason("");
    setValidationAttempted(false);
    setError("");
    setNotice("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit() {
    if (!reviewSet || !sample || !reviewerId || !ratings || sample.submitted) return;
    if (!formComplete) {
      setValidationAttempted(true);
      setNotice("");
      const visible = missingItems.slice(0, 3).map((item) => item.label).join("；");
      const remaining = missingItems.length > 3 ? `；另有 ${missingItems.length - 3} 项` : "";
      setError(`暂时不能提交，还需要填写：${visible}${remaining}。`);
      window.requestAnimationFrame(() => {
        const target = document.getElementById(missingItems[0]?.targetId ?? "score-title");
        target?.scrollIntoView({ behavior: "smooth", block: "center" });
        target?.querySelector<HTMLElement>("input, textarea, button")?.focus({ preventScroll: true });
      });
      return;
    }
    setValidationAttempted(false);
    setSubmitting(true);
    setError("");
    try {
      await submitBlindReview(reviewSet.eval_set_id, sample.sample_id, {
        reviewer_id: reviewerId,
        assignment_token: sample.assignment_token,
        scores: ratings,
        preferred_candidate: preference as Position | "tie",
        preference_reason: preferenceReason.trim(),
      });
      const refreshed = await getBlindReviewSet(reviewSet.eval_set_id, reviewerId);
      setReviewSet(refreshed);
      const nextIndex = refreshed.samples.findIndex((item) => !item.submitted);
      if (nextIndex >= 0) {
        setNotice(`第 ${sample.index} 篇已锁定，已进入下一篇。`);
        setSampleIndex(nextIndex);
        setRatings(emptyRatings(refreshed.dimensions));
        setPreference("");
        setPreferenceReason("");
        setValidationAttempted(false);
        window.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        setNotice(`你的 ${refreshed.progress.total} 篇评审已全部提交。请等待另一位评审者独立完成后统一揭盲。`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (!reviewerId || !reviewSet) {
    return (
      <main className={styles.entryPage}>
        <header className={styles.entryHeader}>
          <Link href="/">视觉主编 / 返回任务台</Link>
          <span>BLIND REVIEW · V0.6</span>
        </header>
        <section className={styles.entryCard}>
          <p className={styles.kicker}>INDEPENDENT EDITORIAL REVIEW</p>
          <h1>先选身份，再看方案。</h1>
          <p className={styles.entryLead}>
            页面不会显示模型、规则或推荐来源。两位评审者请分别完成本轮全部样本，再一起讨论结果。
          </p>
          <div className={styles.reviewerChoices}>
            {reviewerOptions.map((reviewer, index) => (
              <button disabled={loading} key={reviewer.id} onClick={() => chooseReviewer(reviewer.id)} type="button">
                <span>0{index + 1}</span>
                <strong>{reviewer.label}</strong>
                <small>{reviewer.note}</small>
              </button>
            ))}
          </div>
          <div className={styles.protocolNote}>
            <strong>评审纪律</strong>
            <p>提交前不讨论选择；提交后不可修改；本轮只验证页面与规划质量，不评价实际生图画质。</p>
          </div>
          {error ? <p className={styles.error} role="alert">{error}</p> : null}
        </section>
      </main>
    );
  }

  if (!sample) return null;

  return (
    <main className={styles.reviewPage}>
      <header className={styles.stickyHeader}>
        <div className={styles.brandLine}>
          <Link href="/">视觉主编</Link>
          <span>匿名校样台</span>
        </div>
        <div className={styles.progressBlock}>
          <span>{reviewSet.reviewer.label}</span>
          <strong>{reviewSet.progress.completed} / {reviewSet.progress.total}</strong>
          <i style={{ width: `${(reviewSet.progress.completed / reviewSet.progress.total) * 100}%` }} />
        </div>
        <button className={styles.changeIdentity} onClick={() => { setReviewerId(null); setReviewSet(null); }} type="button">
          切换身份
        </button>
      </header>

      <section className={styles.sampleRail} aria-label="样本进度">
        {reviewSet.samples.map((item, index) => (
          <button
            className={`${index === sampleIndex ? styles.sampleCurrent : ""} ${item.submitted ? styles.sampleDone : ""}`}
            key={item.sample_id}
            onClick={() => goToSample(index)}
            type="button"
          >
            <span>{String(item.index).padStart(2, "0")}</span>
            <small>{item.submitted ? "已锁定" : "待评"}</small>
          </button>
        ))}
      </section>

      <section className={styles.sampleHeading}>
        <div>
          <p className={styles.kicker}>SAMPLE {String(sample.index).padStart(2, "0")} / VISUAL CONTRAST SET</p>
          <h1>{sample.title}</h1>
        </div>
        <div className={styles.sampleMeta}>
          <span>{articleLabels[sample.article_type] ?? sample.article_type}</span>
          <span>{sample.visual_scoring ? "可评视觉方向" : "OCR 样本 · 只评规划鲁棒性"}</span>
        </div>
      </section>

      {!reviewSet.formal_conclusion_allowed ? (
        <aside className={styles.devNotice}>{reviewSet.note}</aside>
      ) : null}
      {notice ? <p className={styles.notice} role="status">{notice}</p> : null}
      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <section className={styles.comparisonGrid} aria-label="匿名方案对照">
        {sample.candidates.map((candidate) => (
          <article className={styles.candidateColumn} key={candidate.position}>
            <header>
              <span>{candidate.position === "left" ? "A" : "B"}</span>
              <div><p>ANONYMOUS PLAN</p><h2>{candidate.label}</h2></div>
            </header>
            <div className={styles.summaryStrip}>
              <div><small>读者任务</small><p>{candidate.summary.article.reader_task}</p></div>
              <div><small>风格方向</small><p>{styleLabels[candidate.summary.art_direction.style_family] ?? candidate.summary.art_direction.style_family}</p></div>
              <div><small>组件 / 图片</small><p>{candidate.summary.components.length} / {candidate.summary.images.length}</p></div>
            </div>
            <details className={styles.planNotes}>
              <summary>查看规划依据</summary>
              <div className={styles.noteGrid}>
                <section><h3>受众与叙事</h3><p>{candidate.summary.article.audience.join("、")}</p><p>{candidate.summary.article.narrative}</p></section>
                <section><h3>语义组件</h3>{candidate.summary.components.length ? candidate.summary.components.map((item, index) => <p key={`${item.label}-${index}`}><b>{item.label}</b> · {item.anchor}</p>) : <p>本方案保持朴素正文，不强加语义组件。</p>}</section>
                <section><h3>图片意图</h3>{candidate.summary.images.map((item, index) => <p key={`${item.anchor}-${index}`}><b>{item.purpose}</b> · {item.anchor}<br />{item.visual_intent}</p>)}</section>
              </div>
            </details>
            <div className={styles.previewShell}>
              <div className={styles.previewRuler}><span>390</span><i /><span>MOBILE CONTENT</span></div>
              <iframe src={absoluteApiUrl(candidate.preview_url)} title={`${candidate.label}公众号预览`} />
            </div>
          </article>
        ))}
      </section>

      <section className={styles.scoreSection} aria-labelledby="score-title">
        <header>
          <div><p className={styles.kicker}>SCORE SHEET</p><h2 id="score-title">独立评分</h2></div>
          <p>1 分表示明显不满足，5 分表示可以直接进入下一轮编辑。每项理由用于复盘分歧。</p>
        </header>

        {sample.submitted ? (
          <div className={styles.lockedState}>
            <span>LOCKED</span>
            <h3>该样本已经提交</h3>
            <p>为保护盲评有效性，评分不可修改。请选择其他待评样本。</p>
          </div>
        ) : (
          <div className={styles.scoreTable}>
            {reviewSet.dimensions.map((dimension, index) => {
              const rating = ratings?.[dimension.key] ?? { left: 0, right: 0, reason: "" };
              const rowIncomplete = rating.left <= 0 || rating.right <= 0 || rating.reason.trim().length < 2;
              return (
                <div
                  className={`${styles.scoreRow} ${validationAttempted && rowIncomplete ? styles.scoreRowIncomplete : ""}`}
                  id={`dimension-${dimension.key}`}
                  key={dimension.key}
                >
                  <div className={styles.dimensionCopy}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <div><h3>{dimension.label}</h3><p>{dimension.description}</p></div>
                  </div>
                  <div className={styles.candidateScore}>
                    <small>方案 A</small>
                    <ScorePicker label={`${dimension.key}-left`} value={rating.left} onChange={(value) => updateRating(dimension.key, { left: value })} />
                  </div>
                  <div className={styles.candidateScore}>
                    <small>方案 B</small>
                    <ScorePicker label={`${dimension.key}-right`} value={rating.right} onChange={(value) => updateRating(dimension.key, { right: value })} />
                  </div>
                  <label className={styles.reasonField}>
                    <span>比较理由</span>
                    <input maxLength={240} onChange={(event) => updateRating(dimension.key, { reason: event.target.value })} placeholder="一句话记录关键差异" value={rating.reason} />
                  </label>
                </div>
              );
            })}

            <div
              className={`${styles.preferenceBlock} ${validationAttempted && (!preference || preferenceReason.trim().length < 2) ? styles.preferenceIncomplete : ""}`}
              id="final-preference"
            >
              <div><span>FINAL PICK</span><h3>更愿意继续编辑哪一版？</h3></div>
              <div className={styles.preferenceChoices}>
                {(["left", "right", "tie"] as const).map((value) => (
                  <button className={preference === value ? styles.preferenceActive : ""} key={value} onClick={() => setPreference(value)} type="button">
                    {value === "left" ? "方案 A" : value === "right" ? "方案 B" : "两者持平"}
                  </button>
                ))}
              </div>
              <label><span>最终选择理由</span><textarea maxLength={300} onChange={(event) => setPreferenceReason(event.target.value)} placeholder="哪一点最影响你的继续编辑意愿？" value={preferenceReason} /></label>
            </div>

            <div className={styles.submitBar}>
              <p role={validationAttempted && !formComplete ? "alert" : undefined}>
                {formComplete
                  ? "评分已完整。提交后将永久锁定。"
                  : validationAttempted
                    ? `还差 ${missingItems.length} 组必填内容，已标出并定位到第一处。`
                    : "请完成 12 个分数、6 条比较理由和最终选择；点击提交可检查漏填项。"}
              </p>
              <button disabled={submitting} onClick={handleSubmit} type="button">
                {submitting ? "正在锁定…" : `提交第 ${sample.index} 篇`}
              </button>
            </div>
          </div>
        )}
      </section>

      {allComplete ? <aside className={styles.completeBanner}><strong>你的评审已完成</strong><span>请让另一位评审者使用自己的身份继续完成，全部结束后再统一揭盲。</span></aside> : null}
    </main>
  );
}
