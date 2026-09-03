import { useEffect, useState } from "react";
import Link from "@/lib/router";
import { getApplicationVersion } from "@/lib/api";

export function WorkbenchHeader() {
  const [version, setVersion] = useState("ALPHA");
  useEffect(() => { getApplicationVersion().then(setVersion).catch(() => undefined); }, []);
  return (
    <header className="topbar">
      <Link className="wordmark" href="/" aria-label="视觉主编首页">
        <span className="wordmark-cn">视觉主编</span>
        <span className="wordmark-en">WECHAT VISUAL DIRECTOR</span>
      </Link>
      <nav className="topbar-actions" aria-label="工作台导航">
        <Link className="gallery-link" href="/tasks">最近任务</Link>
        <Link className="gallery-link" href="/theme-gallery">主题样本册</Link>
        <Link className="gallery-link settings-link" href="/settings">本地设置</Link>
        <span className="baseline-badge">LOCAL · {version}</span>
      </nav>
    </header>
  );
}
