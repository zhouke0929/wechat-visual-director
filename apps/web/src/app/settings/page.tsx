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
    mode: "images_api",
    index: "03",
    name: "通用 Images API",
    eyebrow: "OPENAI / ARK / RELAY",
    description: "连接 GPT Image、Seedream 以及兼容 Images API 的中转服务。",
    note: "接口地址、协议和模型 ID 均可替换",
  },
  {
    mode: "gemini",
    index: "04",
    name: "Google Gemini",
    eyebrow: "NATIVE / NANO BANANA",
    description: "通过 Google 原生 Interactions API 调用 Nano Banana 系列。",
    note: "不强行伪装成 OpenAI 协议，减少隐性兼容错误",
  },
];

const imageApiPresets = {
  openai: {
    endpoint: "https://api.openai.com/v1/images/generations",
    model: "gpt-image-2",
    size: "auto",
  },
  ark: {
    endpoint: "https://ark.cn-beijing.volces.com/api/v3/images/generations",
    model: "",
    size: "2K",
  },
  ark_plan: {
    endpoint: "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations",
    model: "doubao-seedream-5.0-lite",
    size: "2K",
  },
  extended: {
    endpoint: "",
    model: "",
    size: "1K",
  },
} as const;

function statusCopy(settings: ImageProviderSettings): string {
  if (settings.mode === "manual") return "人工上传已启用";
  if (settings.mode === "mock") return "本地演示已启用";
  if (settings.real_generation_available) return "真实图片服务已就绪";
  return "图片服务等待 API Key";
}

export default function ImageProviderSettingsPage() {
  const [settings, setSettings] = useState<ImageProviderSettings | null>(null);
  const [mode, setMode] = useState<ImageProviderMode>("manual");
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [endpoint, setEndpoint] = useState("");
  const [model, setModel] = useState("");
  const [protocol, setProtocol] = useState<"openai" | "ark" | "ark_plan" | "extended">("openai");
  const [size, setSize] = useState("auto");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getImageProviderSettings()
      .then((result) => {
        setSettings(result);
        setMode(result.mode);
        if (result.mode === "images_api") {
          setEndpoint(result.providers.images_api.endpoint);
          setModel(result.providers.images_api.model);
          setProtocol(result.providers.images_api.protocol);
          setSize(result.providers.images_api.size);
        } else if (result.mode === "gemini") {
          setEndpoint(result.providers.gemini.endpoint);
          setModel(result.providers.gemini.model);
          setSize(result.providers.gemini.size);
        }
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  const activeConfig = mode === "images_api"
    ? settings?.providers.images_api
    : mode === "gemini"
      ? settings?.providers.gemini
      : null;
  const selectedKeyConfigured = Boolean(activeConfig?.api_key_configured);

  const hasUnsavedChanges = useMemo(() => {
    if (!settings) return false;
    const configChanged = activeConfig
      ? endpoint !== activeConfig.endpoint
        || model !== activeConfig.model
        || size !== activeConfig.size
        || (mode === "images_api" && protocol !== settings.providers.images_api.protocol)
      : false;
    return Boolean(mode !== settings.mode || apiKey.trim() || clearApiKey || configChanged);
  }, [activeConfig, apiKey, clearApiKey, endpoint, mode, model, protocol, settings, size]);

  function selectMode(nextMode: ImageProviderMode) {
    if (!settings) return;
    setMode(nextMode);
    setApiKey("");
    setClearApiKey(false);
    setNotice("");
    if (nextMode === "images_api") {
      setEndpoint(settings.providers.images_api.endpoint);
      setModel(settings.providers.images_api.model);
      setProtocol(settings.providers.images_api.protocol);
      setSize(settings.providers.images_api.size);
    } else if (nextMode === "gemini") {
      setEndpoint(settings.providers.gemini.endpoint);
      setModel(settings.providers.gemini.model);
      setSize(settings.providers.gemini.size);
    }
  }

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
        ...(mode === "images_api" || mode === "gemini"
          ? { endpoint: endpoint.trim(), model: model.trim(), size: size.trim() }
          : {}),
        ...(mode === "images_api" ? { protocol } : {}),
      });
      setSettings(saved);
      setMode(saved.mode);
      setApiKey("");
      setClearApiKey(false);
      setNotice(saved.real_generation_available
        ? "设置已保存并立即生效。首次实际生图会验证模型权限与额度。"
        : "设置已保存并立即生效。");
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
                      onChange={() => selectMode(provider.mode)}
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
                  <span>02 / CONNECTION</span>
                  <h2 id="key-heading">
                    {mode === "images_api"
                      ? "Images API 连接"
                      : mode === "gemini"
                        ? "Gemini 原生连接"
                        : "无需外部连接"}
                  </h2>
                </div>
              </header>

              {activeConfig ? (
                <>
                  <div className={styles.keyStatus}>
                    <span className={selectedKeyConfigured ? styles.readyDot : styles.idleDot} />
                    <div>
                      <strong>{selectedKeyConfigured ? "本机已有 Key" : "尚未配置 Key"}</strong>
                      <small>
                        {selectedKeyConfigured && mode === settings.mode
                          ? `来源：${settings.credential_source === "process_environment" ? "启动环境变量" : "本地私有配置"}`
                          : "Key 仅写入本机私有配置，不会交给宿主智能体。"}
                      </small>
                    </div>
                  </div>

                  <div className={styles.connectionGrid}>
                    {mode === "images_api" ? (
                      <label>
                        <span>接口协议</span>
                        <select
                          disabled={settings.managed_by_environment}
                          onChange={(event) => {
                            const nextProtocol = event.target.value as typeof protocol;
                            const preset = imageApiPresets[nextProtocol];
                            setProtocol(nextProtocol);
                            setEndpoint(preset.endpoint);
                            setModel(preset.model);
                            setSize(preset.size);
                          }}
                          value={protocol}
                        >
                          <option value="openai">OpenAI Images API</option>
                          <option value="ark">火山方舟按量 / Seedream</option>
                          <option value="ark_plan">火山方舟 Agent Plan / Seedream</option>
                          <option value="extended">扩展兼容（旧 Agnes 等）</option>
                        </select>
                      </label>
                    ) : null}
                    <label>
                      <span>Endpoint</span>
                      <input
                        disabled={settings.managed_by_environment}
                        onChange={(event) => setEndpoint(event.target.value)}
                        required
                        spellCheck={false}
                        type="url"
                        value={endpoint}
                      />
                    </label>
                    <label>
                      <span>Model ID</span>
                      <input
                        disabled={settings.managed_by_environment}
                        onChange={(event) => setModel(event.target.value)}
                        placeholder={
                          mode === "images_api" && (protocol === "ark" || protocol === "ark_plan")
                            ? "从火山方舟控制台复制 Model ID"
                            : ""
                        }
                        required
                        spellCheck={false}
                        value={model}
                      />
                    </label>
                    <label>
                      <span>输出尺寸</span>
                      {mode === "gemini" ? (
                        <select
                          disabled={settings.managed_by_environment}
                          onChange={(event) => setSize(event.target.value)}
                          value={size}
                        >
                          <option value="0.5K">0.5K</option>
                          <option value="1K">1K</option>
                          <option value="2K">2K</option>
                          <option value="4K">4K</option>
                        </select>
                      ) : (
                        <input
                          disabled={settings.managed_by_environment}
                          onChange={(event) => setSize(event.target.value)}
                          placeholder="auto / 2K / 1536x1024"
                          value={size}
                        />
                      )}
                    </label>
                  </div>

                  <label className={styles.keyInput}>
                    <span>写入新 API Key</span>
                    <input
                      autoComplete="off"
                      disabled={settings.managed_by_environment || clearApiKey}
                      onChange={(event) => {
                        setApiKey(event.target.value);
                        setNotice("");
                      }}
                      placeholder={selectedKeyConfigured ? "已保存；留空保持不变" : "仅在这里粘贴 API Key"}
                      spellCheck={false}
                      type="password"
                      value={apiKey}
                    />
                    <small>保存后不会在页面、接口响应或日志中显示原值。</small>
                  </label>

                  {selectedKeyConfigured && !settings.managed_by_environment ? (
                    <label className={styles.clearKey}>
                      <input
                        checked={clearApiKey}
                        onChange={(event) => {
                          setClearApiKey(event.target.checked);
                          if (event.target.checked) setApiKey("");
                        }}
                        type="checkbox"
                      />
                      <span>保存时清除当前图片服务的 API Key</span>
                    </label>
                  ) : null}
                </>
              ) : (
                <div className={styles.keyStatus}>
                  <span className={styles.readyDot} />
                  <div>
                    <strong>本地能力可直接使用</strong>
                    <small>人工上传和 Mock 不需要 Endpoint、模型或 API Key。</small>
                  </div>
                </div>
              )}

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
                <div><dt>输出尺寸</dt><dd>{activeConfig?.size ?? "LOCAL"}</dd></div>
                <div><dt>提示词</dt><dd>视觉主编自动生成</dd></div>
                <div><dt>外部连接</dt><dd>首次真实生图时验证</dd></div>
              </dl>
              <details>
                <summary>查看本地配置位置</summary>
                <code>{settings.config_file}</code>
                {activeConfig ? <p>{activeConfig.endpoint}</p> : null}
              </details>
            </aside>
          </div>

          <section className={styles.guardrails}>
            <div><span>01</span><strong>不要求宿主智能体读取 Key</strong><p>OpenCode、OpenClaw、Claude Code 等只需调用视觉规划流程。</p></div>
            <div><span>02</span><strong>提示词由系统自动组织</strong><p>基于文章语义、图片用途和风格约束生成，不让运营手写提示词。</p></div>
            <div><span>03</span><strong>候选图片必须人工确认</strong><p>无论接入哪家模型，候选都不会绕过运营直接成为发布素材。</p></div>
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
