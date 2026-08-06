"use client";

import Link from "@/lib/router";
import { useEffect, useMemo, useState } from "react";
import { BackIcon } from "@/components/icons";
import styles from "./variant-review.module.css";

type CandidateId = "numbered_insight" | "evidence_callout" | "logic_path";
type Decision = "approved" | "needs_revision" | "rejected";

type Candidate = {
  id: CandidateId;
  index: string;
  name: string;
  english: string;
  current: string;
  candidate: string;
  fallback: string;
  difference: string;
  reviewFocus: string;
};

const candidates: Candidate[] = [
  {
    id: "numbered_insight",
    index: "01",
    name: "编号观点",
    english: "NUMBERED INSIGHT",
    current: "清亮观点列",
    candidate: "杂志索引卡",
    fallback: "朴素编号列表",
    difference: "从逐项彩色卡片改为大号索引、连续编辑栏与留白节奏，不靠换色制造新鲜感。",
    reviewFocus: "并列关系是否清楚？大号数字是否帮助扫读？",
  },
  {
    id: "evidence_callout",
    index: "02",
    name: "证据强调",
    english: "EVIDENCE CALLOUT",
    current: "轨道描边框",
    candidate: "编辑批注引文",
    fallback: "朴素证据注释",
    difference: "去掉完整圆角卡，改用引号、批注线和局部底色建立“证据被编辑标出”的语义。",
    reviewFocus: "证据是否比装饰更先被看见？是否像真实编辑标注？",
  },
  {
    id: "logic_path",
    index: "03",
    name: "逻辑路径",
    english: "LOGIC PATH",
    current: "四色路线节点",
    candidate: "折线阶梯",
    fallback: "朴素步骤",
    difference: "从等宽节点卡改为逐级展开的阶梯，使用统一暖色体系表达递进和倒推。",
    reviewFocus: "5 秒内能否看懂先后与递进？视觉是否协调而不沉闷？",
  },
];

const decisionLabels: Record<Decision, string> = {
  approved: "接入正式库",
  needs_revision: "调整后复评",
  rejected: "本轮不接入",
};

function NumberedPreview({ mode }: { mode: "current" | "candidate" | "fallback" }) {
  const items = [
    "保存成绩查询页面或官方截图",
    "记录一分一段表中的准确位次",
    "标记单科成绩可能触发的专业限制",
    "不使用来源不明的“内部排名”",
  ];

  if (mode === "candidate") {
    return (
      <section className={styles.magazineIndex}>
        <div className={styles.magazineHeader}><span>04 POINTS</span><i /></div>
        {items.map((item, index) => (
          <div className={styles.magazineRow} key={item}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <p>{item}</p>
          </div>
        ))}
        <small>核对信息，再做决定</small>
      </section>
    );
  }

  if (mode === "fallback") {
    return (
      <ol className={styles.plainList}>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ol>
    );
  }

  return (
    <section className={styles.currentPoints}>
      <div className={styles.currentLabel}><i /><span>KEY POINTS</span></div>
      {items.map((item, index) => (
        <div className={styles.currentPoint} key={item}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          <p>{item}</p>
        </div>
      ))}
    </section>
  );
}

function EvidencePreview({ mode }: { mode: "current" | "candidate" | "fallback" }) {
  const text = "志愿表不是一次“凭感觉排序”，而是一组需要逐项验证的决策。";

  if (mode === "candidate") {
    return (
      <section className={styles.editorialQuote}>
        <span className={styles.quoteMark} aria-hidden="true">“</span>
        <div className={styles.quoteRail}>
          <span>EDITOR&apos;S NOTE</span>
          <i />
          <small>关键判断</small>
        </div>
        <blockquote>{text}</blockquote>
        <p>先核对依据，再确认顺序</p>
      </section>
    );
  }

  if (mode === "fallback") {
    return <blockquote className={styles.plainQuote}>{text}</blockquote>;
  }

  return (
    <section className={styles.currentEvidence}>
      <p><i />EVIDENCE / 证据<span /></p>
      <strong>{text}</strong>
    </section>
  );
}

function LogicPreview({ mode }: { mode: "current" | "candidate" | "fallback" }) {
  const items = ["先确定一个想完成的作品", "倒推作品需要的能力", "在行动中主动学习"];

  if (mode === "candidate") {
    return (
      <section className={styles.foldedStair}>
        <header><span>BACKCASTING / 03</span><strong>从终点出发，<br />倒推今天的行动。</strong></header>
        <div className={styles.stairTrack}>
          {items.map((item, index) => (
            <div className={styles.stairRow} key={item}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <p>{item}</p>
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (mode === "fallback") {
    return (
      <ol className={`${styles.plainList} ${styles.plainSteps}`}>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ol>
    );
  }

  return (
    <section className={styles.currentRoute}>
      <h4><i />从终点出发 · 反向规划学习路线</h4>
      {items.map((item, index) => (
        <div className={styles.currentRouteRow} key={item}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          <p>{item}</p>
        </div>
      ))}
    </section>
  );
}

function Preview({ id, mode }: { id: CandidateId; mode: "current" | "candidate" | "fallback" }) {
  return (
    <article className={styles.articleCanvas}>
      <div className={styles.articleMeta}><span>示例公众号 · 视觉片段</span><span>390 PX</span></div>
      <p className={styles.context}>填报志愿不是把院校简单排队，而是依据分数、位次和专业条件逐项核验。</p>
      {id === "numbered_insight" ? <NumberedPreview mode={mode} /> : null}
      {id === "evidence_callout" ? <EvidencePreview mode={mode} /> : null}
      {id === "logic_path" ? <LogicPreview mode={mode} /> : null}
      <p className={styles.contextAfter}>每一步都要保留来源，方便在最终提交前再次检查。</p>
    </article>
  );
}

export default function VariantReviewPage() {
  const [decisions, setDecisions] = useState<Partial<Record<CandidateId, Decision>>>({});
  const [notes, setNotes] = useState<Partial<Record<CandidateId, string>>>({});
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const saved = window.localStorage.getItem("visual-director-variant-review-v0.4");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved) as { decisions?: Partial<Record<CandidateId, Decision>>; notes?: Partial<Record<CandidateId, string>> };
      setDecisions(parsed.decisions ?? {});
      setNotes(parsed.notes ?? {});
    } catch {
      window.localStorage.removeItem("visual-director-variant-review-v0.4");
    }
  }, []);

  const reviewedCount = Object.keys(decisions).length;
  const summary = useMemo(() => ({
    schema_version: "variant_review.v0.4",
    reviewed_at: new Date().toISOString(),
    scope_decision: "D20-D24 accepted",
    decisions: candidates.map((item) => ({
      component: item.id,
      candidate_variant: item.candidate,
      decision: decisions[item.id] ?? "pending",
      note: notes[item.id]?.trim() || null,
    })),
  }), [decisions, notes]);

  function persist(nextDecisions: Partial<Record<CandidateId, Decision>>, nextNotes = notes) {
    window.localStorage.setItem("visual-director-variant-review-v0.4", JSON.stringify({ decisions: nextDecisions, notes: nextNotes }));
  }

  function decide(id: CandidateId, decision: Decision) {
    const next = { ...decisions, [id]: decision };
    setDecisions(next);
    persist(next);
  }

  function updateNote(id: CandidateId, value: string) {
    const next = { ...notes, [id]: value };
    setNotes(next);
    persist(decisions, next);
  }

  async function copyReview() {
    await navigator.clipboard.writeText(JSON.stringify(summary, null, 2));
    setNotice("评审结果已复制，可以直接粘贴给 Codex");
    window.setTimeout(() => setNotice(""), 2600);
  }

  return (
    <main className={styles.reviewPage}>
      <header className={styles.topbar}>
        <Link href="/" className={styles.backLink}><BackIcon />返回任务台</Link>
        <div className={styles.topbarTitle}><strong>第二批候选变体</strong><span>VISUAL REVIEW / V0.4</span></div>
        <div className={styles.reviewCount}><span>{reviewedCount}</span> / 3 已评审</div>
      </header>

      <section className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>D20–D24 ACCEPTED · CANDIDATE ONLY</p>
          <h1>看结构差异，<br />不是看换了什么颜色。</h1>
        </div>
        <div className={styles.heroNote}>
          <span>评审边界</span>
          <p>本页只决定三个候选 B 是否值得接入。正式生成链路仍使用 V0.2.2，选择不会立即影响运营。</p>
        </div>
      </section>

      <nav className={styles.jumpNav} aria-label="候选组件快速导航">
        {candidates.map((item) => <a href={`#${item.id}`} key={item.id}><span>{item.index}</span>{item.name}</a>)}
      </nav>

      {candidates.map((item) => (
        <section className={styles.candidateSection} id={item.id} key={item.id}>
          <div className={styles.sectionHeading}>
            <div className={styles.sectionIndex}>{item.index}</div>
            <div>
              <p>{item.english}</p>
              <h2>{item.name}</h2>
            </div>
            <div className={styles.sectionBrief}>
              <span>结构差异</span>
              <p>{item.difference}</p>
              <strong>{item.reviewFocus}</strong>
            </div>
          </div>

          <p className={styles.scrollHint}>左右滑动查看 A 当前版、B 候选版和 C 安全版</p>
          <div className={styles.comparisonGrid}>
            <div className={styles.previewColumn}>
              <header><span>A</span><div><small>当前正式版</small><strong>{item.current}</strong></div><i className={styles.liveBadge}>已验证</i></header>
              <Preview id={item.id} mode="current" />
            </div>
            <div className={`${styles.previewColumn} ${styles.candidateColumn}`}>
              <header><span>B</span><div><small>本轮候选</small><strong>{item.candidate}</strong></div><i className={styles.candidateBadge}>待评审</i></header>
              <Preview id={item.id} mode="candidate" />
            </div>
            <div className={styles.previewColumn}>
              <header><span>C</span><div><small>安全降级</small><strong>{item.fallback}</strong></div><i className={styles.safeBadge}>保留</i></header>
              <Preview id={item.id} mode="fallback" />
            </div>
          </div>

          <div className={styles.decisionPanel}>
            <div><span>PRODUCT DECISION</span><strong>候选 B：{item.candidate}</strong></div>
            <div className={styles.decisionButtons}>
              {(Object.keys(decisionLabels) as Decision[]).map((decision) => (
                <button
                  className={decisions[item.id] === decision ? styles.activeDecision : ""}
                  key={decision}
                  onClick={() => decide(item.id, decision)}
                  type="button"
                >{decisionLabels[decision]}</button>
              ))}
            </div>
            <label>
              <span>可选备注</span>
              <textarea
                onChange={(event) => updateNote(item.id, event.target.value)}
                placeholder="例如：关系直观，但希望减少顶部装饰"
                rows={2}
                value={notes[item.id] ?? ""}
              />
            </label>
          </div>
        </section>
      ))}

      <section className={styles.submitPanel}>
        <div><p>REVIEW CHECKPOINT</p><h2>三类都判断后，再进入实现。</h2></div>
        <p>“接入正式库”仍需经过代码接入、390/375 px 回归与真实微信草稿验证。</p>
        <button disabled={reviewedCount !== candidates.length} onClick={copyReview} type="button">复制评审结果</button>
      </section>

      {notice ? <div className={styles.toast} role="status">{notice}</div> : null}
    </main>
  );
}
