import type {
  BlindReviewSet,
  BlindReviewSubmission,
  CoverWorkspace,
  DraftOperation,
  ImageSlotList,
  PlanList,
  PublicationMetadata,
  PublicationReadiness,
  PublicationRevision,
  Task,
  TaskDetail,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");

export function absoluteApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${API_ORIGIN}${path.startsWith("/") ? path : `/${path}`}`;
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
  const response = await fetch(`${API_BASE}/article-tasks/${taskId}`, { cache: "no-store" });
  return parseResponse<TaskDetail>(response);
}

export async function getPlans(taskId: string): Promise<PlanList> {
  const response = await fetch(`${API_BASE}/article-tasks/${taskId}/plans`, { cache: "no-store" });
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
): Promise<void> {
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
  await parseResponse(response);
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
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/undo`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_plan_revision: expectedPlanRevision }),
    },
  );
  await parseResponse(response);
}

export async function getImageSlots(taskId: string, planId: string): Promise<ImageSlotList> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/image-slots`,
    { cache: "no-store" },
  );
  return parseResponse<ImageSlotList>(response);
}

export async function getCoverWorkspace(taskId: string, planId: string): Promise<CoverWorkspace> {
  const response = await fetch(`${API_BASE}/article-tasks/${taskId}/plans/${planId}/cover-candidates`, {
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
  mode: "start" | "regenerate",
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
): Promise<void> {
  const response = await fetch(
    `${API_BASE}/article-tasks/${taskId}/plans/${planId}/image-slots/${imageSlotId}/candidates/${candidateId}/accept`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_image_revision: expectedImageRevision }),
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
  const response = await fetch(`${API_BASE}/article-tasks/${taskId}/publication-readiness`, {
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
  const response = await fetch(`${API_BASE}/article-tasks/${taskId}/publication-revisions`, {
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

export async function getDraftOperations(taskId: string): Promise<DraftOperation[]> {
  const response = await fetch(`${API_BASE}/article-tasks/${taskId}/draft-operations`, {
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
