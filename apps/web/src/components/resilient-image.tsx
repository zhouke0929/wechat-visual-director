"use client";

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

type Props = {
  src: string;
  alt: string;
  className?: string;
  style?: CSSProperties;
};

function withRetryToken(src: string, attempt: number): string {
  if (!attempt) return src;
  const [withoutHash, hash = ""] = src.split("#", 2);
  const separator = withoutHash.includes("?") ? "&" : "?";
  return `${withoutHash}${separator}asset_retry=${attempt}${hash ? `#${hash}` : ""}`;
}

export function ResilientImage({ src, alt, className, style }: Props) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setAttempt(0);
    setFailed(false);
  }, [src]);

  const resolvedSrc = useMemo(() => withRetryToken(src, attempt), [attempt, src]);

  if (failed) {
    return (
      <span
        className="resilient-image-error"
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setFailed(false);
          setAttempt((value) => value + 1);
        }}
      >
        <strong>图片暂时未加载</strong>
        <small>点击重试</small>
      </span>
    );
  }

  // Local publication assets deliberately use ordinary img elements so the
  // same component works in candidate cards, zoom review and offline installs.
  // eslint-disable-next-line @next/next/no-img-element
  return (
    <img
      alt={alt}
      className={className}
      onError={() => {
        if (attempt < 1) {
          setAttempt((value) => value + 1);
        } else {
          setFailed(true);
        }
      }}
      src={resolvedSrc}
      style={style}
    />
  );
}
