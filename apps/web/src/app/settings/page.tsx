"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { BackIcon, CheckIcon } from "@/components/icons";
import { getImageProviderSettings, saveImageProviderSettings } from "@/lib/api";
import type { ImageProviderMode, ImageProviderSettings } from "@/lib/types";
import styles from "./settings.module.css";

const providerCards: Array<{
  mode: ImageProviderMode;
  index: string;
  name: string;
  eyebrow: string;
  description: string;
  note: string;
}> = [
  {
    mode: "manual",
    index: "01",
    name: "人工上传",
    eyebrow: "MANUAL / SAFE DEFAULT",
    description: "关闭模型生图，只保留正文配图和封面的人工上传、替换与复用。",
    note: "适合正式生产前的稳定兜底",
  },
  {
    mode: "mock",
    index: "02",
    name: "Mock 演示",
    eyebrow: "LOCAL / NO QUOTA",
    description: "生成确定性的本地占位图，用来验收交互、插图位置和候选切换。",
    note: "不消耗额度，不可作为发布素材",
  },
  {
    mode: "agnes",
    index: "03",
    name: "Agnes 生图",
    eyebrow: "REMOTE / EXPERIMENTAL",
    description: "调用 Agnes 生成真实候选图；提示词由视觉主编根据文章自动组织。",
    note: "当前仅用于试验，所有图片必须人工确认",
  },
];

function statusCopy(settings: ImageProviderSettings): string {
  if (settings.mode === "manual") return "人工上传已启用";
  if (settings.mode === "mock") return "本地演示已启用";
  if (settings.real_generation_available) return "Agnes 已就绪";
  return "Agnes 等待 API Key";
}

export default function ImageProviderSettingsPage() {
  const [settings, setSettings] = useState<ImageProviderSettings | null>(null);
  const [mode, setMode] = useState<ImageProviderMode>("manual");
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getImageProviderSettings()
      .then((result) => {
        setSettings(result);
        setMode(result.mode);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  const hasUnsavedChanges = useMemo(
    () => Boolean(settings && (mode !== settings.mode || apiKey.trim() || clearApiKey)),
    [apiKey, clearApiKey, mode, settings],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings || settings.managed_by_environment) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const saved = await saveImageProviderSettings({
        mode,
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        ...(clearApiKey ? { clear_api_key: true } : {}),
      });
      setSettings(saved);
      setMode(saved.mode);
      setApiKey("");
      setClearApiKey(false);
      setNotice(
        saved.mode === "agnes" && saved.real_generation_available
          ? "设置已保存并立即生效。首次实际生图会验证 Agnes 额度和接口权限。"
          : "设置已保存并立即生效。",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存设置失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.topbar}>
        <Link className={styles.back} href="/"><BackIcon />返回任务台</Link>
        <div className={styles.topbarTitle}>
          <strong>本地设置</strong>
          <span>LOCAL CONTROL ROOM / IMAGE PROVIDER</span>
        </div>
        <span className={styles.localOnly}>仅限本机</span>
      </header>

      <section className={styles.hero}>
        <div className={styles.heroIndex}>S / 01</div>
        <div>
          <p>IMAGE PIPELINE</p>
          <h1>图片能力由你控制，<br />密钥只留在本机。</h1>
        </div>
        <aside>
          <span>运行原则</span>
          <p>智能体负责理解文章和生成提示词；工作台负责连接图片服务、保存候选和等待人工确认。</p>
        </aside>
      </section>

      {loading ? (
        <section className={styles.loading} aria-live="polite">
          <span />
          <p>正在读取本机图片设置…</p>
        </section>
      ) : settings ? (
        <form className={styles.workspace} onSubmit={handleSubmit}>
          <section className={styles.providerSection} aria-labelledby="provider-heading">
            <header className={styles.sectionHeading}>
              <div>
                <span>01 / PROVIDER</span>
                <h2 id="provider-heading">选择图片来源</h2>
              </div>
              <p>可以随时切换。已保存的 API Key 不会因为切到人工或 Mock 模式而被删除。</p>
            </header>

            <div className={styles.providerGrid}>
              {providerCards.map((provider) => {
                const selected = mode === provider.mode;
                return (
                  <label
                    className={`${styles.providerCard} ${selected ? styles.providerSelected : ""}`}
                    key={provider.mode}
                  >
                    <input
                      checked={selected}
                      disabled={settings.managed_by_environment}
                      name="provider"
                      onChange={() => {
                        setMode(provider.mode);
                        setNotice("");
                      }}
                      type="radio"
                      value={provider.mode}
                    />
                    <span className={styles.providerIndex}>{provider.index}</span>
                    <span className={styles.providerEyebrow}>{provider.eyebrow}</span>
                    <strong>{provider.name}</strong>
                    <p>{provider.description}</p>
                    <small>{provider.note}</small>
                    <i aria-hidden="true">{selected ? <CheckIcon /> : null}</i>
                  </label>
                );
              })}
            </div>
          </section>

          <div className={styles.detailGrid}>
            <section className={styles.keySection} aria-labelledby="key-heading">
              <header className={styles.sectionHeading}>
                <div>
                  <span>02 / CREDENTIAL</span>
                  <h2 id="key-heading">Agnes API Key</h2>
                </div>
              </header>

              <div className={styles.keyStatus}>
                <span className={settings.api_key_configured ? styles.readyDot : styles.idleDot} />
                <div>
                  <strong>{settings.api_key_configured ? "本机已有 Key" : "尚未配置 Key"}</strong>
                  <small>
                    {settings.api_key_configured
                      ? `来源：${settings.credential_source === "process_environment" ? "启动环境变量" : "本地私有配置"}`
                      : "选择 Agnes 时需要填写；人工和 Mock 模式不需要。"}
                  </small>
                </div>
              </div>

              <label className={styles.keyInput}>
                <span>写入新 Key</span>
                <input
                  autoComplete="off"
                  disabled={settings.managed_by_environment || clearApiKey}
                  onChange={(event) => {
                    setApiKey(event.target.value);
                    setNotice("");
                  }}
                  placeholder={settings.api_key_configured ? "已保存；留空保持不变" : "仅在这里粘贴 API Key"}
                  spellCheck={false}
                  type="password"
                  value={apiKey}
                />
                <small>保存后不会在页面、接口响应或日志中显示原值。</small>
              </label>

              {settings.api_key_configured && !settings.managed_by_environment ? (
                <label className={styles.clearKey}>
                  <input
                    checked={clearApiKey}
                    onChange={(event) => {
                      setClearApiKey(event.target.checked);
                      if (event.target.checked) setApiKey("");
                    }}
                    type="checkbox"
                  />
                  <span>保存时清除本机 Agnes API Key</span>
                </label>
              ) : null}

              {settings.managed_by_environment ? (
                <div className={styles.managedNotice}>
                  <strong>当前由启动环境管理</strong>
                  <p>工作台不会覆盖：{settings.managed_fields.join("、")}。请在启动脚本或系统环境变量中修改。</p>
                </div>
              ) : null}
            </section>

            <aside className={styles.systemSection}>
              <header>
                <span>LIVE STATUS</span>
                <strong>{statusCopy(settings)}</strong>
              </header>
              <dl>
                <div><dt>当前 Provider</dt><dd>{settings.active_provider.toUpperCase()}</dd></div>
                <div><dt>当前模型</dt><dd>{settings.active_model}</dd></div>
                <div><dt>输出尺寸</dt><dd>{settings.agnes.size}</dd></div>
                <div><dt>提示词</dt><dd>视觉主编自动生成</dd></div>
                <div><dt>外部连接</dt><dd>首次真实生图时验证</dd></div>
              </dl>
              <details>
                <summary>查看本地配置位置</summary>
                <code>{settings.config_file}</code>
                <p>{settings.agnes.endpoint}</p>
              </details>
            </aside>
          </div>

          <section className={styles.guardrails}>
            <div><span>01</span><strong>不要求宿主智能体读取 Key</strong><p>OpenCode、OpenClaw、Claude Code 等只需调用视觉规划流程。</p></div>
            <div><span>02</span><strong>提示词由系统自动组织</strong><p>基于文章语义、图片用途和风格约束生成，不让运营手写提示词。</p></div>
            <div><span>03</span><strong>候选图片必须人工确认</strong><p>Agnes 当前未通过生产质量验收，不会自动成为发布素材。</p></div>
          </section>

          <footer className={styles.actionBar}>
            <div aria-live="polite">
              {error ? <p className={styles.error} role="alert">{error}</p> : null}
              {notice ? <p className={styles.success}><CheckIcon />{notice}</p> : null}
              {!error && !notice ? <p>保存只验证本地配置；不会为了测试连接而消耗生图额度。</p> : null}
            </div>
            <button
              disabled={saving || settings.managed_by_environment || !hasUnsavedChanges}
              type="submit"
            >
              <span>{saving ? "正在保存…" : "保存并立即应用"}</span>
              <i>{mode.toUpperCase()}</i>
            </button>
          </footer>
        </form>
      ) : (
        <section className={styles.failure}>
          <strong>无法读取图片设置</strong>
          <p>{error || "请确认本地 API 已启动后刷新页面。"}</p>
          <Link href="/">返回任务台</Link>
        </section>
      )}
    </main>
  );
}
