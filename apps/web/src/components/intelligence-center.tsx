"use client";

import {
  convertNewsItemToTask,
  createManualNewsItem,
  createNewsSource,
  deleteNewsSource,
  generateIntelligenceBrief,
  getIntelligenceOverview,
  getTodayIntelligenceBrief,
  listNewsItems,
  listNewsSources,
  newsItemAction,
  refreshAllNewsSources,
  refreshNewsSource,
  updateIntelligencePreferences,
  updateNewsSource,
  type DailyBrief,
  type IntelligenceOverview,
  type IntelligencePreferences,
  type NewsCategory,
  type NewsItem,
  type NewsSource,
} from "@/lib/api";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { SpecialistHeader } from "@/components/agents/SpecialistHeader";
import { ResearchWorkflowPlanner } from "@/components/research-workflow-planner";
import { formatDateTime, providerDisplayNames } from "@/lib/utils";

type IntelligenceTab = "brief" | "feed" | "sources";

const categories: Array<{
  value: NewsCategory;
  label: string;
  short: string;
}> = [
  { value: "ai", label: "AI / Agent / 大模型", short: "AI" },
  { value: "career", label: "AI 岗位与职业", short: "职业" },
  { value: "technology", label: "技术动态", short: "技术" },
  { value: "english", label: "英语学习", short: "英语" },
  { value: "investment", label: "投资与宏观", short: "投资" },
  { value: "international", label: "国际动态", short: "国际" },
];

const emptyPreferences: IntelligencePreferences = {
  ai: 5,
  career: 5,
  technology: 4,
  english: 3,
  investment: 3,
  international: 3,
};

const emptyOverview: IntelligenceOverview = {
  today_items: 0,
  unread_items: 0,
  saved_items: 0,
  active_sources: 0,
  source_errors: 0,
  today_brief_ready: false,
  today_brief_count: 0,
  last_refresh_at: null,
  interests: emptyPreferences,
};

function categoryLabel(category: NewsCategory) {
  return categories.find((item) => item.value === category)?.short ?? category;
}

function providerLabel(item: NewsItem) {
  if (item.provider_used === "mimo") return `${providerDisplayNames.mimo} 整理`;
  if (item.provider_used === "ollama") {
    return item.fallback_reason
      ? `${providerDisplayNames.ollama} · 自动回退`
      : providerDisplayNames.ollama;
  }
  return "规则分析";
}

function sourceStatus(source: NewsSource) {
  if (!source.enabled) return { label: "已停用", tone: "muted" };
  if (source.last_error) return { label: "需检查", tone: "error" };
  if (source.last_success_at) return { label: "正常", tone: "ready" };
  return { label: "待首次刷新", tone: "wait" };
}

function NewsCard({
  item,
  busy,
  onAction,
  onTask,
}: {
  item: NewsItem;
  busy: string | null;
  onAction: (item: NewsItem, action: "read" | "save" | "ignore") => void;
  onTask: (item: NewsItem) => void;
}) {
  const linkedTask = item.links.find((link) => link.link_type === "task");
  return (
    <article
      className={`intel-card intel-category-${item.category} ${
        item.status === "ignored" ? "intel-card-ignored" : ""
      }`}
    >
      <header className="intel-card-header">
        <div className="intel-card-badges">
          <span className="intel-category-badge">
            {categoryLabel(item.category)}
          </span>
          <span className="intel-source-badge">
            可信度 {item.trust_score}/5
          </span>
          {item.investment_related && (
            <span className="intel-investment-badge">非交易建议</span>
          )}
          {item.status === "saved" && (
            <span className="intel-saved-badge">已收藏</span>
          )}
          {linkedTask && (
            <span className="intel-task-badge">已转任务</span>
          )}
        </div>
        <strong>{Math.round(item.relevance_score)} 相关度</strong>
      </header>

      <h3>{item.title}</h3>
      <div className="intel-card-meta">
        <span>{item.source_name}</span>
        <time>{formatDateTime(item.published_at || item.fetched_at)}</time>
        <span>{providerLabel(item)}</span>
      </div>

      <section className="intel-fact-block">
        <div>
          <span>来源事实</span>
          <small>仅显示来源提供的内容</small>
        </div>
        <p>{item.source_excerpt}</p>
      </section>

      <div className="intel-interpretation-grid">
        <section>
          <span>整理摘要</span>
          <p>{item.summary}</p>
        </section>
        <section>
          <span>分析 · 非来源事实</span>
          <p>{item.analysis_text}</p>
        </section>
      </div>

      <section className="intel-action-block">
        <span>建议行动</span>
        <p>{item.suggestion_text}</p>
        {item.investment_related && (
          <small>
            投资信息只用于研究和记录；Jarvis 不会据此自动买卖、调仓或预测价格。
          </small>
        )}
      </section>

      <footer>
        <a
          href={item.canonical_url}
          onClick={() => onAction(item, "read")}
          rel="noreferrer"
          target="_blank"
        >
          查看原始来源 ↗
        </a>
        <div>
          <button
            disabled={busy === item.id}
            onClick={() => onAction(item, "save")}
            type="button"
          >
            {item.status === "saved" ? "已收藏" : "收藏"}
          </button>
          <button
            disabled={busy === item.id || Boolean(linkedTask)}
            onClick={() => onTask(item)}
            type="button"
          >
            {linkedTask ? "已转任务" : "转为任务"}
          </button>
          <button
            className="intel-ignore-button"
            disabled={busy === item.id}
            onClick={() => onAction(item, "ignore")}
            type="button"
          >
            忽略
          </button>
        </div>
      </footer>
    </article>
  );
}

export function IntelligenceCenter() {
  const [tab, setTab] = useState<IntelligenceTab>("brief");
  const [overview, setOverview] = useState(emptyOverview);
  const [brief, setBrief] = useState<DailyBrief | null>(null);
  const [items, setItems] = useState<NewsItem[]>([]);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [interests, setInterests] =
    useState<IntelligencePreferences>(emptyPreferences);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [processingMode, setProcessingMode] =
    useState<"standard" | "local">("standard");

  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<NewsCategory | "all">("all");
  const [itemStatus, setItemStatus] =
    useState<NewsItem["status"] | "all">("all");
  const [showSourceForm, setShowSourceForm] = useState(false);
  const [showManualForm, setShowManualForm] = useState(false);

  const [sourceName, setSourceName] = useState("");
  const [sourceFeedUrl, setSourceFeedUrl] = useState("");
  const [sourceSiteUrl, setSourceSiteUrl] = useState("");
  const [sourceCategory, setSourceCategory] =
    useState<NewsCategory>("technology");
  const [sourceTrust, setSourceTrust] = useState(4);

  const [manualTitle, setManualTitle] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const [manualSource, setManualSource] = useState("");
  const [manualExcerpt, setManualExcerpt] = useState("");
  const [manualCategory, setManualCategory] =
    useState<NewsCategory>("technology");

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const [nextOverview, nextBrief, nextItems, nextSources] =
        await Promise.all([
          getIntelligenceOverview(signal),
          getTodayIntelligenceBrief(signal),
          listNewsItems({ signal }),
          listNewsSources(signal),
        ]);
      setOverview(nextOverview);
      setBrief(nextBrief);
      setItems(nextItems);
      setSources(nextSources);
      setInterests(nextOverview.interests);
      setError(null);
    } catch (loadError) {
      if (
        loadError instanceof DOMException &&
        loadError.name === "AbortError"
      ) {
        return;
      }
      setError(
        loadError instanceof Error ? loadError.message : "读取情报数据失败",
      );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => void refresh(controller.signal), 0);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [refresh]);

  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      if (category !== "all" && item.category !== category) return false;
      if (itemStatus !== "all" && item.status !== itemStatus) return false;
      if (
        needle &&
        !`${item.title} ${item.source_name} ${item.source_excerpt}`
          .toLowerCase()
          .includes(needle)
      ) {
        return false;
      }
      return true;
    });
  }, [category, itemStatus, items, query]);

  const replaceItem = useCallback((nextItem: NewsItem) => {
    setItems((current) =>
      current.map((item) => (item.id === nextItem.id ? nextItem : item)),
    );
    setBrief((current) =>
      current
        ? {
            ...current,
            items: current.items.map((item) =>
              item.id === nextItem.id ? nextItem : item,
            ),
          }
        : current,
    );
  }, []);

  const run = useCallback(
    async (key: string, action: () => Promise<void>) => {
      setBusy(key);
      setError(null);
      setNotice(null);
      try {
        await action();
      } catch (actionError) {
        setError(
          actionError instanceof Error ? actionError.message : "操作失败",
        );
      } finally {
        setBusy(null);
      }
    },
    [],
  );

  const handleGenerate = () =>
    run("generate", async () => {
      setNotice("正在刷新公开来源、去重并整理今日情报，这可能需要几十秒…");
      const next = await generateIntelligenceBrief({
        processing_mode: processingMode,
        refresh_sources: true,
        notify: true,
        use_ai: true,
      });
      setBrief(next);
      setTab("brief");
      await refresh();
      setNotice(
        next.item_count
          ? `今日情报已生成：${next.item_count} 条，并已发送桌面与语音提醒。`
          : "来源已刷新，但暂时没有足够的新内容。",
      );
    });

  const handleAction = (
    item: NewsItem,
    action: "read" | "save" | "ignore",
  ) => {
    void run(item.id, async () => {
      const result = await newsItemAction(item.id, action);
      replaceItem(result.item);
      setInterests(result.interest_weights);
      setOverview((current) => ({
        ...current,
        interests: result.interest_weights,
      }));
      if (action === "ignore") {
        setNotice("已忽略；Jarvis 会轻微降低这一主题的隐式偏好。");
      } else if (action === "save") {
        setNotice("已收藏；Jarvis 会提高这一主题的隐式偏好。");
      }
    });
  };

  const handleTask = (item: NewsItem) => {
    void run(item.id, async () => {
      const result = await convertNewsItemToTask(item.id, {
        priority: item.relevance_score >= 80 ? 4 : 3,
        estimated_minutes: 30,
      });
      replaceItem(result.item);
      setNotice(`已创建任务“${result.task_title}”，可在成长中心继续安排。`);
    });
  };

  const handleRefreshAll = () =>
    run("refresh-all", async () => {
      const result = await refreshAllNewsSources();
      await refresh();
      setNotice(
        `已检查 ${result.source_count} 个来源，新增 ${result.created_items} 条，合并 ${result.duplicate_items} 条重复事件。`,
      );
    });

  const handleSourceSubmit = (event: FormEvent) => {
    event.preventDefault();
    void run("source-form", async () => {
      await createNewsSource({
        name: sourceName,
        feed_url: sourceFeedUrl,
        site_url: sourceSiteUrl || undefined,
        default_category: sourceCategory,
        language: "en",
        trust_score: sourceTrust,
        refresh_interval_minutes: 360,
      });
      setSourceName("");
      setSourceFeedUrl("");
      setSourceSiteUrl("");
      setShowSourceForm(false);
      await refresh();
      setNotice("RSS 来源已添加；首次刷新后会显示来源状态。");
    });
  };

  const handleManualSubmit = (event: FormEvent) => {
    event.preventDefault();
    void run("manual-form", async () => {
      await createManualNewsItem({
        title: manualTitle,
        url: manualUrl,
        source_name: manualSource || "手动提交",
        source_excerpt: manualExcerpt,
        category: manualCategory,
        language: "zh-CN",
      });
      setManualTitle("");
      setManualUrl("");
      setManualSource("");
      setManualExcerpt("");
      setShowManualForm(false);
      await refresh();
      setTab("feed");
      setNotice("链接和来源摘要已保存；Jarvis 不会擅自抓取普通网页正文。");
    });
  };

  const handleSaveInterests = () =>
    run("interests", async () => {
      const saved = await updateIntelligencePreferences(interests);
      setInterests(saved);
      setOverview((current) => ({ ...current, interests: saved }));
      setNotice("兴趣权重已保存，下一次筛选会立即使用。");
    });

  if (loading) {
    return (
      <main className="intel-page">
        <div className="intel-loading">
          <span />
          正在建立你的情报视图…
        </div>
      </main>
    );
  }

  return (
    <main className="intel-page specialist-page specialist-intelligence">
      <SpecialistHeader
        accent="情报中心"
        activeAgent="research"
        description="公开来源 → 去重筛选 → 可追溯摘要 → 可执行但不越界的下一步"
        eyebrow="INFORMATION INTELLIGENCE"
        status={overview.source_errors ? "SOURCE ATTENTION" : "RADAR ONLINE"}
        title=""
        actions={
          <div className="intel-header-actions">
            <label>
              <span>整理模式</span>
              <select
                onChange={(event) =>
                  setProcessingMode(event.target.value as "standard" | "local")
                }
                value={processingMode}
              >
                <option value="standard">MiMo 优先</option>
                <option value="local">仅本地 Qwen</option>
              </select>
            </label>
            <button
              className="primary-button"
              disabled={busy !== null}
              onClick={handleGenerate}
              type="button"
            >
              {busy === "generate" ? "正在生成…" : "生成今日情报"}
            </button>
          </div>
        }
      />

      {(error || notice) && (
        <div className={`intel-banner ${error ? "intel-banner-error" : ""}`}>
          <span>{error ? "!" : "✓"}</span>
          <p>{error || notice}</p>
          <button
            onClick={() => {
              setError(null);
              setNotice(null);
            }}
            type="button"
          >
            ×
          </button>
        </div>
      )}

      <div className="specialist-section-label">
        <div>
          <span>DAILY INTELLIGENCE</span>
          <strong>今日情报雷达</strong>
        </div>
        <p>只保留与你的目标、投资和国际动态真正相关的信号</p>
      </div>

      <section className="intel-metrics specialist-metrics">
        <article>
          <span>今日入库</span>
          <strong>{overview.today_items}</strong>
          <small>已排除重复事件</small>
        </article>
        <article>
          <span>未读信息</span>
          <strong>{overview.unread_items}</strong>
          <small>等待你判断价值</small>
        </article>
        <article>
          <span>已收藏 / 转任务</span>
          <strong>{overview.saved_items}</strong>
          <small>真实反馈会调整偏好</small>
        </article>
        <article>
          <span>启用来源</span>
          <strong>{overview.active_sources}</strong>
          <small>
            {overview.source_errors
              ? `${overview.source_errors} 个来源需检查`
              : "公开来源状态正常"}
          </small>
        </article>
      </section>

      <div className="specialist-section-label research-section-label">
        <div>
          <span>MULTI-SOURCE RESEARCH</span>
          <strong>深度研究工作流</strong>
        </div>
        <p>计划 → 来源核验 → 模型授权 → 草稿审核 → 独立归档确认</p>
      </div>

      <ResearchWorkflowPlanner
        candidateItems={items}
        onReloadIntelligence={() => refresh()}
      />

      <nav className="intel-tabs specialist-tabs" aria-label="情报中心视图">
        <button
          className={tab === "brief" ? "intel-tab-active" : ""}
          onClick={() => setTab("brief")}
          type="button"
        >
          今日情报
          <span>{brief?.item_count ?? 0}</span>
        </button>
        <button
          className={tab === "feed" ? "intel-tab-active" : ""}
          onClick={() => setTab("feed")}
          type="button"
        >
          信息流
          <span>{items.length}</span>
        </button>
        <button
          className={tab === "sources" ? "intel-tab-active" : ""}
          onClick={() => setTab("sources")}
          type="button"
        >
          来源与偏好
          <span>{sources.length}</span>
        </button>
      </nav>

      {tab === "brief" && (
        <section className="intel-brief-view">
          {brief ? (
            <>
              <header className="intel-brief-header">
                <div>
                  <div className="eyebrow">DAILY BRIEF · {brief.brief_date}</div>
                  <h2>{brief.title}</h2>
                  <p>{brief.overview}</p>
                </div>
                <div className="intel-brief-audit">
                  <span>{brief.item_count} 条高价值信息</span>
                  <small>{brief.generation_note}</small>
                  <small>
                    {brief.reminder_scheduled
                      ? "桌面与语音提醒已安排"
                      : "本次未安排提醒"}
                  </small>
                </div>
              </header>
              {brief.item_count < 3 && (
                <div className="intel-quality-note">
                  当前可用信息少于 3 条。Jarvis 不会为了凑数而虚构内容；添加链接或刷新来源后可重新生成。
                </div>
              )}
              <div className="intel-card-list">
                {brief.items.map((item) => (
                  <NewsCard
                    busy={busy}
                    item={item}
                    key={item.id}
                    onAction={handleAction}
                    onTask={handleTask}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="intel-empty">
              <div>◎</div>
              <h2>今天的情报还没有生成</h2>
              <p>
                Jarvis 会先刷新白名单 RSS，合并重复事件，再从事实、分析和建议三个层级整理 3–5 条内容。
              </p>
              <button
                className="primary-button"
                disabled={busy !== null}
                onClick={handleGenerate}
                type="button"
              >
                生成今日情报
              </button>
            </div>
          )}
        </section>
      )}

      {tab === "feed" && (
        <section className="intel-feed-view">
          <header className="intel-toolbar">
            <div>
              <div className="eyebrow">SOURCE-CONTROLLED FEED</div>
              <h2>全部信息</h2>
              <p>搜索、筛选与反馈都只作用于你自己的本地数据。</p>
            </div>
            <div className="intel-toolbar-actions">
              <input
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索标题、来源或摘要"
                value={query}
              />
              <select
                onChange={(event) =>
                  setCategory(event.target.value as NewsCategory | "all")
                }
                value={category}
              >
                <option value="all">全部主题</option>
                {categories.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.short}
                  </option>
                ))}
              </select>
              <select
                onChange={(event) =>
                  setItemStatus(
                    event.target.value as NewsItem["status"] | "all",
                  )
                }
                value={itemStatus}
              >
                <option value="all">全部状态</option>
                <option value="new">未读</option>
                <option value="read">已读</option>
                <option value="saved">已收藏</option>
                <option value="task_created">已转任务</option>
              </select>
              <button
                className="ghost-button"
                onClick={() => setShowManualForm((value) => !value)}
                type="button"
              >
                手动添加链接
              </button>
            </div>
          </header>

          {showManualForm && (
            <form className="intel-form intel-manual-form" onSubmit={handleManualSubmit}>
              <label>
                <span>标题</span>
                <input
                  onChange={(event) => setManualTitle(event.target.value)}
                  required
                  value={manualTitle}
                />
              </label>
              <label>
                <span>原始链接</span>
                <input
                  onChange={(event) => setManualUrl(event.target.value)}
                  placeholder="https://…"
                  required
                  type="url"
                  value={manualUrl}
                />
              </label>
              <label>
                <span>来源名称</span>
                <input
                  onChange={(event) => setManualSource(event.target.value)}
                  placeholder="例如：公司公告"
                  value={manualSource}
                />
              </label>
              <label>
                <span>主题</span>
                <select
                  onChange={(event) =>
                    setManualCategory(event.target.value as NewsCategory)
                  }
                  value={manualCategory}
                >
                  {categories.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="intel-form-wide">
                <span>来源摘要 / 你确认过的事实</span>
                <textarea
                  onChange={(event) => setManualExcerpt(event.target.value)}
                  placeholder="请粘贴来源明确提供的内容；Jarvis 不会擅自抓取普通网页正文。"
                  required
                  value={manualExcerpt}
                />
              </label>
              <footer className="intel-form-wide">
                <button
                  className="ghost-button"
                  onClick={() => setShowManualForm(false)}
                  type="button"
                >
                  取消
                </button>
                <button
                  className="primary-button"
                  disabled={busy === "manual-form"}
                  type="submit"
                >
                  保存链接
                </button>
              </footer>
            </form>
          )}

          <div className="intel-card-list">
            {filteredItems.map((item) => (
              <NewsCard
                busy={busy}
                item={item}
                key={item.id}
                onAction={handleAction}
                onTask={handleTask}
              />
            ))}
            {!filteredItems.length && (
              <div className="intel-list-empty">
                没有符合当前筛选条件的信息。
              </div>
            )}
          </div>
        </section>
      )}

      {tab === "sources" && (
        <section className="intel-settings-grid">
          <div className="intel-source-panel">
            <header className="intel-panel-header">
              <div>
                <div className="eyebrow">WHITELIST SOURCES</div>
                <h2>RSS 来源管理</h2>
                <p>
                  首批只接入公开 RSS 和手动链接；普通网页自动抓取将在安全隔离完成后开放。
                </p>
              </div>
              <div>
                <button
                  className="ghost-button"
                  disabled={busy !== null}
                  onClick={handleRefreshAll}
                  type="button"
                >
                  {busy === "refresh-all" ? "正在刷新…" : "刷新全部"}
                </button>
                <button
                  className="primary-button"
                  onClick={() => setShowSourceForm((value) => !value)}
                  type="button"
                >
                  添加 RSS
                </button>
              </div>
            </header>

            {showSourceForm && (
              <form className="intel-form" onSubmit={handleSourceSubmit}>
                <label>
                  <span>来源名称</span>
                  <input
                    onChange={(event) => setSourceName(event.target.value)}
                    required
                    value={sourceName}
                  />
                </label>
                <label>
                  <span>RSS / Atom 地址</span>
                  <input
                    onChange={(event) => setSourceFeedUrl(event.target.value)}
                    placeholder="https://…/feed.xml"
                    required
                    type="url"
                    value={sourceFeedUrl}
                  />
                </label>
                <label>
                  <span>网站主页（可选）</span>
                  <input
                    onChange={(event) => setSourceSiteUrl(event.target.value)}
                    placeholder="https://…"
                    type="url"
                    value={sourceSiteUrl}
                  />
                </label>
                <label>
                  <span>默认主题</span>
                  <select
                    onChange={(event) =>
                      setSourceCategory(event.target.value as NewsCategory)
                    }
                    value={sourceCategory}
                  >
                    {categories.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>可信度：{sourceTrust}/5</span>
                  <input
                    max="5"
                    min="1"
                    onChange={(event) =>
                      setSourceTrust(Number(event.target.value))
                    }
                    type="range"
                    value={sourceTrust}
                  />
                </label>
                <footer>
                  <button
                    className="ghost-button"
                    onClick={() => setShowSourceForm(false)}
                    type="button"
                  >
                    取消
                  </button>
                  <button
                    className="primary-button"
                    disabled={busy === "source-form"}
                    type="submit"
                  >
                    保存来源
                  </button>
                </footer>
              </form>
            )}

            <div className="intel-source-list">
              {sources.map((source) => {
                const state = sourceStatus(source);
                return (
                  <article key={source.id}>
                    <div
                      className={`intel-source-state source-state-${state.tone}`}
                    >
                      <i />
                      {state.label}
                    </div>
                    <div className="intel-source-main">
                      <header>
                        <h3>{source.name}</h3>
                        {source.is_default && <span>官方白名单</span>}
                      </header>
                      <a href={source.feed_url} rel="noreferrer" target="_blank">
                        {source.feed_url}
                      </a>
                      <div>
                        <span>{categoryLabel(source.default_category)}</span>
                        <span>可信度 {source.trust_score}/5</span>
                        <span>上次获取 {source.last_item_count} 条</span>
                        <span>{formatDateTime(source.last_success_at)}</span>
                      </div>
                      {source.last_error && <p>{source.last_error}</p>}
                    </div>
                    <div className="intel-source-actions">
                      <button
                        disabled={busy !== null || !source.enabled}
                        onClick={() =>
                          void run(source.id, async () => {
                            const result = await refreshNewsSource(source.id);
                            await refresh();
                            setNotice(
                              result.status === "failed"
                                ? `${source.name} 刷新失败：${result.error}`
                                : `${source.name} 新增 ${result.created_items} 条，合并 ${result.duplicate_items} 条重复。`,
                            );
                          })
                        }
                        type="button"
                      >
                        刷新
                      </button>
                      <button
                        disabled={busy !== null}
                        onClick={() =>
                          void run(source.id, async () => {
                            await updateNewsSource(source.id, {
                              enabled: !source.enabled,
                            });
                            await refresh();
                          })
                        }
                        type="button"
                      >
                        {source.enabled ? "停用" : "启用"}
                      </button>
                      {!source.is_default && (
                        <button
                          className="intel-source-delete"
                          disabled={busy !== null}
                          onClick={() => {
                            if (!window.confirm(`删除来源“${source.name}”？`)) {
                              return;
                            }
                            void run(source.id, async () => {
                              await deleteNewsSource(source.id);
                              await refresh();
                            });
                          }}
                          type="button"
                        >
                          删除
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>

          <aside className="intel-interest-panel">
            <div className="eyebrow">PERSONAL RELEVANCE</div>
            <h2>兴趣权重</h2>
            <p>
              1 表示低优先，5 表示高优先。收藏、忽略和转任务也会小幅调整这些权重。
            </p>
            <div className="intel-interest-list">
              {categories.map((item) => (
                <label key={item.value}>
                  <div>
                    <span>{item.label}</span>
                    <strong>{interests[item.value].toFixed(1)}</strong>
                  </div>
                  <input
                    max="5"
                    min="1"
                    onChange={(event) =>
                      setInterests((current) => ({
                        ...current,
                        [item.value]: Number(event.target.value),
                      }))
                    }
                    step="0.5"
                    type="range"
                    value={interests[item.value]}
                  />
                </label>
              ))}
            </div>
            <button
              className="primary-button"
              disabled={busy === "interests"}
              onClick={handleSaveInterests}
              type="button"
            >
              保存权重
            </button>
            <div className="intel-boundary-note">
              <strong>投资边界</strong>
              <p>
                投资与国际动态可以进入情报，并由监控中心关联持仓与投资理由；系统不会自动交易。
              </p>
            </div>
            <Link className="intel-growth-link" href="/growth">
              查看已转化的成长任务 →
            </Link>
          </aside>
        </section>
      )}
    </main>
  );
}
