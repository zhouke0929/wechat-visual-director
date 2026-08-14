"use client";

import Link, { useRouteParam } from "@/lib/router";
import { useCallback, useEffect, useRef, useState } from "react";
import { BackIcon } from "@/components/icons";
import { ImageReviewPanel } from "@/components/image-review-panel";
import { CoverReviewPanel } from "@/components/cover-review-panel";
import { PreflightPanel } from "@/components/preflight-panel";
import { PublicationPanel } from "@/components/publication-panel";
import { ResilientPreviewFrame } from "@/components/resilient-preview-frame";
import { StatusPill } from "@/components/status-pill";
import {
  absoluteApiUrl,
  assertRuntimeCompatibility,
  acknowledgePreflightFinding,
  acceptImageCandidate,
  continueEditingPublication,
  cropCoverCandidate,
  createWechatDraft,
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
  getWechatPublisherStatus,
  retryWechatDraft,
  resolveUnknownDraft,
  publicationBundleUrl,
  replacePreflightAsset,
  replaceImageSlot,
  reuseCoverCandidate,
  savePublicationDraft,
  selectPlan,
  selectCoverCandidate,
  skipImageSlot,
  switchPlanTheme,
  undoPlanChange,
  useThemeFallbackCover,
} from "@/lib/api";
import type {
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
  WechatPublisherStatus,
} from "@/lib/types";

const styleLabels: Record<string, string> = {
  data_decision: "DATA DECISION",
  editorial_insight: "EDITORIAL INSIGHT",
  lively_science: "LIVELY SCIENCE",
  light_reading: "轻盈阅读",
  editorial_contrast: "编辑对比",
  warm_humanist: "温暖人文",
  structured_grid: "理性网格",
  youth_campus: "青春校园",
  future_tech: "未来科技",
  oriental_archive: "新中式雅集",
  vintage_press: "复古报刊",
  pop_poster: "波普海报",
  natural_atlas: "自然图鉴",
  business_review: "商业画报",
  cinematic_story: "电影叙事",
};

function plannerSourceLabel(plan: VisualPlan): string {
  const metadata = plan.planner_metadata;
  if (!metadata) return "规划来源：历史任务未记录";
  if (metadata.fallback_used && (metadata.provider === "host_agent" || metadata.mode === "host_agent")) {
    return "规划来源：宿主规划无效，已使用本地规则兜底";
  }
  if (metadata.fallback_used) return "规划来源：本地规则兜底";
  if (metadata.provider === "host_agent" || metadata.mode === "host_agent") {
    return "规划来源：宿主 Agent 语义规划";
  }
  return "规划来源：本地规则（未调用文本模型）";
}

export default function TaskReviewPage() {
  const taskId = useRouteParam("tasks");
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [planList, setPlanList] = useState<PlanList | null>(null);
  const [activeEditorTab, setActiveEditorTab] = useState<"images" | "cover">("images");
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState("");
  const [switchingTheme, setSwitchingTheme] = useState("");
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
  const [wechatPublisher, setWechatPublisher] = useState<WechatPublisherStatus | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [workspaceWarning, setWorkspaceWarning] = useState("");
  const initialWorkspaceResolved = useRef(false);
  const imageWorkspaceRequestRef = useRef(0);

  const loadSupplementalWorkspace = useCallback(async (nextDetail: TaskDetail) => {
    const warnings: string[] = [];
    try {
      setWechatPublisher(await getWechatPublisherStatus());
    } catch {
      setWechatPublisher(null);
      warnings.push("公众号草稿发布状态暂时不可用");
    }

    const selectedPlanId = nextDetail.task.selected_plan_id;
    if (selectedPlanId) {
      const requestId = ++imageWorkspaceRequestRef.current;
      if (!initialWorkspaceResolved.current) {
        setActiveEditorTab("images");
        initialWorkspaceResolved.current = true;
      }
      try {
        const nextImageReview = await getImageSlots(taskId, selectedPlanId);
        const nextCoverReview = await getCoverWorkspace(taskId, selectedPlanId);
        if (requestId === imageWorkspaceRequestRef.current) {
          setImageReview(nextImageReview);
          setCoverReview(nextCoverReview);
        }
      } catch {
        if (requestId === imageWorkspaceRequestRef.current) {
          setImageReview(null);
          setCoverReview(null);
          warnings.push("图片与封面工作区暂时未加载，可稍后重试");
        }
      }
    } else {
      imageWorkspaceRequestRef.current += 1;
      setImageReview(null);
      setCoverReview(null);
    }

    if (selectedPlanId || nextDetail.task.active_publication_revision_id) {
      try {
        setPublicationReadiness(await getPublicationReadiness(taskId));
        setPublicationRevisions(await getPublicationRevisions(taskId));
        setDraftOperations(await getDraftOperations(taskId));
      } catch {
        setPublicationReadiness(null);
        setPublicationRevisions([]);
        setDraftOperations([]);
        warnings.push("交付与草稿状态暂时未加载，可稍后重试");
      }
    } else {
      setPublicationReadiness(null);
      setPublicationRevisions([]);
      setDraftOperations([]);
    }
    setWorkspaceWarning(warnings.join("；"));
  }, [taskId]);

  const load = useCallback(async () => {
    await assertRuntimeCompatibility();
    const nextDetail = await getTask(taskId);
    setDetail(nextDetail);
    if (["plans_ready", "plan_selected"].includes(nextDetail.task.status)) {
      setPlanList(await getPlans(taskId));
    } else {
      setPlanList(null);
    }
    void loadSupplementalWorkspace(nextDetail);
  }, [loadSupplementalWorkspace, taskId]);

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

  async function handleThemeSwitch(plan: VisualPlan, visualSystem: string) {
    if (visualSystem === (plan.visual_system ?? plan.style_mode)) return;
    setSwitchingTheme(visualSystem);
    setError("");
    setNotice("");
    try {
      const result = await switchPlanTheme(taskId, plan.id, visualSystem, plan.revision);
      setPlanList((current) => current ? {
        ...current,
        plans: current.plans.map((item) => item.id === result.plan.id ? result.plan : item),
      } : current);
      if (detail?.task.selected_plan_id === plan.id) {
        await refreshImageReview(plan.id);
      }
      setFocusSlotByPlan((current) => ({ ...current, [plan.id]: "" }));
      setNotice(`已切换为「${styleLabels[visualSystem] ?? visualSystem}」；正文、结构和已有图片均已保留，新生成图片会采用当前主题。`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "切换主题失败");
    } finally {
      setSwitchingTheme("");
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
      if (detail?.task.selected_plan_id === plan.id) {
        await refreshImageReview(plan.id);
      }
      setNotice("已回到上一个主题版本；不会在两个修订间反复切换。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "恢复修订失败");
    } finally {
      setRestoring("");
    }
  }

  async function refreshImageReview(planId: string) {
    const requestId = ++imageWorkspaceRequestRef.current;
    const nextImageReview = await getImageSlots(taskId, planId);
    const nextCoverReview = await getCoverWorkspace(taskId, planId);
    if (requestId !== imageWorkspaceRequestRef.current) return;
    setImageReview(nextImageReview);
    setCoverReview(nextCoverReview);
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

  async function handleCoverFallback(plan: VisualPlan) {
    if (!detail) return;
    setCoverBusy("fallback");
    setError("");
    try {
      setCoverReview(await useThemeFallbackCover(detail.task, plan.id));
      await load();
      setNotice("已跳过生图并采用本地主题保底封面，可继续进入草稿交付。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "使用主题保底封面失败");
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

  async function handleCoverCrop(
    plan: VisualPlan,
    candidate: CoverCandidate,
    transform: { scale: number; offsetX: number; offsetY: number },
  ) {
    if (!detail) return;
    setCoverBusy(`crop:${candidate.id}`);
    setError("");
    try {
      setCoverReview(await cropCoverCandidate(detail.task, plan.id, candidate.id, transform));
      await load();
      setNotice("裁切后的封面已保存为新资产并自动采用，原始候选仍然保留。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存封面裁切失败");
      throw reason;
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
      const plan = planList?.plans.find((item) => item.id === nextDetail.task.selected_plan_id)
        ?? planList?.plans[0];
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
      setNotice("预检门禁已通过，推荐稿已生成并自动选中。");
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
      if (wechatPublisher?.ready) {
        setPublicationBusy("publish");
        const result = await createWechatDraft(frozen.task, frozen.revision);
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
      const result = await createWechatDraft(detail.task, revision);
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

  async function handleRetryWechatDraft(operation: DraftOperation) {
    if (!detail) return;
    setPublicationBusy("retry");
    setError("");
    setNotice("");
    try {
      const result = await retryWechatDraft(detail.task, operation);
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

  async function handleResolveUnknownDraft(
    operation: DraftOperation,
    outcome: "confirmed_succeeded" | "confirmed_not_created",
  ) {
    if (!detail) return;
    const confirmed = window.confirm(
      outcome === "confirmed_succeeded"
        ? "请确认：你已经在微信公众号后台找到这篇草稿。确认后系统会把本次交付记为完成。"
        : "请确认：你已经在微信公众号后台搜索并确认没有这篇草稿。确认后会解除锁定，并允许重新保存。",
    );
    if (!confirmed) return;
    setPublicationBusy("resolve-unknown");
    setError("");
    setNotice("");
    try {
      await resolveUnknownDraft(detail.task, operation, outcome);
      await load();
      setNotice(
        outcome === "confirmed_succeeded"
          ? "已记录后台核对结果：草稿存在，本次交付已完成。"
          : "已记录后台核对结果：未发现草稿，锁定已解除，现在可以重新保存。",
      );
    } catch (reason) {
      await load().catch(() => undefined);
      setError(reason instanceof Error ? reason.message : "记录后台核对结果失败");
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
    const plan = planList?.plans.find((item) => item.id === detail?.task.selected_plan_id) ?? planList?.plans[0];
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

  function enterWorkbench(tab: "images" | "cover") {
    setActiveEditorTab(tab);
    window.requestAnimationFrame(() => {
      document.getElementById("editor-workbench")?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "start",
      });
    });
  }

  if (loading) {
    return <main className="review-loading" role="status">正在装订推荐稿…</main>;
  }

  if (error && !detail) {
    return <main className="review-loading"><p role="alert">{error}</p><Link href="/">返回任务台</Link></main>;
  }

  if (!detail) return null;

  const activePlan = planList?.plans.find((item) => item.id === detail.task.selected_plan_id)
    ?? planList?.plans[0]
    ?? null;
  const activePlanSelected = Boolean(activePlan && detail.task.selected_plan_id === activePlan.id);
  const activeRevision = publicationRevisions.find(
    (item) => item.id === detail.task.active_publication_revision_id,
  ) ?? null;
  const activeDraftOperation = draftOperations.find(
    (item) => item.revision_id === activeRevision?.id && item.status !== "superseded",
  ) ?? null;
  const publicationVisible = Boolean(detail.task.selected_plan_id || activeRevision);
  const preflightReport = detail.input_summary.preflight_report;
  const unresolvedManualPreflightCount = preflightReport?.findings.filter(
    (finding) => !finding.resolved_at && finding.resolution_policy !== "REPLACE_ASSET",
  ).length ?? 0;
  const showPreflight = Boolean(
    preflightReport
    && !activeRevision
    && (!activePlan || unresolvedManualPreflightCount > 0),
  );

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

      {showPreflight && preflightReport ? (
        <PreflightPanel
          busyFinding={preflightBusy}
          hasPreview={Boolean(activePlan)}
          imageReferenceCount={detail.input_summary.image_reference_count}
          onAcknowledge={handlePreflightAcknowledge}
          onGeneratePlans={handleGeneratePlans}
          onLocate={handleFindingLocate}
          onReplaceAsset={handlePreflightAssetReplace}
          planningBusy={planningBusy}
          report={preflightReport}
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
          {publicationVisible ? (
            <div id="publication-console">
              <PublicationPanel
                busy={publicationBusy}
                bundleUrl={null}
                operation={activeDraftOperation}
                publisher={wechatPublisher}
                readiness={publicationReadiness}
                revision={activeRevision}
                task={detail.task}
                onAutosave={handlePublicationAutosave}
                onContinueEditing={() => Promise.resolve()}
                onCopy={() => Promise.resolve()}
                onFreeze={handleFreezePublication}
                onPublish={() => Promise.resolve()}
                onRetry={() => Promise.resolve()}
                onResolveUnknown={() => Promise.resolve()}
              />
            </div>
          ) : null}

          {activePlan ? (
            <section className="editor-workbench" id="editor-workbench" aria-label={`${activePlan.plan_name} 编辑工作台`}>
              <aside className="editor-controls">
                <div className="active-plan-summary">
                  <div className="plan-kicker-row">
                    <span>推荐主题</span>
                    <span>{styleLabels[activePlan.style_mode] ?? activePlan.style_mode}</span>
                  </div>
                  <h2>{activePlan.plan_name}</h2>
                  <p>{activePlan.summary}</p>
                  <small className="planner-source-note">{plannerSourceLabel(activePlan)}</small>
                  <div className="theme-switch-controls">
                    <label>
                      <span>整体换主题</span>
                      <select
                        aria-label="选择整篇文章主题"
                        disabled={Boolean(switchingTheme) || Boolean(restoring)}
                        onChange={(event) => handleThemeSwitch(activePlan, event.target.value)}
                        value={activePlan.visual_system ?? activePlan.style_mode}
                      >
                        {(activePlan.visual_system_metadata?.available_visual_systems ?? [
                          { value: "light_reading", label: "轻盈阅读", description: "", recent_use_count: 0 },
                          { value: "warm_humanist", label: "温暖人文", description: "", recent_use_count: 0 },
                          { value: "youth_campus", label: "青春校园", description: "", recent_use_count: 0 },
                          { value: "editorial_contrast", label: "编辑对比", description: "", recent_use_count: 0 },
                          { value: "structured_grid", label: "理性网格", description: "", recent_use_count: 0 },
                          { value: "future_tech", label: "未来科技", description: "", recent_use_count: 0 },
                          { value: "oriental_archive", label: "新中式雅集", description: "", recent_use_count: 0 },
                          { value: "vintage_press", label: "复古报刊", description: "", recent_use_count: 0 },
                          { value: "pop_poster", label: "波普海报", description: "", recent_use_count: 0 },
                          { value: "natural_atlas", label: "自然图鉴", description: "", recent_use_count: 0 },
                          { value: "business_review", label: "商业画报", description: "", recent_use_count: 0 },
                          { value: "cinematic_story", label: "电影叙事", description: "", recent_use_count: 0 },
                        ]).map((theme) => (
                          <option key={theme.value} value={theme.value}>
                            {theme.label}{theme.recent_use_count ? ` · 近五篇 ${theme.recent_use_count} 次` : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      disabled={Boolean(switchingTheme) || Boolean(restoring)}
                      onClick={() => {
                        const themes = activePlan.visual_system_metadata?.available_visual_systems ?? [];
                        const currentIndex = themes.findIndex((item) => item.value === (activePlan.visual_system ?? activePlan.style_mode));
                        const next = themes.length ? themes[(currentIndex + 1) % themes.length] : null;
                        if (next) void handleThemeSwitch(activePlan, next.value);
                      }}
                      type="button"
                    >
                      {switchingTheme ? "换主题中…" : "换一个主题"}
                    </button>
                    {(activePlan.undo_stack ?? []).length ? (
                      <button
                        disabled={Boolean(switchingTheme) || Boolean(restoring)}
                        onClick={() => handleRestore(activePlan)}
                        type="button"
                      >{restoring === activePlan.id ? "回退中…" : "回到上一版"}</button>
                    ) : null}
                  </div>
                  <small className="theme-switch-note">换主题不改正文、图片和文章结构；已有图片始终保留，新生图跟随当前主题，最终冻结后才计入最近五篇。</small>
                  {!activePlanSelected ? (
                    <button
                      className="select-button"
                      disabled={Boolean(selecting)}
                      onClick={() => handleSelection(activePlan)}
                      type="button"
                    >
                      {selecting === activePlan.id ? "保存中…" : "选定这篇旧任务方案"}
                    </button>
                  ) : null}
                </div>

                <div className="workbench-mode-tabs" role="tablist" aria-label="切换编辑内容">
                  <button
                    aria-selected={activeEditorTab === "images"}
                    className={activeEditorTab === "images" ? "active" : ""}
                    onClick={() => enterWorkbench("images")}
                    role="tab"
                    type="button"
                  >
                    <span>01</span>
                    配图审核
                  </button>
                  <button
                    aria-selected={activeEditorTab === "cover"}
                    className={activeEditorTab === "cover" ? "active" : ""}
                    onClick={() => enterWorkbench("cover")}
                    role="tab"
                    type="button"
                  >
                    <span>02</span>
                    文章封面
                  </button>
                </div>

                <div className="editor-control-scroll">
                  {!activePlanSelected ? (
                    <div className="image-locked-panel">
                      <span>EDITORIAL DESK LOCKED</span>
                      <h3>先选定方案，再处理{activeEditorTab === "cover" ? "封面" : "配图"}</h3>
                      <p>这是旧版本遗留的未选方案任务。选定后即可继续处理图片与封面。</p>
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
                      onRestoreTheme={() => handleRestore(activePlan)}
                      onSkip={(slot) => handleImageSkip(activePlan, slot)}
                      plan={activePlan}
                      review={imageReview}
                    />
                  ) : (
                    <CoverReviewPanel
                      busy={coverBusy}
                      onGenerate={() => handleCoverGenerate(activePlan)}
                      onFallback={() => handleCoverFallback(activePlan)}
                      onCrop={(candidate, transform) => handleCoverCrop(activePlan, candidate, transform)}
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
                  <ResilientPreviewFrame
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
            publisher={wechatPublisher}
            readiness={publicationReadiness}
            revision={activeRevision}
            task={detail.task}
            onAutosave={handlePublicationAutosave}
            onContinueEditing={() => activeRevision ? handleContinueEditing(activeRevision) : Promise.resolve()}
            onCopy={() => handleCopyPublication(activeRevision)}
            onFreeze={handleFreezePublication}
            onPublish={() => handlePublishToWechat(activeRevision)}
            onRetry={() => activeDraftOperation ? handleRetryWechatDraft(activeDraftOperation) : Promise.resolve()}
            onResolveUnknown={(outcome) => activeDraftOperation
              ? handleResolveUnknownDraft(activeDraftOperation, outcome)
              : Promise.resolve()}
          />
        </div>
      ) : null}

      {notice ? <div className="toast toast-success" role="status">{notice}</div> : null}
      {workspaceWarning ? <div className="toast toast-warning" role="status">{workspaceWarning}</div> : null}
      {error ? <div className="toast toast-error" role="alert">{error}</div> : null}
    </main>
  );
}
