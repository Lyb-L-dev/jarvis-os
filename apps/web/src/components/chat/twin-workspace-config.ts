export type WorkspaceSide = "left" | "right";

export type WorkspacePanelId =
  | "career"
  | "memory"
  | "knowledge"
  | "growth"
  | "orchestrator"
  | "approval";

export type WorkspacePanelDefinition = {
  id: WorkspacePanelId;
  side: WorkspaceSide;
  title: string;
  shortTitle: string;
  description: string;
  href: string;
  tone: "cyan" | "violet" | "blue" | "green" | "amber";
};

export const WORKSPACE_PANELS: Record<
  WorkspacePanelId,
  WorkspacePanelDefinition
> = {
  career: {
    id: "career",
    side: "left",
    title: "CareerRadar",
    shortTitle: "求职",
    description: "企业、岗位与匹配证据",
    href: "/career",
    tone: "cyan",
  },
  memory: {
    id: "memory",
    side: "left",
    title: "长期记忆",
    shortTitle: "记忆",
    description: "已确认事实与候选记忆",
    href: "/memory",
    tone: "violet",
  },
  knowledge: {
    id: "knowledge",
    side: "left",
    title: "本地知识",
    shortTitle: "知识",
    description: "Obsidian 与语义检索证据",
    href: "/knowledge",
    tone: "blue",
  },
  growth: {
    id: "growth",
    side: "right",
    title: "成长计划",
    shortTitle: "成长",
    description: "目标、计划与当前任务",
    href: "/growth",
    tone: "green",
  },
  orchestrator: {
    id: "orchestrator",
    side: "right",
    title: "任务编排",
    shortTitle: "编排",
    description: "研究与成长工作流状态",
    href: "/observatory",
    tone: "cyan",
  },
  approval: {
    id: "approval",
    side: "right",
    title: "审批中心",
    shortTitle: "审批",
    description: "草稿审阅与人在环控制",
    href: "/approvals",
    tone: "amber",
  },
};

export const DEFAULT_WORKSPACE_PANELS: Record<
  WorkspaceSide,
  WorkspacePanelId[]
> = {
  left: [],
  right: [],
};

const PANEL_INTENT_TERMS: Record<WorkspacePanelId, string[]> = {
  career: ["求职", "岗位", "招聘", "公司", "简历", "面试", "offer"],
  memory: ["记住", "记忆", "偏好", "长期记忆"],
  knowledge: ["知识库", "obsidian", "笔记", "本地资料", "语义检索"],
  growth: ["成长计划", "学习计划", "目标", "里程碑", "任务", "复盘"],
  orchestrator: ["编排", "工作流", "调研流程", "research", "多步骤"],
  approval: ["审批", "授权", "批准", "待确认", "执行确认"],
};

export function detectWorkspacePanels(input: string): WorkspacePanelId[] {
  const normalized = input.trim().toLowerCase();
  if (!normalized) return [];

  return (Object.keys(PANEL_INTENT_TERMS) as WorkspacePanelId[]).filter(
    (panelId) =>
      PANEL_INTENT_TERMS[panelId].some((term) =>
        normalized.includes(term.toLowerCase()),
      ),
  );
}

export function panelsForSide(side: WorkspaceSide): WorkspacePanelDefinition[] {
  return (Object.values(WORKSPACE_PANELS) as WorkspacePanelDefinition[]).filter(
    (panel) => panel.side === side,
  );
}
