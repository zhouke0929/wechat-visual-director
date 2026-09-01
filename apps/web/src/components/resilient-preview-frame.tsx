"use client";

import { useContext, useEffect, useRef, useState } from "react";

import { ArticlePreviewModeContext } from "@/components/article-preview-viewport";

type Props = {
  src: string;
  title: string;
};

function withRetryToken(src: string, retry: number): string {
  if (!retry) return src;
  const [withoutHash, hash = ""] = src.split("#", 2);
  const separator = withoutHash.includes("?") ? "&" : "?";
  return `${withoutHash}${separator}preview_retry=${retry}${hash ? `#${hash}` : ""}`;
}

const PROOF_FONT_SCALE = 1.06;

function applyWorkbenchPreviewProfile(frame: HTMLIFrameElement, mode: "proof" | "mobile") {
  let document: Document | null;
  try {
    document = frame.contentDocument;
  } catch {
    return;
  }
  if (!document?.documentElement) return;

  let normalization = document.querySelector<HTMLStyleElement>("style[data-workbench-preview-normalization]");
  if (!normalization) {
    normalization = document.createElement("style");
    normalization.dataset.workbenchPreviewNormalization = "";
    normalization.textContent = "*,*::before,*::after{box-sizing:border-box!important;}";
    document.head?.append(normalization);
  }

  document.documentElement.dataset.workbenchPreviewMode = mode;
  document.querySelectorAll<HTMLElement>("[style]").forEach((element) => {
    if (!element.dataset.workbenchOriginalFontSize) {
      const original = element.style.fontSize;
      if (!original || !original.endsWith("px")) return;
      element.dataset.workbenchOriginalFontSize = original;
    }
    const original = element.dataset.workbenchOriginalFontSize;
    if (!original) return;
    if (mode === "proof") {
      const pixels = Number.parseFloat(original);
      element.style.fontSize = pixels > 0 ? `${Math.round(pixels * PROOF_FONT_SCALE * 100) / 100}px` : original;
    } else {
      element.style.fontSize = original;
    }
  });
}

export function ResilientPreviewFrame({ src, title }: Props) {
  const previewMode = useContext(ArticlePreviewModeContext);
  const [retry, setRetry] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const retryRef = useRef(0);
  const loadVersionRef = useRef(0);
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    loadVersionRef.current += 1;
    retryRef.current = 0;
    setRetry(0);
    setLoading(true);
    setFailed(false);
  }, [src]);

  useEffect(() => {
    if (frameRef.current) applyWorkbenchPreviewProfile(frameRef.current, previewMode);
  }, [previewMode, retry]);

  function retryOrFail(loadVersion: number) {
    if (loadVersion !== loadVersionRef.current) return;
    if (retryRef.current < 1) {
      retryRef.current += 1;
      setRetry(retryRef.current);
      setLoading(true);
      return;
    }
    setLoading(false);
    setFailed(true);
  }

  function handleLoad(event: React.SyntheticEvent<HTMLIFrameElement>) {
    const frame = event.currentTarget;
    applyWorkbenchPreviewProfile(frame, previewMode);
    const loadVersion = loadVersionRef.current;
    let images: HTMLImageElement[];
    try {
      images = Array.from(frame.contentDocument?.images ?? []);
    } catch {
      setLoading(false);
      return;
    }

    if (!images.length) {
      setLoading(false);
      setFailed(false);
      return;
    }

    const verify = () => {
      if (images.some((image) => image.complete && image.naturalWidth === 0)) {
        retryOrFail(loadVersion);
        return;
      }
      if (images.every((image) => image.complete && image.naturalWidth > 0)) {
        setLoading(false);
        setFailed(false);
      }
    };

    verify();
    if (images.every((image) => image.complete)) return;

    const timeout = window.setTimeout(() => retryOrFail(loadVersion), 12000);
    const settle = () => {
      if (!images.every((image) => image.complete)) return;
      window.clearTimeout(timeout);
      verify();
    };
    images.forEach((image) => {
      image.addEventListener("load", settle, { once: true });
      image.addEventListener("error", settle, { once: true });
    });
  }

  return (
    <div className="preview-frame-shell">
      <iframe
        className="preview-frame"
        onLoad={handleLoad}
        ref={frameRef}
        scrolling="yes"
        src={withRetryToken(src, retry)}
        title={title}
      />
      {loading ? (
        <div className="preview-frame-state" role="status">
          <span />
          <strong>正在加载新主题预览…</strong>
        </div>
      ) : null}
      {failed ? (
        <div className="preview-frame-state preview-frame-failed" role="alert">
          <strong>部分图片暂时未加载</strong>
          <button
            onClick={() => {
              retryRef.current = 0;
              setFailed(false);
              setLoading(true);
              setRetry((value) => value + 1);
            }}
            type="button"
          >
            重新加载预览
          </button>
        </div>
      ) : null}
    </div>
  );
}
