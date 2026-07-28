"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { BackIcon, CheckIcon } from "@/components/icons";
import { ImageReviewPanel } from "@/components/image-review-panel";
import { CoverReviewPanel } from "@/components/cover-review-panel";
import { PreflightPanel } from "@/components/preflight-panel";
import { PublicationPanel } from "@/components/publication-panel";
import { StatusPill } from "@/components/status-pill";
import {
  absoluteApiUrl,
  acknowledgePreflightFinding,
  acceptImageCandidate,
  continueEditingPublication,
  createWenyanDraft,
  freezePublication,
  generatePlans,
  generateCoverCandidate,
  generateImageCandidate,
  getDraftOperations,
  getClipboardPayload,
  getCoverWorkspace,
  getImageSlots,
  getPlans,
  getPublicationReadiness,
  getPublicationRevisions,
  getTask,
  getWenyanPublisherStatus,
  retryWenyanDraft,
  publicationBundleUrl,
  replacePreflightAsset,
  replaceImageSlot,
  reuseCoverCandidate,
  savePublicationDraft,
  selectPlan,
  selectCoverCandidate,
  skipImageSlot,
  switchPlanSlot,
  undoPlanChange,
} from "@/lib/api";
import type {
  ComponentSlot,
  CoverCandidate,
  CoverReuseSource,
  CoverWorkspace,
  DraftOperation,
  ImageCandidate,
  ImageSlotList,
  ImageSlotReview,
  PlanList,
  PreflightFinding,
  PublicationReadiness,
  PublicationMetadata,
  PublicationRevision,
  TaskDetail,
  VisualPlan,
  WenyanPublisherStatus,
} from "@/lib/types";

const styleLabels: Record<string, string> = {
  data_decision: "DATA DECISION",
  editorial_insight: "EDITORIAL INSIGHT",
  lively_science: "LIVELY SCIENCE",
  light_reading: "轻盈阅读",
  editorial_contrast: "编辑对比",
  warm_humanist: "温暖人文",
  structured_grid: "理性网格",
};

function historyMessage(slot: ComponentSlot): string | null {
  const history = slot.history_evidence;
  if (history.penalty_applied && history.avoided_variant) {
    const avoided = slot.variant_options.find((option) => option.value === history.avoided_variant)?.label ?? "默认轮廓";
    return `最近 5 篇中「${avoided}」使用更多，已自动选择较少使用的变体`;
  }
  if (history.component_use_count > 0) {
    return `已检查最近 5 篇：当前变体出现 ${history.recent_use_count} 次`;
  }
  return null;
}

export default function TaskReviewPage() {
  const params = useParams<{ taskId: string }>();
  const taskId = params.taskId;
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [planList, setPlanList] = useState<PlanList | null>(null);
  const [activeMobilePlan, setActiveMobilePlan] = useState(0);
  const [activeEditorTab, setActiveEditorTab] = useState<"components" | "images" | "cover">("components");
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState("");
  const [editingSlot, setEditingSlot] = useState("");
  const [restoring, setRestoring] = useState("");
  const [imageReview, setImageReview] = useState<ImageSlotList | null>(null);
  const [coverReview, setCoverReview] = useState<CoverWorkspace | null>(null);
  const [coverBusy, setCoverBusy] = useState("");
  const [imageBusy, setImageBusy] = useState("");
  const [imageRefreshToken, setImageRefreshToken] = useState(0);
  const [sourceAssetRefreshToken, setSourceAssetRefreshToken] = useState(0);
  const [focusSlotByPlan, setFocusSlotByPlan] = useState<Record<string, string>>({});
  const [preflightBusy, setPreflightBusy] = useState("");
  const [planningBusy, setPlanningBusy] = useState(false);
  const [publicationBusy, setPublicationBusy] = useState("");
  const [publicationReadiness, setPublicationReadiness] = useState<PublicationReadiness | null>(null);
  const [publicationRevisions, setPublicationRevisions] = useState<PublicationRevision[]>([]);
  const [draftOperations, setDraftOperations] = useState<DraftOperation[]>([]);
  const [wenyanPublisher, setWenyanPublisher] = useState<WenyanPublisherStatus | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const initialWorkspaceResolved = useRef(false);

  const load = useCallback(async () => {
    const nextDetail = await getTask(taskId);
    setDetail(nextDetail);
    setWenyanPublisher(await getWenyanPublisherStatus());
    if (["plans_ready", "plan_selected"].includes(nextDetail.task.status)) {
      const nextPlans = await getPlans(taskId);
      setPlanList(nextPlans);
      if (nextDetail.task.selected_plan_id) {
        if (!initialWorkspaceResolved.current) {
          setActiveEditorTab("images");
          initialWorkspaceResolved.current = true;
        }
        setImageReview(await getImageSlots(taskId, nextDetail.task.selected_plan_id));
        setCoverReview(await getCoverWorkspace(taskId, nextDetail.task.selected_plan_id));
      } else {
        setImageReview(null);
        setCoverReview(null);
      }
    } else {
      setPlanList(null);
      setImageReview(null);
      setCoverReview(null);
    }
    if (nextDetail.task.selected_plan_id || nextDetail.task.active_publication_revision_id) {
      // Repository currently uses one SQLite connection. Keep these reads ordered so a
      // browser refresh cannot make three worker threads use that connection at once.
      const nextReadiness = await getPublicationReadiness(taskId);
      const nextRevisions = await getPublicationRevisions(taskId);
      const nextOperations = await getDraftOperations(taskId);
      setPublicationReadiness(nextReadiness);
      setPublicationRevisions(nextRevisions);
      setDraftOperations(nextOperations);
    } else {
      setPublicationReadiness(null);
      setPublicationRevisions([]);
      setDraftOperations([]);
    }
  }, [taskId]);

  useEffect(() => {
    load()
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [load]);

  async function handleSelection(plan: VisualPlan) {
    if (!detail) return;
    setSelecting(plan.id);
    setError("");
    setNotice("");
    try {
      const wasSelected = detail.task.selected_plan_id;
      await selectPlan(detail.task, plan.id);
      await load();
      setActiveEditorTab("images");
      setNotice(wasSelected && wasSelected !== plan.id ? "方案已切换；没有重新调用规划器。" : "方案已选中，可以继续进入下一阶段。 ");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "选择方案失败");
    } finally {
      setSelecting("");
    }
  }

  async function handleVariantSwitch(plan: VisualPlan, slot: ComponentSlot, variant: string) {
    if (variant === slot.variant) return;
    const key = `${plan.id}:${slot.slot_id}`;
    setEditingSlot(key);
    setError("");
    setNotice("");
    try {
      setFocusSlotByPlan((current) => ({ ...current, [plan.id]: slot.slot_id }));
      const result = await switchPlanSlot(taskId, plan.id, slot.slot_id, variant, plan.revision);
      setPlanList((current) => current ? {
        ...current,
        plans: current.plans.map((item) => item.id === result.plan.id ? result.plan : item),
      } : current);
      const label = slot.variant_options.find((item) => item.value === variant)?.label ?? variant;
      setNotice(`「${slot.component_label}」已切换为${label}；预览已定位并标出变化位置。`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "局部换型失败");
    } finally {
      setEditingSlot("");
    }
  }

  async function handleRestore(plan: VisualPlan) {
    if (!(plan.undo_stack ?? []).length) return;
    setRestoring(plan.id);
    setError("");
    setNotice("");
    try {
      const result = await undoPlanChange(taskId, plan.id, plan.revision);
      setPlanList((current) => current ? {
        ...current,
        plans: current.plans.map((item) => item.id === result.plan.id ? result.plan : item),
      } : current);
      setNotice(`方案 ${String.fromCharCode(64 + plan.plan_index)} 已撤回上次局部换型；不会在两个修订间反复切换。`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "恢复修订失败");
    } finally {
      setRestoring("");
    }
  }

  async function refreshImageReview(planId: string) {
    setImageReview(await getImageSlots(taskId, planId));
    setCoverReview(await getCoverWorkspace(taskId, planId));
    setImageRefreshToken((current) => current + 1);
  }

  async function handleImageGenerate(plan: VisualPlan, slot: ImageSlotReview) {
    const key = `${slot.image_slot_id}:generate`;
    const modelCandidateCount = slot.state.candidates.filter((candidate) => candidate.provider !== "manual_upload").length;
    setImageBusy(key);
    setError("");
    setNotice("");
    try {
      await generateImageCandidate(
        taskId,
        plan.id,
        slot.image_slot_id,
        slot.state.image_revision,
        modelCandidateCount ? "regenerate" : "start",
      );
      await refreshImageReview(plan.id);
      setFocusSlotByPlan((current) => ({ ...current, [plan.id]: slot.image_slot_id }));
      setNotice(modelCandidateCount ? `已生成候选 ${modelCandidateCount + 1}，原采纳图片没有被覆盖。` : "第一张候选已生成，请确认后再采用。 ");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "生成图片候选失败";
      try {
        await refreshImageReview(plan.id);
      } catch {
        // 保留原始 Provider 错误，避免刷新错误覆盖真正失败原因。
      }
      setError(message);
    } finally {
      setImageBusy("");
    }
  }

  async function handleImageGenerateAll(plan: VisualPlan) {
    if (!imageReview) return;
    const targets = imageReview.items.filter(
      (slot) =>
        slot.state.decision === "pending" &&
        slot.state.candidates.length === 0,
    );
    if (!targets.length) return;

    setImageBusy("batch");
    setError("");
    setNotice("");
    const failures: string[] = [];
    let generatedCount = 0;
    try {
      // 图片 Provider 常有并发限制。这里有意串行执行，减少限流和重复计费风险。
      for (const slot of targets) {
        try {
          await generateImageCandidate(
            taskId,
            plan.id,
            slot.image_slot_id,
            slot.state.image_revision,
            "start",
          );
          generatedCount += 1;
        } catch (reason) {
          failures.push(
            `${slot.anchor_block_id}：${reason instanceof Error ? reason.message : "生成失败"}`,
          );
        }
      }
      await refreshImageReview(plan.id);
      if (generatedCount) {
        setNotice(
          `已依次生成 ${generatedCount} 张候选，工作台将从第一张大图开始连续审核。`,
        );
      }
      if (failures.length) {
        setError(`有 ${failures.length} 张未生成：${failures.join("；")}`);
      }
    } finally {
      setImageBusy("");
    }
  }

  async function handleImageFallback(plan: VisualPlan, slot: ImageSlotReview) {
    const key = `${slot.image_slot_id}:fallback`;
    setImageBusy(key);
    setError("");
    setNotice("");
    try {
      await generateImageCandidate(
        taskId,
        plan.id,
        slot.image_slot_id,
        slot.state.image_revision,
        "fallback",
      );
      await refreshImageReview(plan.id);
      setFocusSlotByPlan((current) => ({ ...current, [plan.id]: slot.image_slot_id }));
      setNotice("已生成不调用模型的确定性保底信息图，可直接核对原文。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成保底信息图失败");
    } finally {
      setImageBusy("");
    }
  }

  async function handleImageAccept(
    plan: VisualPlan,
    slot: ImageSlotReview,
    candidate: ImageCandidate,
    textVerified: boolean,
  ) {
    setImageBusy(`${slot.image_slot_id}:accept`);
    setError("");
    setNotice("");
    try {
      await acceptImageCandidate(
        taskId,
        plan.id,
        slot.image_slot_id,
        candidate.id,
        slot.state.image_revision,
        textVerified,
      );
      setFocusSlotByPlan((current) => ({ ...current, [plan.id]: slot.image_slot_id }));
      await refreshImageReview(plan.id);
      setNotice("图片已采用，预览已定位到对应插入位置。 ");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "采用图片失败");
    } finally {
      setImageBusy("");
    }
  }

  async function handleImageSkip(plan: VisualPlan, slot: ImageSlotReview) {
    setImageBusy(`${slot.image_slot_id}:skip`);
    setError("");
    setNotice("");
    try {
      await skipImageSlot(taskId, plan.id, slot.image_slot_id, slot.state.image_revision);
      setFocusSlotByPlan((current) => ({ ...current, [plan.id]: slot.image_slot_id }));
      await refreshImageReview(plan.id);
      setNotice("已跳过这个图片槽；图片不是发布阻断项。 ");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "跳过图片槽失败");
    } finally {
      setImageBusy("");
    }
  }

  async function handleImageReplace(plan: VisualPlan, slot: ImageSlotReview, file: File) {
    setImageBusy(`${slot.image_slot_id}:replace`);
    setError("");
    setNotice("");
    try {
      await replaceImageSlot(taskId, plan.id, slot.image_slot_id, slot.state.image_revision, file);
      setFocusSlotByPlan((current) => ({ ...current, [plan.id]: slot.image_slot_id }));
      await refreshImageReview(plan.id);
      setNotice("人工图片已替换并自动采用，预览已更新。 ");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传替换图片失败");
    } finally {
      setImageBusy("");
    }
  }

  async function handleCoverGenerate(plan: VisualPlan) {
    if (!detail) return;
    setCoverBusy("generate");
    setError("");
    try {
      setCoverReview(await generateCoverCandidate(detail.task, plan.id));
      setNotice("封面候选已根据全文编辑简报生成，并自动裁切为 1080×864。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成封面候选失败");
    } finally {
      setCoverBusy("");
    }
  }

  async function handleCoverReuse(plan: VisualPlan, source: CoverReuseSource) {
    if (!detail) return;
    setCoverBusy(`reuse:${source.source_id}`);
    setError("");
    try {
      setCoverReview(await reuseCoverCandidate(detail.task, plan.id, source.source_type, source.source_id));
      setNotice("正文图片已复制为独立封面候选，正文原图没有被修改。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "复用正文图片失败");
    } finally {
      setCoverBusy("");
    }
  }

  async function handleCoverSelect(plan: VisualPlan, candidate: CoverCandidate) {
    if (!detail) return;
    setCoverBusy(`select:${candidate.id}`);
    setError("");
    try {
      await selectCoverCandidate(detail.task, plan.id, candidate.id);
      await load();
      setNotice("封面已进入受控发布资产，发布检查已同步更新。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "采用封面失败");
    } finally {
      setCoverBusy("");
    }
  }

  async function handleCoverUpload(file: File) {
    if (!detail) return;
    const finding = detail.input_summary.preflight_report?.findings.find((item) =>
      ["missing_cover", "placeholder_cover", "cover_requires_import"].includes(item.code),
    );
    if (!finding) {
      setError("当前任务没有可替换的封面预检项");
      return;
    }
    setCoverBusy("upload");
    setError("");
    try {
      await replacePreflightAsset(detail.task, finding.code, finding.block_id, file);
      await load();
      setNotice("人工封面已上传并进入受控发布资产。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传封面失败");
    } finally {
      setCoverBusy("");
    }
  }

  async function handlePreflightAcknowledge(finding: PreflightFinding) {
    if (!detail) return;
    const key = `${finding.code}:${finding.block_id ?? "root"}`;
    setPreflightBusy(key);
    setError("");
    setNotice("");
    try {
      const nextDetail = await acknowledgePreflightFinding(detail.task, finding.code, finding.block_id);
      setDetail(nextDetail);
      setNotice("已记录知情确认；原始 Markdown 和归一化稿均未被改写。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "记录预检确认失败");
    } finally {
      setPreflightBusy("");
    }
  }

  async function handlePreflightAssetReplace(finding: PreflightFinding, file: File) {
    if (!detail) return;
    const key = `${finding.code}:${finding.block_id ?? "root"}`;
    setPreflightBusy(key);
    setError("");
    setNotice("");
    try {
      const nextDetail = await replacePreflightAsset(
        detail.task,
        finding.code,
        finding.block_id,
        file,
      );
      setDetail(nextDetail);
      setSourceAssetRefreshToken((current) => current + 1);
      const plan = planList?.plans[activeMobilePlan];
      if (finding.block_id && plan) {
        setFocusSlotByPlan((current) => ({ ...current, [plan.id]: finding.block_id! }));
      }
      setNotice(
        finding.block_id
          ? "原稿图片已替换，预览与草稿门禁状态已同步更新。"
          : "封面图已替换，草稿门禁状态已同步更新。",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "上传替换图片失败");
    } finally {
      setPreflightBusy("");
    }
  }

  async function handleGeneratePlans() {
    if (!detail) return;
    setPlanningBusy(true);
    setError("");
    setNotice("");
    try {
      await generatePlans(detail.task);
      await load();
      setNotice("预检门禁已通过，双方案已生成。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成视觉方案失败");
    } finally {
      setPlanningBusy(false);
    }
  }

  async function handlePublicationAutosave(metadata: PublicationMetadata) {
    await savePublicationDraft(taskId, metadata);
  }

  async function handleFreezePublication(metadata: PublicationMetadata) {
    if (!detail) return;
    setPublicationBusy("freeze");
    setError("");
    setNotice("");
    try {
      await savePublicationDraft(taskId, metadata);
      const frozen = await freezePublication(detail.task, metadata);
      if (wenyanPublisher?.ready) {
        setPublicationBusy("publish");
        const result = await createWenyanDraft(frozen.task, frozen.revision);
        await load();
        if (result.operation.status === "succeeded") {
          setNotice("最终版本已保存，并创建微信公众号草稿。请到公众号后台完成最终审核。");
        } else if (result.operation.status === "unknown") {
          setError("最终版本已保存，但草稿创建结果未知。请先到公众号草稿箱核对，不要重复点击。");
        } else {
          setError(result.operation.last_error?.message ?? "最终版本已保存，但微信公众号草稿创建失败");
        }
      } else {
        await load();
        setNotice("最终视觉版本已保存。当前未配置微信发布器，可以复制正文或下载交付包。");
      }
      window.requestAnimationFrame(() => document.getElementById("publication-console")?.scrollIntoView({ block: "start" }));
    } catch (reason) {
      await load().catch(() => undefined);
      setError(reason instanceof Error ? reason.message : "保存最终版本失败");
    } finally {
      setPublicationBusy("");
    }
  }

  async function handlePublishToWechat(revision: PublicationRevision) {
    if (!detail) return;
    setPublicationBusy("publish");
    setError("");
    setNotice("");
    try {
      const result = await createWenyanDraft(detail.task, revision);
      await load();
      if (result.operation.status === "succeeded") {
        setNotice("微信公众号草稿已创建，请到后台完成最终审核和发布。");
      } else if (result.operation.status === "unknown") {
        setError("发布结果未知，请先到公众号草稿箱核对，不要重复点击。");
      } else {
        setError(result.operation.last_error?.message ?? "微信公众号草稿创建失败");
      }
    } catch (reason) {
      await load().catch(() => undefined);
      setError(reason instanceof Error ? reason.message : "微信公众号草稿创建失败");
    } finally {
      setPublicationBusy("");
    }
  }

  async function handleCopyPublication(revision: PublicationRevision) {
    setPublicationBusy("copy");
    setError("");
    setNotice("");
    try {
      const payload = await getClipboardPayload(revision.id);
      if (navigator.clipboard.write && typeof ClipboardItem !== "undefined") {
        await navigator.clipboard.write([
          new ClipboardItem({
            "text/html": new Blob([payload.html], { type: "text/html" }),
            "text/plain": new Blob([payload.text], { type: "text/plain" }),
          }),
        ]);
        setNotice("富文本正文已复制。粘贴到公众号后请保存、重新打开并检查图片和手机预览。");
      } else {
        await navigator.clipboard.writeText(payload.text);
        setNotice("当前浏览器只支持复制纯文本，图片和样式需要在公众号后台补充。");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "复制正文失败");
    } finally {
      setPublicationBusy("");
    }
  }

  async function handleRetryWenyanDraft(operation: DraftOperation) {
    if (!detail) return;
    setPublicationBusy("retry");
    setError("");
    setNotice("");
    try {
      const result = await retryWenyanDraft(detail.task, operation);
      await load();
      if (result.operation.status === "succeeded") {
        setNotice("微信公众号草稿已创建，请到后台完成最终审核和发布。");
      } else if (result.operation.status === "unknown") {
        setError("重试结果未知，请先到公众号草稿箱核对，不要再次重试。");
      } else {
        setError(result.operation.last_error?.message ?? "微信公众号草稿重试失败");
      }
    } catch (reason) {
      await load().catch(() => undefined);
      setError(reason instanceof Error ? reason.message : "微信公众号草稿重试失败");
    } finally {
      setPublicationBusy("");
    }
  }

  async function handleContinueEditing(revision: PublicationRevision) {
    if (!detail) return;
    setPublicationBusy("continue");
    setError("");
    setNotice("");
    try {
      await continueEditingPublication(detail.task, revision.id);
      await load();
      setNotice("旧冻结版本已保留并失效；现在可以继续修改工作稿。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "恢复编辑失败");
    } finally {
      setPublicationBusy("");
    }
  }

  function handleFindingLocate(blockId: string) {
    const plan = planList?.plans[activeMobilePlan];
    if (!plan) return;
    setFocusSlotByPlan((current) => ({ ...current, [plan.id]: blockId }));
    window.requestAnimationFrame(() => {
      document.getElementById(`preview-${plan.id}`)?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    });
  }

  function focusedPreviewUrl(plan: VisualPlan) {
    const url = absoluteApiUrl(plan.preview_url);
    const slotId = focusSlotByPlan[plan.id];
    const refreshQuery = `?content_revision=${imageRefreshToken + sourceAssetRefreshToken}`;
    return slotId ? `${url}${refreshQuery}#${slotId}` : `${url}${refreshQuery}`;
  }

  function enterWorkbench(tab: "components" | "images" | "cover") {
    setActiveEditorTab(tab);
    window.requestAnimationFrame(() => {
      document.getElementById("editor-workbench")?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    });
  }

  if (loading) {
    return <main className="review-loading" role="status">正在装订两份预览…</main>;
  }

  if (error && !detail) {
    return <main className="review-loading"><p role="alert">{error}</p><Link href="/">返回任务台</Link></main>;
  }

  if (!detail) return null;

  const activePlan = planList?.plans[activeMobilePlan] ?? null;
  const activePlanSelected = Boolean(activePlan && detail.task.selected_plan_id === activePlan.id);
  const activeRevision = publicationRevisions.find(
    (item) => item.id === detail.task.active_publication_revision_id,
  ) ?? null;
  const activeDraftOperation = draftOperations.find(
    (item) => item.revision_id === activeRevision?.id && item.status !== "superseded",
  ) ?? null;
  const publicationVisible = Boolean(detail.task.selected_plan_id || activeRevision);

  return (
    <main className="review-page">
      <header className="review-topbar">
        <Link className="back-link" href="/"><BackIcon />任务台</Link>
        <div className="review-title">
          <p>VISUAL REVIEW / {taskId.slice(0, 8).toUpperCase()}</p>
          <h1>{detail.task.title}</h1>
        </div>
        <Link className="review-settings-link" href="/settings">图片设置</Link>
        <StatusPill status={detail.task.status} />
      </header>

      <section className="progress-strip" aria-label="方案生成进度">
        {detail.progress.map((step, index) => (
          <div className={`progress-step progress-${step.status}`} key={step.key}>
            <span>{step.status === "succeeded" ? <CheckIcon /> : String(index + 1).padStart(2, "0")}</span>
            <div><strong>{step.label}</strong><small>{step.status === "succeeded" ? "完成" : step.status === "running" ? "进行中" : "等待"}</small></div>
          </div>
        ))}
      </section>

      {detail.input_summary.preflight_report && !activeRevision ? (
        <PreflightPanel
          busyFinding={preflightBusy}
          hasPreview={Boolean(activePlan)}
          imageReferenceCount={detail.input_summary.image_reference_count}
          onAcknowledge={handlePreflightAcknowledge}
          onGeneratePlans={handleGeneratePlans}
          onLocate={handleFindingLocate}
          onReplaceAsset={handlePreflightAssetReplace}
          planningBusy={planningBusy}
          report={detail.input_summary.preflight_report}
          sectionCount={detail.input_summary.section_count}
          taskStatus={detail.task.status}
          titleSource={detail.input_summary.title_source}
        />
      ) : detail.task.status === "created" ? (
        <section className="not-ready-state legacy-preflight-state">
          <p>这个旧任务创建于 Preflight 上线之前，没有可审计的预检报告。</p>
          <Link href="/">重新上传 Markdown 并创建新任务</Link>
        </section>
      ) : null}

      {planList && !activeRevision ? (
        <>
          <section className="plan-switcher-shell">
            <div className="plan-switcher-heading">
              <div>
                <span>PLAN SWITCHBOARD</span>
                <strong>先切换查看方案，再在同一工作台完成修改</strong>
              </div>
              <p>
                {planList.comparison.shared_structure
                  ? "共享 1 份智能结构 · 2 套视觉系统"
                  : `两套方案结构差异 ${planList.comparison.structural_difference_count} 项`}
              </p>
            </div>
            <div className="plan-switcher" role="tablist" aria-label="切换视觉方案">
              {planList.plans.map((plan, index) => {
                const selected = detail.task.selected_plan_id === plan.id;
                return (
                  <button
                    aria-selected={activeMobilePlan === index}
                    className={`${activeMobilePlan === index ? "active" : ""} ${selected ? "selected" : ""}`}
                    key={plan.id}
                    onClick={() => {
                      setActiveMobilePlan(index);
                      setActiveEditorTab("components");
                    }}
                    role="tab"
                    type="button"
                  >
                    <span>方案 {String.fromCharCode(65 + index)}</span>
                    <strong>{plan.plan_name}</strong>
                    <small>{styleLabels[plan.style_mode] ?? plan.style_mode}</small>
                    {selected ? <i><CheckIcon />当前已选</i> : null}
                  </button>
                );
              })}
            </div>
          </section>

          {publicationVisible ? (
            <div id="publication-console">
              <PublicationPanel
                busy={publicationBusy}
                bundleUrl={null}
                operation={activeDraftOperation}
                publisher={wenyanPublisher}
                readiness={publicationReadiness}
                revision={activeRevision}
                task={detail.task}
                onAutosave={handlePublicationAutosave}
                onContinueEditing={() => Promise.resolve()}
                onCopy={() => Promise.resolve()}
                onFreeze={handleFreezePublication}
                onPublish={() => Promise.resolve()}
                onRetry={() => Promise.resolve()}
              />
            </div>
          ) : null}

          {activePlan ? (
            <section className="editor-workbench" id="editor-workbench" aria-label={`${activePlan.plan_name} 编辑工作台`}>
              <aside className="editor-controls">
                <div className="active-plan-summary">
                  <div className="plan-kicker-row">
                    <span>方案 {String.fromCharCode(65 + activeMobilePlan)}</span>
                    <span>{styleLabels[activePlan.style_mode] ?? activePlan.style_mode}</span>
                  </div>
                  <h2>{activePlan.plan_name}</h2>
                  <p>{activePlan.summary}</p>
                  <button
                    className={activePlanSelected ? "selected-button" : "select-button"}
                    disabled={activePlanSelected || Boolean(selecting)}
                    onClick={() => handleSelection(activePlan)}
                    type="button"
                  >
                    {activePlanSelected ? <><CheckIcon />当前已选方案</> : selecting === activePlan.id ? "保存中…" : "选定此方案"}
                  </button>
                </div>

                <div className="workbench-mode-tabs" role="tablist" aria-label="切换编辑内容">
                  <button
                    aria-selected={activeEditorTab === "components"}
                    className={activeEditorTab === "components" ? "active" : ""}
                    onClick={() => enterWorkbench("components")}
                    role="tab"
                    type="button"
                  >
                    <span>{String(activePlan.slots.length).padStart(2, "0")}</span>
                    组件微调（可选）
                  </button>
                  <button
                    aria-selected={activeEditorTab === "images"}
                    className={activeEditorTab === "images" ? "active" : ""}
                    onClick={() => enterWorkbench("images")}
                    role="tab"
                    type="button"
                  >
                    <span>{String(activePlan.image_slots.length).padStart(2, "0")}</span>
                    配图审核
                  </button>
                  <button
                    aria-selected={activeEditorTab === "cover"}
                    className={activeEditorTab === "cover" ? "active" : ""}
                    onClick={() => enterWorkbench("cover")}
                    role="tab"
                    type="button"
                  >
                    <span>{coverReview?.selected_cover ? "01" : "00"}</span>
                    文章封面
                  </button>
                </div>

                <div className="editor-control-scroll">
                  {activeEditorTab === "components" ? (
                    <section className="component-editor workbench-component-editor" aria-label={`${activePlan.plan_name} 局部组件换型`}>
                      <header className="component-editor-header">
                        <div>
                          <span>COMPONENT DECISIONS</span>
                          <h3>局部组件 · 修订 R{String(activePlan.revision).padStart(2, "0")}</h3>
                          <small>左侧切换，右侧文章内部自动定位</small>
                        </div>
                        {(activePlan.undo_stack ?? []).length ? (
                          <button
                            disabled={Boolean(editingSlot) || Boolean(restoring)}
                            onClick={() => handleRestore(activePlan)}
                            type="button"
                          >{restoring === activePlan.id ? "撤回中…" : "撤回上次换型"}</button>
                        ) : <span className="revision-base">初始方案</span>}
                      </header>
                      {activePlan.slots.length ? (
                        <div className="component-decision-list">
                          {activePlan.slots.map((slot, slotIndex) => {
                            const key = `${activePlan.id}:${slot.slot_id}`;
                            return (
                              <div className="component-decision" key={slot.slot_id}>
                                <div className="component-decision-copy">
                                  <span className="component-decision-index">{String(slotIndex + 1).padStart(2, "0")}</span>
                                  <div>
                                    <strong>{slot.component_label}</strong>
                                    <p>{slot.selection_reason}</p>
                                    {historyMessage(slot) ? <small>{historyMessage(slot)}</small> : null}
                                  </div>
                                </div>
                                <div className="variant-choice" role="group" aria-label={`${slot.component_label}变体`}>
                                  {slot.variant_options.map((option) => (
                                    <button
                                      aria-pressed={slot.variant === option.value}
                                      className={slot.variant === option.value ? "active" : ""}
                                      disabled={Boolean(editingSlot) || Boolean(restoring)}
                                      key={option.value}
                                      onClick={() => handleVariantSwitch(activePlan, slot, option.value)}
                                      type="button"
                                    >
                                      <span>{option.marker}</span>
                                      {editingSlot === key && slot.variant !== option.value ? "切换中…" : option.label}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : <p className="component-empty">当前文章没有满足语义条件的强组件，保留普通正文。</p>}
                    </section>
                  ) : !activePlanSelected ? (
                    <div className="image-locked-panel">
                      <span>EDITORIAL DESK LOCKED</span>
                      <h3>先选定方案，再处理{activeEditorTab === "cover" ? "封面" : "配图"}</h3>
                      <p>图片与封面候选只属于最终采用的方案，避免为两套方案重复消耗额度。</p>
                      <button disabled={Boolean(selecting)} onClick={() => handleSelection(activePlan)} type="button">
                        {selecting === activePlan.id ? "选定中…" : `选定当前方案并进入${activeEditorTab === "cover" ? "封面" : "配图"}`}
                      </button>
                    </div>
                  ) : activeEditorTab === "images" ? (
                    <ImageReviewPanel
                      busy={imageBusy}
                      onAccept={(slot, candidate, textVerified) =>
                        handleImageAccept(activePlan, slot, candidate, textVerified)
                      }
                      onFallback={(slot) => handleImageFallback(activePlan, slot)}
                      onGenerate={(slot) => handleImageGenerate(activePlan, slot)}
                      onGenerateAll={() => handleImageGenerateAll(activePlan)}
                      onReplace={(slot, file) => handleImageReplace(activePlan, slot, file)}
                      onSkip={(slot) => handleImageSkip(activePlan, slot)}
                      plan={activePlan}
                      review={imageReview}
                    />
                  ) : (
                    <CoverReviewPanel
                      busy={coverBusy}
                      onGenerate={() => handleCoverGenerate(activePlan)}
                      onReuse={(source) => handleCoverReuse(activePlan, source)}
                      onSelect={(candidate) => handleCoverSelect(activePlan, candidate)}
                      onUpload={handleCoverUpload}
                      review={coverReview}
                    />
                  )}
                </div>
              </aside>

              <section className="preview-workspace" id={`preview-${activePlan.id}`}>
                <header className="preview-workspace-header">
                  <div>
                    <span>LIVE ARTICLE / 390PX</span>
                    <strong>右侧文章预览</strong>
                  </div>
                  <p>操作时页面不跳转，仅文章内部定位变化位置</p>
                </header>
                <div className="phone-stage">
                  <div className="phone-label"><span>390</span><i />MOBILE CONTENT WIDTH</div>
                  <iframe
                    className="preview-frame"
                    src={focusedPreviewUrl(activePlan)}
                    title={`${activePlan.plan_name} 公众号移动端预览`}
                  />
                </div>
              </section>
            </section>
          ) : null}
        </>
      ) : !activeRevision && !["created", "plan_selected"].includes(detail.task.status) ? (
        <section className="not-ready-state">
          <p>方案还没有准备好。</p>
          <button type="button" onClick={() => load()}>刷新状态</button>
        </section>
      ) : null}

      {activeRevision ? (
        <div id="publication-console">
          <PublicationPanel
            busy={publicationBusy}
            bundleUrl={publicationBundleUrl(activeRevision.id)}
            operation={activeDraftOperation}
            publisher={wenyanPublisher}
            readiness={publicationReadiness}
            revision={activeRevision}
            task={detail.task}
            onAutosave={handlePublicationAutosave}
            onContinueEditing={() => activeRevision ? handleContinueEditing(activeRevision) : Promise.resolve()}
            onCopy={() => handleCopyPublication(activeRevision)}
            onFreeze={handleFreezePublication}
            onPublish={() => handlePublishToWechat(activeRevision)}
            onRetry={() => activeDraftOperation ? handleRetryWenyanDraft(activeDraftOperation) : Promise.resolve()}
          />
        </div>
      ) : null}

      {notice ? <div className="toast toast-success" role="status">{notice}</div> : null}
      {error ? <div className="toast toast-error" role="alert">{error}</div> : null}
    </main>
  );
}
