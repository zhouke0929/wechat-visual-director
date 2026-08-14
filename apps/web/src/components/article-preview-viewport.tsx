"use client";

import "@sneas/telephone/iphone-16-max";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

type PreviewMode = "proof" | "mobile";

type Props = {
  accountLabel?: string;
  children: ReactNode;
  label?: string;
};

function BackIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m15 5-7 7 7 7" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" /></svg>;
}

function WechatActionIcon({ kind }: { kind: "like" | "share" | "recommend" }) {
  if (kind === "like") {
    return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M8.5 10.5 11 4.8c.5-1.1 2.1-.7 2.1.5v4.2h4.4c1.2 0 2.1 1.1 1.8 2.3l-1.2 6.1c-.2.9-1 1.6-2 1.6H8.5m0-9v9m0-9H5.8c-.7 0-1.3.6-1.3 1.3v6.4c0 .7.6 1.3 1.3 1.3h2.7" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" /></svg>;
  }
  if (kind === "share") {
    return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M14 5h5v5M19 5l-8 8M10 7H6.5A2.5 2.5 0 0 0 4 9.5v8A2.5 2.5 0 0 0 6.5 20h8a2.5 2.5 0 0 0 2.5-2.5V14" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" /></svg>;
  }
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 20.2 4.6 13A4.8 4.8 0 0 1 11.4 6l.6.7.6-.7a4.8 4.8 0 0 1 6.8 7Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" /></svg>;
}

export function ArticlePreviewViewport({ accountLabel = "公众号预览", children, label = "390px · 模拟预览" }: Props) {
  const [mode, setMode] = useState<PreviewMode>("proof");
  const [mobileViewportScale, setMobileViewportScale] = useState(1);
  const deviceFrameRef = useRef<HTMLElement>(null);
  const previewSlotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const deviceFrame = deviceFrameRef.current;
    const shadowRoot = deviceFrame?.shadowRoot;
    if (!deviceFrame || !shadowRoot) return;

    if (!shadowRoot.querySelector("style[data-preview-proof-style]")) {
      const style = document.createElement("style");
      style.dataset.previewProofStyle = "";
      style.textContent = `
        :host([data-preview-mode="proof"]) { display: block; height: 100%; }
        :host([data-preview-mode="proof"]) .container { height: 100%; }
        :host([data-preview-mode="proof"]) .frame { display: none; }
        :host([data-preview-mode="proof"]) .screenshot {
          position: static;
          inset: auto;
          width: 100%;
          height: 100%;
          border-radius: 0;
        }
      `;
      shadowRoot.append(style);
    }

    deviceFrame.dataset.previewMode = mode;
  }, [mode]);

  useEffect(() => {
    const previewSlot = previewSlotRef.current;
    if (!previewSlot) return;

    const updateScale = () => {
      setMobileViewportScale(Math.min(1, previewSlot.clientWidth / 390));
    };
    const observer = new ResizeObserver(updateScale);
    observer.observe(previewSlot);
    updateScale();
    return () => observer.disconnect();
  }, []);

  return (
    <div className={`article-preview-viewport preview-mode-${mode}`}>
      <div className="article-preview-toolbar">
        <div aria-label="切换文章预览方式" className="preview-mode-switch" role="tablist">
          <button
            aria-selected={mode === "proof"}
            className={mode === "proof" ? "active" : ""}
            onClick={() => setMode("proof")}
            role="tab"
            type="button"
          >
            内容校对
          </button>
          <button
            aria-selected={mode === "mobile"}
            className={mode === "mobile" ? "active" : ""}
            onClick={() => setMode("mobile")}
            role="tab"
            type="button"
          >
            手机预览
          </button>
        </div>
        <span className="preview-simulation-note">{label}</span>
      </div>

      <div className="article-preview-stage">
        <div className="mobile-device-shell">
          <div className="mobile-device-canvas">
            <iphone-16-max class="mobile-device-frame" mode="light" ref={deviceFrameRef}>
              <div className="wechat-device-screen">
                <div aria-hidden="true" className="mobile-device-status">
                  <i />
                </div>
                <div aria-hidden="true" className="mobile-device-nav">
                  <BackIcon />
                  <strong>文章预览</strong>
                  <b>•••</b>
                </div>
                <div
                  className="article-preview-frame-slot"
                  ref={previewSlotRef}
                  style={{ "--mobile-preview-scale": mobileViewportScale } as CSSProperties}
                >
                  {children}
                </div>
                <div aria-hidden="true" className="wechat-action-bar">
                  <div className="wechat-account-chip"><span>阅</span><strong>{accountLabel}</strong></div>
                  <div className="wechat-action-set">
                    <span><WechatActionIcon kind="like" /><small>赞</small></span>
                    <span><WechatActionIcon kind="share" /><small>分享</small></span>
                    <span><WechatActionIcon kind="recommend" /><small>推荐</small></span>
                  </div>
                </div>
                <div aria-hidden="true" className="mobile-device-home"><i /></div>
              </div>
            </iphone-16-max>
          </div>
        </div>
      </div>
    </div>
  );
}
