"use client";

import { useEffect } from "react";

export default function TaskReviewError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("task review render failed", error);
  }, [error]);

  return (
    <main className="review-loading">
      <section>
        <p className="eyebrow">WORKBENCH ERROR</p>
        <h1>工作台没有完成加载</h1>
        <p role="alert">
          {error.message || "页面渲染发生异常。任务数据仍保存在本地，可以安全重试。"}
        </p>
        <div className="form-actions">
          <button className="primary-button" type="button" onClick={reset}>
            重新加载
          </button>
          <a className="back-link" href="/">
            返回任务列表
          </a>
        </div>
      </section>
    </main>
  );
}
