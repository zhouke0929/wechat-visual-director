import { useRef, useState } from "react";

export function HostImageEntry({ taskId, assetType }: { taskId: string; assetType: "body" | "cover" }) {
  const [status, setStatus] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);
  const label = assetType === "cover" ? "封面" : "正文配图";
  const prompt = `请用 wechat-visual-director 继续已有任务 ${taskId}（工作台：${window.location.origin}/tasks/${taskId}）。我确认使用当前主题，请先核对任务状态，再检查当前对话是否有可调用的原生生图工具；有则按 image context 返回的绑定请求生成${label}并导入为待审核候选，保留已采用的图片。没有则说明可用替代方式，不自动使用收费 API。不新建文章，不自动采用图片或创建公众号草稿。`;
  async function copy() {
    try {
      await navigator.clipboard.writeText(prompt);
      setStatus("已复制，回到 Agent 对话发送。生成后刷新本页查看待审核候选。");
    } catch {
      input.current?.focus();
      input.current?.select();
      setStatus("已选中指令，请手动复制到 Agent 对话。");
    }
  }
  return (
    <details className="host-image-entry" key={`${taskId}:${assetType}`}>
      <summary>也可以让 Agent 生成{label}</summary>
      <p>若当前对话支持原生生图，可直接生成候选，无需配置工作台图片 API。这里不会自动调用模型。</p>
      <textarea ref={input} aria-label={`给 Agent 的${label}指令`} readOnly value={prompt} rows={4} />
      <button type="button" onClick={copy}>复制{label}指令</button>
      <p role="status">{status || "复制后发给已安装 Skill 的 Agent，图片仍由你审核采用。"}</p>
    </details>
  );
}
