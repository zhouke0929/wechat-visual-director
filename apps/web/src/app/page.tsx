"use client";

import { useEffect } from "react";
import Link from "@/lib/router";
import { AgentStart } from "@/components/agent-start";
import { GettingStarted } from "@/components/getting-started";
import { WorkbenchHeader } from "@/components/workbench-header";

export default function EditorialDeskPage() {
  useEffect(() => { window.scrollTo(0, 0); }, []);
  return (
    <main className="desk-page home-page">
      <WorkbenchHeader />
      <section className="hero-grid" aria-labelledby="page-title">
        <div className="hero-copy">
          <p className="eyebrow">CONTENT OPERATIONS / 01</p>
          <h1 id="page-title">先让 Agent 读懂，<br />再把文章排好。</h1>
          <p>选题、资料或已有文章，都交给 Agent。它先整理结构、完成语义规划，再把文章送到工作台，由你确认成稿。</p>
          <GettingStarted />
          <Link className="desk-recent-link" href="/tasks">继续已有任务 <span aria-hidden="true">↗</span></Link>
        </div>
        <AgentStart />
      </section>
    </main>
  );
}
