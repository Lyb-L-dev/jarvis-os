// Three variants of /approvals, switchable via ?variant=, on the existing route.
import {
  ArrowRight,
  Ban,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDot,
  Clock3,
  FilePenLine,
  Filter,
  Fingerprint,
  History,
  LockKeyhole,
  Mail,
  Network,
  Play,
  Search,
  Shield,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import styles from "@/app/v3-prototype.module.css";
import {
  PrototypeSwitcher,
  type PrototypeVariant,
} from "@/components/prototypes/prototype-switcher";

const variants: PrototypeVariant[] = [
  { key: "A", name: "决定收件箱" },
  { key: "B", name: "风险分层" },
  { key: "C", name: "审计账本" },
];

export function ApprovalsV3Prototype({ variant }: { variant: "A" | "B" | "C" }) {
  return (
    <>
      {variant === "A" ? <DecisionInbox /> : null}
      {variant === "B" ? <RiskLanes /> : null}
      {variant === "C" ? <AuditLedger /> : null}
      <PrototypeSwitcher current={variant} variants={variants} />
    </>
  );
}

const queueItems = [
  { risk: "R1", kind: "草稿审阅", title: "发布门禁会 · 3 条任务草稿", meta: "Jarvis Core · 刚刚", tone: "low" },
  { risk: "R2", kind: "工具批准", title: "写入 drafts/release-gate.md", meta: "Local Document · 8 分钟前", tone: "medium" },
  { risk: "R2", kind: "模型授权", title: "MiMo 单次云端分析", meta: "Research · 21 分钟前", tone: "medium" },
];

function DecisionInbox() {
  return (
    <main className={`dashboard ${styles.stage} ${styles.approvalInbox}`}>
      <header className={styles.approvalHeader}>
        <div><h1>决定收件箱</h1><p>所有授权都有明确范围、到期时间和下一步。</p></div>
        <div className={styles.safetyPromise}><ShieldCheck /><span><strong>你始终拥有最后决定权</strong><small>批准不等于执行</small></span></div>
      </header>

      <div className={styles.approvalSummaryBar}>
        <span><CircleDot /> <strong>3</strong> 待决定</span>
        <span><CheckCircle2 /> <strong>1</strong> 已批准待执行</span>
        <span><Clock3 /> 最早一项将在 <strong>22 分钟</strong>后到期</span>
        <button type="button"><History /> 查看历史</button>
      </div>

      <div className={styles.inboxGrid}>
        <section className={styles.decisionQueue}>
          <div className={styles.queueToolbar}>
            <label><Search /><input aria-label="搜索决定" placeholder="搜索决定" /></label>
            <button type="button"><Filter /> 筛选</button>
          </div>
          <div className={styles.queueCaption}><span>等待你的决定</span><small>按到期时间排序</small></div>
          {queueItems.map((item, index) => (
            <button className={index === 0 ? styles.selectedQueueItem : styles.queueItem} key={item.title} type="button">
              <RiskBadge risk={item.risk} tone={item.tone} />
              <span><small>{item.kind}</small><strong>{item.title}</strong><em>{item.meta}</em></span>
              <ChevronRight />
            </button>
          ))}
          <div className={styles.queueComplete}><Check /><span><strong>今天已处理 6 项</strong><small>没有跳过任何高风险操作</small></span></div>
        </section>

        <section className={styles.decisionInspector}>
          <div className={styles.inspectorTopline}>
            <div><RiskBadge risk="R1" tone="low" /><span>草稿审阅</span></div>
            <span className={styles.expiresSoon}><Clock3 /> 22 分钟后到期</span>
          </div>
          <h2>发布门禁会 · 3 条任务草稿</h2>
          <p className={styles.decisionReason}>Jarvis 根据刚才的发布复盘生成了任务草稿。通过审阅只允许进入下一步，不会创建正式任务，也不会修改日历。</p>

          <div className={styles.scopeStatement}>
            <Shield /><div><small>本次决定的准确含义</small><strong>允许这 3 条草稿进入 Growth 审阅队列</strong></div>
          </div>

          <div className={styles.draftPreview}>
            <div className={styles.previewHeading}><span>将要继续的内容</span><small>3 条草稿 · 尚未执行</small></div>
            <ol>
              <li><span>09:30</span><div><strong>发布门禁会</strong><p>确认 5 条验收条件与唯一负责人</p></div><em>20 min</em></li>
              <li><span>10:00</span><div><strong>风险清单归档</strong><p>把 2 项未决问题转入审批队列</p></div><em>25 min</em></li>
              <li><span>10:30</span><div><strong>最小发布演练</strong><p>只验证阻断项，不增加新范围</p></div><em>45 min</em></li>
            </ol>
          </div>

          <details className={styles.policyDisclosure}>
            <summary>查看政策与数据范围 <ChevronDown /></summary>
            <p>来源：本地对话、已启用任务。无云端数据扩大；无工具执行权限。</p>
          </details>

          <div className={styles.decisionActions}>
            <button className={styles.rejectButton} type="button"><X /> 拒绝草稿</button>
            <button className={styles.approveButton} type="button"><Check /> 通过审阅</button>
          </div>
          <p className={styles.actionFootnote}>每个决定都写入本地审计记录，可随时查看来源与结果。</p>
        </section>
      </div>
    </main>
  );
}

function RiskLanes() {
  return (
    <main className={`dashboard ${styles.stage} ${styles.approvalLanes}`}>
      <header className={styles.lanesHeader}>
        <div><h1>控制平面</h1><p>按风险语义处理，而不是把所有“确认”混在一个列表里。</p></div>
        <button type="button"><Search /> 搜索审计记录</button>
      </header>

      <section className={styles.boundaryStrip}>
        <div><LockKeyhole /><span><strong>R3 永不开放执行入口</strong><small>支付、交易、凭据操作与不可恢复删除始终阻断</small></span></div>
        <button type="button">查看永久边界 <ArrowRight /></button>
      </section>

      <div className={styles.laneStack}>
        <section className={`${styles.riskLane} ${styles.riskLaneOne}`}>
          <div className={styles.laneLabel}><RiskBadge risk="R1" tone="low" /><span><strong>审阅</strong><small>决定草稿是否继续</small></span><em>1</em></div>
          <article className={styles.laneCard}>
            <span className={styles.laneIcon}><FilePenLine /></span>
            <div><small>任务草稿 · Jarvis Core</small><h2>发布门禁会 · 3 条任务草稿</h2><p>仅进入下一层审阅，不创建正式任务。</p></div>
            <span className={styles.laneExpiry}>22 min</span>
            <button type="button">审阅 <ChevronRight /></button>
          </article>
        </section>

        <section className={`${styles.riskLane} ${styles.riskLaneTwo}`}>
          <div className={styles.laneLabel}><RiskBadge risk="R2" tone="medium" /><span><strong>批准</strong><small>允许一次明确副作用</small></span><em>2</em></div>
          <div className={styles.laneCards}>
            <article className={styles.laneCard}>
              <span className={styles.laneIcon}><FilePenLine /></span>
              <div><small>工具批准 · Local Document</small><h2>写入 release-gate.md</h2><p>受控目录 · 1.8 KB · 不覆盖已有文件</p></div>
              <span className={styles.laneExpiry}>47 min</span>
              <button type="button">检查 <ChevronRight /></button>
            </article>
            <article className={styles.laneCard}>
              <span className={styles.laneIcon}><Network /></span>
              <div><small>模型授权 · Research</small><h2>MiMo 单次云端分析</h2><p>只发送已显示的 3 条公开摘要</p></div>
              <span className={styles.laneExpiry}>9 min</span>
              <button type="button">检查 <ChevronRight /></button>
            </article>
          </div>
        </section>

        <section className={`${styles.riskLane} ${styles.riskLaneThree}`}>
          <div className={styles.laneLabel}><RiskBadge risk="R3" tone="high" /><span><strong>永久阻断</strong><small>Agent 没有执行接口</small></span><em>4 类</em></div>
          <div className={styles.blockedActions}>
            <span><Ban /> 支付</span><span><Ban /> 投资交易</span><span><Ban /> 凭据操作</span><span><Ban /> 不可恢复删除</span>
          </div>
        </section>
      </div>

      <section className={styles.expandedDecision}>
        <div className={styles.expandedDecisionHead}><div><RiskBadge risk="R1" tone="low" /><span><small>当前选中</small><strong>发布门禁会 · 3 条任务草稿</strong></span></div><button aria-label="关闭详情" type="button"><X /></button></div>
        <div className={styles.expandedColumns}>
          <div><h3>为什么需要你</h3><p>这是一项产品方向决定。Jarvis 可以准备草稿，但不能替你确认下周投入。</p></div>
          <div><h3>通过之后</h3><p>3 条内容进入 Growth 草稿审阅。不会创建正式任务，也不会触发工具。</p></div>
          <div><h3>来源</h3><p>当前对话、4 个本地任务、1 份验收文档。</p></div>
          <div className={styles.expandedActions}><button className={styles.rejectButton} type="button">拒绝</button><button className={styles.approveButton} type="button">通过审阅</button></div>
        </div>
      </section>
    </main>
  );
}

function AuditLedger() {
  return (
    <main className={`dashboard ${styles.stage} ${styles.approvalLedger}`}>
      <header className={styles.ledgerHeader}>
        <div><h1>授权账本</h1><p>每个请求从提出、决定到执行都有一条可核对的轨迹。</p></div>
        <div className={styles.ledgerHeaderTools}><label><Search /><input aria-label="搜索账本" placeholder="搜索请求、Agent 或指纹" /></label><button type="button"><Filter /> 本周</button></div>
      </header>

      <div className={styles.ledgerLayout}>
        <section className={styles.ledgerTable}>
          <div className={styles.ledgerColumns}><span>时间 / 状态</span><span>请求</span><span>范围</span><span>决定</span></div>
          <LedgerRow time="10:24" status="等待" icon={<Sparkles />} title="发布门禁会 · 3 条任务草稿" meta="Jarvis Core · Draft Review" scope="R1 · 仅草稿" decision="需要你" active />
          <LedgerRow time="10:08" status="等待" icon={<FilePenLine />} title="写入 release-gate.md" meta="Local Document · Tool Approval" scope="R2 · 单次写入" decision="47 min" />
          <LedgerRow time="09:42" status="已通过" icon={<Network />} title="MiMo 单次云端分析" meta="Research · Model Consent" scope="3 条公开摘要" decision="刘烨宝" />
          <LedgerRow time="昨天" status="已执行" icon={<CalendarClock />} title="读取未来 7 天日历" meta="Jarvis Core · Read-only Tool" scope="R0 · 只读" decision="自动允许" />
          <LedgerRow time="昨天" status="已拒绝" icon={<Mail />} title="准备一封跟进邮件草稿" meta="Jarvis Core · Draft Review" scope="R1 · 本地草稿" decision="刘烨宝" />
        </section>

        <aside className={styles.ledgerInspector}>
          <div className={styles.ledgerInspectorHead}><RiskBadge risk="R1" tone="low" /><span>等待决定</span></div>
          <h2>发布门禁会 · 3 条任务草稿</h2>
          <p>通过只代表“接受这个计划方向”，不会创建正式任务。</p>
          <div className={styles.auditPath}>
            <div className={styles.auditPathDone}><Check /><span><strong>请求已创建</strong><small>10:24:08 · Jarvis Core</small></span></div>
            <div className={styles.auditPathCurrent}><CircleDot /><span><strong>等待你的决定</strong><small>22 分钟后自动过期</small></span></div>
            <div><Play /><span><strong>后续仍需审阅</strong><small>Growth 草稿队列</small></span></div>
          </div>
          <dl className={styles.scopeFacts}>
            <div><dt>政策</dt><dd>draft.review.r1</dd></div>
            <div><dt>数据范围</dt><dd>本地对话 + 已启用任务</dd></div>
            <div><dt>外部副作用</dt><dd>无</dd></div>
            <div><dt>请求指纹</dt><dd><Fingerprint /> 8ca2…19f4</dd></div>
          </dl>
          <div className={styles.ledgerActions}><button className={styles.rejectButton} type="button"><X /> 拒绝</button><button className={styles.approveButton} type="button"><Check /> 通过审阅</button></div>
          <button className={styles.textButton} type="button">查看完整请求 JSON <ChevronRight /></button>
        </aside>
      </div>
      <footer className={styles.ledgerFooter}><ShieldCheck /> 所有记录保存在本地事实源中；Run、Step 与事件流只引用请求，不复制私人正文。</footer>
    </main>
  );
}

function RiskBadge({ risk, tone }: { risk: string; tone: string }) {
  return <span className={`${styles.riskBadge} ${styles[`risk_${tone}`]}`}>{risk}</span>;
}

function LedgerRow({
  time,
  status,
  icon,
  title,
  meta,
  scope,
  decision,
  active = false,
}: {
  time: string;
  status: string;
  icon: React.ReactNode;
  title: string;
  meta: string;
  scope: string;
  decision: string;
  active?: boolean;
}) {
  return (
    <button className={`${styles.ledgerRow} ${active ? styles.activeLedgerRow : ""}`} type="button">
      <span><strong>{time}</strong><small>{status}</small></span>
      <span className={styles.ledgerRequest}><i>{icon}</i><span><strong>{title}</strong><small>{meta}</small></span></span>
      <span>{scope}</span>
      <span><strong>{decision}</strong><ChevronRight /></span>
    </button>
  );
}
