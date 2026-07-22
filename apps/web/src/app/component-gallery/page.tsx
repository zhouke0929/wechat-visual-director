"use client";

import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BackIcon, CheckIcon } from "@/components/icons";
import styles from "./component-gallery.module.css";

type ComponentId =
  | "question_hook"
  | "numbered_insight"
  | "evidence_callout"
  | "before_after_timeline"
  | "logic_path"
  | "concept_explainer";

type Definition = {
  id: ComponentId;
  index: string;
  name: string;
  english: string;
  purpose: string;
  useWhen: string;
  variants: [string, string];
  accent: string;
  pale: string;
};

const definitions: Definition[] = [
  {
    id: "question_hook",
    index: "01",
    name: "问题钩子",
    english: "QUESTION HOOK",
    purpose: "把章节的核心疑问变成视线入口。",
    useWhen: "开篇设问、对比命题、读者最关心的问题",
    variants: ["轻盈气泡", "编辑式问号卡"],
    accent: "#2387D8",
    pale: "#EAF6FF",
  },
  {
    id: "numbered_insight",
    index: "02",
    name: "编号观点",
    english: "NUMBERED INSIGHT",
    purpose: "让并列观点有节奏，而不是连续堆正文。",
    useWhen: "核心差异、方法拆解、连续观点",
    variants: ["渐变引导签", "票券式观点条"],
    accent: "#E95D8F",
    pale: "#FFF0F5",
  },
  {
    id: "evidence_callout",
    index: "03",
    name: "证据强调",
    english: "EVIDENCE CALLOUT",
    purpose: "把论据、解释和关键事实从正文中托出来。",
    useWhen: "数据解释、研究结论、关键事实",
    variants: ["轨道描边框", "研究注释框"],
    accent: "#0D9D9A",
    pale: "#E7F8F5",
  },
  {
    id: "before_after_timeline",
    index: "04",
    name: "前后时间线",
    english: "BEFORE / AFTER",
    purpose: "让变化关系先于细节被理解。",
    useWhen: "改革前后、问题与结果、旧方式与新方式",
    variants: ["双节点时间线", "左右对照账本"],
    accent: "#F05A36",
    pale: "#FFF1E8",
  },
  {
    id: "logic_path",
    index: "05",
    name: "逻辑路径",
    english: "LOGIC PATH",
    purpose: "把因果、推导和行动顺序变成可扫描路径。",
    useWhen: "方法论、目标倒推、三步流程",
    variants: ["暖色路线节点", "深色推导阶梯"],
    accent: "#D85B3D",
    pale: "#FFF1D7",
  },
  {
    id: "concept_explainer",
    index: "06",
    name: "概念解释",
    english: "CONCEPT EXPLAINER",
    purpose: "把抽象概念变成一个可以记住的视觉模型。",
    useWhen: "新概念、核心方法、抽象观点",
    variants: ["节点说明卡", "概念公式卡"],
    accent: "#7452A6",
    pale: "#F3EEFB",
  },
];

const initialVariants = Object.fromEntries(definitions.map((item) => [item.id, 0])) as Record<ComponentId, number>;

function Spark({ small = false }: { small?: boolean }) {
  return <span className={small ? styles.sparkSmall : styles.spark} aria-hidden="true" />;
}

function QuestionHook({ variant }: { variant: number }) {
  if (variant === 0) {
    return (
      <>
        <div className={styles.bubbleHook}>
          <Spark />
          <strong>AI 私塾 VS 传统学校，<br />有什么本质不同？</strong>
          <span className={styles.bubbleTail} aria-hidden="true" />
        </div>
        <p className={styles.contextText}>以典型的 AI 驱动学校为例，它与传统课堂存在根本性差异。</p>
      </>
    );
  }
  return (
    <>
      <div className={styles.editorialQuestion}>
        <span className={styles.giantQuestion} aria-hidden="true">?</span>
        <div>
          <small>THE QUESTION / 01</small>
          <strong>当知识可以随时获得，学校真正应该教什么？</strong>
        </div>
      </div>
      <p className={styles.contextText}>答案不再只是“更多知识”，而是定义问题、组织项目和与他人协作。</p>
    </>
  );
}

function NumberedInsight({ variant }: { variant: number }) {
  if (variant === 0) {
    return (
      <>
        <div className={styles.gradientLabel}>
          <span>01</span><strong>每天只学 2 小时</strong><b aria-hidden="true">?</b>
        </div>
        <p className={styles.bodyLead}>学生每天接受约两小时的 AI 辅助学习，平台会根据注意力与掌握程度动态调整内容。</p>
        <div className={styles.gradientLabelAlt}>
          <span>02</span><strong>其余时间做项目</strong><b aria-hidden="true">↗</b>
        </div>
      </>
    );
  }
  return (
    <div className={styles.ticketStack}>
      {[
        ["01", "个性化学习", "难度跟随掌握程度变化"],
        ["02", "项目式实践", "把知识放进真实任务"],
        ["03", "教练式引导", "从讲授转向反馈与协作"],
      ].map(([number, title, copy]) => (
        <div className={styles.ticketInsight} key={number}>
          <span>{number}</span><div><strong>{title}</strong><small>{copy}</small></div>
        </div>
      ))}
    </div>
  );
}

function EvidenceCallout({ variant }: { variant: number }) {
  if (variant === 0) {
    return (
      <>
        <p className={styles.contextText}>个性化不是“为了 AI 而 AI”，而是让学习难度真正跟随学生变化。</p>
        <div className={styles.orbitCallout}>
          <Spark small />
          <span className={styles.orbitDots} aria-hidden="true">•••</span>
          <strong>一个 AI 平台根据注意力状态和知识掌握程度，动态调整未来数天乃至数周的学习内容。</strong>
        </div>
      </>
    );
  }
  return (
    <div className={styles.researchNote}>
      <div className={styles.researchIndex}><span>证据</span><strong>01</strong></div>
      <div>
        <small>OBSERVATION</small>
        <p>真正的一对一个性化，不是所有学生使用同一个 AI 工具，而是每个人拥有不同的学习路径。</p>
        <span className={styles.sourceLine}>来自文章原始论据 · 待发布前核验来源</span>
      </div>
    </div>
  );
}

function BeforeAfterTimeline({ variant }: { variant: number }) {
  const before = ["知识碎片化，学完容易忘", "课堂以统一进度为中心"];
  const after = ["学生围绕项目主动补充知识", "作品成为学习成果的证据"];
  if (variant === 0) {
    return (
      <div className={styles.timeline}>
        <TimelineNode label="改革前" tone="before" items={before} />
        <TimelineNode label="改革后" tone="after" items={after} />
      </div>
    );
  }
  return (
    <div className={styles.ledgerCompare}>
      <div><small>BEFORE</small><strong>先学知识</strong><p>课程彼此分散，学生不知道知识能解决什么问题。</p></div>
      <span className={styles.ledgerArrow} aria-hidden="true">→</span>
      <div><small>AFTER</small><strong>先定目标</strong><p>从作品倒推所需能力，再主动建立知识之间的连接。</p></div>
    </div>
  );
}

function TimelineNode({ label, tone, items }: { label: string; tone: string; items: string[] }) {
  return (
    <div className={`${styles.timelineNode} ${styles[tone]}`}>
      <span className={styles.timelineMark}><CheckIcon /></span>
      <div><strong>{label}</strong><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></div>
    </div>
  );
}

function LogicPath({ variant }: { variant: number }) {
  if (variant === 0) {
    return (
      <div className={styles.routeMap}>
        <div className={styles.routeHeading}><span>从终点出发</span><strong>反向规划学习路线</strong></div>
        <div className={styles.routeTrack}>
          <div className={styles.routeStop}>
            <span className={styles.routeNumber}>01</span>
            <div><small>DESTINATION</small><strong>先定目标</strong><p>想完成什么作品？</p></div>
          </div>
          <div className={styles.routeStop}>
            <span className={styles.routeNumber}>02</span>
            <div><small>BACKCAST</small><strong>倒推能力</strong><p>作品需要哪些知识？</p></div>
          </div>
          <div className={styles.routeStop}>
            <span className={styles.routeNumber}>03</span>
            <div><small>MOVE</small><strong>主动学习</strong><p>在行动中建立连接。</p></div>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className={styles.editorialStair}>
      <div className={styles.stairHeading}><small>GOAL / BACKCASTING</small><strong>先看终点，<br />再决定今天学什么。</strong></div>
      <div className={styles.stairSteps}>
        <div className={styles.stairStep}><span>01</span><div><small>目标</small><strong>一个想完成的作品</strong></div></div>
        <div className={styles.stairStep}><span>02</span><div><small>倒推</small><strong>为了作品寻找知识</strong></div></div>
        <div className={styles.stairStep}><span>03</span><div><small>行动</small><strong>让知识形成系统</strong></div></div>
      </div>
    </div>
  );
}

function ConceptExplainer({ variant }: { variant: number }) {
  if (variant === 0) {
    return (
      <>
        <p className={styles.conceptIntro}>核心概念：<strong>系统观念学习法</strong></p>
        <div className={styles.nodeConcept}>
          <span className={styles.nodeOrb}><Spark small /></span>
          <div><p>知识在脑中只是数据；只有进入真实任务、经历试错与反馈，知识才会成为能力。</p></div>
        </div>
      </>
    );
  }
  return (
    <div className={styles.conceptFormula}>
      <small>A MEMORABLE MODEL</small>
      <div><strong>兴趣</strong><span>×</span><strong>行动</strong><span>×</span><strong>反馈</strong></div>
      <p>不是“先全部学会再开始”，而是在行动中建立知识连接。</p>
    </div>
  );
}

function Preview({ id, variant }: { id: ComponentId; variant: number }) {
  const content: Record<ComponentId, ReactNode> = {
    question_hook: <QuestionHook variant={variant} />,
    numbered_insight: <NumberedInsight variant={variant} />,
    evidence_callout: <EvidenceCallout variant={variant} />,
    before_after_timeline: <BeforeAfterTimeline variant={variant} />,
    logic_path: <LogicPath variant={variant} />,
    concept_explainer: <ConceptExplainer variant={variant} />,
  };
  return (
    <article className={styles.articleCanvas} aria-label={`${definitions.find((item) => item.id === id)?.name}预览`}>
      <div className={styles.articleMeta}><span>示例公众号 · 视觉片段</span><span>390 PX</span></div>
      {content[id]}
    </article>
  );
}

export default function ComponentGalleryPage() {
  const [variants, setVariants] = useState<Record<ComponentId, number>>(initialVariants);
  const [approved, setApproved] = useState<Partial<Record<ComponentId, number>>>({});
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const saved = window.localStorage.getItem("visual-director-component-review-v0.2");
    if (saved) {
      try { setApproved(JSON.parse(saved)); } catch { window.localStorage.removeItem("visual-director-component-review-v0.2"); }
    }
  }, []);

  const approvedCount = Object.keys(approved).length;
  const reviewSummary = useMemo(
    () => definitions.map((item) => ({
      component: item.id,
      decision: approved[item.id] === undefined ? "pending" : "candidate",
      variant: approved[item.id] === undefined ? null : item.variants[approved[item.id] ?? 0],
    })),
    [approved],
  );

  function chooseVariant(id: ComponentId, index: number) {
    setVariants((current) => ({ ...current, [id]: index }));
  }

  function toggleApproval(item: Definition) {
    const selected = variants[item.id];
    const next = { ...approved };
    if (next[item.id] === selected) delete next[item.id];
    else next[item.id] = selected;
    setApproved(next);
    window.localStorage.setItem("visual-director-component-review-v0.2", JSON.stringify(next));
    setNotice(next[item.id] === undefined ? `已撤销「${item.name}」入库标记` : `已记录「${item.name} · ${item.variants[selected]}」`);
    window.setTimeout(() => setNotice(""), 2200);
  }

  async function copyReview() {
    const payload = { schema_version: "component_review.v0.2", reviewed_at: new Date().toISOString(), decisions: reviewSummary };
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setNotice("评审结果已复制，可以直接粘贴给 Codex");
    window.setTimeout(() => setNotice(""), 2600);
  }

  return (
    <main className={styles.galleryPage}>
      <header className={styles.topbar}>
        <Link href="/" className={styles.backLink}><BackIcon />返回任务台</Link>
        <div className={styles.topbarTitle}><strong>组件画廊</strong><span>SEMANTIC LIBRARY / V0.2</span></div>
        <div className={styles.reviewCount}><span>{approvedCount}</span> / 6 已标记</div>
      </header>

      <section className={styles.hero}>
        <p className={styles.eyebrow}>VISUAL GRAMMAR, NOT ANOTHER TEMPLATE</p>
        <h1>不是把文字装进框，<br />而是让关系被看见。</h1>
        <p>六种高频语义，十二个原创变体。先评审视觉语言，再把通过的组件接入 Agent。</p>
        <dl className={styles.metrics}>
          <div><dt>语义组件</dt><dd>06</dd></div>
          <div><dt>原创变体</dt><dd>12</dd></div>
          <div><dt>内容宽度</dt><dd>390</dd></div>
        </dl>
      </section>

      <nav className={styles.jumpNav} aria-label="组件快速导航">
        {definitions.map((item) => <a href={`#${item.id}`} key={item.id}><span>{item.index}</span>{item.name}</a>)}
      </nav>

      <section className={styles.galleryList}>
        {definitions.map((item) => {
          const selected = variants[item.id];
          const isApproved = approved[item.id] === selected;
          const variables = { "--component-accent": item.accent, "--component-pale": item.pale } as CSSProperties;
          return (
            <section className={styles.componentRow} id={item.id} key={item.id} style={variables}>
              <div className={styles.componentBrief}>
                <div className={styles.componentIndex}>{item.index}</div>
                <p className={styles.componentEnglish}>{item.english}</p>
                <h2>{item.name}</h2>
                <p className={styles.purpose}>{item.purpose}</p>
                <div className={styles.useWhen}><span>适用内容</span><p>{item.useWhen}</p></div>
                <div className={styles.variantTabs} role="tablist" aria-label={`${item.name}变体`}>
                  {item.variants.map((variant, index) => (
                    <button
                      aria-selected={selected === index}
                      className={selected === index ? styles.activeVariant : ""}
                      key={variant}
                      onClick={() => chooseVariant(item.id, index)}
                      role="tab"
                      type="button"
                    ><span>{String.fromCharCode(65 + index)}</span>{variant}</button>
                  ))}
                </div>
                <button className={isApproved ? styles.approvedButton : styles.approveButton} onClick={() => toggleApproval(item)} type="button">
                  {isApproved ? <><CheckIcon />已标记为入库候选</> : "将当前变体标记为入库候选"}
                </button>
                {approved[item.id] !== undefined && !isApproved ? <p className={styles.previousChoice}>已记录：{item.variants[approved[item.id] ?? 0]}</p> : null}
              </div>
              <div className={styles.previewStage}>
                <div className={styles.ruler}><span>0</span><i /><span>390</span></div>
                <Preview id={item.id} variant={selected} />
              </div>
            </section>
          );
        })}
      </section>

      <section className={styles.reviewPanel}>
        <div><p>REVIEW CHECKPOINT</p><h2>先选择，再接入 Agent。</h2></div>
        <p>建议至少标记 4 类。没有合适变体的组件保持未选择，并把原因告诉我。</p>
        <button disabled={approvedCount === 0} onClick={copyReview} type="button">复制评审结果</button>
      </section>

      {notice ? <div className={styles.toast} role="status">{notice}</div> : null}
    </main>
  );
}
