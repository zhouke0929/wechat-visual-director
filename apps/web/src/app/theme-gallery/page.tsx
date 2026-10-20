"use client";

import { themeCoverageLabel } from "@/lib/theme-coverage";

import Link from "@/lib/router";
import { ChangeEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { deleteThemePack, getThemeGallery, installThemePack, themePackExportUrl } from "@/lib/api";
import type { ThemeGalleryItem } from "@/lib/types";
import styles from "./theme-gallery.module.css";

export default function ThemeGalleryPage() {
  const [themes, setThemes] = useState<ThemeGalleryItem[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activeCollection, setActiveCollection] = useState<"official" | "custom">("official");
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    const collection = await getThemeGallery();
    setThemes(collection);
    return collection;
  };

  useEffect(() => {
    refresh().catch((reason: Error) => setError(reason.message));
  }, []);

  const officialThemes = useMemo(() => themes.filter((theme) => theme.source !== "custom"), [themes]);
  const customThemes = useMemo(() => themes.filter((theme) => theme.source === "custom" && theme.availability !== "unavailable"), [themes]);
  const unavailableThemes = useMemo(() => themes.filter((theme) => theme.availability === "unavailable"), [themes]);
  const visibleThemes = activeCollection === "official" ? officialThemes : customThemes;

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

  const handleDelete = async (event: MouseEvent, theme: ThemeGalleryItem) => {
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

  const handleExport = (event: MouseEvent, theme: ThemeGalleryItem) => {
    event.preventDefault();
    event.stopPropagation();
    window.location.href = themePackExportUrl(theme.id);
  };

  const specimenCount = themes[0]
    ? themes[0].components.length + (themes[0].foundation_specimens ?? themes[0].rhythm_primitives).length
    : 26;

  return (
    <main className={styles.page}>
      <header className={styles.topbar}>
        <Link href="/">← 返回任务台</Link>
        <div>
          <strong>主题样本册</strong>
          <span>VISUAL THEME LIBRARY · LIVE COLLECTION</span>
        </div>
      </header>

      <section className={styles.hero}>
        <p>EXPLORE THE VISUAL LANGUAGE</p>
        <h1>每一种主题，<br />都是一套完整阅读气质。</h1>
        <div className={styles.heroFoot}>
          <p>
            这里展示官方主题与本机自定义主题，包括完整文章和全部基础、语义样式。每套主题都有自己的标题、留白、图文节奏，
            官方主题与本机扩展包遵守同一套语义组件和编辑契约。同一篇文章可以即时切换风格，正文结构保持不变。
          </p>
          <dl>
            <div><dt>官方主题</dt><dd>{String(officialThemes.length || 12).padStart(2, "0")}</dd></div>
            <div><dt>我的主题</dt><dd>{String(customThemes.length).padStart(2, "0")}</dd></div>
            <div><dt>单套样本</dt><dd>{specimenCount}</dd></div>
            <div><dt>更新方式</dt><dd>持续</dd></div>
          </dl>
        </div>
      </section>

      <nav className={styles.collections} aria-label="主题集合">
        <div className={styles.collectionTabs}>
          <button
            className={activeCollection === "official" ? styles.activeCollection : ""}
            onClick={() => setActiveCollection("official")}
            type="button"
          >
            官方主题 <span>{officialThemes.length}</span>
          </button>
          <button
            className={activeCollection === "custom" ? styles.activeCollection : ""}
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
          <button disabled={busy} onClick={() => fileInput.current?.click()} type="button">
            {busy ? "正在校验…" : "导入主题扩展包 ↗"}
          </button>
          <small>仅接收声明式视觉 DNA，不执行 CSS 或脚本</small>
        </div>
      </nav>

      {error ? <p className={styles.error}>{error}</p> : null}
      {notice ? <p className={styles.notice}>{notice}</p> : null}
      {unavailableThemes.length > 0 && <section className={styles.error} role="status" aria-label="暂不可用的主题">
        <strong>{unavailableThemes.length} 个自定义主题暂不可用，正常主题仍可浏览。</strong>
        <ul>{unavailableThemes.map((theme) => <li key={theme.id}>{theme.label}：{theme.diagnostic?.message}（{theme.diagnostic?.code}）</li>)}</ul>
        <p>请让 Agent 检查这些主题并修复后重新导入；原文件没有被自动删除。</p>
      </section>}
      {!error && themes.length === 0 ? <p className={styles.loading}>正在装订主题样本……</p> : null}

      {activeCollection === "custom" && !error && customThemes.length === 0 ? (
        <section className={styles.emptyCollection}>
          <span>YOUR VISUAL DNA / 00</span>
          <h2>这里会收纳你自己的阅读气质。</h2>
          <p>
            推荐给已安装 Skill 的 Agent 喜欢的组件截图，更容易对齐风格；没有图也可描述需求探索。它会寻找具体参考、联想并延展整套视觉语言；完成的扩展包可在这里浏览、导入和导出，再用于真实文章。
          </p>
          <button disabled={busy} onClick={() => fileInput.current?.click()} type="button">导入第一套主题</button>
        </section>
      ) : null}

      <section className={styles.themeGrid} aria-label={`${activeCollection === "official" ? "官方" : "我的"}视觉主题`}>
        {visibleThemes.map((theme, index) => (
          <article className={styles.themeCard} key={theme.id}>
            <Link className={styles.cardLink} href={`/theme-gallery/${theme.id}`}>
              <div className={styles.cardTop}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <small>VISUAL SYSTEM · {theme.english}</small>
              </div>
              <div className={styles.palette} aria-label={`${theme.label}色板`}>
                {theme.palette.map((color) => <i key={color} style={{ backgroundColor: color }} />)}
              </div>
              <h2>{theme.label}</h2>
              {theme.delivery_report?.coverage && <p className={styles.coverage}>{themeCoverageLabel(theme.delivery_report.coverage)}</p>}
              <p>{theme.description}</p>
              <div className={styles.tags}>
                {theme.ideal_for.map((item) => <span key={item}>{item}</span>)}
              </div>
            </Link>
            <footer>
              <span>{(theme.foundation_specimens ?? theme.rhythm_primitives).length} 种基础样式 + {theme.components.length} 类语义组件</span>
              {theme.source === "custom" ? (
                <div className={styles.cardActions}>
                  <button onClick={(event) => handleExport(event, theme)} type="button">导出</button>
                  <button onClick={(event) => handleDelete(event, theme)} type="button">删除</button>
                  <Link className={styles.detailLink} href={`/theme-gallery/${theme.id}`}>{theme.delivery_report?.coverage?.status === "partial" ? "查看试样 →" : "查看主题 →"}</Link>
                </div>
              ) : <Link className={styles.detailLink} href={`/theme-gallery/${theme.id}`}>查看完整主题 →</Link>}
            </footer>
          </article>
        ))}
      </section>

      <section className={styles.policy}>
        <span>CONTENT FIDELITY / 00</span>
        <h2>组件只负责组织，不负责替文章发言。</h2>
        <p>
          编号、线条、图标和色块可以属于组件；事实、结论、口号和行动建议必须来自原文。
          这条规则会进入自动测试，不依赖人工记忆。
        </p>
      </section>
    </main>
  );
}
