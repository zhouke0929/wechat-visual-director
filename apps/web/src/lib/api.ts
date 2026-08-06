import type {
  BlindReviewSet,
  BlindReviewSubmission,
  ClipboardPayload,
  CapabilitySettings,
  CoverWorkspace,
  DraftOperation,
  ImageProviderMode,
  ImageProviderSettings,
  ImageSlotList,
  PlanList,
  PublicationMetadata,
  PublicationReadiness,
  PublicationRevision,
  PublicIpProbe,
  SetupTargetMode,
  Task,
  TaskDetail,
  ThemeGalleryItem,
  VisualPlan,
  WechatConnectionProbe,
  WechatPublisherSettings,
  WenyanPublisherStatus,
} from "./types";

// Browser traffic stays on the workbench origin and is forwarded by the
// runtime proxy. This keeps a production build portable across API ports and
// avoids baking a previous machine's API address into the static workbench bundle.
export const API_BASE = "/api/v1";

const API_ORIGIN = "";
const REQUEST_TIMEOUT_MS = 12_000;
const EXPECTED_APPLICATION_VERSION =
  process.env.NEXT_PUBLIC_VISUAL_DIRECTOR_VERSION ?? null;

type RuntimeHealth = {
  status: string;
  application_version?: string;
  image_provider_settings_schema_version?: string;
  capability_settings_schema_version?: string;
};

async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === "AbortError") {
      throw new Error("本地服务响应超时，请运行 doctor --json 检查后重试。");
    }
    throw reason;
  } finally {
    window.clearTimeout(timer);
  }
}

export function absoluteApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${API_ORIGIN}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function getApplicationVersion(): Promise<string> {
  const response = await fetchWithTimeout(`${API_ORIGIN}/health`, { cache: "no-store" });
  const payload = await parseResponse<{ application_version: string }>(response);
  return payload.application_version;
}

export async function assertRuntimeCompatibility(): Promise<RuntimeHealth> {
  const response = await fetchWithTimeout(`${API_ORIGIN}/health`, { cache: "no-store" });
  const payload = await parseResponse<RuntimeHealth>(response);
  const versionMatches =
    !EXPECTED_APPLICATION_VERSION
    || payload.application_version === EXPECTED_APPLICATION_VERSION;
  if (
    !payload.application_version
    || payload.image_provider_settings_schema_version !== "image_provider_settings.v0.2"
    || payload.capability_settings_schema_version !== "capability_settings.v0.1"
    || !versionMatches
  ) {
    throw new Error(
      "检测到旧版或不匹配的核心服务仍占用端口。请关闭旧服务，再通过稳定启动器重新打开工作台。",
    );
  }
  return payload;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error?.message ?? `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export async function listTasks(): Promise<Task[]> {
  const response = await fetch(`${API_BASE}/article-tasks`, { cache: "no-store" });
  const payload = await parseResponse<{ items: Task[] }>(response);
  return payload.items;
}

export async function deleteTasks(taskIds: string[]): Promise<{
  schema_version: "task_batch_delete_result.v0.1";
  deleted_count: number;
  deleted_task_ids: string[];
  missing_task_ids: string[];
  asset_cleanup_warnings: string[];
}> {
  const response = await fetchWithTimeout(`${API_BASE}/article-tasks/batch-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_ids: taskIds }),
  });
  return parseResponse(response);
}

export async function getThemeGallery(): Promise<ThemeGalleryItem[]> {
  const response = await fetch(`${API_BASE}/theme-gallery`, { cache: "no-store" });
  const payload = await parseResponse<{
    schema_version: "theme_gallery.v0.3";
    themes: ThemeGalleryItem[];
  }>(response);
  return payload.themes;
}

export async function getImageProviderSettings(): Promise<ImageProviderSettings> {
  const response = await fetch(`${API_BASE}/settings/image-provider`, { cache: "no-store" });
  const payload = await parseResponse<{ settings: ImageProviderSettings }>(response);
  if (
    payload.settings?.schema_version !== "image_provider_settings.v0.2"
    || !payload.settings.providers?.images_api
    || !payload.settings.providers?.gemini
  ) {
    throw new Error("检测到旧版核心服务仍占用端口。请停止旧服务并重新启动当前版本。");
  }
  return payload.settings;
}

export async function saveImageProviderSettings(payload: {
  mode: ImageProviderMode;
  api_key?: string;
  clear_api_key?: boolean;
  endpoint?: string;
  model?: string;
  protocol?: "openai" | "ark" | "ark_plan" | "extended";
  size?: string;
}): Promise<ImageProviderSettings> {
  const response = await fetch(`${API_BASE}/settings/image-provider`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-Settings-Intent": "local-operator",
    },
    body: JSON.stringify(payload),
  });
  const result = await parseResponse<{ settings: ImageProviderSettings }>(response);
  return result.settings;
}

export async function getCapabilitySettings(): Promise<CapabilitySettings> {
  const response = await fetchWithTimeout(`${API_BASE}/settings/capabilities`, { cache: "no-store" });
  const payload = await parseResponse<{ settings: CapabilitySettings }>(response);
  return payload.settings;
}

export async function saveSetupPreferences(targetMode: SetupTargetMode): Promise<CapabilitySettings> {
  const response = await fetchWithTimeout(`${API_BASE}/settings/setup-preferences`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-Settings-Intent": "local-operator",
    },
    body: JSON.stringify({ target_mode: targetMode }),
  });
  const payload = await parseResponse<{ capability_settings: CapabilitySettings }>(response);
  return payload.capability_settings;
}

export async function getWechatPublisherSettings(): Promise<WechatPublisherSettings> {
  const response = await fetchWithTimeout(`${API_BASE}/settings/wechat-publisher`, { cache: "no-store" });
  const payload = await parseResponse<{ settings: WechatPublisherSettings }>(response);
  return payload.settings;
}

export async function saveWechatPublisherSettings(payload: {
  app_id?: string;
  app_secret?: string;
  clear_credentials?: boolean;
  ip_whitelist_confirmed?: boolean;
}): Promise<WechatPublisherSettings> {
  const response = await fetchWithTimeout(`${API_BASE}/settings/wechat-publisher`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-Settings-Intent": "local-operator",
    },
    body: JSON.stringify(payload),
  });
  const result = await parseResponse<{ settings: WechatPublisherSettings }>(response);
  return result.settings;
}

export async function probeWechatPublisher(): Promise<WechatConnectionProbe> {
  const response = await fetchWithTimeout(`${API_BASE}/settings/wechat-publisher/probe`, {
    method: "POST",
    headers: { "X-Settings-Intent": "local-operator" },
  }, 20_000);
  return parseResponse<WechatConnectionProbe>(response);
}

export async function probePublicIp(): Promise<PublicIpProbe> {
  const response = await fetchWithTimeout(`${API_BASE}/settings/network/public-ip-probe`, {
    method: "POST",
    headers: { "X-Settings-Intent": "local-operator" },
  }, 15_000);
  return parseResponse<PublicIpProbe>(response);
}

export async function createTask(file: File, articleType: string): Promise<Task> {
  const form = new FormData();
  form.append("account_id", "default");
  form.append("markdown_file", file);
  if (articleType) form.append("article_type", articleType);
  const response = await fetch(`${API_BASE}/article-tasks`, {
    method: "POST",
    body: form,
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
  const payload = await parseResponse<{ task: Task }>(response);
  return payload.task;
}

export async function generatePlans(task: Task): Promise<void> {
  const response = await fetch(`${API_BASE}/article-tasks/${task.id}/generate-plans`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify({
      mode: "start",
      planner: "intelligent",
      expected_task_version: task.version,
    }),
  });
  await parseResponse(response);
}

export async function acknowledgePreflightFinding(
  task: Task,
  findingCode: string,
  blockId: string | null,
): Promise<TaskDetail> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${task.id}/preflight/findings/${findingCode}/acknowledge`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Operator-Id": "operator",
      },
      body: JSON.stringify({ expected_task_version: task.version, block_id: blockId }),
    },
  );
  return parseResponse<TaskDetail>(response);
}

export async function replacePreflightAsset(
  task: Task,
  findingCode: string,
  blockId: string | null,
  file: File,
): Promise<TaskDetail> {
  const form = new FormData();
  form.append("expected_task_version", String(task.version));
  if (blockId) form.append("block_id", blockId);
  form.append("image_file", file);
  const response = await fetch(
    `${API_BASE}/article-tasks/${task.id}/preflight/findings/${findingCode}/replace-asset`,
    {
      method: "POST",
      headers: { "X-Operator-Id": "operator" },
      body: form,
    },
  );
  return parseResponse<TaskDetail>(response);
}

export async function getTask(taskId: string): Promise<TaskDetail> {
  const response = await fetchWithTimeout(`${API_BASE}/article-tasks/${taskId}`, { cache: "no-store" });
  return parseResponse<TaskDetail>(response);
}

export async function getPlans(taskId: string): Promise<PlanList> {
  const response = await fetchWithTimeout(`${API_BASE}/article-tasks/${taskId}/plans`, { cache: "no-store" });
  return parseResponse<PlanList>(response);
}

export async function selectPlan(task: Task, planId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${task.id}/plans/${planId}/select`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ plan_id: planId, expected_task_version: task.version }),
    },
  );
  await parseResponse(response);
}

export async function switchPlanSlot(
  taskId: string,
  planId: string,
  slotId: string,
  variant: string,
  expectedPlanRevision: number,
): Promise<{ plan: VisualPlan }> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/slots/${slotId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        variant,
        expected_plan_revision: expectedPlanRevision,
        reason: "operator_manual_switch",
      }),
    },
  );
  return parseResponse<{ plan: VisualPlan }>(response);
}

export async function restorePlanRevision(
  taskId: string,
  planId: string,
  revision: number,
  expectedPlanRevision: number,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/revisions/${revision}/restore`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_plan_revision: expectedPlanRevision }),
    },
  );
  await parseResponse(response);
}

export async function undoPlanChange(
  taskId: string,
  planId: string,
  expectedPlanRevision: number,
): Promise<{ plan: VisualPlan }> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/undo`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_plan_revision: expectedPlanRevision }),
    },
  );
  return parseResponse<{ plan: VisualPlan }>(response);
}

export async function getImageSlots(taskId: string, planId: string): Promise<ImageSlotList> {
  const response = await fetchWithTimeout(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/image-slots`,
    { cache: "no-store" },
  );
  return parseResponse<ImageSlotList>(response);
}

export async function getCoverWorkspace(taskId: string, planId: string): Promise<CoverWorkspace> {
  const response = await fetchWithTimeout(`${API_BASE}/article-tasks/${taskId}/plans/${planId}/cover-candidates`, {
    cache: "no-store",
  });
  return parseResponse<CoverWorkspace>(response);
}

export async function generateCoverCandidate(task: Task, planId: string): Promise<CoverWorkspace> {
  const response = await fetch(`${API_BASE}/article-tasks/${task.id}/plans/${planId}/cover-candidates/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_task_version: task.version }),
  });
  const payload = await parseResponse<{ workspace: CoverWorkspace }>(response);
  return payload.workspace;
}

export async function reuseCoverCandidate(
  task: Task,
  planId: string,
  sourceType: "accepted_body_image" | "controlled_source_image",
  sourceId: string,
): Promise<CoverWorkspace> {
  const response = await fetch(`${API_BASE}/article-tasks/${task.id}/plans/${planId}/cover-candidates/reuse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      expected_task_version: task.version,
      source_type: sourceType,
      source_id: sourceId,
    }),
  });
  const payload = await parseResponse<{ workspace: CoverWorkspace }>(response);
  return payload.workspace;
}

export async function selectCoverCandidate(
  task: Task,
  planId: string,
  candidateId: string,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${task.id}/plans/${planId}/cover-candidates/${candidateId}/select`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Operator-Id": "operator" },
      body: JSON.stringify({ expected_task_version: task.version }),
    },
  );
  await parseResponse(response);
}

export async function generateImageCandidate(
  taskId: string,
  planId: string,
  imageSlotId: string,
  expectedImageRevision: number,
  mode: "start" | "regenerate" | "fallback",
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/image-slots/${imageSlotId}/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, expected_image_revision: expectedImageRevision }),
    },
  );
  await parseResponse(response);
}

export async function acceptImageCandidate(
  taskId: string,
  planId: string,
  imageSlotId: string,
  candidateId: string,
  expectedImageRevision: number,
  textVerified = false,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/image-slots/${imageSlotId}/candidates/${candidateId}/accept`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        expected_image_revision: expectedImageRevision,
        text_verified: textVerified,
      }),
    },
  );
  await parseResponse(response);
}

export async function skipImageSlot(
  taskId: string,
  planId: string,
  imageSlotId: string,
  expectedImageRevision: number,
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/image-slots/${imageSlotId}/skip`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_image_revision: expectedImageRevision }),
    },
  );
  await parseResponse(response);
}

export async function replaceImageSlot(
  taskId: string,
  planId: string,
  imageSlotId: string,
  expectedImageRevision: number,
  file: File,
): Promise<void> {
  const form = new FormData();
  form.append("expected_image_revision", String(expectedImageRevision));
  form.append("image_file", file);
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/image-slots/${imageSlotId}/replace`,
    { method: "POST", body: form },
  );
  await parseResponse(response);
}

export async function getPublicationReadiness(taskId: string): Promise<PublicationReadiness> {
  const response = await fetchWithTimeout(`${API_BASE}/article-tasks/${taskId}/publication-readiness`, {
    cache: "no-store",
  });
  return parseResponse<PublicationReadiness>(response);
}

export async function savePublicationDraft(
  taskId: string,
  metadata: PublicationMetadata,
): Promise<{ metadata: PublicationMetadata; saved_at: string }> {
  const response = await fetch(`${API_BASE}/article-tasks/${taskId}/publication-draft`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-Operator-Id": "operator" },
    body: JSON.stringify(metadata),
  });
  return parseResponse(response);
}

export async function getPublicationRevisions(taskId: string): Promise<PublicationRevision[]> {
  const response = await fetchWithTimeout(`${API_BASE}/article-tasks/${taskId}/publication-revisions`, {
    cache: "no-store",
  });
  const payload = await parseResponse<{ items: PublicationRevision[] }>(response);
  return payload.items;
}

export async function freezePublication(
  task: Task,
  metadata: PublicationMetadata,
): Promise<{ revision: PublicationRevision; task: Task }> {
  const response = await fetch(`${API_BASE}/article-tasks/${task.id}/publication-revisions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
      "X-Operator-Id": "operator",
    },
    body: JSON.stringify({ expected_task_version: task.version, metadata }),
  });
  return parseResponse(response);
}

export async function continueEditingPublication(
  task: Task,
  revisionId: string,
): Promise<{ task: Task }> {
  const response = await fetch(`${API_BASE}/publication-revisions/${revisionId}/continue-editing`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Operator-Id": "operator" },
    body: JSON.stringify({ expected_task_version: task.version }),
  });
  return parseResponse(response);
}

export async function createMockDraft(
  task: Task,
  revision: PublicationRevision,
): Promise<{ operation: DraftOperation; task: Task }> {
  const response = await fetch(`${API_BASE}/publication-revisions/${revision.id}/draft-operations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
      "X-Operator-Id": "operator",
    },
    body: JSON.stringify({
      expected_task_version: task.version,
      draft_slot: revision.suggested_draft_slot,
      simulation_mode: "success",
    }),
  });
  return parseResponse(response);
}

export async function getWenyanPublisherStatus(): Promise<WenyanPublisherStatus> {
  const response = await fetchWithTimeout(`${API_BASE}/publishers/wenyan/status`, { cache: "no-store" });
  return parseResponse<WenyanPublisherStatus>(response);
}

export async function createWenyanDraft(
  task: Task,
  revision: PublicationRevision,
): Promise<{ operation: DraftOperation; task: Task; idempotency_replayed: boolean }> {
  const response = await fetch(`${API_BASE}/publication-revisions/${revision.id}/wenyan-draft`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
      "X-Operator-Id": "operator",
    },
    body: JSON.stringify({
      expected_task_version: task.version,
      draft_slot: revision.suggested_draft_slot,
    }),
  });
  return parseResponse(response);
}

export async function getClipboardPayload(revisionId: string): Promise<ClipboardPayload> {
  const response = await fetch(`${API_BASE}/publication-revisions/${revisionId}/clipboard`, {
    cache: "no-store",
  });
  return parseResponse<ClipboardPayload>(response);
}

export function publicationBundleUrl(revisionId: string): string {
  return `${API_BASE}/publication-revisions/${revisionId}/bundle`;
}

export async function getDraftOperations(taskId: string): Promise<DraftOperation[]> {
  const response = await fetchWithTimeout(`${API_BASE}/article-tasks/${taskId}/draft-operations`, {
    cache: "no-store",
  });
  const payload = await parseResponse<{ items: DraftOperation[] }>(response);
  return payload.items;
}

export async function retryMockDraft(
  task: Task,
  operation: DraftOperation,
): Promise<{ operation: DraftOperation; task: Task }> {
  const response = await fetch(`${API_BASE}/draft-operations/${operation.id}/retry`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
      "X-Operator-Id": "operator",
    },
    body: JSON.stringify({
      expected_task_version: task.version,
      expected_operation_version: operation.version,
    }),
  });
  return parseResponse(response);
}

export async function retryWenyanDraft(
  task: Task,
  operation: DraftOperation,
): Promise<{ operation: DraftOperation; task: Task; idempotency_replayed: boolean }> {
  const response = await fetch(`${API_BASE}/draft-operations/${operation.id}/wenyan-retry`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
      "X-Operator-Id": "operator",
    },
    body: JSON.stringify({
      expected_task_version: task.version,
      expected_operation_version: operation.version,
    }),
  });
  return parseResponse(response);
}

export async function getBlindReviewSet(
  evalSetId: string,
  reviewerId: "product_owner" | "operator",
): Promise<BlindReviewSet> {
  const response = await fetch(
    `${API_BASE}/blind-reviews/${evalSetId}?reviewer_id=${reviewerId}`,
    { cache: "no-store" },
  );
  return parseResponse<BlindReviewSet>(response);
}

export async function submitBlindReview(
  evalSetId: string,
  sampleId: string,
  payload: BlindReviewSubmission,
): Promise<{ submitted: true; locked: true; progress: { completed: number; total: number } }> {
  const response = await fetch(
    `${API_BASE}/blind-reviews/${evalSetId}/samples/${sampleId}/submissions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return parseResponse(response);
}
