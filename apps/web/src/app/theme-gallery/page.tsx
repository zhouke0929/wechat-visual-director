"use client";

import Link from "@/lib/router";
import { useEffect, useState } from "react";
import { getThemeGallery } from "@/lib/api";
import type { ThemeGalleryItem } from "@/lib/types";
import styles from "./theme-gallery.module.css";

export default function ThemeGalleryPage() {
  const [themes, setThemes] = useState<ThemeGalleryItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getThemeGallery().then(setThemes).catch((reason: Error) => setError(reason.message));
  }, []);

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
            这里展示当前可用于真实公众号文章的完整视觉主题。每套主题都有独立的标题、留白、图文节奏与语义组件，
            新主题会持续加入，同一篇文章也可以在工作台即时切换。
          </p>
          <dl>
            <div><dt>当前主题</dt><dd>{String(themes.length || 6).padStart(2, "0")}</dd></div>
            <div><dt>单套部件</dt><dd>14</dd></div>
            <div><dt>更新方式</dt><dd>持续</dd></div>
          </dl>
        </div>
      </section>

      {error ? <p className={styles.error}>{error}</p> : null}
      {!error && themes.length === 0 ? <p className={styles.loading}>正在装订主题样本……</p> : null}

      <section className={styles.themeGrid} aria-label="现有六套视觉主题">
        {themes.map((theme, index) => (
          <Link className={styles.themeCard} href={`/theme-gallery/${theme.id}`} key={theme.id}>
            <div className={styles.cardTop}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <small>VISUAL SYSTEM · {theme.english}</small>
            </div>
            <div className={styles.palette} aria-label={`${theme.label}色板`}>
              {theme.palette.map((color) => <i key={color} style={{ backgroundColor: color }} />)}
            </div>
            <h2>{theme.label}</h2>
            <p>{theme.description}</p>
            <div className={styles.tags}>
              {theme.ideal_for.map((item) => <span key={item}>{item}</span>)}
            </div>
            <footer>
              <span>6 个节奏部件 + 8 个语义组件</span>
              <strong>查看完整主题 →</strong>
            </footer>
          </Link>
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
