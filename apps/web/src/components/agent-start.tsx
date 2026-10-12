import { useEffect, useRef, useState } from "react";

const prompts = {
  topic: "请用 wechat-visual-director，帮我写一篇关于【填写主题】的公众号文章，整理内容结构并完成语义规划后，打开本机工作台供我编辑和审核。先不要生成图片或创建公众号草稿。",
  article: "请用 wechat-visual-director，整理我提供的这篇文章。在保留事实、数字、观点和结论的前提下梳理标题层级、段落与列表，完成语义规划和排版后，打开本机工作台供我编辑和审核。先不要生成图片或创建公众号草稿。",
  theme: "请用 wechat-visual-director，根据我附上的组件参考图，或下面的风格描述【填写风格】，创作一整套新的主题。寻找相关组件参考，联想关联元素，延展完整视觉语言，不要只给已有主题换色。正文保持可编辑，先在样本册和一篇示例文章中让我查看整体效果，不要创建公众号草稿。",
};

export function AgentStart() {
  const [mode, setMode] = useState<keyof typeof prompts>("topic");
  const [copyState, setCopyState] = useState<"idle" | "copying" | "copied" | "failed">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const copyAttempt = useRef(0);
  const promptRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => () => {
    copyAttempt.current += 1;
    if (timer.current) clearTimeout(timer.current);
  }, []);

  function chooseMode(next: keyof typeof prompts) {
    copyAttempt.current += 1;
    if (timer.current) clearTimeout(timer.current);
    setMode(next);
    setCopyState("idle");
  }

  async function copyPrompt() {
    const attempt = ++copyAttempt.current;
    if (timer.current) clearTimeout(timer.current);
    setCopyState("copying");
    try {
      await navigator.clipboard.writeText(prompts[mode]);
      if (attempt !== copyAttempt.current) return;
      setCopyState("copied");
      timer.current = setTimeout(() => setCopyState("idle"), 1800);
    } catch {
      if (attempt !== copyAttempt.current) return;
      promptRef.current?.focus({ preventScroll: true });
      promptRef.current?.select();
      setCopyState("failed");
    }
  }

  return (
    <section className="agent-start" aria-labelledby="agent-start-title">
      <p className="eyebrow">START WITH YOUR AGENT</p>
      <h2 id="agent-start-title">在 Agent 对话里开始</h2>
      <p className="agent-start-hint">不必自己整理 Markdown 格式，把需求或原稿交给安装了此 Skill 的 Agent 就好。</p>
      <div className="agent-start-modes" role="group" aria-label="选择给 Agent 的需求">
        <button type="button" aria-pressed={mode === "topic"} onClick={() => chooseMode("topic")}>我有一个选题</button>
        <button type="button" aria-pressed={mode === "article"} onClick={() => chooseMode("article")}>我有一篇文章</button>
        <button type="button" aria-pressed={mode === "theme"} onClick={() => chooseMode("theme")}>我想创作新主题</button>
      </div>
      <div className="agent-start-prompt">
        <label htmlFor="agent-writing-prompt">可以这样对 Agent 说</label>
        <textarea ref={promptRef} id="agent-writing-prompt" readOnly value={prompts[mode]} rows={5} />
        <button className={`primary-button ${copyState === "copied" ? "is-copied" : ""}`} data-copy-state={copyState} type="button" aria-live="polite" disabled={copyState === "copying"} onClick={copyPrompt}>
          {copyState === "copied" ? "✓ 已复制" : copyState === "copying" ? "正在复制…" : copyState === "failed" ? "重试复制" : "复制给 Agent 的指令 ↗"}
        </button>
        <p className="agent-start-next" role="status">{copyState === "failed" ? "已选中指令，请手动复制到 Agent 对话。" : mode === "theme" ? "附上喜欢的组件截图，或填写风格描述，回到 Agent 对话发送。这里不会自动发送。" : mode === "topic" ? "复制后填写主题，回到 Agent 对话发送。这里不会自动发送。" : "附上原文或 Markdown 文件，回到 Agent 对话发送。"}</p>
      </div>
    </section>
  );
}
