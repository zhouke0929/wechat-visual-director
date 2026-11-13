"use client";

import { themeCoverageLabel } from "@/lib/theme-coverage";
import { groupThemes, themeGroupLabel } from "@/lib/theme-groups";
import { WorkspacePageIntro } from "@/components/workspace-page";
import { WorkbenchHeader } from "@/components/workbench-header";

import Link from "@/lib/router";
import { ChangeEvent, MouseEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { deleteThemePack, getThemeGallerySummary, installThemePack, themePackExportUrl } from "@/lib/api";
import type { ThemeGallerySummary } from "@/lib/types";
import styles from "./theme-gallery.module.css";

export default function ThemeGalleryPage() {
  const [themes, setThemes] = useState<ThemeGallerySummary[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activeCollection, setActiveCollection] = useState<"official" | "custom">("official");
  const [activeGroup, setActiveGroup] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useLayoutEffect(() => { window.scrollTo(0, 0); }, []);

  const refresh = async () => {
    const collection = await getThemeGallerySummary();
    setThemes(collection);
    setLoaded(true);
    return collection;
  };

  useEffect(() => {
    refresh().catch((reason: Error) => setError(reason.message));
  }, []);

  const officialThemes = useMemo(() => themes.filter((theme) => theme.source !== "custom"), [themes]);
  const customThemes = useMemo(() => themes.filter((theme) => theme.source === "custom" && theme.availability !== "unavailable"), [themes]);
  const unavailableThemes = useMemo(() => themes.filter((theme) => theme.availability === "unavailable"), [themes]);
  const officialGroups = useMemo(() => groupThemes(officialThemes), [officialThemes]);
  const collectionThemes = activeCollection === "official" ? officialThemes : customThemes;
  const visibleThemes = activeCollection === "official" && activeGroup
    ? officialGroups.find((group) => group.label === activeGroup)?.options ?? officialThemes
    : collectionThemes;

  const handleInstall = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const installed = await installThemePack(file);
      const collection = await refresh();
      setActiveCollection("custom");
      const coverage = collection.find((theme) => theme.id === installed.id)?.delivery_report?.coverage;
      setNotice(coverage?.status === "partial"
        ? `${installed.name} 已安装为未完成试样（${coverage.covered_count}/${coverage.total_count}），请让 Agent 补齐剩余布局。`
        : `${installed.name} 已通过本地交付检查并安装到本机，请查看整篇视觉效果；微信保存效果仍需单独核对。`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "主题扩展包安装失败");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (event: MouseEvent, theme: ThemeGallerySummary) => {
    event.preventDefault();
    event.stopPropagation();
    if (!window.confirm(`从本机删除“${theme.label}”？文章内容不会被删除。`)) return;
    setBusy(true);
    try {
      await deleteThemePack(theme.id);
      await refresh();
      setNotice(`${theme.label} 已从本机主题库移除。`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除失败");
    } finally {
      setBusy(false);
    }
  };

  const handleExport = (event: MouseEvent, theme: ThemeGallerySummary) => {
    event.preventDefault();
    event.stopPropagation();
    window.location.href = themePackExportUrl(theme.id);
  };

  const foundationCount = (theme: ThemeGallerySummary) => theme.foundation_count ?? (theme.foundation_specimens ?? theme.rhythm_primitives)?.length ?? 0;
  return (
    <main className={`workspace-page ${styles.page}`}>
      <WorkbenchHeader current="/theme-gallery" />
      <WorkspacePageIntro eyebrow="THEME LIBRARY" title="主题样本册" description="选一套主题，查看整篇样张与排版部件。" />

      <nav className={styles.collections} aria-label="主题集合">
        <div className={styles.collectionTabs}>
          <button
            className={activeCollection === "official" ? styles.activeCollection : ""}
            aria-pressed={activeCollection === "official"}
            onClick={() => setActiveCollection("official")}
            type="button"
          >
            官方主题 <span>{officialThemes.length}</span>
          </button>
          <button
            className={activeCollection === "custom" ? styles.activeCollection : ""}
            aria-pressed={activeCollection === "custom"}
            onClick={() => setActiveCollection("custom")}
            type="button"
          >
            我的主题 <span>{customThemes.length}</span>
          </button>
        </div>
        <div className={styles.importControl}>
          <input
            accept=".json,.zip,.vdtheme,application/json,application/zip"
            onChange={handleInstall}
            ref={fileInput}
            type="file"
          />
          <button className="workspace-button" disabled={busy} onClick={() => fileInput.current?.click()} type="button" title="仅接收声明式主题扩展包，不执行 CSS 或脚本">
            {busy ? "正在校验…" : "导入主题扩展包"}
          </button>
        </div>
      </nav>

      {error ? <p className={styles.error}>{error}</p> : null}
      {notice ? <p className={styles.notice}>{notice}</p> : null}
      {unavailableThemes.length > 0 && <section className={styles.error} role="status" aria-label="暂不可用的主题">
        <strong>{unavailableThemes.length} 个自定义主题暂不可用，正常主题仍可浏览。</strong>
        <ul>{unavailableThemes.map((theme) => <li key={theme.id}>{theme.label}：{theme.diagnostic?.message}（{theme.diagnostic?.code}）</li>)}</ul>
        <p>请让 Agent 检查这些主题并修复后重新导入；原文件没有被自动删除。</p>
      </section>}
      {!error && !loaded ? <p className={styles.loading}>正在装订主题样本……</p> : null}

      {activeCollection === "custom" && loaded && !error && customThemes.length === 0 ? (
        <section className={styles.emptyCollection}>
          <span>YOUR VISUAL DNA / 00</span>
          <h2>这里会收纳你自己的阅读气质。</h2>
          <p>
            推荐给已安装 Skill 的 Agent 喜欢的组件截图，更容易对齐风格；没有图也可描述需求探索。它会寻找具体参考、联想并延展整套视觉语言；完成的扩展包可在这里浏览、导入和导出，再用于真实文章。
          </p>
          <button className="workspace-button workspace-button-primary" disabled={busy} onClick={() => fileInput.current?.click()} type="button">导入第一套主题</button>
        </section>
      ) : null}

      {activeCollection === "official" && officialGroups.length > 1 && (
        <div className={styles.groupBar}>
          <div className={styles.groupFilters} role="group" aria-label="按主题分组筛选">
            <button type="button" aria-pressed={!activeGroup} onClick={() => setActiveGroup("")}>全部</button>
            {officialGroups.map(({ label }) => (
              <button type="button" key={label} aria-pressed={activeGroup === label} onClick={() => setActiveGroup(label)}>{label}</button>
            ))}
          </div>
          <span role="status">{visibleThemes.length} 套</span>
        </div>
      )}

      {visibleThemes.length > 0 && <section className={styles.themeGrid} aria-label={`${activeCollection === "official" ? "官方" : "我的"}视觉主题`}>
        {visibleThemes.map((theme, index) => (
          <article className={styles.themeCard} key={theme.id}>
            <Link className={styles.cardLink} href={`/theme-gallery/${theme.id}`}>
              <div className={styles.cardTop}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <small>{theme.source === "custom" ? "我的主题" : themeGroupLabel(theme)}</small>
              </div>
              <div className={styles.palette} aria-label={`${theme.label}色板`}>
                {theme.palette.map((color, i) => <i key={i} style={{ backgroundColor: color }} />)}
              </div>
              <h2>{theme.label}</h2>
              {theme.delivery_report?.coverage && <p className={styles.coverage}>{themeCoverageLabel(theme.delivery_report.coverage)}</p>}
              <p className={styles.description}>{theme.description}</p>
              <p className={styles.cardTags}>{theme.ideal_for.join(" · ")}</p>
              {theme.source !== "custom" && (
                <div className={styles.cardFooter}>
                  <span>{foundationCount(theme) + theme.semantic_component_count} 个部件</span>
                  <span className={styles.detailLink}>查看样张 →</span>
                </div>
              )}
            </Link>
            {theme.source === "custom" && (
              <footer className={styles.cardFooter}>
                <span>{foundationCount(theme) + theme.semantic_component_count} 个部件</span>
                <div className={styles.cardActions}>
                  <button onClick={(event) => handleExport(event, theme)} type="button">导出</button>
                  <button disabled={busy} onClick={(event) => handleDelete(event, theme)} type="button">删除</button>
                  <Link className={styles.detailLink} href={`/theme-gallery/${theme.id}`}>{theme.delivery_report?.coverage?.status === "partial" ? "查看试样 →" : "查看主题 →"}</Link>
                </div>
              </footer>
            )}
          </article>
        ))}
      </section>}
    </main>
  );
}
