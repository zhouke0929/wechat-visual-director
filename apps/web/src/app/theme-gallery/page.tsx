"use client";

import Link from "next/link";
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
          <span>THEME KIT PROOF · ROUND 01</span>
        </div>
        <Link href="/component-gallery">旧组件实验</Link>
      </header>

      <section className={styles.hero}>
        <p>FROM COLOR SKINS TO THEME KITS</p>
        <h1>统一设计基因，<br />拒绝统一卡片形状。</h1>
        <div className={styles.heroFoot}>
          <p>
            第一轮先重做轻盈阅读与理性网格：每套包含六类节奏部件和八类语义组件。
            温暖人文与编辑对比暂时保留旧版，等待首轮方法通过后再升级。
          </p>
          <dl>
            <div><dt>重做主题</dt><dd>02</dd></div>
            <div><dt>单套部件</dt><dd>14</dd></div>
            <div><dt>目标主题</dt><dd>10</dd></div>
          </dl>
        </div>
      </section>

      {error ? <p className={styles.error}>{error}</p> : null}
      {!error && themes.length === 0 ? <p className={styles.loading}>正在装订主题样本……</p> : null}

      <section className={styles.themeGrid} aria-label="现有四套视觉主题">
        {themes.map((theme, index) => (
          <Link className={styles.themeCard} href={`/theme-gallery/${theme.id}`} key={theme.id}>
            <div className={styles.cardTop}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <small>{theme.status === "theme_kit_v1_review" ? "NEW KIT · " : "LEGACY · "}{theme.english}</small>
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
              <span>{theme.status === "theme_kit_v1_review" ? "6 个节奏部件 + 8 个语义组件" : `${theme.core_component_count} 个旧版组件`}</span>
              <strong>进入主题评审 →</strong>
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
