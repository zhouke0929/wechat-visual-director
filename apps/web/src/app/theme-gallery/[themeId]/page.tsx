"use client";

import Link, { useRouteParam } from "@/lib/router";
import { useEffect, useMemo, useState } from "react";
import { getThemeGallery } from "@/lib/api";
import type { ThemeGalleryItem } from "@/lib/types";
import styles from "./theme-detail.module.css";

export default function ThemeDetailPage() {
  const themeId = useRouteParam("theme-gallery");
  const [themes, setThemes] = useState<ThemeGalleryItem[]>([]);
  const [mode, setMode] = useState<"article" | "components">("article");
  const [error, setError] = useState("");

  useEffect(() => {
    getThemeGallery().then(setThemes).catch((reason: Error) => setError(reason.message));
  }, []);

  const theme = useMemo(() => themes.find((item) => item.id === themeId), [themeId, themes]);

  if (error) return <main className={styles.statePage}><p>{error}</p><Link href="/theme-gallery">返回主题样本册</Link></main>;
  if (!theme) return <main className={styles.statePage}>正在展开主题样张……</main>;

  const specimenTotal = theme.components.length + theme.rhythm_primitives.length;

  return (
    <main className={styles.page} style={{ "--theme-primary": theme.palette[0], "--theme-accent": theme.palette[2] } as React.CSSProperties}>
      <header className={styles.topbar}>
        <Link href="/theme-gallery">← 主题总览</Link>
        <div>
          <strong>{theme.label}</strong>
          <span>{theme.english}</span>
        </div>
        <span>{specimenTotal} 个展示部件</span>
      </header>

      <section className={styles.masthead}>
        <div className={styles.themeIntro}>
          <p>THEME LIBRARY / {theme.id.toUpperCase()}</p>
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
          <span>浏览方式</span>
          <ol>
            <li>先看整篇样张，感受标题、正文与留白节奏</li>
            <li>再浏览主题部件，了解同一设计语言如何组织不同内容</li>
            <li>实际文章会根据原文语义选用其中一部分，不会全部堆叠</li>
          </ol>
        </aside>
      </section>

      <nav className={styles.modeSwitch} aria-label="主题展示视图">
        <button className={mode === "article" ? styles.active : ""} onClick={() => setMode("article")}>01　整篇样张</button>
        <button className={mode === "components" ? styles.active : ""} onClick={() => setMode("components")}>02　主题部件库</button>
      </nav>

      {mode === "article" ? (
        <section className={styles.articleReview}>
          <div className={styles.articleNotes}>
            <span>WHOLE ARTICLE VIEW</span>
            <h2>先看整篇节奏，<br />再认识局部组件。</h2>
            <p>完整样张展示这套主题在长文章中的标题层级、行内强调、图片节奏、语义组件和品牌页尾。</p>
            <dl>
              <div><dt>正文宽度</dt><dd>390 px</dd></div>
              <div><dt>展示部件</dt><dd>{specimenTotal}</dd></div>
              <div><dt>渲染方式</dt><dd>正式组件库</dd></div>
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
            <h2>文章骨架与阅读节奏。</h2>
            <p>标题、行内强调、图文位置、分割线和页尾共同形成主题气质；它们不会改写原文事实。</p>
          </header>
          {theme.rhythm_primitives.map((primitive, index) => (
            <article className={styles.specimen} key={primitive.role}>
              <div className={styles.specimenInfo}>
                <span>R{String(index + 1).padStart(2, "0")} / {primitive.role}</span>
                <h2>{primitive.label}</h2>
                <p>{primitive.production_trigger}</p>
              </div>
              <div className={styles.componentStage}>
                <div className={styles.componentCanvas} dangerouslySetInnerHTML={{ __html: primitive.html }} />
              </div>
            </article>
          ))}
          <header className={styles.libraryDivider}>
            <span>SEMANTIC COMPONENTS / 02</span>
            <h2>八类语义，八种内容轮廓。</h2>
            <p>组件只组织原文已经存在的关系；真实文章根据内容选择，不会为了装饰机械套用。</p>
          </header>
          {theme.components.map((component, index) => (
            <article className={styles.specimen} key={component.component_type}>
              <div className={styles.specimenInfo}>
                <span>{String(index + 1).padStart(2, "0")} / {component.component_type}</span>
                <h2>{component.label}</h2>
                <p>{component.variant_label}</p>
              </div>
              <div className={styles.componentStage}>
                <div className={styles.componentCanvas} dangerouslySetInnerHTML={{ __html: component.html }} />
              </div>
            </article>
          ))}
        </section>
      )}

      <section className={styles.finalReview}>
        <div>
          <span>THEME AT A GLANCE</span>
          <h2>「{theme.label}」适合这些文章</h2>
          <p>{theme.ideal_for.join("、")}。任务工作台会结合文章类型和最近五篇主题历史推荐，但始终允许人工切换。</p>
        </div>
        <Link className={styles.browseReturn} href="/theme-gallery">继续浏览其他主题 →</Link>
      </section>
    </main>
  );
}
