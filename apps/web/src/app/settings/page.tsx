"use client";

import Link from "@/lib/router";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { BackIcon, CheckIcon } from "@/components/icons";
import {
  getCapabilitySettings,
  getImageProviderSettings,
  getWechatPublisherSettings,
  probePublicIp,
  probeWechatPublisher,
  saveImageProviderSettings,
  saveSetupPreferences,
  saveWechatPublisherSettings,
} from "@/lib/api";
import type {
  CapabilitySettings,
  ImageProviderMode,
  ImageProviderSettings,
  SetupTargetMode,
  WechatPublisherSettings,
} from "@/lib/types";
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

const targetCards: Array<{
  mode: SetupTargetMode;
  index: string;
  name: string;
  description: string;
  output: string;
}> = [
  {
    mode: "typeset_only",
    index: "A",
    name: "只做排版",
    description: "不配置任何外部 API，也能生成双方案、切换组件并导出全文。",
    output: "复制全文 / 下载交付包",
  },
  {
    mode: "images",
    index: "B",
    name: "排版 + 生图",
    description: "在排版基础上连接图片模型，生成正文插图和封面候选。",
    output: "人工确认图片后交付",
  },
  {
    mode: "full_delivery",
    index: "C",
    name: "完整交付",
    description: "配置图片服务和微信公众号，将最终版本直接写入公众号草稿箱。",
    output: "微信草稿 + 本地备份",
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
  const [capabilities, setCapabilities] = useState<CapabilitySettings | null>(null);
  const [settings, setSettings] = useState<ImageProviderSettings | null>(null);
  const [wechatSettings, setWechatSettings] = useState<WechatPublisherSettings | null>(null);
  const [mode, setMode] = useState<ImageProviderMode>("manual");
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [endpoint, setEndpoint] = useState("");
  const [model, setModel] = useState("");
  const [protocol, setProtocol] = useState<"openai" | "ark" | "ark_plan" | "extended">("openai");
  const [size, setSize] = useState("auto");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [targetSaving, setTargetSaving] = useState(false);
  const [wechatSaving, setWechatSaving] = useState(false);
  const [wechatTesting, setWechatTesting] = useState(false);
  const [publicIpLoading, setPublicIpLoading] = useState(false);
  const [wechatAppId, setWechatAppId] = useState("");
  const [wechatSecret, setWechatSecret] = useState("");
  const [whitelistConfirmed, setWhitelistConfirmed] = useState(false);
  const [publicIp, setPublicIp] = useState("");
  const [ipCopied, setIpCopied] = useState(false);
  const [wechatNotice, setWechatNotice] = useState("");
  const [wechatError, setWechatError] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      getCapabilitySettings(),
      getImageProviderSettings(),
      getWechatPublisherSettings(),
    ])
      .then(([capabilityResult, imageResult, wechatResult]) => {
        setCapabilities(capabilityResult);
        setSettings(imageResult);
        setWechatSettings(wechatResult);
        setWhitelistConfirmed(wechatResult.ip_whitelist_confirmed);
        setMode(imageResult.mode);
        if (imageResult.mode === "images_api") {
          setEndpoint(imageResult.providers.images_api.endpoint);
          setModel(imageResult.providers.images_api.model);
          setProtocol(imageResult.providers.images_api.protocol);
          setSize(imageResult.providers.images_api.size);
        } else if (imageResult.mode === "gemini") {
          setEndpoint(imageResult.providers.gemini.endpoint);
          setModel(imageResult.providers.gemini.model);
          setSize(imageResult.providers.gemini.size);
        }
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  async function refreshCapabilities() {
    const next = await getCapabilitySettings();
    setCapabilities(next);
    return next;
  }

  async function selectTargetMode(nextMode: SetupTargetMode) {
    if (!capabilities || targetSaving || nextMode === capabilities.target_mode) return;
    setTargetSaving(true);
    setError("");
    try {
      setCapabilities(await saveSetupPreferences(nextMode));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存使用目标失败");
    } finally {
      setTargetSaving(false);
    }
  }

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
      await refreshCapabilities();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存设置失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleWechatSave() {
    if (!wechatSettings || wechatSettings.managed_by_environment) return;
    setWechatSaving(true);
    setWechatError("");
    setWechatNotice("");
    try {
      const saved = await saveWechatPublisherSettings({
        ...(wechatAppId.trim() ? { app_id: wechatAppId.trim() } : {}),
        ...(wechatSecret.trim() ? { app_secret: wechatSecret.trim() } : {}),
        ip_whitelist_confirmed: whitelistConfirmed,
      });
      setWechatSettings(saved);
      setWechatAppId("");
      setWechatSecret("");
      setWechatNotice("公众号设置已保存。下一步点击“检测连接”，不会创建草稿。");
      await refreshCapabilities();
    } catch (reason) {
      setWechatError(reason instanceof Error ? reason.message : "保存公众号设置失败");
    } finally {
      setWechatSaving(false);
    }
  }

  async function handleClearWechatCredentials() {
    if (!wechatSettings || wechatSettings.managed_by_environment) return;
    const confirmed = window.confirm(
      "确定解除这台电脑与当前公众号的绑定吗？这只会删除本机保存的 AppID 和 AppSecret，不会重置微信开发者后台的 AppSecret，也不会影响公众号本身。",
    );
    if (!confirmed) return;
    setWechatSaving(true);
    setWechatError("");
    setWechatNotice("");
    try {
      const saved = await saveWechatPublisherSettings({ clear_credentials: true });
      setWechatSettings(saved);
      setWechatAppId("");
      setWechatSecret("");
      setWechatNotice("已解除本机绑定；微信开发者后台中的凭据没有被重置。 ");
      await refreshCapabilities();
    } catch (reason) {
      setWechatError(reason instanceof Error ? reason.message : "解除本机绑定失败");
    } finally {
      setWechatSaving(false);
    }
  }

  async function handleWechatProbe() {
    setWechatTesting(true);
    setWechatError("");
    setWechatNotice("");
    try {
      const result = await probeWechatPublisher();
      setWechatNotice(result.message || (result.ok ? "连接检测通过。" : "连接检测未通过。"));
      setWechatSettings(await getWechatPublisherSettings());
      await refreshCapabilities();
    } catch (reason) {
      setWechatError(reason instanceof Error ? reason.message : "连接检测失败");
    } finally {
      setWechatTesting(false);
    }
  }

  async function handlePublicIpProbe() {
    setPublicIpLoading(true);
    setWechatError("");
    try {
      const result = await probePublicIp();
      if (!result.ok || !result.public_ip) throw new Error(result.message);
      setPublicIp(result.public_ip);
      setIpCopied(false);
      setWechatNotice("已获取公网出口 IP，请复制到微信公众号后台的 IP 白名单。这里显示的不是 192.168 开头的局域网地址。");
    } catch (reason) {
      setWechatError(reason instanceof Error ? reason.message : "公网 IP 获取失败");
    } finally {
      setPublicIpLoading(false);
    }
  }

  async function handleCopyPublicIp() {
    if (!publicIp) return;
    try {
      await navigator.clipboard.writeText(publicIp);
      setIpCopied(true);
      window.setTimeout(() => setIpCopied(false), 1800);
    } catch {
      setWechatError("复制失败，请选中公网 IP 后手动复制。");
    }
  }

  return (
    <main className={styles.page}>
      <header className={styles.topbar}>
        <Link className={styles.back} href="/"><BackIcon />返回任务台</Link>
        <div className={styles.topbarTitle}>
          <strong>本地设置</strong>
          <span>LOCAL CONTROL ROOM / CAPABILITY SETUP</span>
        </div>
        <span className={styles.localOnly}>仅限本机</span>
      </header>

      <section className={styles.hero}>
        <div className={styles.heroIndex}>S / 01</div>
        <div>
          <p>ONE-TIME LOCAL SETUP</p>
          <h1>选择你要走到哪一步，<br />其余能力按需配置。</h1>
        </div>
        <aside>
          <span>运行原则</span>
          <p>设置属于这台电脑，不属于某个对话。换新窗口后，智能体会继续使用已经保存的本机能力。</p>
        </aside>
      </section>

      {loading ? (
        <section className={styles.loading} aria-live="polite">
          <span />
          <p>正在读取本机图片设置…</p>
        </section>
      ) : settings && capabilities && wechatSettings ? (
        <form className={styles.workspace} onSubmit={handleSubmit}>
          <section className={styles.targetSection} aria-labelledby="target-heading">
            <header className={styles.sectionHeading}>
              <div>
                <span>01 / TARGET</span>
                <h2 id="target-heading">这台电脑准备做到哪一步？</h2>
              </div>
              <div className={`${styles.targetSummary} ${capabilities.complete_for_target ? styles.targetReady : ""}`}>
                <strong>{capabilities.complete_for_target ? "目标能力已就绪" : "还差一项配置"}</strong>
                <small>{capabilities.next_action.replaceAll("_", " ")}</small>
              </div>
            </header>
            <div className={styles.targetGrid}>
              {targetCards.map((target) => {
                const selected = target.mode === capabilities.target_mode;
                const capabilityState = target.mode === "typeset_only"
                  ? "随时可用"
                  : target.mode === "images"
                    ? capabilities.capabilities.image_generation.state === "ready" ? "已就绪" : "待配置图片"
                    : capabilities.capabilities.wechat_draft.state === "ready" ? "已就绪" : "待配置完整交付";
                return (
                  <button
                    className={`${styles.targetCard} ${selected ? styles.targetSelected : ""}`}
                    disabled={targetSaving}
                    key={target.mode}
                    onClick={() => selectTargetMode(target.mode)}
                    type="button"
                  >
                    <span>{target.index}</span>
                    <div><strong>{target.name}</strong><p>{target.description}</p></div>
                    <footer><small>{target.output}</small><i>{capabilityState}</i></footer>
                  </button>
                );
              })}
            </div>
          </section>

          {capabilities.target_mode === "typeset_only" ? (
            <section className={styles.typesetReadyPanel}>
              <span>READY / NO EXTRA SETUP</span>
              <div><strong>只做排版已经可以使用</strong><p>无需图片 API，也无需公众号凭据。现在可以返回任务台创建文章，完成后复制全文或下载交付包。</p></div>
              <Link href="/">返回任务台</Link>
            </section>
          ) : (
          <>
          <section className={styles.providerSection} aria-labelledby="provider-heading">
            <header className={styles.sectionHeading}>
              <div>
                <span>02 / IMAGE PROVIDER</span>
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
                  <span>03 / IMAGE CONNECTION</span>
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

          <footer className={styles.actionBar}>
            <div aria-live="polite">
              {error ? <p className={styles.error} role="alert">{error}</p> : null}
              {notice ? <p className={styles.success}><CheckIcon />{notice}</p> : null}
              {!error && !notice ? <p>这里仅保存图片服务配置；不会为了测试连接而消耗生图额度。</p> : null}
            </div>
            <button
              disabled={saving || settings.managed_by_environment || !hasUnsavedChanges}
              type="submit"
            >
              <span>{saving ? "正在保存…" : "保存图片设置"}</span>
              <i>{mode.toUpperCase()}</i>
            </button>
          </footer>
          </>
          )}

          {capabilities.target_mode === "full_delivery" ? (
          <section className={styles.wechatSection} aria-labelledby="wechat-heading">
            <header className={styles.sectionHeading}>
              <div>
                <span>04 / WECHAT DELIVERY</span>
                <h2 id="wechat-heading">连接微信公众号草稿箱</h2>
              </div>
              <p>保存凭据、检测连接、创建草稿是三个独立动作。这里的检测只验证权限，不会往后台写文章。</p>
            </header>

            <div className={styles.wechatGrid}>
              <div className={styles.wechatGuide}>
                <ol>
                  <li><span>1</span><div><strong>在微信开发者后台获取凭据</strong><p>进入“开发接口管理”，在账号开发信息中复制 AppID，并生成或重置 AppSecret。具体栏目名称以微信当前页面为准。</p></div></li>
                  <li><span>2</span><div><strong>加入当前公网 IP</strong><p>点击下方检测按钮，将结果加入微信开发者后台的 IP 白名单。</p></div></li>
                  <li><span>3</span><div><strong>保存后检测连接</strong><p>检测通过后，文章冻结页才会把 Wenyan 草稿交付标记为可用。</p></div></li>
                </ol>
                <div className={styles.ipProbe}>
                  <button disabled={publicIpLoading} onClick={handlePublicIpProbe} type="button">
                    {publicIpLoading ? "正在检测…" : "检测当前公网 IP"}
                  </button>
                  {publicIp ? (
                    <button
                      aria-live="polite"
                      className={`${styles.ipValue} ${ipCopied ? styles.ipCopied : ""}`}
                      onClick={handleCopyPublicIp}
                      title={ipCopied ? "已复制到剪贴板" : "点击复制公网 IP"}
                      type="button"
                    >
                      <code>{publicIp}</code><span>{ipCopied ? "✓ 已复制" : "点击复制"}</span>
                    </button>
                  ) : <small>仅点击时访问外部查询服务，普通启动不会自动检测。</small>}
                </div>
              </div>

              <div className={styles.wechatForm}>
                <div className={styles.wechatStatus}>
                  <span className={wechatSettings.connection_probe?.ok ? styles.readyDot : styles.idleDot} />
                  <div>
                    <strong>
                      {wechatSettings.connection_probe?.ok
                        ? "微信公众号连接已验证"
                        : wechatSettings.credentials_configured
                          ? "凭据已保存，等待检测连接"
                          : "尚未配置微信公众号"}
                    </strong>
                    <small>
                      {wechatSettings.connection_probe?.code === "wechat_ip_not_whitelisted"
                        ? "凭据可识别，但当前公网 IP 未在白名单中。"
                        : "AppID、AppSecret 和 access token 都不会返回给页面或宿主智能体。"}
                    </small>
                  </div>
                </div>

                <div className={styles.wechatInputs}>
                  <label><span>AppID</span><input
                    autoComplete="off"
                    disabled={wechatSettings.managed_by_environment}
                    onChange={(event) => setWechatAppId(event.target.value)}
                    placeholder={wechatSettings.app_id_configured ? "已保存；留空保持不变" : "粘贴公众号 AppID"}
                    spellCheck={false}
                    value={wechatAppId}
                  /></label>
                  <label><span>AppSecret</span><input
                    autoComplete="off"
                    disabled={wechatSettings.managed_by_environment}
                    onChange={(event) => setWechatSecret(event.target.value)}
                    placeholder={wechatSettings.app_secret_configured ? "已保存；留空保持不变" : "仅在这里粘贴 AppSecret"}
                    spellCheck={false}
                    type="password"
                    value={wechatSecret}
                  /></label>
                </div>

                <label className={styles.whitelistCheck}><input
                  checked={whitelistConfirmed}
                  disabled={wechatSettings.managed_by_environment}
                  onChange={(event) => setWhitelistConfirmed(event.target.checked)}
                  type="checkbox"
                /><span>我已将当前公网 IP 加入微信公众号后台白名单</span></label>

                {wechatSettings.managed_by_environment ? (
                  <div className={styles.managedNotice}><strong>当前由启动环境管理</strong><p>工作台不会覆盖：{wechatSettings.managed_fields.join("、")}。</p></div>
                ) : null}

                <div className={styles.wechatActions}>
                  <button
                    disabled={wechatSaving || wechatSettings.managed_by_environment}
                    onClick={handleWechatSave}
                    type="button"
                  >{wechatSaving ? "正在保存…" : "保存公众号设置"}</button>
                  <button
                    className={styles.secondaryAction}
                    disabled={wechatTesting || !wechatSettings.credentials_configured}
                    onClick={handleWechatProbe}
                    type="button"
                  >{wechatTesting ? "正在检测…" : "检测连接（不建草稿）"}</button>
                </div>
                <div aria-live="polite" className={styles.wechatFeedback}>
                  {wechatError ? <p className={styles.error} role="alert">{wechatError}</p> : null}
                  {wechatNotice ? <p className={styles.success}><CheckIcon />{wechatNotice}</p> : null}
                </div>
                {wechatSettings.credentials_configured && !wechatSettings.managed_by_environment ? (
                  <details className={styles.dangerZone}>
                    <summary>高级操作</summary>
                    <p>解除本机绑定只删除这台电脑保存的 AppID 和 AppSecret，不会重置微信开发者后台的凭据。</p>
                    <button disabled={wechatSaving} onClick={handleClearWechatCredentials} type="button">解除本机绑定</button>
                  </details>
                ) : null}
              </div>
            </div>
          </section>
          ) : null}

          {capabilities.target_mode !== "typeset_only" ? (
          <section className={styles.guardrails}>
            <div><span>01</span><strong>不要求宿主智能体读取 Key</strong><p>OpenCode、OpenClaw、Claude Code 等只需调用视觉规划流程。</p></div>
            <div><span>02</span><strong>提示词由系统自动组织</strong><p>基于文章语义、图片用途和风格约束生成，不让运营手写提示词。</p></div>
            <div><span>03</span><strong>候选图片必须人工确认</strong><p>无论接入哪家模型，候选都不会绕过运营直接成为发布素材。</p></div>
          </section>
          ) : null}

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
