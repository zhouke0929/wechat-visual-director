"use client";

import Link, { useRouteParam } from "@/lib/router";
import { WorkspacePageIntro } from "@/components/workspace-page";
import { WorkbenchHeader } from "@/components/workbench-header";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { getThemeGallery } from "@/lib/api";
import type { ThemeGalleryItem } from "@/lib/types";
import { themeCoverageLabel, themeRoleLabel } from "@/lib/theme-coverage";
import { PREVIEW_BODY_PADDING_X, PREVIEW_PROFILES } from "@/lib/preview-profiles";
import styles from "./theme-detail.module.css";

export default function ThemeDetailPage() {
  const themeId = useRouteParam("theme-gallery");
  const [themes, setThemes] = useState<ThemeGalleryItem[]>([]);
  const [mode, setMode] = useState<"article" | "components">("article");
  const [error, setError] = useState("");
  const modeSwitch = useRef<HTMLElement>(null);

  useLayoutEffect(() => { window.scrollTo(0, 0); }, [themeId]);

  useEffect(() => {
    let ignore = false;
    setError("");
    getThemeGallery(themeId).then((items) => {
      if (ignore) return;
      setThemes(items);
      if (!items.some((item) => item.id === themeId)) setError("没有找到这个主题。");
    }).catch((reason: Error) => { if (!ignore) setError(reason.message); });
    return () => { ignore = true; };
  }, [themeId]);

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
  const roundtripChecked = theme.wechat_acceptance?.status === "owner_reported_pass";
  const report = theme.delivery_report;
  const isBlocking = report?.rehearsal.status === "blocking";

  function switchMode(nextMode: typeof mode) {
    if (nextMode === mode) return;
    const tabs = modeSwitch.current;
    if (tabs) {
      const stickyTop = parseFloat(getComputedStyle(tabs).top);
      const introBottom = tabs.previousElementSibling?.getBoundingClientRect().bottom;
      if (introBottom !== undefined && introBottom < stickyTop) {
        window.scrollTo(0, window.scrollY + introBottom - stickyTop);
      }
    }
    setMode(nextMode);
  }

  return (
    <main className={`workspace-page ${styles.page}`} style={{ "--theme-primary": theme.palette[0], "--gallery-viewport-width": `${PREVIEW_PROFILES.mobile.viewport_width}px`, "--gallery-body-padding": `${PREVIEW_BODY_PADDING_X}px` } as React.CSSProperties}>
      <WorkbenchHeader current="/theme-gallery" detail />
      <div>
        <WorkspacePageIntro eyebrow="THEME SPECIMEN" title={theme.label} description={theme.description}>
          <aside className={styles.themeMeta}>
            <div className={styles.palette}>
              {theme.palette.map((color, i) => <i key={i} style={{ backgroundColor: color }} />)}
            </div>
            <p>{theme.ideal_for.join(" · ")}</p>
          </aside>
        </WorkspacePageIntro>
        {(isPartial || isBlocking) && (
          <p className={styles.warning}>
            {isBlocking && "交付检查发现问题。"}
            {isPartial && "这是未完成的主题试样，部分部件仍使用默认样式。"}
            <a href="#theme-delivery">查看检查信息 ↓</a>
          </p>
        )}
      </div>

      <nav ref={modeSwitch} className={styles.modeSwitch} aria-label="主题展示视图">
        <button type="button" aria-pressed={mode === "article"} className={mode === "article" ? styles.active : ""} onClick={() => switchMode("article")}>01　{isPartial ? "试样预览（含默认样式）" : "整篇样张"}</button>
        <button type="button" aria-pressed={mode === "components"} className={mode === "components" ? styles.active : ""} onClick={() => switchMode("components")}>02　主题部件库</button>
      </nav>

      {mode === "article" ? (
        <section className={styles.articleReview} aria-label="整篇样张">
          <div className={styles.phoneStage}>
            <div className={styles.ruler}><span>手机预览</span><i /><span>{PREVIEW_PROFILES.mobile.viewport_width} px 参考视口</span></div>
            <article className={styles.phone} dangerouslySetInnerHTML={{ __html: theme.article_preview_html ?? theme.full_preview_html }} />
          </div>
        </section>
      ) : (
        <section className={styles.specimenList}>
          <details className={styles.indexDisclosure}>
            <summary>部件索引 · {specimenTotal} 个</summary>
            <nav className={styles.componentIndex} aria-label="全部部件索引">
              <strong>基础样式</strong>
              {foundations.map((item) => <a key={item.role} href={`#foundation-${item.role}`}>{item.label}</a>)}
              <strong>语义组件</strong>
              {theme.components.map((item) => <a key={item.component_type} href={`#component-${item.component_type}`}>{item.label}</a>)}
            </nav>
          </details>
          <div className={styles.specimenGrid}>
            <header className={styles.libraryDivider}>
              <span>RHYTHM PRIMITIVES / 01</span>
              <h2>基础样式 <small>{foundations.length} 个</small></h2>
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
              <h2>语义组件 <small>{theme.components.length} 个</small></h2>
            </header>
            {theme.components.map((component, index) => (
              <article className={styles.specimen} id={`component-${component.component_type}`} key={component.component_type}>
                <div className={styles.specimenInfo}>
                  <span>{String(index + 1).padStart(2, "0")} / {component.component_type}</span>
                  <h2>{component.label}</h2>
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
          </div>
        </section>
      )}

      <section className={styles.finalReview}>
        {report && (
          <details id="theme-delivery" className={styles.deliveryNote} open={isBlocking || isPartial || undefined}>
            <summary>主题交付检查{coverage ? ` · ${themeCoverageLabel(coverage)}` : ""}</summary>
            {isPartial && <p>待设计：{coverage.missing_roles.map(themeRoleLabel).join("、")}。</p>}
            <p>{isBlocking ? "交付检查发现问题。" : report.rehearsal.status === "pass" ? "已声明布局的本地编译检查通过。" : "沿用基础主题交付结构。"}</p>
            <p>{report.capabilities.raster_decoration?.length ? "装饰使用高清图片，正文保持可编辑。" : "正文与主题结构保持独立。"}{roundtripChecked ? "该版验收稿已通过复制粘贴和 API 保存实测。" : "微信保存后的实际效果尚待核对。"}</p>
            {report.findings.length > 0 && (
              <p>本轮重点：{Array.from(new Set(report.findings.map((item) => ({ fixed_label_review: "固定标签与正文含义", gradient_edge: "凹口边缘", rotated_layout: "旋转位置", surface_shadow: "阴影", overlap_spacing: "错位留白" }[item.code] || item.code)))).join("、")}。</p>
            )}
            <p>保存草稿后重新打开，再检查手机预览；仅粘贴成功不代表验证完成。</p>
            {!!report.design_review?.unchanged_template_roles.length && <p>仍有 {report.design_review.unchanged_template_roles.length} 个布局与字段模板一致，请核对是否为有意保留的简洁设计，不能仅凭布局齐全认定视觉完成。</p>}
          </details>
        )}
        <Link className={`workspace-button ${styles.browseReturn}`} href="/theme-gallery">继续浏览其他主题 →</Link>
      </section>
    </main>
  );
}
