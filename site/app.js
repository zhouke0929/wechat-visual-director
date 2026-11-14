const copyToast = document.querySelector("#copyToast");
const dialog = document.querySelector("#installDialog");
const promptField = document.querySelector("#installPromptText");
const promptHelpLink = document.querySelector("#promptHelpLink");
let toastTimer;
let dialogTrigger = null;

const installPrompt = `请打开并完整执行下面的 Agent 安装说明，为我安装或升级完整的 wechat-visual-director 产品。使用当前安装入口，不要沿用旧文档里的固定版本。必须同时安装轻量 Skill 和本地工作台、运行 doctor --json 并打开工作台；不要只复制 Skill，也不要把源码仓库克隆到 Skill 目录。完成后给我实际安装版本、工作台链接和不超过五行的上手说明，包括下一句可以怎么使用；如果受限未完成，说明当前状态和下一步，不要只回复已安装。不要读取或回显任何密钥。
https://github.com/zhouke0929/wechat-visual-director/blob/main/INSTALL_FOR_AGENT.md`;
promptField.value = installPrompt;
const themePrompt = `请用 wechat-visual-director，根据我提供的组件参考图或风格描述【填写风格】，创作一整套新的主题。只有描述时先寻找可查看的成品组件参考，把方向具体化。联想关联元素，延展完整视觉语言，不要只给现有主题换色。正文保持可编辑，先在样本册和一篇示例文章中让我查看效果，不要创建公众号草稿。`;

const defaultTheme = "pixel_live";
const $ = (selector) => document.querySelector(selector);

function renderLiveTheme(theme) {
  $("#themeStage").style.setProperty("--wash", theme.palette[0]);
  const viewport = $("#themeLive");
  viewport.innerHTML = theme.article_preview_html;
  viewport.dataset.theme = theme.id;
  viewport.setAttribute("aria-label", `${theme.label} · 文章预览`);
  viewport.scrollTop = 0;
  $("#themeLiveLabel").textContent = theme.label;
  $("#themeChoices").querySelectorAll("button").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.theme === theme.id));
  });
  $("#themeLiveStatus").textContent = `已切换为${theme.label}`;
}

function renderGallery(catalog, selected) {
  $("#themeTotal").textContent = `${catalog.length} 套内置主题`;
  const choices = $("#themeChoices");
  choices.replaceChildren(...catalog.map(theme => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.theme = theme.id;
    button.setAttribute("aria-controls", "themeLive");
    const swatch = document.createElement("span");
    swatch.className = "theme-choice-swatch";
    swatch.setAttribute("aria-hidden", "true");
    swatch.style.setProperty("--swatch", theme.palette[0]);
    button.append(swatch, theme.label);
    button.addEventListener("click", () => {
      if (button.getAttribute("aria-pressed") !== "true") renderLiveTheme(theme);
    });
    return button;
  }));
  renderLiveTheme(selected);
  $("#themePicker").hidden = false;
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
    const requested = new URLSearchParams(window.location.search).get("theme");
    renderGallery(catalog, catalog.find(theme => theme.id === requested) ?? catalog[0]);
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
  toastTimer = window.setTimeout(() => copyToast.classList.remove("show"), 2600);
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
      showToast("已复制。回到 Agent 对话，粘贴即可。");
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
