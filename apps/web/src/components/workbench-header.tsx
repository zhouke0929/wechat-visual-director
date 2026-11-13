import { useEffect, useState } from "react";
import Link from "@/lib/router";
import { getApplicationVersion } from "@/lib/api";

const sections = [
  { href: "/tasks", label: "最近任务" },
  { href: "/theme-gallery", label: "主题样本册" },
  { href: "/settings", label: "本地设置" },
] as const;

let versionRequest: Promise<string> | undefined;

export function WorkbenchHeader({ current, detail = false }: {
  current?: typeof sections[number]["href"];
  detail?: boolean;
}) {
  const [version, setVersion] = useState("");
  useEffect(() => {
    let active = true;
    versionRequest ??= getApplicationVersion().catch(() => {
      versionRequest = undefined;
      return "";
    });
    void versionRequest.then((value) => { if (active) setVersion(value); });
    return () => { active = false; };
  }, []);
  return (
    <header className={`workspace-topbar${detail ? " workspace-topbar-sticky" : ""}`}>
      <Link className="wordmark" href="/" aria-label="视觉主编首页">
        <span className="wordmark-cn">视觉主编</span>
        <span className="wordmark-en">WECHAT VISUAL DIRECTOR</span>
      </Link>
      <nav className="workspace-nav" aria-label="工作台导航">
        {sections.map(({ href, label }) => (
          <Link key={href} href={href} aria-current={href === current ? (detail ? "location" : "page") : undefined}>
            {label}
          </Link>
        ))}
      </nav>
      <span className="workspace-version baseline-badge">{version ? `LOCAL · ${version}` : "本机工作台"}</span>
    </header>
  );
}
