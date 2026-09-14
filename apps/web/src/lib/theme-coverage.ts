import type { ThemeLayoutCoverage } from "./types";

const roleLabels: Record<string, string> = {
  hero: "文章标题", heading: "章节标题", subheading: "小标题", lead: "导语", quote: "引用",
  list: "普通列表", question_hook: "问题引入", numbered_insight: "编号要点",
  evidence_callout: "证据说明", before_after_timeline: "前后变化", logic_path: "逻辑路径",
  concept_explainer: "概念解释", case_card: "案例", warning_note: "提醒",
  action_checklist: "行动清单", faq_card: "问答", comparison_card: "对比",
  section_summary: "章节小结", divider: "分隔线", image_caption: "图片说明", closing_cta: "收尾",
};

export const themeRoleLabel = (role: string) => roleLabels[role] || role;
export function themeCoverageLabel(coverage?: ThemeLayoutCoverage): string {
  if (!coverage) return "";
  if (coverage.status === "inherited") return "沿用基础样式";
  const count = `${coverage.covered_count}/${coverage.total_count}`;
  return coverage.status === "partial" ? `未完成 · 布局覆盖 ${count}` : `布局覆盖完整 · ${count}`;
}
