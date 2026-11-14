"use client";

import { useEffect, useRef, useState } from "react";
import { getThemeCardSpecimens } from "@/lib/api";
import { groupThemes } from "@/lib/theme-groups";
import type { VisualPlan } from "@/lib/types";
import styles from "./theme-quick-pick.module.css";

type Props = {
  activeTheme: string;
  activeThemeLabel: string;
  busy: boolean;
  onPick: (theme: string) => void;
  onRefresh?: () => void;
  onUndo?: () => void;
  options: NonNullable<VisualPlan["visual_system_metadata"]>["available_visual_systems"];
  pendingTheme: string;
  previewId: string;
  restoring: boolean;
};

function specimenDocument(html: string) {
  // Use the production renderer's specimen without letting its styles or links
  // interact with the editing page. The card itself owns all interaction.
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <style>
      html { background: #fff; }
      body { margin: 0; padding: 0 18px; overflow: hidden; display: grid; align-items: center; min-height: 100vh; }
      body > * { margin-top: 0 !important; margin-bottom: 0 !important; min-width: 0; }
    </style></head><body>${html}</body></html>`;
}

export function ThemeQuickPick({ activeTheme, activeThemeLabel, busy, onPick, onRefresh, onUndo, options, pendingTheme, previewId, restoring }: Props) {
  const [specimens, setSpecimens] = useState<Record<string, string> | null>(null);
  const [specimensFailed, setSpecimensFailed] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [groupFilter, setGroupFilter] = useState("");
  const catalogRef = useRef<HTMLDivElement>(null);
  const groups = groupThemes(options);
  const activeFilter = groups.some((group) => group.label === groupFilter) ? groupFilter : "";
  const visibleGroups = activeFilter ? groups.filter((group) => group.label === activeFilter) : groups;

  useEffect(() => {
    const controller = new AbortController();
    void getThemeCardSpecimens(controller.signal).then((result) => {
      if (!controller.signal.aborted) setSpecimens(result);
    }).catch(() => {
      if (!controller.signal.aborted) setSpecimensFailed(true);
    });
    return () => controller.abort();
  }, [loadAttempt]);

  function filterBy(label: string) {
    setGroupFilter(label);
    if (catalogRef.current) catalogRef.current.scrollTop = 0;
  }

  return (
    <div className={styles.picker}>
      <header className={styles.pickerHeader}>
        <div className={styles.currentTheme} aria-live="polite">
          <span>当前主题</span>
          <strong data-current-theme={activeTheme}>{activeThemeLabel}</strong>
        </div>
        <div className={styles.actions}>
          {onRefresh && (
            <button disabled={busy} onClick={onRefresh} type="button" title="保留当前主题和内容，使用新版渲染器更新预览">更新主题渲染</button>
          )}
          {onUndo && (
            <button aria-disabled={busy} onClick={() => { if (!busy) onUndo(); }} type="button" title="撤回上次样式修改，保留当前正文和图片">
              {restoring ? "回退中…" : "回到上一版"}
            </button>
          )}
          <a className={styles.previewJump} href={`#${previewId}`}>查看文章 ↓</a>
        </div>
      </header>
      <div className={styles.filters} role="group" aria-label="按风格筛选主题">
        <button aria-pressed={!activeFilter} onClick={() => filterBy("")} type="button">全部 <small>{options.length}</small></button>
        {groups.map(({ label }) => (
          <button aria-pressed={activeFilter === label} key={label} onClick={() => filterBy(label)} type="button">{label}</button>
        ))}
      </div>
      {specimensFailed && (
        <p className={styles.notice}>样张暂未加载，仍可按名称切换。 <button onClick={() => { setSpecimensFailed(false); setLoadAttempt((attempt) => attempt + 1); }} type="button">重新加载</button></p>
      )}
      {!options.length && <p className={styles.notice}>暂时没有可选主题。</p>}
      <div aria-label="主题小卡" className={styles.catalog} ref={catalogRef} role="region" tabIndex={0}>
        {visibleGroups.map(({ label: groupLabel, options: cards }) => (
          <section aria-label={groupLabel} className={styles.group} key={groupLabel}>
            <h3>{groupLabel} <small>{cards.length}</small></h3>
            <div className={styles.cards}>
              {cards.map(({ value, label, layout_coverage }) => {
                const isActive = value === activeTheme;
                const isPending = value === pendingTheme;
                const specimen = specimens?.[value];
                return (
                  <div className={styles.card} data-active={isActive} key={value}>
                    <span aria-hidden="true" className={styles.sample}>
                      {specimen ? (
                        <iframe loading="lazy" sandbox="" srcDoc={specimenDocument(specimen)} tabIndex={-1} title={`${label}文章开场样张`} />
                      ) : (
                        <span className={styles.sampleMessage}>{specimens || specimensFailed ? "暂无样张" : "加载样张…"}</span>
                      )}
                    </span>
                    <button
                      aria-controls={previewId}
                      aria-disabled={busy}
                      aria-label={label}
                      aria-pressed={isActive}
                      className={styles.caption}
                      data-theme={value}
                      onClick={() => { if (!busy) onPick(value); }}
                      type="button"
                    >
                      <strong>{label}{layout_coverage?.status === "partial" && <small className={styles.partial}>试样</small>}</strong>
                      {isPending || isActive ? <small>{isPending ? "切换中" : "当前"}</small> : <span aria-hidden="true">→</span>}
                    </button>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
      <footer className={styles.footer}><a href="/theme-gallery" target="_blank" rel="noopener">主题样本册 ↗</a></footer>
    </div>
  );
}
