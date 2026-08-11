"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  BookOpen,
  Brain,
  BriefcaseBusiness,
  Check,
  CircleAlert,
  Clock3,
  ListChecks,
  LoaderCircle,
  RefreshCw,
  Route,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import {
  WORKSPACE_PANELS,
  type WorkspacePanelId,
} from "@/components/chat/twin-workspace-config";
import { getCareerOverview, type CareerOverview } from "@/lib/api/career";
import {
  getGrowthOverview,
  listGoals,
  listGrowthTasks,
  listGrowthWorkflows,
  listResearchWorkflows,
  type Goal,
  type GrowthOverview,
  type GrowthTask,
  type GrowthWorkflowRun,
  type ResearchWorkflowRun,
} from "@/lib/api/growth";
import {
  getKnowledgeStatus,
  listKnowledgeDocuments,
  type KnowledgeDocument,
  type KnowledgeVaultStatus,
} from "@/lib/api/knowledge";
import {
  getMemoryStats,
  listMemories,
  type Memory,
  type MemoryStats,
} from "@/lib/api/memory";
import {
  getApprovalCenter,
  type ApprovalCenterResponse,
} from "@/lib/api/tools";

import styles from "./twin-workspace.module.css";

type PanelContentProps = {
  panelId: WorkspacePanelId;
  disabled: boolean;
  onSync: (prompt: string) => void;
};

type MemoryPanelData = {
  stats: MemoryStats;
  memories: Memory[];
};

type KnowledgePanelData = {
  status: KnowledgeVaultStatus;
  documents: KnowledgeDocument[];
};

type GrowthPanelData = {
  overview: GrowthOverview;
  goals: Goal[];
  tasks: GrowthTask[];
};

type OrchestratorPanelData = {
  growth: GrowthWorkflowRun[];
  research: ResearchWorkflowRun[];
};

const PANEL_ICONS = {
  career: BriefcaseBusiness,
  memory: Brain,
  knowledge: BookOpen,
  growth: Route,
  orchestrator: Workflow,
  approval: ShieldCheck,
} satisfies Record<WorkspacePanelId, typeof BriefcaseBusiness>;

async function loadCareer(signal: AbortSignal) {
  return getCareerOverview(signal);
}

async function loadMemory(signal: AbortSignal): Promise<MemoryPanelData> {
  const [stats, memories] = await Promise.all([
    getMemoryStats(signal),
    listMemories({ signal }),
  ]);
  return { stats, memories };
}

async function loadKnowledge(signal: AbortSignal): Promise<KnowledgePanelData> {
  const [status, documents] = await Promise.all([
    getKnowledgeStatus(signal),
    listKnowledgeDocuments(undefined, undefined, signal),
  ]);
  return { status, documents };
}

async function loadGrowth(signal: AbortSignal): Promise<GrowthPanelData> {
  const [overview, goals, tasks] = await Promise.all([
    getGrowthOverview(signal),
    listGoals(signal),
    listGrowthTasks(signal),
  ]);
  return { overview, goals, tasks };
}

async function loadOrchestrator(
  signal: AbortSignal,
): Promise<OrchestratorPanelData> {
  const [growth, research] = await Promise.all([
    listGrowthWorkflows(signal),
    listResearchWorkflows(signal),
  ]);
  return { growth, research };
}

async function loadApprovals(signal: AbortSignal) {
  return getApprovalCenter(signal);
}

function usePanelQuery<T>(loader: (signal: AbortSignal) => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    loader(controller.signal)
      .then((result) => {
        setData(result);
        setError(null);
      })
      .catch((loadError: unknown) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") {
          return;
        }
        setError(
          loadError instanceof Error ? loadError.message : "暂时无法读取数据。",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [loader, revision]);

  return {
    data,
    error,
    loading,
    retry: () => {
      setLoading(true);
      setRevision((value) => value + 1);
    },
  };
}

export function WorkspacePanelIcon({ panelId }: { panelId: WorkspacePanelId }) {
  const Icon = PANEL_ICONS[panelId];
  return <Icon aria-hidden="true" />;
}

export function TwinWorkspacePanelContent({
  panelId,
  disabled,
  onSync,
}: PanelContentProps) {
  if (panelId === "career") {
    return <CareerPanel disabled={disabled} onSync={onSync} />;
  }
  if (panelId === "memory") {
    return <MemoryPanel disabled={disabled} onSync={onSync} />;
  }
  if (panelId === "knowledge") {
    return <KnowledgePanel disabled={disabled} onSync={onSync} />;
  }
  if (panelId === "growth") {
    return <GrowthPanel disabled={disabled} onSync={onSync} />;
  }
  if (panelId === "orchestrator") {
    return <OrchestratorPanel disabled={disabled} onSync={onSync} />;
  }
  return <ApprovalPanel disabled={disabled} onSync={onSync} />;
}

function QueryState({
  error,
  loading,
  onRetry,
}: {
  error: string | null;
  loading: boolean;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <div className={styles.panelLoading} role="status">
        <LoaderCircle aria-hidden="true" />
        <span>正在读取本地数据…</span>
      </div>
    );
  }
  if (!error) return null;
  return (
    <div className={styles.panelError} role="alert">
      <CircleAlert aria-hidden="true" />
      <p>{error}</p>
      <button onClick={onRetry} type="button">
        <RefreshCw aria-hidden="true" />
        重试
      </button>
    </div>
  );
}

function PanelFooter({ panelId }: { panelId: WorkspacePanelId }) {
  const panel = WORKSPACE_PANELS[panelId];
  return (
    <Link className={styles.panelDeepLink} href={panel.href}>
      打开完整页面
      <ArrowUpRight aria-hidden="true" />
    </Link>
  );
}

function CareerPanel({
  disabled,
  onSync,
}: Omit<PanelContentProps, "panelId">) {
  const query = usePanelQuery<CareerOverview>(loadCareer);
  const [selected, setSelected] = useState<string[]>([]);
  const opportunities = [...(query.data?.opportunities ?? [])]
    .sort((a, b) => b.match_score - a.match_score)
    .slice(0, 4);

  return (
    <div className={styles.panelContent}>
      <QueryState error={query.error} loading={query.loading} onRetry={query.retry} />
      {query.data ? (
        <>
          <div className={styles.panelStatusLine}>
            <span data-state={query.data.provider.status}>
              {query.data.provider.enabled ? "只读研究已启用" : "只读研究未启用"}
            </span>
            <strong>{query.data.opportunities.length} 个岗位</strong>
          </div>
          <div className={styles.panelList} aria-label="匹配岗位">
            {opportunities.map((opportunity) => {
              const isSelected = selected.includes(opportunity.id);
              return (
                <button
                  aria-pressed={isSelected}
                  className={isSelected ? styles.panelListSelected : ""}
                  key={opportunity.id}
                  onClick={() =>
                    setSelected((items) =>
                      items.includes(opportunity.id)
                        ? items.filter((id) => id !== opportunity.id)
                        : [...items, opportunity.id],
                    )
                  }
                  type="button"
                >
                  <span className={styles.selectionMark}>
                    {isSelected ? <Check aria-hidden="true" /> : null}
                  </span>
                  <span>
                    <strong>{opportunity.company}</strong>
                    <small>{opportunity.title}</small>
                  </span>
                  <time>{Math.round(opportunity.match_score)}%</time>
                </button>
              );
            })}
            {!opportunities.length ? (
              <p className={styles.panelEmpty}>当前没有可用岗位，先到 CareerRadar 添加来源。</p>
            ) : null}
          </div>
          <button
            className={styles.panelPrimaryAction}
            disabled={disabled || !selected.length}
            onClick={() => {
              const chosen = opportunities.filter((item) => selected.includes(item.id));
              onSync(
                `请比较这些 CareerRadar 岗位并给出下一步建议：${chosen
                  .map((item) => `${item.company}｜${item.title}`)
                  .join("；")}`,
              );
            }}
            type="button"
          >
            交给 Jarvis 比较
          </button>
        </>
      ) : null}
      <PanelFooter panelId="career" />
    </div>
  );
}

function MemoryPanel({
  disabled,
  onSync,
}: Omit<PanelContentProps, "panelId">) {
  const query = usePanelQuery<MemoryPanelData>(loadMemory);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const memories = (query.data?.memories ?? [])
    .filter((memory) => memory.status === "active" || memory.status === "pending")
    .slice(0, 4);
  const selected = memories.find((memory) => memory.id === selectedId) ?? null;

  return (
    <div className={styles.panelContent}>
      <QueryState error={query.error} loading={query.loading} onRetry={query.retry} />
      {query.data ? (
        <>
          <div className={styles.metricStrip}>
            <span><strong>{query.data.stats.active}</strong>正在使用</span>
            <span><strong>{query.data.stats.pending}</strong>等待确认</span>
          </div>
          <div className={styles.panelList} aria-label="近期记忆">
            {memories.map((memory) => (
              <button
                aria-pressed={selectedId === memory.id}
                className={selectedId === memory.id ? styles.panelListSelected : ""}
                key={memory.id}
                onClick={() => setSelectedId(memory.id)}
                type="button"
              >
                <span className={styles.statusDot} data-state={memory.status} />
                <span>
                  <strong>{memory.memory_type}</strong>
                  <small>{memory.content}</small>
                </span>
                <time>{memory.importance}/5</time>
              </button>
            ))}
            {!memories.length ? (
              <p className={styles.panelEmpty}>还没有已启用或待确认的长期记忆。</p>
            ) : null}
          </div>
          <button
            className={styles.panelPrimaryAction}
            disabled={disabled || !selected}
            onClick={() =>
              selected &&
              onSync(`请在本次回答中参考这条长期记忆：${selected.content}`)
            }
            type="button"
          >
            带入当前对话
          </button>
        </>
      ) : null}
      <PanelFooter panelId="memory" />
    </div>
  );
}

function KnowledgePanel({
  disabled,
  onSync,
}: Omit<PanelContentProps, "panelId">) {
  const query = usePanelQuery<KnowledgePanelData>(loadKnowledge);
  const [selected, setSelected] = useState<string[]>([]);
  const documents = (query.data?.documents ?? []).slice(0, 4);

  return (
    <div className={styles.panelContent}>
      <QueryState error={query.error} loading={query.loading} onRetry={query.retry} />
      {query.data ? (
        <>
          <div className={styles.panelStatusLine}>
            <span data-state={query.data.status.status}>
              {query.data.status.connected ? "Obsidian 已连接" : "Obsidian 未连接"}
            </span>
            <strong>{query.data.status.document_count} 篇笔记</strong>
          </div>
          <div className={styles.panelList} aria-label="本地知识笔记">
            {documents.map((document) => {
              const isSelected = selected.includes(document.id);
              return (
                <button
                  aria-pressed={isSelected}
                  className={isSelected ? styles.panelListSelected : ""}
                  key={document.id}
                  onClick={() =>
                    setSelected((items) =>
                      items.includes(document.id)
                        ? items.filter((id) => id !== document.id)
                        : [...items, document.id],
                    )
                  }
                  type="button"
                >
                  <span className={styles.selectionMark}>
                    {isSelected ? <Check aria-hidden="true" /> : null}
                  </span>
                  <span>
                    <strong>{document.title}</strong>
                    <small>{document.content_preview || document.relative_path}</small>
                  </span>
                </button>
              );
            })}
            {!documents.length ? (
              <p className={styles.panelEmpty}>当前知识库没有可检索笔记。</p>
            ) : null}
          </div>
          <button
            className={styles.panelPrimaryAction}
            disabled={disabled || !selected.length}
            onClick={() => {
              const titles = documents
                .filter((document) => selected.includes(document.id))
                .map((document) => document.title);
              onSync(`请检索并参考这些本地笔记：${titles.join("；")}`);
            }}
            type="button"
          >
            用这些笔记回答
          </button>
        </>
      ) : null}
      <PanelFooter panelId="knowledge" />
    </div>
  );
}

function GrowthPanel({
  disabled,
  onSync,
}: Omit<PanelContentProps, "panelId">) {
  const query = usePanelQuery<GrowthPanelData>(loadGrowth);
  const activeGoals = (query.data?.goals ?? [])
    .filter((goal) => goal.status === "active")
    .slice(0, 3);
  const currentTasks = (query.data?.tasks ?? [])
    .filter((task) => task.status === "in_progress" || task.status === "todo")
    .slice(0, 3);

  return (
    <div className={styles.panelContent}>
      <QueryState error={query.error} loading={query.loading} onRetry={query.retry} />
      {query.data ? (
        <>
          <div className={styles.metricStrip}>
            <span><strong>{query.data.overview.active_goals}</strong>活跃目标</span>
            <span><strong>{query.data.overview.today_tasks}</strong>今日任务</span>
            <span><strong>{query.data.overview.today_completed}</strong>已完成</span>
          </div>
          <div className={styles.goalSummary}>
            <h3>当前目标</h3>
            {activeGoals.map((goal) => (
              <div key={goal.id}>
                <span>{goal.title}</span>
                <strong>{goal.progress.percent}%</strong>
              </div>
            ))}
            {!activeGoals.length ? <p>还没有活跃目标。</p> : null}
          </div>
          <div className={styles.compactTaskList}>
            {currentTasks.map((task) => (
              <span data-state={task.status} key={task.id}>
                <i />
                <strong>{task.title}</strong>
                <small>{task.estimated_minutes} 分钟</small>
              </span>
            ))}
          </div>
          <button
            className={styles.panelPrimaryAction}
            disabled={disabled}
            onClick={() =>
              onSync(
                activeGoals.length
                  ? `请根据当前目标“${activeGoals[0].title}”和今天的任务进度，调整接下来的行动顺序。`
                  : "请帮我梳理一个新的成长目标，并先生成可审阅草稿。",
              )
            }
            type="button"
          >
            调整行动计划
          </button>
        </>
      ) : null}
      <PanelFooter panelId="growth" />
    </div>
  );
}

function OrchestratorPanel({
  disabled,
  onSync,
}: Omit<PanelContentProps, "panelId">) {
  const query = usePanelQuery<OrchestratorPanelData>(loadOrchestrator);
  const workflows = [
    ...(query.data?.growth ?? []).map((run) => ({
      id: run.id,
      title: run.request.objective,
      kind: "成长规划",
      status: run.status,
      step: run.current_step,
    })),
    ...(query.data?.research ?? []).map((run) => ({
      id: run.id,
      title: run.request.question,
      kind: "研究任务",
      status: run.status,
      step: run.current_step,
    })),
  ].slice(0, 4);

  return (
    <div className={styles.panelContent}>
      <QueryState error={query.error} loading={query.loading} onRetry={query.retry} />
      {query.data ? (
        <>
          <div className={styles.panelStatusLine}>
            <span data-state="ready">按需运行，不在后台自主启动</span>
            <strong>{workflows.length} 个最近流程</strong>
          </div>
          <div className={styles.workflowList}>
            {workflows.map((workflow) => (
              <button
                disabled={disabled}
                key={workflow.id}
                onClick={() =>
                  onSync(
                    `请汇报${workflow.kind}“${workflow.title}”当前状态，并说明继续前需要我确认什么。`,
                  )
                }
                type="button"
              >
                <Clock3 aria-hidden="true" />
                <span>
                  <small>{workflow.kind} · {workflow.status}</small>
                  <strong>{workflow.title}</strong>
                </span>
                <i data-state={workflow.status} />
              </button>
            ))}
            {!workflows.length ? (
              <p className={styles.panelEmpty}>还没有研究或成长工作流。</p>
            ) : null}
          </div>
          <p className={styles.panelBoundaryNote}>
            这里只读取状态；模型付费、草稿确认与工具执行仍走各自审批。
          </p>
        </>
      ) : null}
      <PanelFooter panelId="orchestrator" />
    </div>
  );
}

function ApprovalPanel({
  disabled,
  onSync,
}: Omit<PanelContentProps, "panelId">) {
  const query = usePanelQuery<ApprovalCenterResponse>(loadApprovals);
  const pending = (query.data?.items ?? [])
    .filter((item) => item.status === "pending")
    .slice(0, 4);

  return (
    <div className={styles.panelContent}>
      <QueryState error={query.error} loading={query.loading} onRetry={query.retry} />
      {query.data ? (
        <>
          <div className={styles.metricStrip}>
            <span><strong>{query.data.pending_count}</strong>等待决定</span>
            <span><strong>{query.data.approved_count}</strong>已批准</span>
          </div>
          <div className={styles.approvalList}>
            {pending.map((item) => (
              <button
                disabled={disabled}
                key={`${item.source}-${item.id}`}
                onClick={() =>
                  onSync(
                    `请解释待审批项“${item.title}”的目的、风险和边界，但不要替我批准。`,
                  )
                }
                type="button"
              >
                <ShieldCheck aria-hidden="true" />
                <span>
                  <small>{item.source} · {item.risk_level}</small>
                  <strong>{item.title}</strong>
                </span>
                <ArrowUpRight aria-hidden="true" />
              </button>
            ))}
            {!pending.length ? (
              <div className={styles.approvalClear}>
                <ListChecks aria-hidden="true" />
                <strong>当前没有待审批项</strong>
                <span>需要你决定的操作会出现在这里。</span>
              </div>
            ) : null}
          </div>
          <p className={styles.panelBoundaryNote}>
            面板不提供快捷批准。所有决定都在完整审批页中完成并记录审计事件。
          </p>
        </>
      ) : null}
      <PanelFooter panelId="approval" />
    </div>
  );
}
