const index = document.querySelector("#themeIndex");
const preview = document.querySelector("#themePreview");
const label = document.querySelector("#themeLabel");
const english = document.querySelector("#themeEnglish");
const description = document.querySelector("#themeDescription");
const swatches = document.querySelector("#themeSwatches");
const copyInstallButtons = document.querySelectorAll("[data-copy-install]");
const copyToast = document.querySelector("#copyToast");
const installCopyHint = document.querySelector("#installCopyHint");

let themes = [];
let selectedThemeId = "youth_campus";

const installPrompt = `请打开并完整执行下面的 Agent 安装说明，为我安装或升级完整的 wechat-visual-director 产品。使用当前安装入口，不要沿用旧文档里的固定版本。必须同时安装轻量 Skill 和本地工作台、运行 doctor --json 并打开工作台；不要只复制 Skill，也不要把源码仓库克隆到 Skill 目录。完成后给我实际安装版本、工作台链接和不超过五行的上手说明，包括下一句可以怎么使用；如果受限未完成，说明当前状态和下一步，不要只回复已安装。不要读取或回显任何密钥。
https://github.com/zhouke0929/wechat-visual-director/blob/main/INSTALL_FOR_AGENT.md`;

function renderTheme(theme) {
  selectedThemeId = theme.id;
  label.textContent = theme.label;
  english.textContent = theme.english;
  description.textContent = theme.description;
  swatches.replaceChildren(
    ...theme.palette.map((color) => {
      const item = document.createElement("i");
      item.style.backgroundColor = color;
      return item;
    }),
  );
  preview.innerHTML = theme.full_preview_html;
  preview.scrollTop = 0;
  document.querySelectorAll(".theme-button").forEach((button) => {
    const active = button.dataset.themeId === theme.id;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function createThemeButton(theme, themeIndex) {
  const button = document.createElement("button");
  button.className = "theme-button";
  button.type = "button";
  button.dataset.themeId = theme.id;
  button.setAttribute("aria-pressed", "false");

  const number = document.createElement("span");
  number.className = "theme-num";
  number.textContent = String(themeIndex + 1).padStart(2, "0");

  const name = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = theme.label;
  const subtitle = document.createElement("small");
  subtitle.textContent = theme.english;
  name.append(title, subtitle);

  const palette = document.createElement("span");
  palette.className = "mini-swatches";
  theme.palette.forEach((color) => {
    const item = document.createElement("i");
    item.style.backgroundColor = color;
    palette.append(item);
  });

  button.append(number, name, palette);
  button.addEventListener("click", () => renderTheme(theme));
  return button;
}

async function loadThemes() {
  try {
    const response = await fetch("./data/themes.json");
    if (!response.ok) throw new Error(`主题数据加载失败（${response.status}）`);
    const payload = await response.json();
    themes = payload.themes ?? [];
    index.replaceChildren(...themes.map(createThemeButton));
    const initial = themes.find((theme) => theme.id === selectedThemeId) ?? themes[0];
    if (initial) renderTheme(initial);
  } catch (error) {
    index.innerHTML = `<p style="padding:24px;line-height:1.7">${error.message}</p>`;
  }
}

loadThemes();

async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch {
    // Some embedded browsers expose the Clipboard API but reject writes.
    // Continue with the selection-based fallback instead of failing silently.
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.inset = "0 auto auto 0";
  textarea.style.width = "1px";
  textarea.style.height = "1px";
  textarea.style.opacity = "0.01";
  document.body.append(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("copy_command_rejected");
}

function showCopyFeedback(message, state = "success") {
  if (copyToast) {
    copyToast.textContent = message;
    copyToast.dataset.state = state;
    copyToast.classList.add("show");
    window.setTimeout(() => copyToast.classList.remove("show"), 2600);
  }
  if (installCopyHint) {
    installCopyHint.textContent = message;
    installCopyHint.dataset.state = state;
  }
}

copyInstallButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const original = button.textContent;
    button.disabled = true;
    try {
      await copyText(installPrompt);
      button.textContent = button.id === "copyInstallPrompt" ? "已复制 ✓" : "已复制，可粘贴给 Agent ✓";
      showCopyFeedback("安装提示词已复制，可直接粘贴到 Agent 对话中。", "success");
    } catch {
      button.textContent = "复制失败，请重试";
      showCopyFeedback("浏览器未允许复制，请刷新页面后重试。", "error");
    }
    window.setTimeout(() => {
      button.textContent = original;
      button.disabled = false;
    }, 2600);
  });
});
