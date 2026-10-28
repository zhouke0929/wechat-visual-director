import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function HostImageEntry({ taskId, assetType }: { taskId: string; assetType: "body" | "cover" }) {
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [copying, setCopying] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const promptId = useId();
  const label = assetType === "cover" ? "封面" : "正文配图";
  const prompt = `请用 wechat-visual-director 继续已有任务 ${taskId}。\n工作台：${window.location.origin}/tasks/${taskId}\n\n我确认使用当前主题，请先核对任务状态，再检查当前对话是否有可调用的原生生图工具；有则按 image context 返回的绑定请求生成${label}并导入为待审核候选，保留已采用的图片。\n\n没有则说明可用替代方式，不自动使用收费 API。不新建文章，不自动采用图片或创建公众号草稿。`;

  useEffect(() => {
    if (!open) return;
    dialog.current?.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [open]);

  async function copy() {
    setCopying(true);
    try {
      await navigator.clipboard.writeText(prompt);
      setStatus("已复制，回到 Agent 对话发送。生成后刷新本页查看待审核候选。");
    } catch {
      setStatus("已选中指令，请手动复制到 Agent 对话。");
      requestAnimationFrame(() => {
        input.current?.focus();
        input.current?.select();
      });
    } finally {
      setCopying(false);
    }
  }

  return (
    <>
      <header className="host-image-toolbar">
        <h3>{assetType === "cover" ? "封面准备" : "正文配图"}</h3>
        <button
          aria-haspopup="dialog"
          className="host-image-trigger"
          onClick={() => { setStatus(""); setOpen(true); }}
          type="button"
        >
          <svg aria-hidden="true" width="15" height="15" viewBox="0 0 20 20" fill="none">
            <path d="M11 3H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7M11 9l6-6M13 3h4v4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {assetType === "cover" ? "让 Agent 生成" : "让 Agent 配图"}
        </button>
      </header>
      {open ? createPortal(
        <dialog
          aria-describedby={descriptionId}
          aria-labelledby={titleId}
          className="host-image-dialog"
          onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }}
          onClose={() => setOpen(false)}
          ref={dialog}
        >
          <section className="host-image-sheet">
            <header>
              <span className="host-image-kicker">AGENT · 图片协作</span>
              <button aria-label="关闭配图指令窗口" className="host-image-close" onClick={() => dialog.current?.close()} type="button">
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 20 20"><path d="m5 5 10 10M15 5 5 15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
              </button>
            </header>
            <h2 id={titleId}>让 Agent 生成{label}</h2>
            <p className="host-image-description" id={descriptionId}>复制下面的指令，发回 Agent 对话。</p>
            <div className="host-image-prompt">
              <label className="visually-hidden" htmlFor={promptId}>{`给 Agent 的${label}指令`}</label>
              <textarea id={promptId} ref={input} readOnly value={prompt} rows={12} spellCheck={false} />
            </div>
            <button className="host-image-copy" disabled={copying} onClick={() => void copy()} type="button">{copying ? "正在复制…" : `复制${label}指令`}</button>
            {status ? <p className="host-image-status" role="status">{status}</p> : null}
            <p className="host-image-footnote">需 Agent 支持生图。生成后刷新本页，审核采用图片。</p>
          </section>
        </dialog>, document.body,
      ) : null}
    </>
  );
}
