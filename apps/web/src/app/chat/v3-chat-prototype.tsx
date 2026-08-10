// Three variants of /chat, switchable via ?variant=, on the existing route.
import {
  Archive,
  ArrowUp,
  Brain,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock3,
  Command,
  FileText,
  History,
  Layers3,
  MessageSquareText,
  Mic,
  MoreHorizontal,
  Paperclip,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";

import styles from "@/app/v3-prototype.module.css";
import {
  PrototypeSwitcher,
  type PrototypeVariant,
} from "@/components/prototypes/prototype-switcher";

const variants: PrototypeVariant[] = [
  { key: "A", name: "安静对话" },
  { key: "B", name: "任务驾驶舱" },
  { key: "C", name: "时间流" },
];

export function ChatV3Prototype({ variant }: { variant: "A" | "B" | "C" }) {
  return (
    <>
      {variant === "A" ? <QuietConversation /> : null}
      {variant === "B" ? <MissionControl /> : null}
      {variant === "C" ? <ConversationTimeline /> : null}
      <PrototypeSwitcher current={variant} variants={variants} />
    </>
  );
}

function QuietConversation() {
  return (
    <main className={`dashboard ${styles.stage} ${styles.chatQuiet}`}>
      <header className={styles.quietHeader}>
        <div>
          <button className={styles.breadcrumbButton} type="button">
            <History aria-hidden="true" /> 产品发布复盘
          </button>
          <h1>把这周真正重要的事，收束成下一步。</h1>
        </div>
        <div className={styles.headerActions}>
          <span className={styles.localStatus}><ShieldCheck /> 本地优先</span>
          <button className={styles.iconButton} aria-label="更多操作" type="button">
            <MoreHorizontal />
          </button>
        </div>
      </header>

      <div className={styles.quietLayout}>
        <section className={styles.conversationCanvas}>
          <div className={styles.dayDivider}><span>今天 · 10:24</span></div>
          <article className={styles.userMessage}>
            <p>我不想再做一份很长的周报。请结合这周的任务和对话，告诉我：真正拖慢发布的是什么，以及下周一最先做什么。</p>
          </article>
          <article className={styles.assistantTurn}>
            <div className={styles.assistantMark}><Sparkles aria-hidden="true" /></div>
            <div className={styles.assistantBody}>
              <p>真正拖慢发布的不是开发量，而是<strong>验收标准直到最后两天才被统一</strong>。三个证据都指向同一个问题：</p>
              <ol className={styles.reasonList}>
                <li><span>01</span><div><strong>审批在实现后发生</strong><p>两次返工都来自验收口径变化，而不是代码缺陷。</p></div></li>
                <li><span>02</span><div><strong>负责人分散</strong><p>设计、数据和发布检查没有一个共同的“完成定义”。</p></div></li>
                <li><span>03</span><div><strong>关键问题没有提前暴露</strong><p>风险在聊天里出现过，但没有进入可追踪的决策队列。</p></div></li>
              </ol>
              <div className={styles.answerConclusion}>
                <Target aria-hidden="true" />
                <div><small>下周一第一步</small><strong>09:30 前完成 20 分钟发布门禁会，只确认 5 条验收条件。</strong></div>
                <button type="button">转为行动 <ChevronRight /></button>
              </div>
              <div className={styles.sourceLine}>
                <span><FileText /> 3 个任务</span><span><MessageSquareText /> 2 轮对话</span><span><Clock3 /> 最近 7 天</span>
              </div>
            </div>
          </article>
          <Composer mode="专注模式" />
        </section>

        <aside className={styles.contextRail}>
          <div className={styles.railHeading}><span>本轮上下文</span><button type="button">管理</button></div>
          <section className={styles.railSection}>
            <h2><Brain /> Jarvis 正在参考</h2>
            <button className={styles.contextItem} type="button"><span className={styles.contextIcon}><Layers3 /></span><div><strong>发布准备</strong><small>4 个任务 · 2 个逾期</small></div><ChevronRight /></button>
            <button className={styles.contextItem} type="button"><span className={styles.contextIcon}><Archive /></span><div><strong>验收标准</strong><small>上次更新于周四</small></div><ChevronRight /></button>
          </section>
          <section className={styles.railSection}>
            <h2><CircleDot /> 需要留意</h2>
            <div className={styles.signalRow}><span className={styles.signalDot} /><p><strong>2 项决定未归档</strong><small>可能影响下周发布</small></p></div>
            <div className={styles.signalRow}><span className={styles.signalDotAmber} /><p><strong>审批平均等待 18h</strong><small>比上周多 6 小时</small></p></div>
          </section>
          <div className={styles.railPrivacy}><ShieldCheck /><p><strong>私人上下文只在本机使用</strong><small>本轮未扩大云端数据范围</small></p></div>
        </aside>
      </div>
    </main>
  );
}

function MissionControl() {
  return (
    <main className={`dashboard ${styles.stage} ${styles.chatControl}`}>
      <header className={styles.controlHeader}>
        <div><h1>任务驾驶舱</h1><p>对话负责意图，状态与决定始终可见。</p></div>
        <div className={styles.controlHeaderActions}>
          <button type="button"><Search /> 搜索</button>
          <button className={styles.primaryButton} type="button"><Plus /> 新对话</button>
        </div>
      </header>

      <div className={styles.controlGrid}>
        <aside className={styles.sessionColumn}>
          <label className={styles.searchField}><Search /><input aria-label="搜索会话" placeholder="搜索会话" /></label>
          <nav className={styles.sessionList}>
            <small>今天</small>
            <button className={styles.activeSession} type="button"><MessageSquareText /><span><strong>发布复盘与下周计划</strong><small>刚刚 · 标准模式</small></span></button>
            <button type="button"><MessageSquareText /><span><strong>英语面试复习</strong><small>09:12 · English Coach</small></span></button>
            <small>昨天</small>
            <button type="button"><MessageSquareText /><span><strong>记忆网络验收</strong><small>昨天 · 本地模式</small></span></button>
            <button type="button"><MessageSquareText /><span><strong>行业情报筛选</strong><small>昨天 · Research</small></span></button>
          </nav>
          <div className={styles.sessionFooter}><Archive /><span><strong>42 个会话</strong><small>可搜索、可归档</small></span></div>
        </aside>

        <section className={styles.controlConversation}>
          <div className={styles.controlConversationHead}>
            <div><span className={styles.agentAvatar}>J</span><p><strong>Jarvis Core</strong><small>标准模式 · 已连接记忆网络</small></p></div>
            <button type="button"><MoreHorizontal /></button>
          </div>
          <div className={styles.controlTranscript}>
            <article className={styles.userBubble}>请把这周的发布问题整理成一个我周一可以直接执行的计划。</article>
            <article className={styles.jarvisBubble}>
              <span className={styles.agentAvatar}>J</span>
              <div>
                <p>我把它收束成一个 90 分钟启动流程。重点不是“继续开发”，而是先冻结验收边界。</p>
                <div className={styles.actionPlan}>
                  <div><CheckCircle2 /><span><strong>09:30 · 发布门禁会</strong><small>确认 5 条验收条件与唯一负责人</small></span><span>20 min</span></div>
                  <div><CircleDot /><span><strong>10:00 · 风险清单归档</strong><small>把两项未决问题转入审批队列</small></span><span>25 min</span></div>
                  <div><CircleDot /><span><strong>10:30 · 最小发布演练</strong><small>只验证阻断项，不扩展范围</small></span><span>45 min</span></div>
                </div>
                <div className={styles.jarvisActions}><button type="button">生成任务草稿</button><button type="button">查看依据</button></div>
              </div>
            </article>
          </div>
          <Composer mode="标准 · Jarvis Core" compact />
        </section>

        <aside className={styles.missionColumn}>
          <div className={styles.missionHeading}><h2>本轮任务</h2><span>进行中</span></div>
          <div className={styles.missionProgress}><div><span style={{ width: "64%" }} /></div><small>2 / 3 个步骤已确认</small></div>
          <section className={styles.missionBlock}>
            <h3>运行状态</h3>
            <div className={styles.runtimeRow}><span className={styles.liveDot} /><p><strong>Direct Runtime</strong><small>未触发编排器</small></p></div>
            <div className={styles.runtimeRow}><ShieldCheck /><p><strong>权限未扩大</strong><small>无待执行工具</small></p></div>
          </section>
          <section className={styles.missionBlock}>
            <h3>待你决定</h3>
            <button className={styles.decisionItem} type="button"><span>R1</span><p><strong>3 条任务草稿</strong><small>审阅后才会继续</small></p><ChevronRight /></button>
          </section>
          <section className={styles.missionBlock}>
            <h3>引用</h3>
            <div className={styles.referenceStack}><span>发布准备 · 4 个任务</span><span>周四复盘 · 8 条消息</span><span>验收标准 · 1 份文档</span></div>
          </section>
        </aside>
      </div>
    </main>
  );
}

function ConversationTimeline() {
  return (
    <main className={`dashboard ${styles.stage} ${styles.chatTimeline}`}>
      <header className={styles.timelineHeader}>
        <div><h1>今天</h1><p>2026 年 8 月 10 日，星期一</p></div>
        <div className={styles.timelineTools}><button type="button"><Search /> 搜索时间流</button><button type="button"><Command /> 命令面板</button></div>
      </header>

      <div className={styles.timelineLayout}>
        <section className={styles.timelineFeed}>
          <div className={styles.timeRail}><span>09:12</span><i /></div>
          <article className={styles.timelineEvent}>
            <div className={styles.eventMeta}><span><MessageSquareText /> 对话</span><small>English Coach · 18 分钟</small></div>
            <h2>英语面试复习：行为问题</h2>
            <p>完成 6 个 STAR 回答练习，Jarvis 记录了 2 个需要复习的语法问题。</p>
            <div className={styles.eventTags}><span>英语</span><span>复习已安排</span></div>
          </article>

          <div className={styles.timeRail}><span>10:24</span><i className={styles.activeTimeDot} /></div>
          <article className={`${styles.timelineEvent} ${styles.activeEvent}`}>
            <div className={styles.eventMeta}><span><Sparkles /> 当前对话</span><small>Jarvis Core · 进行中</small></div>
            <div className={styles.timelineDialogue}>
              <p className={styles.timelineUser}>这周真正拖慢发布的是什么？</p>
              <div className={styles.timelineAnswer}>
                <p>验收标准出现得太晚。返工主要来自范围变化，不是实现质量。</p>
                <blockquote>下周一先冻结 5 条验收条件，再开始任何新开发。</blockquote>
                <button type="button">展开完整分析 <ChevronRight /></button>
              </div>
            </div>
            <Composer mode="继续这段对话" compact />
          </article>

          <div className={styles.timeRail}><span>11:00</span><i className={styles.futureDot} /></div>
          <article className={`${styles.timelineEvent} ${styles.futureEvent}`}>
            <div className={styles.eventMeta}><span><Clock3 /> 接下来</span><small>建议 · 尚未创建任务</small></div>
            <h2>把发布门禁会加入行动计划？</h2>
            <p>Jarvis 只提出建议。确认后会先生成草稿，不会直接修改日历。</p>
            <div className={styles.inlineActions}><button type="button">稍后再说</button><button className={styles.primaryButton} type="button">生成草稿</button></div>
          </article>
        </section>

        <aside className={styles.daySummary}>
          <h2>今天的脉络</h2>
          <div className={styles.summaryStatement}><strong>你正在从“完成更多”转向“先消除不确定性”。</strong><p>这个变化同时出现在发布复盘和英语练习中。</p></div>
          <dl className={styles.dayFacts}><div><dt>专注时间</dt><dd>1h 26m</dd></div><div><dt>已完成</dt><dd>3 项</dd></div><div><dt>待决定</dt><dd>1 项</dd></div></dl>
          <section><h3>长期线索</h3><button type="button"><Brain /><span><strong>提前定义完成标准</strong><small>过去 30 天出现 4 次</small></span><ChevronRight /></button></section>
          <section><h3>数据范围</h3><p className={styles.privacyCopy}><ShieldCheck /> 本页摘要只使用你已启用的本地记录。</p></section>
        </aside>
      </div>
    </main>
  );
}

function Composer({ mode, compact = false }: { mode: string; compact?: boolean }) {
  return (
    <div className={`${styles.prototypeComposer} ${compact ? styles.compactComposer : ""}`}>
      <div className={styles.composerInput}>
        <button aria-label="添加附件" type="button"><Paperclip /></button>
        <textarea aria-label="发送给 Jarvis" placeholder="继续告诉 Jarvis…" rows={compact ? 1 : 2} />
        <button aria-label="语音输入" type="button"><Mic /></button>
        <button className={styles.sendButton} aria-label="发送" type="button"><ArrowUp /></button>
      </div>
      <div className={styles.composerMeta}><span>{mode}</span><span>Enter 发送 · 音频仅在点击后采集</span></div>
    </div>
  );
}
