const index = document.querySelector("#themeIndex");
const preview = document.querySelector("#themePreview");
const label = document.querySelector("#themeLabel");
const english = document.querySelector("#themeEnglish");
const description = document.querySelector("#themeDescription");
const swatches = document.querySelector("#themeSwatches");
const stage = document.querySelector("#themeStage");
const announcement = document.querySelector("#themeAnnouncement");
const copyToast = document.querySelector("#copyToast");
const dialog = document.querySelector("#installDialog");
const promptField = document.querySelector("#installPromptText");
const specimenSelect = document.querySelector("#specimenSelect");
let currentTheme;
let selectedThemeId = "youth_campus";
let toastTimer;
let dialogTrigger = null;

const installPrompt = `请打开并完整执行下面的 Agent 安装说明，为我安装或升级完整的 wechat-visual-director 产品。使用当前安装入口，不要沿用旧文档里的固定版本。必须同时安装轻量 Skill 和本地工作台、运行 doctor --json 并打开工作台；不要只复制 Skill，也不要把源码仓库克隆到 Skill 目录。完成后给我实际安装版本、工作台链接和不超过五行的上手说明，包括下一句可以怎么使用；如果受限未完成，说明当前状态和下一步，不要只回复已安装。不要读取或回显任何密钥。
https://github.com/zhouke0929/wechat-visual-director/blob/main/INSTALL_FOR_AGENT.md`;
promptField.value = installPrompt;
const themePrompt = `请用 wechat-visual-director，根据我提供的组件参考图或风格描述【填写风格】，创作一整套新的主题。只有描述时先寻找可查看的成品组件参考，把方向具体化。联想关联元素，延展完整视觉语言，不要只给现有主题换色。正文保持可编辑，先在样本册和一篇示例文章中让我查看效果，不要创建公众号草稿。`;

function renderSpecimen() {
  if (!currentTheme) return;
  const selected = [...(currentTheme.foundation_specimens ?? currentTheme.rhythm_primitives), ...currentTheme.components].find((item) => (item.role ?? item.component_type) === specimenSelect.value);
  preview.innerHTML = selected
    ? `<div style="padding:24px;background:#fff">${selected.html}</div>`
    : (currentTheme.article_preview_html ?? currentTheme.full_preview_html);
  preview.scrollTop = 0;
  preview.setAttribute("aria-label", currentTheme.label + (selected ? ` · ${selected.label}` : "主题文章预览"));
}
specimenSelect.addEventListener("change", renderSpecimen);

function renderTheme(theme, announce = true) {
  selectedThemeId = theme.id;
  currentTheme = theme;
  label.textContent = theme.label;
  english.textContent = theme.english;
  description.textContent = theme.description;
  stage.style.setProperty("--theme-accent", theme.palette[0]);
  swatches.replaceChildren(...theme.palette.map((color) => {
    const dot = document.createElement("i");
    dot.style.backgroundColor = color;
    return dot;
  }));
  // HTML comes from the repository's generated, public theme catalog.
  const previousSpecimen = specimenSelect.value;
  const articleOption = new Option("整篇文章 · 正式渲染", "article");
  const groups = [["基础样式", theme.foundation_specimens ?? theme.rhythm_primitives], ["语义组件", theme.components]].map(([name, items]) => {
    const group = document.createElement("optgroup");
    group.label = name;
    group.append(...items.map((item) => new Option(item.label, item.role ?? item.component_type)));
    return group;
  });
  specimenSelect.replaceChildren(articleOption, ...groups);
  specimenSelect.value = [...specimenSelect.options].some((option) => option.value === previousSpecimen) ? previousSpecimen : "article";
  renderSpecimen();
  document.querySelectorAll(".theme-button").forEach((button) => {
    const active = button.dataset.themeId === theme.id;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if (announce) announcement.textContent = "已切换为" + theme.label;
}

function createThemeButton(theme, themeIndex) {
  const button = document.createElement("button");
  button.className = "theme-button";
  button.type = "button";
  button.dataset.themeId = theme.id;
  button.setAttribute("aria-pressed", "false");
  button.setAttribute("aria-label", "切换至" + theme.label);
  const number = document.createElement("span");
  number.className = "theme-num";
  number.textContent = String(themeIndex + 1).padStart(2, "0");
  number.setAttribute("aria-hidden", "true");
  const title = document.createElement("strong");
  title.textContent = theme.label;
  const palette = document.createElement("span");
  palette.className = "mini-swatches";
  palette.setAttribute("aria-hidden", "true");
  theme.palette.forEach((color) => {
    const item = document.createElement("i");
    item.style.backgroundColor = color;
    palette.append(item);
  });
  button.append(number, title, palette);
  button.addEventListener("click", () => renderTheme(theme));
  return button;
}

async function loadThemes() {
  index.setAttribute("aria-busy", "true");
  try {
    const response = await fetch("./data/themes.json");
    if (!response.ok) throw new Error("theme_fetch_failed");
    const payload = await response.json();
    const themes = payload.themes;
    if (!Array.isArray(themes) || !themes.length) throw new Error("theme_catalog_empty");
    index.replaceChildren(...themes.map(createThemeButton));
    renderTheme(themes.find((theme) => theme.id === selectedThemeId) ?? themes[0], false);
  } catch {
    const notice = document.createElement("p");
    notice.className = "theme-loading";
    notice.textContent = "主题暂时未加载。你仍可阅读上方完整成稿，或";
    const retry = document.createElement("button");
    retry.className = "theme-retry";
    retry.type = "button";
    retry.textContent = "重新加载";
    retry.addEventListener("click", loadThemes);
    notice.append(retry);
    index.replaceChildren(notice);
  } finally {
    index.setAttribute("aria-busy", "false");
  }
}

index.addEventListener("keydown", (event) => {
  if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
  const buttons = [...index.querySelectorAll(".theme-button")];
  const current = buttons.indexOf(event.target);
  if (current === -1) return;
  event.preventDefault();
  let target = current;
  if (event.key === "ArrowRight") target = (current + 1) % buttons.length;
  if (event.key === "ArrowLeft") target = (current - 1 + buttons.length) % buttons.length;
  if (event.key === "Home") target = 0;
  if (event.key === "End") target = buttons.length - 1;
  buttons[target].focus({ preventScroll: true });
  buttons[target].click();
});

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
  toastTimer = window.setTimeout(() => copyToast.classList.remove("show"), 2600);
}

document.querySelectorAll("[data-copy-install], [data-copy-theme]").forEach((button) => {
  button.addEventListener("click", async () => {
    const original = button.innerHTML;
    const previousWidth = button.style.width;
    button.style.width = button.getBoundingClientRect().width + "px";
    button.disabled = true;
    const text = button.hasAttribute("data-copy-theme") ? themePrompt : installPrompt;
    try {
      await copyText(text);
      button.textContent = "已复制 ✓";
      showToast("已复制。回到 Agent 对话，粘贴即可。");
    } catch {
      button.disabled = false;
      button.style.width = previousWidth;
      dialogTrigger = button;
      promptField.value = text;
      promptField.setAttribute("aria-label", button.hasAttribute("data-copy-theme") ? "完整主题创作指令" : "完整安装指令");
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
const productFilm = document.querySelector("#productFilm");
const filmPlay = document.querySelector(".film-play");
productFilm.controls = false;
filmPlay.hidden = false;
filmPlay.addEventListener("click", async () => {
  productFilm.controls = true;
  try {
    await productFilm.play();
  } catch {
    // Native controls remain available if playback cannot start.
    filmPlay.hidden = true;
    productFilm.focus({ preventScroll: true });
  }
});
productFilm.addEventListener("play", () => {
  productFilm.controls = true;
  const returnFocus = document.activeElement === filmPlay;
  filmPlay.hidden = true;
  if (returnFocus) productFilm.focus({ preventScroll: true });
});
productFilm.addEventListener("ended", () => {
  productFilm.controls = false;
  filmPlay.hidden = false;
});

// Fit real article excerpts through the end of the first paragraph. Each card
// retains its article's own typography; no live paragraph is cut off above art.
document.querySelectorAll(".edition-preview").forEach((excerpt) => {
  const frame = excerpt.querySelector("iframe");
  const fit = () => {
    const paragraph = frame.contentDocument?.querySelector(".wechat-document > main > p");
    if (!paragraph) return;
    const scale = excerpt.clientWidth / 405;
    excerpt.style.setProperty("--edition-scale", scale);
    excerpt.style.setProperty("--excerpt-source-height", (paragraph.getBoundingClientRect().bottom + 1) + "px");
    excerpt.style.setProperty("--excerpt-height", Math.ceil((paragraph.getBoundingClientRect().bottom + 20) * scale) + "px");
  };
  frame.addEventListener("load", fit);
  new ResizeObserver(fit).observe(excerpt);
  fit();
});
loadThemes();
