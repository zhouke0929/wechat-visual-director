export type TaskStatus =
  | "created"
  | "analyzing"
  | "plans_ready"
  | "plan_selected"
  | "publication_frozen"
  | "mock_draft_created"
  | "mock_draft_failed"
  | "mock_draft_unknown"
  | "failed";

export type Task = {
  id: string;
  account_id: string;
  title: string;
  article_type: string | null;
  status: TaskStatus;
  history_window: number;
  brand_profile_version: string;
  fixed_footer_asset_version: string;
  selected_plan_id: string | null;
  active_publication_revision_id: string | null;
  publication_mode: "mock";
  publication_draft_metadata: PublicationMetadata;
  version: number;
  created_at: string;
  updated_at: string;
};

export type PublicationMetadata = {
  author: string;
  digest: string;
  content_source_url: string;
  show_cover_pic: boolean;
};

export type ProgressStep = {
  key: string;
  label: string;
  status: "pending" | "running" | "succeeded" | "failed";
  message: string | null;
};

export type PreflightResolutionPolicy =
  | "ACKNOWLEDGE"
  | "EDIT_SOURCE"
  | "REPLACE_ASSET"
  | "HARD_BLOCK";

export type PreflightFinding = {
  code: string;
  message: string;
  resolution_policy: PreflightResolutionPolicy;
  planning_blocking: boolean;
  draft_blocking: boolean;
  block_id: string | null;
  details: Record<string, unknown> | null;
  resolved_at?: string;
  resolved_by?: "operator" | "product_owner";
  resolution_action?: "ACKNOWLEDGE" | "REPLACE_ASSET";
  resolution_evidence?: {
    asset_id: string;
    asset_role: "cover" | "body_image";
    content_url: string;
    content_type: "image/png" | "image/jpeg" | "image/webp";
    output_sha256: string;
    width: number;
    height: number;
  };
};

export type PreflightReport = {
  schema_version: string;
  ruleset_version: string;
  status: "PASS" | "REVIEW" | "BLOCK";
  source_hash: string;
  normalized_hash: string;
  canonical_title: string | null;
  title_source: string | null;
  auto_repairs: Array<{ code: string; message: string; before: string | null; after: string | null }>;
  findings: PreflightFinding[];
  quality_dimensions: Record<string, "pass" | "warning" | "blocking">;
  planning_allowed: boolean;
  draft_creation_allowed: boolean;
};

export type TaskDetail = {
  task: Task;
  progress: ProgressStep[];
  input_summary: {
    title_source: string;
    section_count: number;
    image_reference_count: number;
    warnings: Array<{ code: string; message: string }>;
    preflight_report?: PreflightReport;
  };
  available_actions: string[];
  last_error: { message: string } | null;
};

export type VisualPlan = {
  id: string;
  plan_index: number;
  plan_name: string;
  recommendation: "recommended" | "alternative";
  style_mode: string;
  visual_system?: "light_reading" | "editorial_contrast" | "warm_humanist" | "structured_grid";
  structure_fingerprint?: string;
  visual_system_metadata?: {
    planner_recalled: false;
    shared_structure: true;
    recent_counts: Record<string, number>;
  };
  planner_metadata?: {
    mode: "rule" | "intelligent";
    provider: string;
    model: string;
    planner_call_count: number;
    fallback_used: boolean;
    fallback_reason?: string | null;
    repair_count?: number;
    input_tokens?: number;
    output_tokens?: number;
    normalization_count?: number;
    normalization_adjustments?: Array<Record<string, string>>;
    provider_error_code?: string | null;
  };
  summary: string;
  difference_from_recent: string[];
  structural_differences: string[];
  component_usage: Record<string, number>;
  preview_artifact_id: string;
  preview_content_hash: string;
  preview_url: string;
  revision: number;
  undo_stack: number[];
  component_library_version: string;
  slots: ComponentSlot[];
  image_slots: ImageSlotPlan[];
};

export type ImagePurpose = "atmosphere" | "structured_infographic";

export type ImageSlotPlan = {
  image_slot_id: string;
  anchor_block_id: string;
  source_block_ids: string[];
  placement: "after_anchor";
  purpose: ImagePurpose;
  required: false;
  reason: string;
  aspect_ratio: "4:3" | "16:9";
  visual_intent: {
    subject: string;
    composition: "branching" | "layered" | "wide_scene" | "centered";
    style_family: "editorial_paper_cut" | "soft_flat_illustration" | "clean_3d_geometry";
    palette_role: "plan_palette";
    negative_space: "none" | "lower_right" | "lower_third";
  };
};

export type ImageCandidate = {
  id: string;
  image_slot_id: string;
  candidate_index: number;
  provider: "mock" | "agnes" | "manual_upload";
  model: string;
  provider_prompt: string;
  status: "generated";
  content_url: string;
  width: number;
  height: number;
  latency_ms: number;
  human_decision: "pending" | "accepted" | "rejected";
  machine_checks: {
    file_valid: boolean;
    ratio_valid: boolean;
    qr_risk: string;
    text_risk: string;
    logo_risk: string;
    person_risk: string;
  };
};

export type ImageSlotState = {
  image_slot_id: string;
  status: "planned" | "generated" | "accepted" | "replaced" | "skipped" | "failed";
  image_revision: number;
  selected_candidate_id: string | null;
  decision: "pending" | "accepted" | "replaced" | "skipped";
  last_error: {
    code: string;
    message: string;
    retryable: boolean;
  } | null;
  candidates: ImageCandidate[];
};

export type ImageSlotReview = ImageSlotPlan & {
  state: ImageSlotState;
};

export type ImageSlotList = {
  task_id: string;
  plan_id: string;
  provider_mode: "mock" | "agnes";
  items: ImageSlotReview[];
};

export type CoverCandidate = {
  id: string;
  candidate_index: number;
  source_type: "ai_generated" | "accepted_body_image" | "controlled_source_image";
  source_resource_id: string | null;
  provider: string;
  model: string;
  content_url: string;
  output_sha256: string;
  width: 1080;
  height: 864;
  latency_ms: number;
  selected: boolean;
};

export type CoverReuseSource = {
  source_type: "accepted_body_image" | "controlled_source_image";
  source_id: string;
  label: string;
  content_url: string;
};

export type CoverWorkspace = {
  task_id: string;
  plan_id: string;
  provider_mode: "mock" | "agnes";
  cover_brief: {
    title: string;
    article_type: string;
    audience: string[];
    reader_task: string;
    narrative: string;
    visual_system: string;
    output_size: "1080x864";
    text_policy: "image_only";
    recommended_source: "reuse_body_image" | "ai_generated";
  };
  selected_cover: {
    id: string;
    content_url: string;
    output_sha256: string;
    width: number;
    height: number;
  } | null;
  candidates: CoverCandidate[];
  reuse_sources: CoverReuseSource[];
};

export type VariantOption = {
  value: string;
  label: string;
  kind: "primary" | "alternate" | "fallback";
  marker: "A" | "B" | "C" | "D" | "E";
  status: "wechat_verified" | "wechat_candidate" | "product_approved";
};

export type ComponentSlot = {
  slot_id: string;
  anchor_block_id: string;
  consume_block_ids: string[];
  semantic_role: string;
  component_type: string;
  component_label: string;
  variant: string;
  fallback_variant: string;
  emphasis: "primary" | "secondary" | "subtle";
  selection_reason: string;
  variant_options: VariantOption[];
  history_evidence: {
    recent_use_count: number;
    penalty_applied: boolean;
    component_use_count: number;
    selected_variant: string | null;
    avoided_variant: string | null;
  };
};

export type PlanList = {
  task_id: string;
  selected_plan_id: string | null;
  plans: VisualPlan[];
  comparison: {
    structural_difference_count: number;
    shared_structure?: boolean;
    summary: string;
  };
};

export type PublicationBlocker = {
  code: string;
  message: string;
  resource_type: string;
  resource_id: string | null;
  action: string;
};

export type PublicationReadiness = {
  task_id: string;
  ready: boolean;
  publication_mode: "mock";
  suggested_draft_slot: string;
  blockers: PublicationBlocker[];
  checks: Record<string, "pass" | "pending" | "blocking">;
};

export type PublicationRevision = {
  id: string;
  task_id: string;
  revision_number: number;
  lifecycle_status: "active" | "superseded";
  plan_id: string;
  plan_revision: number;
  title: string;
  metadata: PublicationMetadata & { title: string };
  asset_summary: {
    cover_count: number;
    source_image_count: number;
    planned_image_count: number;
    brand_asset_count: number;
  };
  preflight_status: string;
  compatibility_status: "pass" | "blocking";
  frozen_html_hash: string;
  structure_hash: string;
  asset_manifest_hash: string;
  frozen_by: string;
  frozen_at: string;
  preview_url: string;
  is_mock: true;
  suggested_draft_slot: string;
};

export type DraftOperationStep = {
  id: string;
  step_key: string;
  sequence_no: number;
  status: "pending" | "running" | "succeeded" | "failed" | "unknown";
  version: number;
  attempt_count: number;
  output: Record<string, unknown> | null;
  last_error: { code: string; message: string; retryable: boolean } | null;
};

export type DraftOperation = {
  id: string;
  task_id: string;
  revision_id: string;
  draft_slot: string;
  provider: "mock";
  status: "pending" | "running" | "succeeded" | "failed" | "unknown" | "superseded";
  version: number;
  simulation_mode: "success" | "fail_once" | "unknown";
  media_id: string | null;
  is_mock: true;
  confirmed_by: string;
  confirmed_at: string;
  last_error: { code: string; message: string; retryable: boolean } | null;
  steps: DraftOperationStep[];
};

export type BlindReviewDimension = {
  key: BlindReviewDimensionKey;
  label: string;
  description: string;
};

export type BlindReviewDimensionKey =
  | "article_understanding"
  | "component_planning"
  | "image_planning"
  | "style_direction"
  | "history_freshness"
  | "direct_adoption";

export type BlindCandidateSummary = {
  article: {
    article_type: string;
    audience: string[];
    reader_task: string;
    narrative: string;
  };
  art_direction: {
    tone: string[];
    palette_roles: string[];
    style_family: string;
    avoid_recent_patterns: string[];
  };
  components: Array<{ label: string; anchor: string; reason: string }>;
  images: Array<{ anchor: string; purpose: string; reason: string; visual_intent: string }>;
};

export type BlindCandidate = {
  position: "left" | "right";
  label: "方案 A" | "方案 B";
  summary: BlindCandidateSummary;
  preview_url: string;
};

export type BlindReviewSample = {
  sample_id: string;
  index: number;
  title: string;
  article_type: string;
  role: string;
  visual_scoring: boolean;
  submitted: boolean;
  assignment_token: string;
  candidates: [BlindCandidate, BlindCandidate];
};

export type BlindReviewSet = {
  schema_version: string;
  eval_set_id: string;
  mode: "development_ui_validation";
  formal_conclusion_allowed: false;
  note: string;
  reviewer: { id: "product_owner" | "operator"; label: string };
  dimensions: BlindReviewDimension[];
  progress: { completed: number; total: number };
  samples: BlindReviewSample[];
};

export type BlindDimensionRating = {
  left: number;
  right: number;
  reason: string;
};

export type BlindReviewSubmission = {
  reviewer_id: "product_owner" | "operator";
  assignment_token: string;
  scores: Record<BlindReviewDimensionKey, BlindDimensionRating>;
  preferred_candidate: "left" | "right" | "tie";
  preference_reason: string;
};
