const copyToast = document.querySelector("#copyToast");
const dialog = document.querySelector("#installDialog");
const promptField = document.querySelector("#installPromptText");
const promptHelpLink = document.querySelector("#promptHelpLink");
let toastTimer;
let dialogTrigger = null;

const installPrompt = `请打开并完整执行下面的 Agent 安装说明，为我安装或升级完整的 wechat-visual-director 产品。使用当前安装入口，不要沿用旧文档里的固定版本。必须同时安装轻量 Skill 和本地工作台、运行 doctor --json 并打开工作台；不要只复制 Skill，也不要把源码仓库克隆到 Skill 目录。完成后给我实际安装版本、工作台链接和不超过五行的上手说明，包括下一句可以怎么使用；如果受限未完成，说明当前状态和下一步，不要只回复已安装。不要读取或回显任何密钥。
https://github.com/zhouke0929/wechat-visual-director/blob/main/INSTALL_FOR_AGENT.md`;
promptField.value = installPrompt;
const themePrompt = `请用 wechat-visual-director，根据我发来的样式截图（例如 135编辑器或秀米里的标题、正文框、对话气泡），提取配色、造型和排版细节，延展成一套可复用的公众号主题。如果我只提供风格描述，请先找可查看的组件样例来确认方向。正文保持可编辑，先在样本册和一篇示例文章中让我查看效果，不要创建公众号草稿。`;

const defaultTheme = "pixel_live";
const $ = (selector) => document.querySelector(selector);
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
let themeCatalog = [];
const featuredThemes = ["pixel_live", "warm_humanist", "oriental_archive", "pop_poster", "natural_atlas", "youth_campus"];
const themeChapter = $("#themes");
const themeDeck = $("#themeDeck");
const wideThemeDeck = matchMedia("(min-width: 900px)");
let deckThemes = [];
let deckCovers = [];
let extraCover;
let frontCover;
let deckPosition = 0;
let deckProgress = 0;
let deckDraw;
let queuedDeckPosition;
let manualThemeAnchor;
let scrollToThemeStop = () => false;
let goToChapter = (target) => target.scrollIntoView({ behavior: "instant" });

const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

const chapterPicker = $(".chapter-picker");
document.addEventListener("click", event => {
  if (chapterPicker.open &&
      (!chapterPicker.contains(event.target) || event.target.closest(".section-nav a"))) {
    chapterPicker.open = false;
  }
});
document.addEventListener("keydown", event => {
  if (event.key !== "Escape" || !chapterPicker.open) return;
  const restoreFocus = chapterPicker.contains(document.activeElement);
  chapterPicker.open = false;
  if (restoreFocus) chapterPicker.querySelector("summary").focus();
});

function renderLiveTheme(theme) {
  const viewport = $("#themeLive");
  const previous = viewport.dataset.theme;
  if (previous === theme.id) return;
  $("#themeStage").style.setProperty("--wash", theme.palette[0]);
  const content = document.createElement("div");
  content.className = "theme-preview-article";
  content.innerHTML = theme.article_preview_html;
  viewport.replaceChildren(content);
  viewport.dataset.theme = theme.id;
  viewport.setAttribute("aria-label", `${theme.label} · 文章预览`);
  viewport.scrollTop = 0;
  $("#themeLiveLabel").textContent = theme.label;
  $("#stageThemeName").textContent = theme.label;
  $("#stageThemeDescription").textContent = theme.description;
  $("#themeCatalog").value = theme.id;
  let selectedButton;
  $("#themeChoices").querySelectorAll("button").forEach(button => {
    const selected = button.dataset.theme === theme.id;
    button.setAttribute("aria-pressed", String(selected));
    if (selected) selectedButton = button;
  });
  if (selectedButton) {
    const choices = $("#themeChoices");
    const card = selectedButton.getBoundingClientRect();
    const strip = choices.getBoundingClientRect();
    if (card.left < strip.left || card.right > strip.right) {
      choices.scrollLeft += card.left - strip.left - (strip.width - card.width) / 2;
    }
  }
  if (previous && !reducedMotion.matches) {
    content.animate([{ opacity: .35, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], {
      duration: 260,
      easing: "ease-out",
    });
  }
  $("#themeLiveStatus").textContent = `已切换为${theme.label}`;
}

function themeSpecimen(theme, shortCover = false) {
  const sample = document.createElement("div");
  sample.className = "theme-mini";
  sample.setAttribute("aria-hidden", "true");
  sample.inert = true;
  sample.style.setProperty("--mini-paper", theme.palette[3]);
  const source = document.createElement("div");
  source.className = "theme-mini-source";
  const article = new DOMParser().parseFromString(theme.article_preview_html, "text/html");
  source.innerHTML = article.querySelector('header, [data-theme-layout="hero"]')?.outerHTML ?? "";
  const title = source.querySelector("h1");
  if (shortCover && title) title.textContent = theme.label;
  source.querySelectorAll("[id]").forEach(element => element.removeAttribute("id"));
  sample.append(source);
  return sample;
}

const coverResize = new ResizeObserver(entries => {
  for (const { target } of entries) {
    const sample = target.closest(".theme-mini");
    if (!sample) continue;
    const source = sample.firstElementChild;
    if (sample.clientWidth && source.offsetHeight) {
      const scale = Math.min(sample.clientWidth / source.offsetWidth, sample.clientHeight / source.offsetHeight);
      sample.style.setProperty("--cover-scale", scale);
    }
  }
});

function makeThemeCover(theme) {
  const cover = document.createElement("div");
  cover.className = "theme-cover";
  cover.dataset.theme = theme.id;
  cover.style.setProperty("--cover-ink", theme.palette[0]);
  cover.style.setProperty("--cover-paper", theme.palette[3]);
  const label = document.createElement("strong");
  label.textContent = theme.english;
  const colors = document.createElement("span");
  colors.className = "theme-cover-colors";
  colors.append(...theme.palette.slice(0, 3).map(color => {
    const swatch = document.createElement("span");
    swatch.style.backgroundColor = color;
    return swatch;
  }));
  const footer = document.createElement("div");
  footer.className = "theme-cover-label";
  footer.append(label, colors);
  const sample = themeSpecimen(theme, true);
  cover.append(sample, footer);
  coverResize.observe(sample);
  coverResize.observe(sample.firstElementChild);
  return cover;
}

function animateThemeDraw(incoming, outgoing, outgoingStart) {
  if (reducedMotion.matches) {
    const lifted = "translate(18px, 5px)";
    const draw = incoming.animate([
      { transform: "translate(10px, 4px)", opacity: .5, zIndex: 6, offset: 0 },
      { transform: lifted, opacity: .78, zIndex: 6, offset: .30 },
      { transform: lifted, opacity: .78, zIndex: 8, offset: .31 },
      { transform: "none", opacity: 1, zIndex: 8, offset: 1 }
    ], { duration: 260, easing: "ease-out" });
    if (outgoing.isConnected) {
      const rest = getComputedStyle(outgoing);
      outgoing.animate([
        { transform: outgoingStart, opacity: 1, zIndex: 7, offset: 0 },
        { transform: outgoingStart, opacity: 1, zIndex: 7, offset: .31 },
        { transform: rest.transform, opacity: Number(rest.opacity), zIndex: Number(rest.zIndex), offset: 1 }
      ], { duration: 260, easing: "ease-out" });
    }
    return draw;
  }

  const lifted = "translate(clamp(66px, 9vw, 124px), 15px) rotate(9deg) scale(.98)";
  const duration = 560;
  const draw = incoming.animate([
    { transform: "translate(24px, 12px) rotate(4deg) scale(.945)", zIndex: 6, offset: 0, easing: "cubic-bezier(.20,.68,.34,1)" },
    { transform: lifted, zIndex: 6, offset: .40 },
    { transform: lifted, zIndex: 8, offset: .41, easing: "cubic-bezier(.20,.74,.27,1)" },
    { transform: "translate(-5px, -3px) rotate(-1deg) scale(1.012)", zIndex: 8, offset: .87, easing: "ease-out" },
    { transform: "none", zIndex: 8, offset: 1 }
  ], { duration });
  if (outgoing.isConnected) {
    const rest = getComputedStyle(outgoing);
    outgoing.animate([
      { transform: outgoingStart, opacity: 1, zIndex: 7, offset: 0 },
      { transform: "translate(-11px, 3px) rotate(-2deg) scale(.98)", opacity: 1, zIndex: 7, offset: .41, easing: "ease-out" },
      { transform: rest.transform, opacity: Number(rest.opacity), zIndex: Number(rest.zIndex), offset: 1 }
    ], { duration });
  }
  return draw;
}

function displayThemeDeck(position, theme, draw = true) {
  queuedDeckPosition = undefined;
  if (position === deckPosition && frontCover?.dataset.theme === theme.id) return;
  const outgoing = frontCover;
  const animate = draw && outgoing && wideThemeDeck.matches;
  const outgoingStart = animate ? getComputedStyle(outgoing).transform : undefined;
  themeDeck.getAnimations({ subtree: true }).forEach(animation => animation.cancel());
  deckPosition = position;
  for (const [index, cover] of deckCovers.entries()) {
    const depth = (index - position + deckCovers.length) % deckCovers.length;
    cover.style.setProperty("--cover-rear", Math.min(depth, 3));
    cover.style.zIndex = 6 - depth;
    cover.style.opacity = depth < 3 ? "1" : "0";
  }
  const featured = deckThemes.some(item => item.id === theme.id);
  if (extraCover && (featured || extraCover.dataset.theme !== theme.id)) {
    const sample = extraCover.querySelector(".theme-mini");
    coverResize.unobserve(sample);
    coverResize.unobserve(sample.firstElementChild);
    extraCover.remove();
    extraCover = undefined;
  }
  if (!featured && !extraCover) {
    extraCover = makeThemeCover(theme);
    extraCover.classList.add("theme-cover-extra");
    themeDeck.append(extraCover);
  }
  frontCover = extraCover ?? deckCovers[position];
  deckDraw = animate && outgoing !== frontCover ? animateThemeDraw(frontCover, outgoing, outgoingStart) : undefined;
  if (deckDraw) deckDraw.onfinish = event => {
    if (event.target !== deckDraw) return;
    deckDraw = undefined;
    const next = queuedDeckPosition;
    if (next !== undefined) displayThemeDeck(next, deckThemes[next]);
  };
  renderLiveTheme(theme);
}

function showThemeProgress(value, remeasure = false, scrolling = false) {
  deckProgress = clamp(value, 0, 1);
  if (!deckThemes.length) return;
  if (manualThemeAnchor !== undefined) {
    if (manualThemeAnchor === null || remeasure) manualThemeAnchor = deckProgress;
    if (Math.abs(deckProgress - manualThemeAnchor) < .018) return;
    manualThemeAnchor = undefined;
  }
  const index = Math.round(deckProgress * (deckThemes.length - 1));
  if (scrolling && deckDraw?.playState === "running") {
    queuedDeckPosition = index;
    if (index !== deckPosition && deckDraw.playbackRate === 1) {
      for (const motion of themeDeck.getAnimations({ subtree: true })) motion.updatePlaybackRate(1.5);
    }
    return;
  }
  displayThemeDeck(index, deckThemes[index], !remeasure);
}

function selectGalleryTheme(theme, { stay = false } = {}) {
  const index = deckThemes.indexOf(theme);
  if (!stay && index >= 0 && scrollToThemeStop(index)) return;
  manualThemeAnchor = stay ? null : deckProgress;
  displayThemeDeck(index < 0 ? deckPosition : index, theme, !stay);
}

function stepThemeDeck(direction) {
  const index = deckThemes.findIndex(theme => theme.id === $("#themeLive").dataset.theme);
  const count = deckThemes.length;
  if (count < 2) return;
  const next = index < 0 ? (direction > 0 ? 0 : count - 1) : (index + direction + count) % count;
  selectGalleryTheme(deckThemes[next]);
}

$("#previousTheme").addEventListener("click", () => stepThemeDeck(-1));
$("#nextTheme").addEventListener("click", () => stepThemeDeck(1));

function renderGallery(catalog, requested) {
  $("#themeTotal").textContent = `${catalog.length} 套内置主题`;
  const select = $("#themeCatalog");
  select.replaceChildren(...catalog.map(theme => {
    const option = document.createElement("option");
    option.value = theme.id;
    option.textContent = theme.label;
    return option;
  }));
  deckThemes = featuredThemes.map(id => catalog.find(theme => theme.id === id)).filter(Boolean);
  if (!deckThemes.length) deckThemes = catalog.slice(0, featuredThemes.length);
  deckCovers = deckThemes.map(makeThemeCover);
  themeDeck.replaceChildren(...deckCovers);
  extraCover = undefined;
  frontCover = undefined;
  manualThemeAnchor = undefined;
  const choices = $("#themeChoices");
  choices.replaceChildren(...deckThemes.map(theme => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.theme = theme.id;
    button.setAttribute("aria-controls", "themeLive");
    button.setAttribute("aria-label", theme.label);
    button.style.setProperty("--cover-ink", theme.palette[0]);
    button.style.setProperty("--cover-highlight", theme.palette[1]);
    const label = document.createElement("span");
    label.className = "theme-choice-label";
    label.textContent = theme.label;
    button.append(themeSpecimen(theme), label);
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-pressed") !== "true") selectGalleryTheme(theme);
    });
    return button;
  }));
  $("#themePicker").hidden = false;
  if (requested) selectGalleryTheme(requested, { stay: true });
  else showThemeProgress(deckProgress);
}

$("#themeCatalog").addEventListener("change", event => {
  const theme = themeCatalog.find(item => item.id === event.target.value);
  if (theme) selectGalleryTheme(theme);
});

function visitTheme(theme) {
  selectGalleryTheme(theme, { stay: true });
  $("#themeLive").scrollTop = 0;
  goToChapter(themeChapter);
  $("#themes-title").focus({ preventScroll: true });
}

async function loadThemes() {
  const gallery = $("#themeLive");
  gallery.setAttribute("aria-busy", "true");
  try {
    const response = await fetch("./data/themes.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("theme_fetch_failed");
    const payload = await response.json();
    if (!Array.isArray(payload.themes) || !payload.themes.length) throw new Error("theme_catalog_empty");
    const catalog = [...payload.themes].sort((a, b) => Number(b.id === defaultTheme) - Number(a.id === defaultTheme));
    themeCatalog = catalog;
    const requested = new URLSearchParams(window.location.search).get("theme");
    renderGallery(catalog, catalog.find(theme => theme.id === requested));
  } catch {
    const notice = document.createElement("p");
    notice.className = "theme-loading";
    notice.textContent = "文章预览暂时未加载。";
    const retry = document.createElement("button");
    retry.className = "theme-retry";
    retry.type = "button";
    retry.textContent = "重新加载";
    retry.addEventListener("click", loadThemes);
    notice.append(retry);
    gallery.replaceChildren(notice);
  } finally {
    gallery.setAttribute("aria-busy", "false");
    themeChapter.dispatchEvent(new Event("theme-gallery-ready"));
  }
}

async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch {
    // Embedded browsers may deny the async clipboard but allow a user copy.
  }
  const previousFocus = document.activeElement;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  Object.assign(textarea.style, { position: "fixed", left: "0", top: "0", width: "1px", height: "1px", opacity: ".01" });
  document.body.append(textarea);
  let copied = false;
  try {
    textarea.focus({ preventScroll: true });
    textarea.select();
    copied = document.execCommand("copy");
  } finally {
    textarea.remove();
    previousFocus?.focus({ preventScroll: true });
  }
  if (!copied) throw new Error("copy_rejected");
}

function showToast(message) {
  window.clearTimeout(toastTimer);
  copyToast.textContent = message;
  copyToast.classList.add("show");
  toastTimer = window.setTimeout(() => copyToast.classList.remove("show"), 4200);
}

document.querySelectorAll("[data-copy-install], [data-copy-theme]").forEach((button) => {
  button.addEventListener("click", async () => {
    const original = button.innerHTML;
    const previousWidth = button.style.width;
    button.style.width = button.getBoundingClientRect().width + "px";
    button.disabled = true;
    const isTheme = button.hasAttribute("data-copy-theme");
    const text = isTheme ? themePrompt : installPrompt;
    try {
      await copyText(text);
      button.textContent = "已复制 ✓";
      showToast(isTheme ? "创作指令已复制，和参考图一起发给 Agent 即可。" : "安装指令已复制，发给你的 Agent 即可。");
    } catch {
      button.disabled = false;
      button.style.width = previousWidth;
      dialogTrigger = button;
      promptField.value = text;
      promptField.setAttribute("aria-label", isTheme ? "完整主题创作指令" : "完整安装指令");
      promptHelpLink.hidden = isTheme;
      if (!dialog.open) dialog.showModal();
      promptField.focus({ preventScroll: true });
      promptField.select();
    } finally {
      window.setTimeout(() => {
        button.innerHTML = original;
        button.style.width = previousWidth;
        button.disabled = false;
      }, 1800);
    }
  });
});
dialog.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
dialog.addEventListener("close", () => {
  dialogTrigger?.focus({ preventScroll: true });
  dialogTrigger = null;
});
dialog.addEventListener("click", (event) => {
  if (event.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
});
const productFilm = $("#productFilm");
const filmDialog = $("#filmDialog");
const filmFile = filmDialog.querySelector(".film-file");
$("#product-film").addEventListener("click", event => {
  if (!isPlainClick(event) || typeof filmDialog.showModal !== "function") return;
  event.preventDefault();
  filmDialog.showModal();
  if (productFilm.ended) productFilm.currentTime = 0;
  productFilm.play().catch(() => { filmFile.hidden = false; });
});
filmDialog.addEventListener("close", () => productFilm.pause());
productFilm.addEventListener("playing", () => { filmFile.hidden = true; });
productFilm.addEventListener("error", () => { filmFile.hidden = false; });

// Keep mobile browsing horizontal, without moving the page to an anchor.
const layoutChapter = $("#layout-demo");
const editionCards = [...layoutChapter.querySelectorAll(".edition")];
layoutChapter.toggleAttribute("data-full-preview", new URLSearchParams(location.search).get("preview") === "paper-arrival-full");
function syncEditionVisibility() {
  layoutChapter.toggleAttribute("data-page-hidden", document.hidden);
}
syncEditionVisibility();
document.addEventListener("visibilitychange", syncEditionVisibility);
// Match the workbench mobile profile (405px viewport, 24px inner gutters).
const phoneSourceWidth = 405;
const phonePreviewResize = new ResizeObserver(entries => {
  entries.forEach(({ target }) => {
    const scale = Math.min(1, target.clientWidth / phoneSourceWidth);
    target.style.setProperty("--phone-preview-scale", scale || 1);
    if (scale && target.classList.contains("edition-sheet")) {
      target.style.setProperty("--edition-source-height", `${target.clientHeight / scale}px`);
    }
  });
});
const editionSelections = {
  natural_atlas: [
    "#slot-003",
    "#image-slot-001",
    "#slot-002"
  ],
  warm_humanist: [
    '[data-heading-level="2"]',
    "#image-slot-001",
    "#slot-004"
  ],
  editorial_contrast: [
    "#slot-003",
    "#image-slot-001",
    '[data-heading-level="2"]'
  ]
};
const editionMobileStyles = `
  *, *::before, *::after { box-sizing: border-box !important; }
  .wechat-document {
    width: ${phoneSourceWidth}px;
    min-height: var(--edition-source-height, 0px);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 13px 24px 14px;
    color: #000;
    font-family: "Noto Sans SC", "Microsoft YaHei", Arial, sans-serif;
  }
  img { max-width: 100%; height: auto; }
  :is(p, span, strong, b, em, i, a, blockquote, li, td, th) { overflow-wrap: anywhere !important; word-break: break-word; }
  .preview-part, .preview-part > div { display: flow-root; }
  /* Keep the authored component styles. The excerpt's host sets the spacing between them. */
  .preview-part + .preview-part { margin-top: 15px; }
  .preview-part > div > :first-child,
  .preview-part:first-child [data-content-role="article-metadata-preview"],
  .preview-part :is([id^="slot-"] > section:only-child, [id^="slot-"] > section:only-child > :is(section, blockquote):only-child) {
    margin-block: 0 !important;
  }
`;

function isPlainClick(event) {
  return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey;
}

const editionDocuments = new Map();

function loadEdition(url) {
  if (!editionDocuments.has(url)) {
    const pending = fetch(url, { cache: "no-cache" }).then(async response => {
      if (!response.ok) throw new Error("edition_unavailable");
      const page = new DOMParser().parseFromString(await response.text(), "text/html");
      const documentBody = page.querySelector(".wechat-document");
      const label = page.querySelector(".article-tag")?.firstChild?.textContent.trim();
      if (!documentBody?.querySelector("h1") || !label) throw new Error("invalid_edition");
      documentBody.querySelectorAll("img[src]").forEach(image => {
        image.src = new URL(image.getAttribute("src"), url).href;
        image.loading = "lazy";
        image.decoding = "async";
      });
      return { documentBody, label };
    }).catch(error => {
      editionDocuments.delete(url);
      throw error;
    });
    editionDocuments.set(url, pending);
  }
  return editionDocuments.get(url);
}

function demoteEditionTitle(article) {
  const title = article.querySelector("h1");
  const heading = document.createElement("h3");
  heading.style.cssText = title.style.cssText;
  heading.append(...title.childNodes);
  title.replaceWith(heading);
}

const caseChapter = $("#custom-themes");
async function loadThemeCase() {
  try {
    const { documentBody } = await loadEdition($("#themeCaseArticle").href);
    const shadow = $("#caseResults").attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      *, *::before, *::after { box-sizing: border-box; }
      .wechat-document { display: flow-root; padding: 8px 18px; color: #343331; background-color: #fff; }
      img { max-width: 100%; height: auto; }
    `;
    const article = makeEditionArticle(documentBody);
    article.querySelectorAll("img").forEach(image => { image.loading = "eager"; });
    shadow.append(style, article);
    caseChapter.querySelector(".case-reading-window").hidden = false;
    $("#themeCaseArticle").hidden = true;
    caseChapter.toggleAttribute("data-case-ready", true);
  } catch {
    $("#themeCaseArticle").hidden = false;
  } finally {
    caseChapter.dispatchEvent(new Event("theme-case-ready"));
  }
}

function makeEditionArticle(documentBody) {
  const article = documentBody.cloneNode(true);
  // The embedded article sits within the homepage's own main landmark.
  const main = article.querySelector("main");
  const content = document.createElement("div");
  content.style.cssText = main.style.cssText;
  content.append(...main.childNodes);
  main.replaceWith(content);
  demoteEditionTitle(article);
  return article;
}

async function renderEditionPreview(card) {
  const { documentBody } = await loadEdition(card.href);
  const main = documentBody.querySelector("main");
  const parts = [
    documentBody.firstElementChild,
    ...editionSelections[card.dataset.editionTheme].map(selector => main.querySelector(selector))
  ];
  if (parts.some(part => !part)) throw new Error("missing_edition_component");

  const host = document.createElement("div");
  host.className = "edition-preview";
  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = editionMobileStyles;
  const article = document.createElement("div");
  article.className = "wechat-document";
  parts.forEach(source => {
    const part = document.createElement("div");
    part.className = "preview-part";
    const content = document.createElement("div");
    content.append(source.cloneNode(true));
    if (source.id === "slot-002" && card.dataset.editionTheme === "natural_atlas") {
      // The complete article keeps all four steps of the published component.
      content.querySelector("[data-list-role] > section:last-child")?.remove();
    }
    content.querySelectorAll("img").forEach(image => { image.loading = "eager"; });
    part.append(content);
    article.append(part);
  });
  demoteEditionTitle(article);
  shadow.append(style, article);

  const sheet = card.querySelector(".edition-sheet");
  sheet.replaceChildren(host);
  phonePreviewResize.observe(sheet);
}

async function buildEditionPreviews() {
  await Promise.allSettled(editionCards.map(renderEditionPreview));
  layoutChapter.dispatchEvent(new Event("edition-ready"));
}

let coverSlots = [];
const coverPhotograph = $(".cover-photograph");
let shownCoverPairs = 0;

// A small gap between the forward and reverse thresholds absorbs trackpad jitter.
function crossedSteps(value, count, first, interval, previous) {
  const stepsAt = offset => clamp(Math.floor((value + offset - first) / interval) + 1, 0, count);
  return clamp(previous, stepsAt(0), stepsAt(.012));
}

function showCoverProgress(value) {
  const pairCount = Math.ceil(coverSlots.length / 2);
  const shown = crossedSteps(value, pairCount, .028, .37, shownCoverPairs);
  if (shown === shownCoverPairs) return;
  coverPhotograph.style.setProperty("--cover-focus-loss", shown / pairCount);
  coverSlots.forEach((slot, index) => {
    const pair = Math.floor(index / 2);
    const entering = pair >= shownCoverPairs && pair < shown;
    const delay = entering ? (pair - shownCoverPairs) * 155 + (index % 2) * 115 : 0;
    slot.style.setProperty("--entry-delay", delay + "ms");
    slot.toggleAttribute("data-shown", pair < shown);
    slot.toggleAttribute("data-previous-pair", pair < shown - 1);
  });
  shownCoverPairs = shown;
}

async function loadCoverExcerpts() {
  const cover = $("#top");
  try {
    const { documentBody } = await loadEdition($("#edition-coffee").href);
    const parts = [
      ["chapter", '[data-heading-level="2"]'],
      ["term", "#slot-002 > section"],
      ["list", "#slot-001 > section"],
      ["quote", "#slot-004 > section"],
      ["picture", "#image-slot-002"],
      ["question", '[data-content-role="inline-emphasis"]'],
    ];
    const slips = parts.map(([name, selector]) => {
      const source = documentBody.querySelector(selector);
      if (!source) return null;
      const component = source.cloneNode(true);
      component.removeAttribute("id");
      if (name === "list") component.querySelectorAll(":scope > section:nth-of-type(n+3)").forEach(row => row.remove());
      if (name === "term") {
        component.querySelectorAll(":scope > section:not(:first-of-type), :scope > section > section > p + p").forEach(el => el.remove());
      }
      const slip = document.createElement("div");
      slip.className = "cover-slip";
      slip.dataset.part = name;
      slip.append(component);
      const slot = document.createElement("div");
      slot.className = "cover-slot";
      slot.append(slip);
      return slot;
    });
    if (slips.some(slip => !slip)) return;
    coverSlots = slips;
    $(".cover-excerpts").replaceChildren(...slips);
    // Measure untransformed paper so the real component can fit either grid dimension.
    const fitPapers = new ResizeObserver(entries => {
      for (const { target } of entries) {
        const slot = target.closest(".cover-slot");
        const paper = slot.firstElementChild;
        if (!slot.clientWidth || !paper.offsetHeight) continue;
        const scale = Math.min(slot.clientWidth / paper.offsetWidth, slot.clientHeight / paper.offsetHeight, 1.5);
        slot.style.setProperty("--slip-scale", scale.toFixed(4));
      }
    });
    slips.forEach(slot => {
      fitPapers.observe(slot);
      fitPapers.observe(slot.firstElementChild);
    });
    cover.setAttribute("data-has-excerpts", "");
    cover.dispatchEvent(new Event("cover-ready"));
  } catch {
    // The photograph and film stay available if the sample article cannot load.
  }
}

const reader = $("#editionReader");
const readerScroll = $("#editionReaderScroll");
const readerTheme = $("#editionReaderTheme");
let readerRequest = 0;

async function showEdition(card) {
  const request = ++readerRequest;
  $("#editionReaderTitle").textContent = "成稿阅读";
  readerTheme.dataset.theme = card.dataset.editionTheme;
  readerTheme.href = `?theme=${encodeURIComponent(card.dataset.editionTheme)}#themes`;
  const message = document.createElement("p");
  message.className = "edition-reader-message";
  message.setAttribute("role", "status");
  message.textContent = "正在打开成稿…";
  readerScroll.replaceChildren(message);
  readerScroll.scrollTop = 0;
  const sheet = card.querySelector(".edition-sheet").getBoundingClientRect();
  reader.showModal();
  if (!reducedMotion.matches) {
    const frame = reader.getBoundingClientRect();
    const x = sheet.left + sheet.width / 2 - frame.left - frame.width / 2;
    const y = sheet.top + sheet.height / 2 - frame.top - frame.height / 2;
    const scale = Math.min(sheet.width / frame.width, sheet.height / frame.height, .92);
    reader.animate([
      { transform: `translate(${x}px, ${y}px) scale(${scale})`, opacity: .3 },
      { transform: "none", opacity: 1 },
    ], { duration: 540, easing: "cubic-bezier(.28,.12,.22,1)" });
  }

  try {
    const { documentBody, label } = await loadEdition(card.href);
    if (!reader.open || request !== readerRequest) return;
    $("#editionReaderTitle").textContent = `${label} · 成稿`;
    readerScroll.replaceChildren(makeEditionArticle(documentBody));
  } catch {
    if (!reader.open || request !== readerRequest) return;
    message.textContent = "成稿暂时未能加载，请关闭后重试。";
  }
}

editionCards.forEach(card => {
  card.addEventListener("click", event => {
    if (!isPlainClick(event)) return;
    event.preventDefault();
    showEdition(card);
  });
});
$("#editionReaderClose").addEventListener("click", () => reader.close());
reader.addEventListener("click", event => {
  if (event.target === reader) {
    const rect = reader.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientY < rect.top || event.clientX > rect.right || event.clientY > rect.bottom) reader.close();
  }
});
readerTheme.addEventListener("click", event => {
  const theme = themeCatalog.find(item => item.id === readerTheme.dataset.theme);
  if (!theme || !isPlainClick(event)) return;
  event.preventDefault();
  reader.close();
  visitTheme(theme);
});

function setupChapterStack() {
  const main = $("#main");
  const cover = $("#top");
  const nav = $(".site-nav");
  const stackingViewport = matchMedia("(min-width: 900px) and (min-height: 650px)");
  const viewport = window.visualViewport;
  const chapters = [...main.querySelectorAll(":scope > .sheet-chapter")].map((sheet, index) => {
    const start = document.createElement("div");
    const runway = document.createElement("div");
    const pin = sheet.querySelector(".sheet-pin");
    const shade = document.createElement("span");
    start.className = "stack-start";
    runway.className = "stack-runway";
    shade.className = "stack-shade";
    start.setAttribute("aria-hidden", "true");
    runway.setAttribute("aria-hidden", "true");
    shade.setAttribute("aria-hidden", "true");
    sheet.before(start);
    sheet.after(runway);
    pin.append(shade);
    sheet.style.setProperty("--stack-index", index);
    sheet.style.setProperty("--stack-order", index + 1);
    return {
      sheet, start, runway, pin, shade,
      face: sheet.querySelector(".sheet-section"), at: 0, progressStart: 0, distance: 0, progress: null,
    };
  });
  const editions = chapters.find(chapter => chapter.sheet === layoutChapter);
  const themes = chapters.find(chapter => chapter.sheet === themeChapter);
  main.style.setProperty("--stack-last-index", chapters.length - 1);
  let stacked = false;
  let requestedFrame = 0;
  let editionReady = false;
  let galleryReady = false;
  let themeCaseReady = false;
  let activeChapter = -1;
  let lastEditionWheel = 0;
  let lastEditionDelta = 0;
  let tailUntil = 0;
  let chapterAnimation;
  let layerAnimations = [];
  let departingChapter;

  function stopChapterAnimation() {
    chapterAnimation?.cancel();
    layerAnimations.forEach(animation => animation.cancel());
    layerAnimations = [];
    if (departingChapter) departingChapter.sheet.removeAttribute("data-stack-visible");
    chapterAnimation = undefined;
    departingChapter = undefined;
  }

  function activateChapter(next, animate) {
    if (next === activeChapter) return;
    const direction = next - activeChapter;
    const animateTurn = animate && activeChapter >= 0 && Math.abs(direction) === 1;
    const reduced = reducedMotion.matches;
    const previous = chapters[activeChapter];
    const moving = direction > 0 ? chapters[next] : previous;
    const interrupted = animateTurn && chapterAnimation?.effect?.target === moving.face
      ? getComputedStyle(moving.face)
      : null;
    const resume = interrupted && { transform: interrupted.transform, opacity: interrupted.opacity };
    const layers = animateTurn
      ? chapters.slice(0, Math.min(next, activeChapter) + 1).map(({ pin, shade }) => ({
          pin, shade, transform: getComputedStyle(pin).transform, opacity: getComputedStyle(shade).opacity,
        }))
      : [];

    stopChapterAnimation();
    if (previous?.sheet === themeChapter) previous.progress = null;
    departingChapter = animateTurn && direction < 0 ? previous : undefined;
    activeChapter = next;
    lastEditionWheel = 0;
    tailUntil = 0;
    chapters.forEach((chapter, index) => {
      chapter.sheet.toggleAttribute("data-stack-visible", index <= next || chapter === departingChapter);
      chapter.sheet.toggleAttribute("data-stack-active", index === next);
      chapter.sheet.style.setProperty("--stack-depth", Math.max(0, next - index));
      chapter.pin.inert = index !== next;
    });

    const enteringEditions = chapters[next].sheet === layoutChapter;
    if (enteringEditions) {
      if (animateTurn && direction > 0 && !reduced) layoutChapter.style.setProperty("--arrival-lead", "420ms");
      else layoutChapter.style.removeProperty("--arrival-lead");
      layoutChapter.dataset.entrance = direction < 0 ? "settled" : "playing";
    }
    else if (previous?.sheet === layoutChapter) {
      layoutChapter.removeAttribute("data-entrance");
      layoutChapter.style.removeProperty("--arrival-lead");
    }
    if (!animateTurn) return;
    const forward = direction > 0;
    const duration = reduced ? 280 : forward ? 960 : 740;
    const lead = forward && !reduced && !resume ? 80 : 0;
    // Let the lower card begin receding before the rising card covers most of it.
    const layerEasing = !reduced && forward
      ? "cubic-bezier(.26,.065,.2,1.27)"
      : "cubic-bezier(.3,.08,.26,1)";
    const layerTiming = { duration: duration + lead, easing: layerEasing };
    layerAnimations = layers.flatMap(({ pin, shade, transform, opacity }) => [
      pin.animate([{ transform }, { transform: getComputedStyle(pin).transform }], layerTiming),
      shade.animate([{ opacity }, { opacity: getComputedStyle(shade).opacity }], layerTiming),
    ]);
    const distance = reduced ? "14px" : "calc(100svh - var(--stack-header))";
    const resting = { transform: "translateY(0)", opacity: 1 };
    const below = { transform: `translateY(${distance})`, opacity: forward ? (reduced ? .82 : 1) : 0 };
    const frames = forward ? [below, resting] : [resting, below];
    if (resume) frames[0] = { ...frames[0], ...resume };
    const animation = moving.face.animate(frames, {
      duration,
      delay: lead,
      easing: reduced ? "cubic-bezier(.32,.08,.27,1)" : forward
        ? "cubic-bezier(.32,.08,.24,1.05)"
        : "cubic-bezier(.4,.08,.55,1)",
      fill: "both",
    });
    chapterAnimation = animation;
    animation.onfinish = () => {
      if (chapterAnimation !== animation) return;
      stopChapterAnimation();
      if (chapters[next].sheet === themeChapter) paint();
    };
  }

  function paint(remeasure = false, animate = true) {
    if (!stacked) {
      const travel = cover.offsetHeight - cover.firstElementChild.offsetHeight;
      const position = nav.offsetHeight - cover.getBoundingClientRect().top;
      showCoverProgress(travel > 0 ? clamp(position / travel, 0, 1) : 0);
      const papers = layoutChapter.getBoundingClientRect();
      const visible = Math.min(papers.bottom, innerHeight) - Math.max(papers.top, nav.offsetHeight);
      if (visible <= 0) {
        layoutChapter.dataset.entrance = "waiting";
      }
      else if (visible >= .3 * Math.min(papers.height, innerHeight)) layoutChapter.dataset.entrance = "playing";
      return;
    }
    const position = window.scrollY;
    const scrollTurn = !remeasure && animate;
    // Leave room for tiny touchpad reversals at a chapter boundary.
    const current = chapters.findLastIndex(({ at }, index) =>
      position + .25 >= at - (scrollTurn && index <= activeChapter ? 12 : 0)
    );
    activateChapter(Math.max(0, current), scrollTurn);
    chapters.forEach(chapter => {
      const { sheet, progressStart, distance } = chapter;
      if (!distance) return;
      const active = sheet === chapters[activeChapter].sheet;
      if (sheet === themeChapter && active && scrollTurn && chapterAnimation &&
          chapterAnimation.effect.getComputedTiming().progress < .8) return;
      const progress = clamp((position - progressStart) / distance, 0, 1);
      if (!remeasure && progress === chapter.progress) return;
      chapter.progress = progress;
      if (sheet === cover) showCoverProgress(progress);
      if (sheet === themeChapter) showThemeProgress(progress, remeasure || !active, active && scrollTurn);
    });
  }

  function handleScroll() {
    if (requestedFrame) return;
    requestedFrame = requestAnimationFrame(() => {
      requestedFrame = 0;
      paint();
    });
  }

  function measure() {
    const previousY = window.scrollY;
    const previousChapter = chapters.findLast(chapter => chapter.at !== 0 && chapter.at <= previousY + 2);
    const previousOffset = previousChapter ? previousY - previousChapter.at : 0;
    const wasStacked = stacked;
    const eligible = stackingViewport.matches && (viewport?.scale ?? 1) <= 1.01;
    const header = nav.offsetHeight;
    const bottomLimit = document.documentElement.clientHeight - 8;
    main.style.setProperty("--stack-header", `${header}px`);
    main.classList.toggle("is-stacked", eligible);
    stacked = eligible && chapters.every(({ face, pin }) =>
      pin.offsetHeight <= Math.ceil(Number.parseFloat(getComputedStyle(face).minHeight)) &&
      Number.parseFloat(getComputedStyle(pin).top) + pin.offsetHeight <= bottomLimit
    );
    main.classList.toggle("is-stacked", stacked);
    if (stacked !== wasStacked) {
      if (stacked) window.addEventListener("wheel", paceEditionWheel, { passive: false });
      else window.removeEventListener("wheel", paceEditionWheel);
    }
    if (!stacked && activeChapter >= 0) {
      stopChapterAnimation();
      chapters.forEach(({ sheet, pin }) => {
        sheet.removeAttribute("data-stack-visible");
        sheet.removeAttribute("data-stack-active");
        pin.inert = false;
      });
      activeChapter = -1;
    }

    chapters.forEach(chapter => {
      const { sheet, runway } = chapter;
      const themeScroll = stacked && sheet === themeChapter;
      runway.classList.toggle("stack-cover", stacked && sheet === cover && cover.hasAttribute("data-has-excerpts"));
      runway.classList.toggle("stack-themes", themeScroll);
      sheet.classList.toggle("has-theme-scroll", themeScroll);
    });
    chapters.forEach(chapter => {
      const { start, runway, sheet } = chapter;
      chapter.at = start.getBoundingClientRect().top + window.scrollY - header;
      const runwayHeight = runway.matches(".stack-cover, .stack-themes") ? runway.offsetHeight : 0;
      chapter.progressStart = chapter.at;
      chapter.distance = runwayHeight;
    });
    // Probing fixed sheets can temporarily shorten the document on a small desktop.
    if (previousChapter && previousY > 0) {
      const top = wasStacked === stacked ? previousY : previousChapter.at + previousOffset;
      if (Math.abs(window.scrollY - top) > 1) window.scrollTo({ top, behavior: "instant" });
    }
    paint(true);
  }

  function scrollToPosition(top) {
    window.scrollTo({ top, behavior: "instant" });
    paint(false, false);
  }

  goToChapter = target => {
    const chapter = chapters.find(({ sheet }) => sheet === target.closest(".sheet-chapter"));
    if (stacked && chapter) {
      scrollToPosition(chapter.at + .5);
    } else {
      target.scrollIntoView({ behavior: "instant" });
    }
  };

  scrollToThemeStop = index => {
    const chapter = chapters.find(({ sheet }) => sheet === themeChapter);
    if (!chapter.distance || deckThemes.length < 2) return false;
    manualThemeAnchor = undefined;
    chapter.progress = null;
    const stop = chapter.progressStart + chapter.distance * index / (deckThemes.length - 1);
    scrollToPosition(Math.max(chapter.at, stop));
    return true;
  };

  function revealHash() {
    const target = document.getElementById(location.hash.slice(1));
    if (target?.closest(".sheet-chapter")) goToChapter(target);
  }

  function revealInitialHash() {
    if (editionReady && galleryReady && themeCaseReady && document.readyState === "complete") revealHash();
  }

  window.addEventListener("scroll", handleScroll, { passive: true });
  // Let the three papers settle before another forward wheel tick turns the page.
  // Leave nested readers, zoom gestures and horizontal scrolling alone.
  function paceEditionWheel(event) {
    if (!event.cancelable || event.defaultPrevented || event.ctrlKey || !event.deltaY ||
        Math.abs(event.deltaX) > Math.abs(event.deltaY) || document.querySelector("dialog[open]") ||
        event.target.closest?.("select")) return;
    const reader = event.target.closest?.(".preview-scroll, .case-reading-window");
    if (reader && (event.deltaY < 0 ? reader.scrollTop > 0 :
        reader.scrollTop + reader.clientHeight < reader.scrollHeight - 1)) return;
    const activeSheet = chapters[activeChapter]?.sheet;
    if (activeSheet !== layoutChapter) {
      // A single fast wheel tick can cross both boundaries of this short chapter.
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1;
      const destination = window.scrollY + event.deltaY * unit;
      if ((activeSheet === cover && event.deltaY > 0 && destination >= themes.at) ||
          (activeSheet === themeChapter && event.deltaY < 0 && destination < editions.at)) {
        event.preventDefault();
        window.scrollTo({ top: (editions.at + themes.at) / 2, behavior: "instant" });
        paint();
      }
      return;
    }
    const now = performance.now();
    const delta = event.deltaY;
    const trailing = now < tailUntil && now - lastEditionWheel < 90 &&
      event.deltaMode === 0 && delta <= 16 && delta <= lastEditionDelta;
    lastEditionWheel = now;
    lastEditionDelta = delta;
    if (delta > 0) {
      // The last paper finishes last, even when the layout switches at a breakpoint.
      const arriving = editionCards.at(-1)?.getAnimations().some(animation =>
        animation.animationName === "edition-arrive" && animation.playState !== "finished");
      if (arriving || trailing) event.preventDefault();
    }
    if (delta < 0 && departingChapter && chapterAnimation) event.preventDefault();
  }
  editionCards.at(-1)?.addEventListener("animationend", event => {
    if (event.animationName === "edition-arrive" && chapters[activeChapter]?.sheet === layoutChapter) {
      tailUntil = performance.now() + 240;
    }
  });
  window.addEventListener("resize", measure);
  viewport?.addEventListener("resize", measure);
  stackingViewport.addEventListener("change", measure);
  cover.addEventListener("cover-ready", () => {
    measure();
    revealInitialHash();
  }, { once: true });
  layoutChapter.addEventListener("edition-ready", () => {
    editionReady = true;
    measure();
    revealInitialHash();
  }, { once: true });
  themeChapter.addEventListener("theme-gallery-ready", () => {
    galleryReady = true;
    measure();
    revealInitialHash();
  }, { once: true });
  $("#custom-themes").addEventListener("theme-case-ready", () => {
    themeCaseReady = true;
    measure();
    revealInitialHash();
  }, { once: true });
  window.addEventListener("hashchange", revealHash);
  window.addEventListener("load", revealInitialHash, { once: true });
  document.addEventListener("click", event => {
    const link = event.target.closest('a[href^="#"]');
    const target = link && document.getElementById(link.hash.slice(1));
    if (!stacked || !target?.closest(".sheet-chapter") || !isPlainClick(event)) return;
    event.preventDefault();
    if (location.hash !== link.hash) history.pushState(null, "", link.hash);
    goToChapter(target);
    const heading = document.getElementById(target.closest(".sheet-chapter").getAttribute("aria-labelledby"));
    heading?.focus({ preventScroll: true });
  });
  const observer = new ResizeObserver(measure);
  observer.observe(nav);
  chapters.forEach(({ pin }) => observer.observe(pin));
  measure();
}

setupChapterStack();
phonePreviewResize.observe($("#themeLive"));
loadThemes();
buildEditionPreviews();
loadCoverExcerpts();
loadThemeCase();
