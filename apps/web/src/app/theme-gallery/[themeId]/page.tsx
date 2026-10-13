"use client";

import Link, { useRouteParam } from "@/lib/router";
import { useEffect, useMemo, useState } from "react";
import { getThemeGallery } from "@/lib/api";
import type { ThemeGalleryItem } from "@/lib/types";
import { themeCoverageLabel, themeRoleLabel } from "@/lib/theme-coverage";
import { PREVIEW_BODY_PADDING_X, PREVIEW_PROFILES } from "@/lib/preview-profiles";
import styles from "./theme-detail.module.css";

const compatibilityLabel = (status: string) => {
  if (status === "wechat_verified") return "公众号已验证";
  if (status === "candidate_theme_lab") return "主题实验 · 待验证";
  return "公众号候选 · 待验证";
};

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
  if (theme.availability === "unavailable") return <main className={styles.statePage}>
    <h1>{theme.label} · 暂不可用</h1><p>{theme.diagnostic?.message}</p>
    <p>请让 Agent 修复后重新导入；原主题文件保留，其他主题不受影响。</p>
    <Link href="/theme-gallery">返回主题样本册</Link>
  </main>;

  const foundations = theme.foundation_specimens ?? theme.rhythm_primitives;
  const specimenTotal = theme.components.length + foundations.length;
  const coverage = theme.delivery_report?.coverage;
  const isPartial = coverage?.status === "partial";

  return (
    <main className={styles.page} style={{ "--theme-primary": theme.palette[0], "--theme-accent": theme.palette[2], "--gallery-viewport-width": `${PREVIEW_PROFILES.mobile.viewport_width}px`, "--gallery-body-padding": `${PREVIEW_BODY_PADDING_X}px` } as React.CSSProperties}>
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
          {coverage && (
            <section className={styles.deliveryNote} aria-label="主题完整性">
              <strong>{themeCoverageLabel(coverage)}</strong>
              {isPartial ? <>
                <p>这是尚未完成的主题试样，预览混合了已设计布局与默认样式。请让 Agent 补齐后再作为完整主题使用。</p>
                <p>待设计：{coverage.missing_roles.map(themeRoleLabel).join("、")}。</p>
              </> : <p>{coverage.status === "complete" ? "全部布局角色已有声明；视觉效果仍需整体复核，微信保存效果需单独实测。" : "此主题使用基础样式进行气质调整，不代表重新设计了整套布局。"}</p>}
            </section>
          )}
          <p>{theme.description}</p>
          <div className={styles.palette}>
            {theme.palette.map((color) => <i key={color} style={{ backgroundColor: color }} />)}
          </div>
          <div className={styles.tags}>
            {theme.ideal_for.map((item) => <span key={item}>{item}</span>)}
          </div>
          {theme.delivery_report && (
            <section className={styles.deliveryNote} aria-label="主题交付检查">
              <strong>{theme.delivery_report.rehearsal.status === "blocking" ? "交付检查发现问题" : theme.delivery_report.rehearsal.status === "pass" ? "已声明布局的本地编译检查通过" : "沿用基础主题交付结构"}</strong>
              <p>{theme.delivery_report.capabilities.raster_decoration?.length ? "装饰使用高清图片，正文保持可编辑。" : "正文与主题结构保持独立。"}微信保存后的实际效果尚待核对。</p>
              {theme.delivery_report.findings.length > 0 && (
                <p>本轮重点：{Array.from(new Set(theme.delivery_report.findings.map((item) => ({ fixed_label_review: "固定标签与正文含义", gradient_edge: "凹口边缘", rotated_layout: "旋转位置", surface_shadow: "阴影", overlap_spacing: "错位留白" }[item.code] || item.code)))).join("、")}。</p>
              )}
              <p>保存草稿后重新打开，再检查手机预览；仅粘贴成功不代表验证完成。</p>
              {!!theme.delivery_report.design_review?.unchanged_template_roles.length && <p>仍有 {theme.delivery_report.design_review.unchanged_template_roles.length} 个布局与字段模板一致，请核对是否为有意保留的简洁设计，不能仅凭布局齐全认定视觉完成。</p>}
            </section>
          )}
        </div>
        <aside className={styles.reviewGuide}>
          <span>浏览方式</span>
          <ol>
            <li>先看整篇样张，感受标题、正文与留白节奏</li>
            <li>再浏览 {foundations.length} 种基础样式与 {theme.components.length} 类语义组件，理解它们各自的触发条件</li>
            <li>实际文章会根据原文语义选用其中一部分，不会全部堆叠</li>
          </ol>
        </aside>
      </section>

      <nav className={styles.modeSwitch} aria-label="主题展示视图">
        <button className={mode === "article" ? styles.active : ""} onClick={() => setMode("article")}>01　{isPartial ? "试样预览（含默认样式）" : "整篇样张"}</button>
        <button className={mode === "components" ? styles.active : ""} onClick={() => setMode("components")}>02　主题部件库</button>
      </nav>

      {mode === "article" ? (
        <section className={styles.articleReview}>
          <div className={styles.articleNotes}>
            <span>WHOLE ARTICLE VIEW</span>
            <h2>先看整篇节奏，<br />再认识局部组件。</h2>
            <p>{isPartial ? "本页用于检查阶段性效果，尚未覆盖的角色仍显示默认样式，并非完整主题成品。" : "公开样张由正式文章渲染器生成，展示正文、引用、列表、图文和少量语义组件的真实阅读节奏。全部部件请在部件库中查看。"}</p>
            <dl>
              <div><dt>手机视口</dt><dd>{PREVIEW_PROFILES.mobile.viewport_width} px</dd></div>
              <div><dt>正文净宽</dt><dd>{PREVIEW_PROFILES.mobile.content_width} px · 两侧各 {PREVIEW_BODY_PADDING_X} px</dd></div>
              <div><dt>展示部件</dt><dd>{specimenTotal}</dd></div>
              <div><dt>渲染方式</dt><dd>正式组件库</dd></div>
            </dl>
          </div>
          <div className={styles.phoneStage}>
            <div className={styles.ruler}><span>{PREVIEW_PROFILES.mobile.viewport_width}</span><i /><span>WORKBENCH MOBILE VIEWPORT</span></div>
            <article className={styles.phone} dangerouslySetInnerHTML={{ __html: theme.article_preview_html ?? theme.full_preview_html }} />
          </div>
        </section>
      ) : (
        <section className={styles.specimenList}>
          <nav className={styles.componentIndex} aria-label="全部部件索引">
            <strong>基础样式</strong>
            {foundations.map((item) => <a key={item.role} href={`#foundation-${item.role}`}>{item.label}</a>)}
            <strong>语义组件</strong>
            {theme.components.map((item) => <a key={item.component_type} href={`#component-${item.component_type}`}>{item.label}</a>)}
          </nav>
          <header className={styles.libraryDivider}>
            <span>RHYTHM PRIMITIVES / 01</span>
            <h2>文章骨架与阅读节奏。</h2>
            <p>包含普通引用、有序与无序列表、表格和来源说明等真实正文样式。它们与强调语义组件不同，不再隐藏在整篇样张里。</p>
          </header>
          {foundations.map((primitive, index) => (
            <article className={styles.specimen} id={`foundation-${primitive.role}`} key={primitive.role}>
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
            <h2>十二类语义，覆盖完整内容关系。</h2>
            <p>每个组件都标明触发语义与公众号兼容状态；真实文章只选择原文需要的部分，不会为了装饰机械套用。</p>
          </header>
          {theme.components.map((component, index) => (
            <article className={styles.specimen} id={`component-${component.component_type}`} key={component.component_type}>
              <div className={styles.specimenInfo}>
                <span>{String(index + 1).padStart(2, "0")} / {component.component_type}</span>
                <h2>{component.label}</h2>
                <p className={styles.variantName}>{component.variant_label}</p>
                <span className={`${styles.compatibilityBadge} ${component.status === "wechat_verified" ? styles.verifiedBadge : styles.candidateBadge}`}>
                  {compatibilityLabel(component.status)}
                </span>
                <dl className={styles.componentGuide}>
                  <div><dt>它解决什么</dt><dd>{component.purpose}</dd></div>
                  <div><dt>何时触发</dt><dd>{component.use_when}</dd></div>
                </dl>
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
