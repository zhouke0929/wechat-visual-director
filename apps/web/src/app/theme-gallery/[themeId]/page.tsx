"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { getThemeGallery } from "@/lib/api";
import type { ThemeGalleryItem } from "@/lib/types";
import styles from "./theme-detail.module.css";

type Decision = "approved" | "revise" | "rejected";
type ReviewState = {
  theme?: Decision;
  components: Record<string, Decision>;
  primitives: Record<string, Decision>;
};

const decisionLabels: Record<Decision, string> = {
  approved: "通过",
  revise: "需修改",
  rejected: "淘汰",
};

function reviewKey(themeId: string) {
  return `wechat-visual-director:theme-review:${themeId}:v0.2`;
}

function readReview(themeId: string): ReviewState {
  if (typeof window === "undefined") return { components: {}, primitives: {} };
  try {
    const stored = JSON.parse(localStorage.getItem(reviewKey(themeId)) ?? '{"components":{},"primitives":{}}') as Partial<ReviewState>;
    return { ...stored, components: stored.components ?? {}, primitives: stored.primitives ?? {} };
  } catch {
    return { components: {}, primitives: {} };
  }
}

export default function ThemeDetailPage() {
  const params = useParams<{ themeId: string }>();
  const themeId = params.themeId;
  const [themes, setThemes] = useState<ThemeGalleryItem[]>([]);
  const [mode, setMode] = useState<"article" | "components">("article");
  const [review, setReview] = useState<ReviewState>({ components: {}, primitives: {} });
  const [error, setError] = useState("");

  useEffect(() => {
    getThemeGallery().then(setThemes).catch((reason: Error) => setError(reason.message));
    setReview(readReview(themeId));
  }, [themeId]);

  const theme = useMemo(() => themes.find((item) => item.id === themeId), [themeId, themes]);

  function saveReview(next: ReviewState) {
    setReview(next);
    localStorage.setItem(reviewKey(themeId), JSON.stringify(next));
  }

  function decideComponent(componentType: string, decision: Decision) {
    saveReview({
      ...review,
      components: { ...review.components, [componentType]: decision },
    });
  }

  function decidePrimitive(role: string, decision: Decision) {
    saveReview({
      ...review,
      primitives: { ...review.primitives, [role]: decision },
    });
  }

  function exportReview() {
    if (!theme) return;
    const payload = {
      schema_version: "theme_review.v0.2",
      reviewed_at: new Date().toISOString(),
      theme_id: theme.id,
      theme_label: theme.label,
      theme_decision: review.theme ?? "pending",
      component_decisions: theme.components.map((component) => ({
        component_type: component.component_type,
        variant: component.variant,
        decision: review.components[component.component_type] ?? "pending",
      })),
      primitive_decisions: theme.rhythm_primitives.map((primitive) => ({
        role: primitive.role,
        decision: review.primitives[primitive.role] ?? "pending",
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${theme.id}-theme-review.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (error) return <main className={styles.statePage}><p>{error}</p><Link href="/theme-gallery">返回主题样本册</Link></main>;
  if (!theme) return <main className={styles.statePage}>正在展开主题样张……</main>;

  const reviewedCount = Object.keys(review.components).length + Object.keys(review.primitives).length;
  const reviewTotal = theme.components.length + theme.rhythm_primitives.length;

  return (
    <main className={styles.page} style={{ "--theme-primary": theme.palette[0], "--theme-accent": theme.palette[2] } as React.CSSProperties}>
      <header className={styles.topbar}>
        <Link href="/theme-gallery">← 六主题总览</Link>
        <div>
          <strong>{theme.label}</strong>
          <span>{theme.english}</span>
        </div>
        <span>{reviewedCount} / {reviewTotal} 已评</span>
      </header>

      <section className={styles.masthead}>
        <div className={styles.themeIntro}>
          <p>THEME PROOF / {theme.id.toUpperCase()}</p>
          <h1>{theme.label}</h1>
          <p>{theme.description}</p>
          <div className={styles.palette}>
            {theme.palette.map((color) => <i key={color} style={{ backgroundColor: color }} />)}
          </div>
          <div className={styles.tags}>
            {theme.ideal_for.map((item) => <span key={item}>{item}</span>)}
          </div>
        </div>
        <aside className={styles.reviewGuide}>
          <span>评审顺序</span>
          <ol>
            <li>先看整篇是否协调、有呼吸感</li>
            <li>再检查六类节奏部件和八个语义组件</li>
            <li>最后给出主题整体结论</li>
          </ol>
        </aside>
      </section>

      <nav className={styles.modeSwitch} aria-label="评审视图">
        <button className={mode === "article" ? styles.active : ""} onClick={() => setMode("article")}>01　整篇协调性</button>
        <button className={mode === "components" ? styles.active : ""} onClick={() => setMode("components")}>02　主题部件库</button>
      </nav>

      {mode === "article" ? (
        <section className={styles.articleReview}>
          <div className={styles.articleNotes}>
            <span>WHOLE ARTICLE FIRST</span>
            <h2>先判断主题，<br />不要先挑卡片。</h2>
            <p>这篇样稿故意穿插正文和八类组件，用来检查长文章里的节奏是否自然，以及组件是否显得刻意堆砌。</p>
            <dl>
              <div><dt>正文宽度</dt><dd>390 px</dd></div>
              <div><dt>主题部件</dt><dd>{reviewTotal}</dd></div>
              <div><dt>渲染来源</dt><dd>真实后端</dd></div>
            </dl>
          </div>
          <div className={styles.phoneStage}>
            <div className={styles.ruler}><span>390</span><i /><span>MOBILE CONTENT WIDTH</span></div>
            <article className={styles.phone} dangerouslySetInnerHTML={{ __html: theme.full_preview_html }} />
          </div>
        </section>
      ) : (
        <section className={styles.specimenList}>
          <header className={styles.libraryDivider}>
            <span>RHYTHM PRIMITIVES / 01</span>
            <h2>先看文章骨架，再看强调组件。</h2>
            <p>标题、行内强调、图文位置、分割线和页尾共同决定整篇节奏；它们不消费原文事实。</p>
          </header>
          {theme.rhythm_primitives.map((primitive, index) => {
            const decision = review.primitives[primitive.role];
            return (
              <article className={styles.specimen} key={primitive.role}>
                <div className={styles.specimenInfo}>
                  <span>R{String(index + 1).padStart(2, "0")} / {primitive.role}</span>
                  <h2>{primitive.label}</h2>
                  <p>正式链路已接入 · {primitive.production_trigger}</p>
                  <div className={styles.decisionGroup}>
                    {(["approved", "revise", "rejected"] as Decision[]).map((value) => (
                      <button
                        className={decision === value ? styles.selectedDecision : ""}
                        key={value}
                        onClick={() => decidePrimitive(primitive.role, value)}
                      >
                        {decisionLabels[value]}
                      </button>
                    ))}
                  </div>
                </div>
                <div className={styles.componentStage}>
                  <div className={styles.componentCanvas} dangerouslySetInnerHTML={{ __html: primitive.html }} />
                </div>
              </article>
            );
          })}
          <header className={styles.libraryDivider}>
            <span>SEMANTIC COMPONENTS / 02</span>
            <h2>八类组件，八种不同轮廓。</h2>
            <p>组件只组织原文中已经存在的关系；不添加口号，不把每段正文都变成卡片。</p>
          </header>
          {theme.components.map((component, index) => {
            const decision = review.components[component.component_type];
            return (
              <article className={styles.specimen} key={component.component_type}>
                <div className={styles.specimenInfo}>
                  <span>{String(index + 1).padStart(2, "0")} / {component.component_type}</span>
                  <h2>{component.label}</h2>
                  <p>{component.variant_label}</p>
                  <div className={styles.decisionGroup}>
                    {(["approved", "revise", "rejected"] as Decision[]).map((value) => (
                      <button
                        className={decision === value ? styles.selectedDecision : ""}
                        key={value}
                        onClick={() => decideComponent(component.component_type, value)}
                      >
                        {decisionLabels[value]}
                      </button>
                    ))}
                  </div>
                </div>
                <div className={styles.componentStage}>
                  <div className={styles.componentCanvas} dangerouslySetInnerHTML={{ __html: component.html }} />
                </div>
              </article>
            );
          })}
        </section>
      )}

      <section className={styles.finalReview}>
        <div>
          <span>THEME DECISION</span>
          <h2>给「{theme.label}」一个整体结论</h2>
          <p>组件逐项意见会保存在当前电脑；导出 JSON 后可以直接交给开发继续修改。</p>
        </div>
        <div className={styles.themeDecisions}>
          {(["approved", "revise", "rejected"] as Decision[]).map((value) => (
            <button
              className={review.theme === value ? styles.selectedDecision : ""}
              key={value}
              onClick={() => saveReview({ ...review, theme: value })}
            >
              {decisionLabels[value]}
            </button>
          ))}
          <button className={styles.exportButton} onClick={exportReview}>导出评审 JSON</button>
        </div>
      </section>
    </main>
  );
}
