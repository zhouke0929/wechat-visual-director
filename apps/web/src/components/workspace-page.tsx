import type { ReactNode } from "react";

export function WorkspacePageIntro({ title, titleId, description, eyebrow, children }: {
  title: string;
  titleId?: string;
  description: string;
  eyebrow?: string;
  children?: ReactNode;
}) {
  return (
    <section className="workspace-intro">
      <div>
        {eyebrow && <span className="workspace-eyebrow" lang="en" aria-hidden="true">{eyebrow}</span>}
        <h1 id={titleId}>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </section>
  );
}
