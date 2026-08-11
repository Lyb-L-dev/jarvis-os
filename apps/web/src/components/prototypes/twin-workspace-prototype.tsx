"use client";

import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Brain,
  BriefcaseBusiness,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Database,
  ListFilter,
  MessageSquareText,
  PanelLeftOpen,
  PanelRightOpen,
  Pin,
  Plus,
  Route,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Workflow,
  X,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import styles from "./twin-workspace-prototype.module.css";

type VariantKey = "A" | "B" | "C";
type Side = "left" | "right";
type LeftPanelId = "career" | "memory" | "knowledge";
type RightPanelId = "growth" | "orchestrator" | "approval";
type PanelId = LeftPanelId | RightPanelId;
type DeckPresentation = "stack" | "rail" | "collapsed" | "stage";

type PanelDefinition = {
  id: PanelId;
  title: string;
  shortTitle: string;
  subtitle: string;
  side: Side;
  tone: "cyan" | "violet" | "amber" | "green" | "rose" | "blue";
  icon: typeof BriefcaseBusiness;
};

type PrototypeMessage = {
  id: number;
  role: "jarvis" | "user" | "event";
  text: string;
  source?: string;
};

const VARIANTS: Record<VariantKey, { name: string; description: string }> = {
  A: {
    name: "平衡双翼",
    description: "左右功能面板常驻，中央对话保持稳定。",
  },
  B: {
    name: "专注轨道",
    description: "一次突出一侧，另一侧收成任务轨道。",
  },
  C: {
    name: "空间舞台",
    description: "卡片像系统后台一样错位悬停在对话两侧。",
  },
};

const PANELS: Record<PanelId, PanelDefinition> = {
  career: {
    id: "career",
    title: "CareerRadar",
    shortTitle: "求职",
    subtitle: "企业与岗位上下文",
    side: "left",
    tone: "cyan",
    icon: BriefcaseBusiness,
  },
  memory: {
    id: "memory",
    title: "长期记忆",
    shortTitle: "记忆",
    subtitle: "候选事实与关系",
    side: "left",
    tone: "violet",
    icon: Brain,
  },
  knowledge: {
    id: "knowledge",
    title: "本地知识",
    shortTitle: "知识",
    subtitle: "Obsidian 与检索证据",
    side: "left",
    tone: "blue",
    icon: BookOpen,
  },
  growth: {
    id: "growth",
    title: "成长计划",
    shortTitle: "成长",
    subtitle: "目标、里程碑与任务草稿",
    side: "right",
    tone: "green",
    icon: Route,
  },
  orchestrator: {
    id: "orchestrator",
    title: "任务编排",
    shortTitle: "编排",
    subtitle: "Research → Growth",
    side: "right",
    tone: "cyan",
    icon: Workflow,
  },
  approval: {
    id: "approval",
    title: "审阅与审批",
    shortTitle: "审批",
    subtitle: "人在环控制面",
    side: "right",
    tone: "amber",
    icon: ShieldCheck,
  },
};

const INITIAL_MESSAGES: PrototypeMessage[] = [
  {
    id: 1,
    role: "user",
    text: "根据最近的求职情况，帮我调整下周成长计划。",
  },
  {
    id: 2,
    role: "jarvis",
    text: "我已在左侧打开 CareerRadar，并在右侧准备成长计划。你可以先筛选企业，我会把最终选择带入计划。",
  },
  {
    id: 3,
    role: "event",
    source: "空间工作台",
    text: "CareerRadar 与成长计划已建立共享上下文",
  },
];

export function TwinWorkspacePrototype() {
  const searchParams = useSearchParams();
  const requestedVariant = searchParams.get("variant")?.toUpperCase();
  const variant: VariantKey =
    requestedVariant === "B" || requestedVariant === "C"
      ? requestedVariant
      : "A";
  const [leftPanels, setLeftPanels] = useState<PanelId[]>([
    "career",
    "memory",
    "knowledge",
  ]);
  const [rightPanels, setRightPanels] = useState<PanelId[]>([
    "growth",
    "orchestrator",
    "approval",
  ]);
  const [pinned, setPinned] = useState<PanelId[]>(["career", "growth"]);
  const [focusSide, setFocusSide] = useState<Side>("left");
  const [messages, setMessages] = useState<PrototypeMessage[]>(INITIAL_MESSAGES);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    document.body.classList.add("twin-workspace-prototype-active");
    return () => document.body.classList.remove("twin-workspace-prototype-active");
  }, []);

  const leftActive = leftPanels[0] ?? null;
  const rightActive = rightPanels[0] ?? null;

  function bringForward(side: Side, panelId: PanelId) {
    const update = (items: PanelId[]) => [
      panelId,
      ...items.filter((id) => id !== panelId),
    ];
    if (side === "left") setLeftPanels(update);
    else setRightPanels(update);
    setFocusSide(side);
  }

  function closePanel(side: Side, panelId: PanelId) {
    if (side === "left") {
      setLeftPanels((items) => items.filter((id) => id !== panelId));
    } else {
      setRightPanels((items) => items.filter((id) => id !== panelId));
    }
  }

  function restorePanel(side: Side) {
    const current = side === "left" ? leftPanels : rightPanels;
    const candidate = (Object.values(PANELS) as PanelDefinition[]).find(
      (panel) => panel.side === side && !current.includes(panel.id),
    );
    if (!candidate) return;
    if (side === "left") setLeftPanels((items) => [candidate.id, ...items]);
    else setRightPanels((items) => [candidate.id, ...items]);
  }

  function togglePin(panelId: PanelId) {
    setPinned((items) =>
      items.includes(panelId)
        ? items.filter((id) => id !== panelId)
        : [...items, panelId],
    );
  }

  function syncToConversation(text: string, source: string) {
    const base = Date.now();
    setMessages((items) => [
      ...items,
      { id: base, role: "user", text, source },
      {
        id: base + 1,
        role: "jarvis",
        text: responseForSource(source),
      },
    ]);
  }

  function submitDraft() {
    const text = draft.trim();
    if (!text) return;
    const base = Date.now();
    setMessages((items) => [
      ...items,
      { id: base, role: "user", text },
      {
        id: base + 1,
        role: "jarvis",
        text: "收到。我会继续在中央对话中处理，并在需要真实数据或行动时更新两侧面板。",
      },
    ]);
    setDraft("");
  }

  const sharedProps: WorkspaceVariantProps = {
    leftPanels,
    rightPanels,
    pinned,
    focusSide,
    setFocusSide,
    bringForward,
    closePanel,
    restorePanel,
    togglePin,
    syncToConversation,
    messages,
    draft,
    setDraft,
    submitDraft,
  };

  return (
    <main className={styles.prototypeRoot} data-variant={variant}>
      <PrototypeHeader
        variant={variant}
        leftCount={leftPanels.length}
        rightCount={rightPanels.length}
      />

      <div className={styles.prototypeViewport}>
        {variant === "A" ? <VariantA {...sharedProps} /> : null}
        {variant === "B" ? <VariantB {...sharedProps} /> : null}
        {variant === "C" ? <VariantC {...sharedProps} /> : null}
      </div>

      <PrototypeSwitcher current={variant} />

      <div className={styles.stateReadout} aria-live="polite">
        <span>左侧 {leftPanels.length}/3</span>
        <span>右侧 {rightPanels.length}/3</span>
        <span>前台：{leftActive ? PANELS[leftActive].shortTitle : "无"}</span>
        <span>前台：{rightActive ? PANELS[rightActive].shortTitle : "无"}</span>
      </div>
    </main>
  );
}

type WorkspaceVariantProps = {
  leftPanels: PanelId[];
  rightPanels: PanelId[];
  pinned: PanelId[];
  focusSide: Side;
  setFocusSide: (side: Side) => void;
  bringForward: (side: Side, panelId: PanelId) => void;
  closePanel: (side: Side, panelId: PanelId) => void;
  restorePanel: (side: Side) => void;
  togglePin: (panelId: PanelId) => void;
  syncToConversation: (text: string, source: string) => void;
  messages: PrototypeMessage[];
  draft: string;
  setDraft: (value: string) => void;
  submitDraft: () => void;
};

function VariantA(props: WorkspaceVariantProps) {
  return (
    <div className={styles.variantA}>
      <PanelDeck
        panelIds={props.leftPanels}
        side="left"
        presentation="stack"
        {...panelActions(props)}
      />
      <ConversationCore {...conversationProps(props)} />
      <PanelDeck
        panelIds={props.rightPanels}
        side="right"
        presentation="stack"
        {...panelActions(props)}
      />
    </div>
  );
}

function VariantB(props: WorkspaceVariantProps) {
  const leftFocused = props.focusSide === "left";
  return (
    <div className={styles.variantB} data-focus={props.focusSide}>
      <PanelDeck
        panelIds={props.leftPanels}
        side="left"
        presentation={leftFocused ? "rail" : "collapsed"}
        {...panelActions(props)}
      />
      <ConversationCore {...conversationProps(props)} />
      <PanelDeck
        panelIds={props.rightPanels}
        side="right"
        presentation={leftFocused ? "collapsed" : "rail"}
        {...panelActions(props)}
      />
      <div className={styles.focusToggle}>
        <button
          aria-label="突出左侧资料面板"
          className={leftFocused ? styles.focusToggleActive : ""}
          onClick={() => props.setFocusSide("left")}
          type="button"
        >
          <PanelLeftOpen size={16} />
          资料
        </button>
        <button
          aria-label="突出右侧行动面板"
          className={!leftFocused ? styles.focusToggleActive : ""}
          onClick={() => props.setFocusSide("right")}
          type="button"
        >
          行动
          <PanelRightOpen size={16} />
        </button>
      </div>
    </div>
  );
}

function VariantC(props: WorkspaceVariantProps) {
  return (
    <div className={styles.variantC}>
      <PanelDeck
        panelIds={props.leftPanels}
        side="left"
        presentation="stage"
        {...panelActions(props)}
      />
      <ConversationCore {...conversationProps(props)} />
      <PanelDeck
        panelIds={props.rightPanels}
        side="right"
        presentation="stage"
        {...panelActions(props)}
      />
    </div>
  );
}

function panelActions(props: WorkspaceVariantProps) {
  return {
    pinned: props.pinned,
    onActivate: props.bringForward,
    onClose: props.closePanel,
    onRestore: props.restorePanel,
    onTogglePin: props.togglePin,
    onSync: props.syncToConversation,
  };
}

function conversationProps(props: WorkspaceVariantProps) {
  return {
    messages: props.messages,
    draft: props.draft,
    setDraft: props.setDraft,
    submitDraft: props.submitDraft,
  };
}

type PanelDeckProps = {
  side: Side;
  panelIds: PanelId[];
  presentation: DeckPresentation;
  pinned: PanelId[];
  onActivate: (side: Side, panelId: PanelId) => void;
  onClose: (side: Side, panelId: PanelId) => void;
  onRestore: (side: Side) => void;
  onTogglePin: (panelId: PanelId) => void;
  onSync: (text: string, source: string) => void;
};

function PanelDeck({
  side,
  panelIds,
  presentation,
  pinned,
  onActivate,
  onClose,
  onRestore,
  onTogglePin,
  onSync,
}: PanelDeckProps) {
  const activeId = panelIds[0];
  const sideLabel = side === "left" ? "资料与上下文" : "行动与结果";

  if (presentation === "collapsed") {
    return (
      <aside className={styles.collapsedDeck} data-side={side}>
        <button
          className={styles.collapsedDeckLabel}
          onClick={() => activeId && onActivate(side, activeId)}
          type="button"
        >
          {side === "left" ? <ChevronRight /> : <ChevronLeft />}
          <span>{sideLabel}</span>
        </button>
        <div className={styles.collapsedPanelList}>
          {panelIds.map((panelId) => {
            const panel = PANELS[panelId];
            const Icon = panel.icon;
            return (
              <button
                aria-label={`打开${panel.title}`}
                data-tone={panel.tone}
                key={panel.id}
                onClick={() => onActivate(side, panel.id)}
                title={panel.title}
                type="button"
              >
                <Icon size={17} />
                <span>{panel.shortTitle}</span>
              </button>
            );
          })}
        </div>
      </aside>
    );
  }

  return (
    <aside
      className={styles.panelDeck}
      data-presentation={presentation}
      data-side={side}
    >
      <div className={styles.deckHeading}>
        <div>
          <span>{sideLabel}</span>
          <small>{panelIds.length}/3 个临时面板</small>
        </div>
        <button
          aria-label={`添加${sideLabel}面板`}
          disabled={panelIds.length >= 3}
          onClick={() => onRestore(side)}
          type="button"
        >
          <Plus size={15} />
        </button>
      </div>

      {panelIds.length === 0 ? (
        <div className={styles.emptyDeck}>
          <Sparkles size={20} />
          <p>在对话中提到相关功能，Jarvis 会把面板放到这里。</p>
          <button onClick={() => onRestore(side)} type="button">
            选择面板
          </button>
        </div>
      ) : (
        <div className={styles.deckSurface}>
          <div className={styles.deckBackCards}>
            {panelIds.slice(1).map((panelId, index) => {
              const panel = PANELS[panelId];
              const Icon = panel.icon;
              return (
                <button
                  className={styles.deckBackCard}
                  data-depth={index + 1}
                  data-tone={panel.tone}
                  key={panel.id}
                  onClick={() => onActivate(side, panel.id)}
                  type="button"
                >
                  <Icon size={15} />
                  <span>{panel.shortTitle}</span>
                  {pinned.includes(panel.id) ? <Pin size={11} /> : null}
                </button>
              );
            })}
          </div>

          {activeId ? (
            <PanelCard
              panel={PANELS[activeId]}
              pinned={pinned.includes(activeId)}
              onClose={() => onClose(side, activeId)}
              onSync={onSync}
              onTogglePin={() => onTogglePin(activeId)}
            />
          ) : null}
        </div>
      )}
    </aside>
  );
}

type PanelCardProps = {
  panel: PanelDefinition;
  pinned: boolean;
  onClose: () => void;
  onTogglePin: () => void;
  onSync: (text: string, source: string) => void;
};

function PanelCard({ panel, pinned, onClose, onTogglePin, onSync }: PanelCardProps) {
  const Icon = panel.icon;
  return (
    <section className={styles.panelCard} data-tone={panel.tone}>
      <header className={styles.panelHeader}>
        <div className={styles.panelIdentity}>
          <span className={styles.panelIcon}>
            <Icon size={17} />
          </span>
          <div>
            <h2>{panel.title}</h2>
            <p>{panel.subtitle}</p>
          </div>
        </div>
        <div className={styles.panelControls}>
          <button
            aria-label={pinned ? `取消固定${panel.title}` : `固定${panel.title}`}
            className={pinned ? styles.pinnedButton : ""}
            onClick={onTogglePin}
            type="button"
          >
            <Pin size={14} />
          </button>
          <button aria-label={`关闭${panel.title}`} onClick={onClose} type="button">
            <X size={15} />
          </button>
        </div>
      </header>
      <div className={styles.panelBody}>
        <PanelContent panelId={panel.id} onSync={onSync} />
      </div>
    </section>
  );
}

function PanelContent({
  panelId,
  onSync,
}: {
  panelId: PanelId;
  onSync: (text: string, source: string) => void;
}) {
  if (panelId === "career") {
    return <CareerPanel onSync={onSync} />;
  }
  if (panelId === "memory") {
    return <MemoryPanel onSync={onSync} />;
  }
  if (panelId === "knowledge") {
    return <KnowledgePanel onSync={onSync} />;
  }
  if (panelId === "growth") {
    return <GrowthPanel onSync={onSync} />;
  }
  if (panelId === "orchestrator") {
    return <OrchestratorPanel onSync={onSync} />;
  }
  return <ApprovalPanel onSync={onSync} />;
}

function CareerPanel({ onSync }: Pick<PanelContentProps, "onSync">) {
  const [region, setRegion] = useState("福建");
  const companies = [
    ["星网锐捷", "数据分析", "福州 · 2 天前"],
    ["三棵树", "数字化运营", "莆田 · 4 天前"],
    ["美图公司", "数据产品", "厦门 · 5 天前"],
  ];
  return (
    <div className={styles.moduleContent}>
      <label className={styles.panelSearch}>
        <Search size={14} />
        <input defaultValue="数据分析" aria-label="搜索岗位或企业" />
      </label>
      <div className={styles.filterRow}>
        {["福建", "远程", "校招"].map((item) => (
          <button
            className={region === item ? styles.filterActive : ""}
            key={item}
            onClick={() => setRegion(item)}
            type="button"
          >
            {item}
          </button>
        ))}
        <button aria-label="更多筛选" type="button">
          <ListFilter size={13} />
        </button>
      </div>
      <div className={styles.resultSummary}>
        <strong>12</strong>
        <span>个匹配岗位 · 已选择 3 家企业</span>
      </div>
      <div className={styles.companyList}>
        {companies.map(([name, role, meta]) => (
          <button key={name} type="button">
            <span className={styles.companyCheck}>
              <Check size={11} />
            </span>
            <span>
              <strong>{name}</strong>
              <small>{role}</small>
            </span>
            <time>{meta}</time>
          </button>
        ))}
      </div>
      <button
        className={styles.panelPrimaryAction}
        onClick={() =>
          onSync(
            "已从 CareerRadar 选择星网锐捷、三棵树和美图公司，请分析岗位匹配度并生成跟进建议。",
            "CareerRadar",
          )
        }
        type="button"
      >
        交给 Jarvis 分析
        <ArrowRight size={14} />
      </button>
    </div>
  );
}

type PanelContentProps = {
  onSync: (text: string, source: string) => void;
};

function MemoryPanel({ onSync }: PanelContentProps) {
  return (
    <div className={styles.moduleContent}>
      <div className={styles.memorySource}>
        <Database size={15} />
        <div>
          <span>来自 8 月 9 日对话</span>
          <strong>“暂时不考虑销售岗位。”</strong>
        </div>
      </div>
      <div className={styles.relationPreview}>
        <span>求职偏好</span>
        <i>excludes</i>
        <span>销售岗位</span>
      </div>
      <p className={styles.panelHint}>候选关系尚未进入长期上下文。</p>
      <div className={styles.actionGrid}>
        <button
          onClick={() =>
            onSync("确认记忆：暂时不考虑销售岗位。", "Memory")
          }
          type="button"
        >
          确认
        </button>
        <button type="button">合并</button>
        <button type="button">忽略</button>
      </div>
    </div>
  );
}

function KnowledgePanel({ onSync }: PanelContentProps) {
  return (
    <div className={styles.moduleContent}>
      <div className={styles.knowledgeStatus}>
        <span>本地索引在线</span>
        <small>Obsidian · 46 篇 · 刚刚同步</small>
      </div>
      {["求职复盘/岗位筛选标准", "项目经历/Jarvis OS", "数据分析面试笔记"].map(
        (title, index) => (
          <button className={styles.knowledgeHit} key={title} type="button">
            <span>{index + 1}</span>
            <div>
              <strong>{title}</strong>
              <small>匹配当前对话 · 本地可用</small>
            </div>
          </button>
        ),
      )}
      <button
        className={styles.panelPrimaryAction}
        onClick={() =>
          onSync("请结合这 3 篇本地笔记继续分析当前求职问题。", "Knowledge")
        }
        type="button"
      >
        加入当前对话
        <ArrowRight size={14} />
      </button>
    </div>
  );
}

function GrowthPanel({ onSync }: PanelContentProps) {
  return (
    <div className={styles.moduleContent}>
      <div className={styles.goalHeader}>
        <div>
          <span>当前目标</span>
          <strong>获得数据相关岗位 Offer</strong>
        </div>
        <b>本周</b>
      </div>
      <ol className={styles.taskList}>
        <li data-state="done">
          <span />
          <div><strong>更新项目描述</strong><small>已完成</small></div>
        </li>
        <li data-state="active">
          <span />
          <div><strong>筛选 10 家目标企业</strong><small>正在进行</small></div>
        </li>
        <li>
          <span />
          <div><strong>准备岗位定向问答</strong><small>等待企业选择</small></div>
        </li>
      </ol>
      <button
        className={styles.panelPrimaryAction}
        onClick={() =>
          onSync("基于刚才选择的企业，生成下周成长计划草稿。", "Growth")
        }
        type="button"
      >
        生成下周计划
        <ArrowRight size={14} />
      </button>
    </div>
  );
}

function OrchestratorPanel({ onSync }: PanelContentProps) {
  return (
    <div className={styles.moduleContent}>
      <div className={styles.runStatus}>
        <span className={styles.liveDot} />
        <div><strong>Research → Growth</strong><small>2 / 4 步已完成</small></div>
        <Clock3 size={15} />
      </div>
      <div className={styles.stepList}>
        <span data-state="done">读取企业证据</span>
        <span data-state="done">比较岗位要求</span>
        <span data-state="active">生成匹配分析</span>
        <span>形成成长草稿</span>
      </div>
      <button
        className={styles.secondaryAction}
        onClick={() => onSync("暂停当前编排并向我解释已有结果。", "Orchestrator")}
        type="button"
      >
        暂停并汇报
      </button>
    </div>
  );
}

function ApprovalPanel({ onSync }: PanelContentProps) {
  return (
    <div className={styles.moduleContent}>
      <div className={styles.approvalNotice}>
        <ShieldCheck size={18} />
        <div><span>Draft Review</span><strong>下周成长计划草稿</strong></div>
      </div>
      <dl className={styles.approvalMeta}>
        <div><dt>类型</dt><dd>Jarvis 内部草稿</dd></div>
        <div><dt>外部副作用</dt><dd>无</dd></div>
        <div><dt>等待</dt><dd>你的审阅</dd></div>
      </dl>
      <button
        className={styles.panelPrimaryAction}
        onClick={() => onSync("打开成长计划草稿，让我逐项审阅。", "Approval")}
        type="button"
      >
        进入草稿审阅
        <ArrowRight size={14} />
      </button>
    </div>
  );
}

type ConversationCoreProps = {
  messages: PrototypeMessage[];
  draft: string;
  setDraft: (value: string) => void;
  submitDraft: () => void;
};

function ConversationCore({
  messages,
  draft,
  setDraft,
  submitDraft,
}: ConversationCoreProps) {
  return (
    <section className={styles.conversationCore}>
      <header className={styles.conversationHeader}>
        <div className={styles.jarvisIdentity}>
          <span>J</span>
          <div><h1>Jarvis</h1><p>双翼对话工作台 · Prototype</p></div>
        </div>
        <div className={styles.conversationStatus}>
          <span />
          本地在线
        </div>
      </header>

      <div className={styles.messageFlow}>
        <div className={styles.sessionMarker}>
          <span />
          当前目标：求职进展与成长计划
          <span />
        </div>
        {messages.map((message) => (
          <article
            className={styles.message}
            data-role={message.role}
            key={message.id}
          >
            {message.role === "jarvis" ? (
              <span className={styles.messageAvatar}>J</span>
            ) : null}
            <div>
              {message.source ? <small>{message.source}</small> : null}
              <p>{message.text}</p>
            </div>
          </article>
        ))}
      </div>

      <form
        className={styles.prototypeComposer}
        onSubmit={(event) => {
          event.preventDefault();
          submitDraft();
        }}
      >
        <MessageSquareText size={17} />
        <input
          aria-label="继续与 Jarvis 对话"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="继续对话，或直接说“打开记忆面板”"
          value={draft}
        />
        <button aria-label="发送消息" disabled={!draft.trim()} type="submit">
          <Send size={16} />
        </button>
      </form>
    </section>
  );
}

function PrototypeHeader({
  variant,
  leftCount,
  rightCount,
}: {
  variant: VariantKey;
  leftCount: number;
  rightCount: number;
}) {
  return (
    <header className={styles.prototypeHeader}>
      <div>
        <strong>JARVIS / V3-4b</strong>
        <span>双翼对话工作台原型</span>
      </div>
      <p>{VARIANTS[variant].description}</p>
      <div>
        <span>资料 {leftCount}/3</span>
        <span>行动 {rightCount}/3</span>
        <b>仅原型 · 不写入真实数据</b>
      </div>
    </header>
  );
}

function PrototypeSwitcher({ current }: { current: VariantKey }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const keys = useMemo(() => Object.keys(VARIANTS) as VariantKey[], []);

  function move(direction: -1 | 1) {
    const currentIndex = keys.indexOf(current);
    const next = keys[(currentIndex + direction + keys.length) % keys.length];
    const params = new URLSearchParams(searchParams.toString());
    params.set("variant", next);
    router.replace(`${pathname}?${params.toString()}`);
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target?.matches("input, textarea, select, [contenteditable='true']")
      ) {
        return;
      }
      if (event.key === "ArrowLeft") move(-1);
      if (event.key === "ArrowRight") move(1);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  return (
    <nav className={styles.prototypeSwitcher} aria-label="原型变体切换">
      <button aria-label="上一个变体" onClick={() => move(-1)} type="button">
        <ArrowLeft size={16} />
      </button>
      <div>
        <span>方案 {current}</span>
        <strong>{VARIANTS[current].name}</strong>
      </div>
      <button aria-label="下一个变体" onClick={() => move(1)} type="button">
        <ArrowRight size={16} />
      </button>
    </nav>
  );
}

function responseForSource(source: string): string {
  const responses: Record<string, string> = {
    CareerRadar: "我已接收这 3 家企业。接下来会比较岗位要求、项目经历和你的求职偏好。",
    Memory: "这条候选已加入本次确认流程，后续回答会优先遵守该求职偏好。",
    Knowledge: "已把选中的本地笔记加入当前上下文，正文仍保留在本机。",
    Growth: "我会先生成可编辑草稿，不会直接创建正式任务。",
    Orchestrator: "已暂停在可恢复状态。我会先汇报完成步骤和仍缺少的证据。",
    Approval: "已打开草稿审阅。该操作不代表任何外部工具授权。",
  };
  return responses[source] ?? "已同步面板上下文，我会在这里继续处理。";
}
