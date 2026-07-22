import type { TaskStatus } from "@/lib/types";

const labels: Record<TaskStatus, string> = {
  created: "待生成",
  analyzing: "规划中",
  plans_ready: "待选方案",
  plan_selected: "已选方案",
  publication_frozen: "版本已冻结",
  mock_draft_created: "模拟草稿已创建",
  mock_draft_failed: "模拟创建失败",
  mock_draft_unknown: "模拟结果未知",
  failed: "需要处理",
};

export function StatusPill({ status }: { status: TaskStatus }) {
  return <span className={`status-pill status-${status}`}>{labels[status]}</span>;
}
