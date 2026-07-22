"use client";

import Link from "next/link";
import { CheckIcon } from "@/components/icons";
import { absoluteApiUrl } from "@/lib/api";
import type { PreflightFinding, PreflightReport, TaskStatus } from "@/lib/types";

type PreflightPanelProps = {
  report: PreflightReport;
  taskStatus: TaskStatus;
  titleSource: string;
  sectionCount: number;
  imageReferenceCount: number;
  busyFinding: string;
  planningBusy: boolean;
  hasPreview: boolean;
  onAcknowledge: (finding: PreflightFinding) => void;
  onGeneratePlans: () => void;
  onLocate: (blockId: string) => void;
  onReplaceAsset: (finding: PreflightFinding, file: File) => void;
};

const titleSourceLabels: Record<string, string> = {
  override: "运营上传参数",
  frontmatter: "Frontmatter",
  first_h1: "正文首个 H1",
};

const policyLabels = {
  ACKNOWLEDGE: "知情确认",
  EDIT_SOURCE: "修改原稿",
  REPLACE_ASSET: "替换资产",
  HARD_BLOCK: "硬性阻断",
};

function findingStage(finding: PreflightFinding): string {
  if (finding.resolved_at) return finding.resolution_action === "REPLACE_ASSET" ? "已替换" : "已确认";
  if (finding.resolution_policy === "HARD_BLOCK") return "停止处理";
  if (finding.planning_blocking) return "生成方案前";
  if (finding.draft_blocking) return "创建草稿前";
  return "进入受限规划";
}

function detailLine(finding: PreflightFinding): string | null {
  if (!finding.details) return null;
  const source = typeof finding.details.source === "string" ? finding.details.source : null;
  if (source) return source;
  const candidates = Array.isArray(finding.details.candidates) ? finding.details.candidates : [];
  if (candidates.length) {
    return candidates
      .map((candidate) => {
        if (!candidate || typeof candidate !== "object") return null;
        const value = candidate as { source?: string; title?: string };
        return value.title ? `${titleSourceLabels[value.source ?? ""] ?? value.source}：${value.title}` : null;
      })
      .filter(Boolean)
      .join(" / ");
  }
  const from = finding.details.from_level;
  const to = finding.details.to_level;
  if (typeof from === "number" && typeof to === "number") return `检测路径：H${from} → H${to}`;
  return null;
}

export function PreflightPanel({
  report,
  taskStatus,
  titleSource,
  sectionCount,
  imageReferenceCount,
  busyFinding,
  planningBusy,
  hasPreview,
  onAcknowledge,
  onGeneratePlans,
  onLocate,
  onReplaceAsset,
}: PreflightPanelProps) {
  const unresolved = report.findings.filter((finding) => !finding.resolved_at);
  const planningBlockers = unresolved.filter((finding) => finding.planning_blocking).length;
  const draftBlockers = unresolved.filter((finding) => finding.draft_blocking).length;
  const acknowledgements = unresolved.filter((finding) => finding.resolution_policy === "ACKNOWLEDGE").length;
  const isTaskCreated = taskStatus === "created";
  const shouldOpen = isTaskCreated || planningBlockers > 0;

  return (
    <section className={`preflight-dossier preflight-${report.status.toLowerCase()} ${hasPreview ? "preflight-compact" : ""}`} aria-labelledby="preflight-title">
      <header className="preflight-masthead">
        <div className="preflight-stamp" aria-label={`预检状态 ${report.status}`}>
          <span>INPUT</span>
          <strong>{report.status}</strong>
          <small>{report.ruleset_version.replace("preflight_rules.", "RULES ")}</small>
        </div>
        <div className="preflight-heading">
          <span>INPUT CONTROL / MARKDOWN DOSSIER</span>
          <h2 id="preflight-title">
            {report.status === "PASS"
              ? "结构清晰，可以进入视觉规划"
              : report.status === "BLOCK"
                ? "输入已停止，需要修改原稿"
                : planningBlockers
                  ? `发现 ${planningBlockers} 项生成前问题`
                  : "可进入受限规划，草稿前仍需收尾"}
          </h2>
          <p>
            {report.status === "PASS"
              ? "系统只进行了可验证的机械整理，没有发现需要人工判断的问题。"
              : "预检不会改写事实或观点；每个问题都标明影响阶段和允许的处理方式。"}
          </p>
        </div>
        <dl className="preflight-facts">
          <div><dt>标题来源</dt><dd>{titleSourceLabels[titleSource] ?? titleSource}</dd></div>
          <div><dt>主章节</dt><dd>{sectionCount}</dd></div>
          <div><dt>原稿图片</dt><dd>{imageReferenceCount}</dd></div>
          <div><dt>机械调整</dt><dd>{report.auto_repairs.length}</dd></div>
        </dl>
      </header>

      <div className="preflight-ledger" aria-label="预检影响摘要">
        <div className={planningBlockers ? "ledger-alert" : "ledger-clear"}>
          <span>{String(planningBlockers).padStart(2, "0")}</span>
          <p><strong>生成前处理</strong><small>{planningBlockers ? "必须修改后才能调用 Planner" : "Planner 入口已开放"}</small></p>
        </div>
        <div className={draftBlockers ? "ledger-warning" : "ledger-clear"}>
          <span>{String(draftBlockers).padStart(2, "0")}</span>
          <p><strong>草稿前处理</strong><small>{draftBlockers ? "允许先看方案，不允许创建草稿" : "没有未解决的发布资产问题"}</small></p>
        </div>
        <div className={acknowledgements ? "ledger-note" : "ledger-clear"}>
          <span>{String(acknowledgements).padStart(2, "0")}</span>
          <p><strong>待知情确认</strong><small>{acknowledgements ? "确认只记录选择，不会改写原稿" : "所有提示均已确认"}</small></p>
        </div>
      </div>

      <details className="preflight-findings" open={shouldOpen}>
        <summary>
          <span>ISSUE LEDGER</span>
          <strong>{report.findings.length ? `${unresolved.length} 项待处理 / ${report.findings.length} 项总计` : "没有发现问题"}</strong>
          <i>{shouldOpen ? "展开状态" : "查看详情"}</i>
        </summary>
        {report.findings.length ? (
          <div className="preflight-finding-list">
            {report.findings.map((finding, index) => {
              const key = `${finding.code}:${finding.block_id ?? "root"}`;
              const resolved = Boolean(finding.resolved_at);
              const detail = detailLine(finding);
              return (
                <article className={`preflight-finding ${resolved ? "finding-resolved" : ""}`} key={key}>
                  <span className="finding-number">{String(index + 1).padStart(2, "0")}</span>
                  <div className="finding-copy">
                    <div className="finding-labels">
                      <span>{findingStage(finding)}</span>
                      <span>{policyLabels[finding.resolution_policy]}</span>
                      {finding.block_id ? <span>{finding.block_id}</span> : null}
                    </div>
                    <h3>{finding.message}</h3>
                    {detail ? <p title={detail}>{detail}</p> : null}
                    <code>{finding.code}</code>
                  </div>
                  <div className="finding-action">
                    {resolved && finding.resolution_action === "REPLACE_ASSET" && finding.resolution_evidence ? (
                      <div className="finding-asset-resolved">
                        <img
                          alt={finding.resolution_evidence.asset_role === "cover" ? "已替换封面" : "已替换原稿图片"}
                          src={absoluteApiUrl(finding.resolution_evidence.content_url)}
                        />
                        <span><CheckIcon />{finding.resolution_evidence.width} × {finding.resolution_evidence.height}</span>
                      </div>
                    ) : resolved ? (
                      <span className="finding-done"><CheckIcon />已由{finding.resolved_by === "product_owner" ? "产品负责人" : "运营"}确认</span>
                    ) : finding.resolution_policy === "ACKNOWLEDGE" ? (
                      <button disabled={Boolean(busyFinding)} onClick={() => onAcknowledge(finding)} type="button">
                        {busyFinding === key ? "记录中…" : "确认按当前结构继续"}
                      </button>
                    ) : finding.resolution_policy === "REPLACE_ASSET" ? (
                      <div className="finding-asset-actions">
                        <label className={busyFinding ? "disabled" : ""}>
                          <strong>{busyFinding === key ? "上传校验中…" : "上传真实图片"}</strong>
                          <small>PNG / JPG / WebP · 至少 480×240</small>
                          <input
                            accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                            disabled={Boolean(busyFinding)}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              if (file) onReplaceAsset(finding, file);
                              event.currentTarget.value = "";
                            }}
                            type="file"
                          />
                        </label>
                        {finding.block_id && hasPreview ? (
                          <button className="locate-finding" onClick={() => onLocate(finding.block_id!)} type="button">先定位</button>
                        ) : null}
                      </div>
                    ) : finding.block_id && hasPreview ? (
                      <button className="locate-finding" onClick={() => onLocate(finding.block_id!)} type="button">定位到文章</button>
                    ) : finding.planning_blocking ? (
                      <Link href="/">返回修改并重新上传</Link>
                    ) : (
                      <span className="finding-pending">保留到发布准备阶段</span>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="preflight-empty"><CheckIcon /><span>结构与发布资产检查均未发现问题。</span></div>
        )}
      </details>

      {isTaskCreated ? (
        <footer className="preflight-gate">
          <div>
            <span>PLANNER GATE</span>
            <strong>{report.planning_allowed ? "输入已具备规划条件" : "Planner 暂时锁定"}</strong>
            <p>{report.planning_allowed ? "未确认提示可以随受限方案继续展示。" : "请修改原稿并创建新任务；当前任务不会静默修复。"}</p>
          </div>
          {report.planning_allowed ? (
            <button disabled={planningBusy} onClick={onGeneratePlans} type="button">
              {planningBusy ? "正在生成两套方案…" : report.status === "PASS" ? "生成两套视觉方案" : "进入受限规划"}
            </button>
          ) : (
            <Link href="/">选择修改后的 Markdown</Link>
          )}
        </footer>
      ) : null}
    </section>
  );
}
