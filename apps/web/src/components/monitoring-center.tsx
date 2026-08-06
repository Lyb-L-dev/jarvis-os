"use client";

import {
  Activity,
  BellRing,
  Check,
  ExternalLink,
  Globe2,
  Plus,
  Radar,
  RefreshCw,
  ShieldAlert,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CommandTelemetry } from "@/components/command-telemetry";
import {
  createMonitorRule,
  deleteMonitorRule,
  getMonitoringOverview,
  listInvestmentAssets,
  listInvestmentTheses,
  listMonitorEvents,
  listMonitorRules,
  scanMonitoring,
  updateMonitorEvent,
  updateMonitorRule,
  type ImpactDirection,
  type InvestmentAsset,
  type InvestmentThesis,
  type MonitorEvent,
  type MonitoringOverview,
  type MonitorRule,
  type MonitorType,
} from "@/lib/api";

type View = "events" | "rules";

const directionLabels: Record<ImpactDirection, string> = {
  positive: "可能正面",
  negative: "可能负面",
  mixed: "影响混合",
  uncertain: "仍不确定",
};

const monitorTypeLabels: Record<MonitorType, string> = {
  asset: "资产与持仓",
  macro: "宏观变量",
  international: "国际动态",
};

function parseTerms(value: string) {
  return [...new Set(value.split(/[，,\n]/).map((term) => term.trim()).filter(Boolean))];
}

function timeLabel(value?: string | null) {
  if (!value) return "尚未运行";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function MonitoringCenter() {
  const [view, setView] = useState<View>("events");
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [rules, setRules] = useState<MonitorRule[]>([]);
  const [events, setEvents] = useState<MonitorEvent[]>([]);
  const [assets, setAssets] = useState<InvestmentAsset[]>([]);
  const [theses, setTheses] = useState<InvestmentThesis[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [monitorType, setMonitorType] = useState<MonitorType>("international");
  const [assetId, setAssetId] = useState("");
  const [thesisId, setThesisId] = useState("");
  const [keywords, setKeywords] = useState("");
  const [regions, setRegions] = useState("");
  const [riskChannels, setRiskChannels] = useState("");
  const [minSeverity, setMinSeverity] = useState(3);
  const [notifyEnabled, setNotifyEnabled] = useState(true);

  const filteredTheses = useMemo(
    () => theses.filter((thesis) => thesis.asset.id === assetId && thesis.is_current),
    [assetId, theses],
  );

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const [nextOverview, nextRules, nextEvents, nextAssets, nextTheses] =
        await Promise.all([
          getMonitoringOverview(signal),
          listMonitorRules(signal),
          listMonitorEvents({ status: "new", signal }),
          listInvestmentAssets(signal),
          listInvestmentTheses(signal),
        ]);
      setOverview(nextOverview);
      setRules(nextRules);
      setEvents(nextEvents);
      setAssets(nextAssets);
      setTheses(nextTheses);
      setAssetId((current) =>
        nextAssets.some((asset) => asset.id === current)
          ? current
          : (nextAssets[0]?.id ?? ""),
      );
      setError(null);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setError(loadError instanceof Error ? loadError.message : "读取监控中心失败");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  function resetForm() {
    setName("");
    setKeywords("");
    setRegions("");
    setRiskChannels("");
    setThesisId("");
    setMinSeverity(3);
    setNotifyEnabled(true);
  }

  async function saveRule() {
    const terms = parseTerms(keywords);
    if (!name.trim() || busy) return;
    if (monitorType === "asset" && !assetId) {
      setError("请先在投资助手录入资产，再建立资产监控。");
      return;
    }
    if (monitorType !== "asset" && terms.length === 0) {
      setError("宏观或国际主题至少需要一个监控关键词。");
      return;
    }
    setBusy("create");
    setError(null);
    setNotice(null);
    try {
      await createMonitorRule({
        name: name.trim(),
        monitor_type: monitorType,
        asset_id: monitorType === "asset" ? assetId : undefined,
        thesis_id: monitorType === "asset" && thesisId ? thesisId : undefined,
        keywords: terms,
        regions: parseTerms(regions),
        risk_channels: parseTerms(riskChannels),
        min_severity: minSeverity,
        cooldown_minutes: 240,
        notify_enabled: notifyEnabled,
        cloud_allowed: false,
      });
      resetForm();
      setShowForm(false);
      setView("rules");
      setNotice("监控项已建立。系统将按来源刷新周期检查新事件。");
      await load();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "建立监控项失败");
    } finally {
      setBusy(null);
    }
  }

  async function runScan() {
    if (busy) return;
    setBusy("scan");
    setError(null);
    setNotice("正在核对最近 72 小时的已保存来源…");
    try {
      const result = await scanMonitoring();
      setNotice(
        result.events_created
          ? `发现 ${result.events_created} 个新事件，已安排 ${result.notifications_scheduled} 条提醒。`
          : `已检查 ${result.items_examined} 条情报，没有发现新的匹配事件。`,
      );
      await load();
      setView("events");
    } catch (scanError) {
      setError(scanError instanceof Error ? scanError.message : "扫描失败");
    } finally {
      setBusy(null);
    }
  }

  async function actOnEvent(event: MonitorEvent, action: "acknowledge" | "dismiss") {
    if (busy) return;
    setBusy(event.id);
    try {
      await updateMonitorEvent(event.id, action);
      setEvents((current) => current.filter((item) => item.id !== event.id));
      setNotice(action === "acknowledge" ? "事件已确认并留档。" : "事件已忽略。后续不会改变原始情报。" );
      const nextOverview = await getMonitoringOverview();
      setOverview(nextOverview);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "更新事件失败");
    } finally {
      setBusy(null);
    }
  }

  async function toggleRule(rule: MonitorRule) {
    if (busy) return;
    setBusy(rule.id);
    try {
      await updateMonitorRule(rule.id, { enabled: !rule.enabled });
      await load();
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : "更新监控项失败");
    } finally {
      setBusy(null);
    }
  }

  async function removeRule(rule: MonitorRule) {
    if (!window.confirm(`确定移除监控项“${rule.name}”吗？历史事件会继续保留。`)) return;
    setBusy(rule.id);
    try {
      await deleteMonitorRule(rule.id);
      setNotice("监控项已停止并移除，历史事件仍可审计。");
      await load();
    } catch (removeError) {
      setError(removeError instanceof Error ? removeError.message : "移除监控项失败");
    } finally {
      setBusy(null);
    }
  }

  if (loading && !overview) {
    return (
      <main className="monitor-page">
        <div className="monitor-loading"><Radar /> Jarvis 正在校准全球监控雷达…</div>
      </main>
    );
  }

  return (
    <main className="monitor-page">
      <header className="monitor-hero">
        <div className="monitor-hero-copy">
          <div className="eyebrow">SPRINT 22 · VERIFIED SIGNALS</div>
          <h1>投资与国际动态 <span>监控中心</span></h1>
          <p>把公开事件与你的资产、投资理由和长期关注主题连接起来。</p>
        </div>
        <div className="monitor-hero-actions">
          <button className="ghost-button" onClick={() => setShowForm((value) => !value)} type="button">
            <Plus size={16} /> 新建监控
          </button>
          <button className="primary-button" disabled={Boolean(busy)} onClick={() => void runScan()} type="button">
            <RefreshCw className={busy === "scan" ? "is-spinning" : ""} size={16} />
            {busy === "scan" ? "扫描中" : "立即扫描"}
          </button>
        </div>
      </header>

      <section className="monitor-radar-shell">
        <div className="monitor-radar" aria-hidden="true">
          <i /><i /><i /><span />
          <b>{overview?.new_events ?? 0}</b>
          <small>NEW SIGNALS</small>
        </div>
        <div className="monitor-radar-copy">
          <span><Activity size={15} /> MONITORING ACTIVE</span>
          <h2>{overview?.critical_events ? `${overview.critical_events} 个事件需要优先复核` : "当前没有高等级未确认事件"}</h2>
          <p>最近一次事件：{timeLabel(overview?.latest_event_at)}</p>
        </div>
      </section>

      <CommandTelemetry
        label="监控中心状态"
        items={[
          { label: "ACTIVE RULES", value: overview?.active_rules ?? 0, detail: `${overview?.asset_rules ?? 0} 个资产监控`, tone: "cyan" },
          { label: "GLOBAL THEMES", value: overview?.topic_rules ?? 0, detail: "宏观与国际主题", tone: "green" },
          { label: "CRITICAL", value: overview?.critical_events ?? 0, detail: "影响等级 4–5", tone: overview?.critical_events ? "amber" : "green" },
          { label: "PRICE MODE", value: "带时间戳", detail: "不冒充实时行情" },
        ]}
      />

      <section className="monitor-safety-line">
        <ShieldAlert size={18} />
        <p>{overview?.disclaimer}</p>
      </section>

      {error ? <div className="monitor-feedback is-error">{error}</div> : null}
      {notice ? <div className="monitor-feedback">{notice}</div> : null}

      {showForm ? (
        <section className="panel monitor-form-panel">
          <div className="monitor-section-head">
            <div><span>NEW WATCH VECTOR</span><h2>建立一个监控项</h2></div>
            <button className="quiet-button" onClick={() => setShowForm(false)} type="button">收起</button>
          </div>
          <div className="monitor-type-grid">
            {(["asset", "macro", "international"] as MonitorType[]).map((type) => (
              <button className={monitorType === type ? "is-active" : ""} key={type} onClick={() => setMonitorType(type)} type="button">
                {type === "asset" ? <Activity /> : type === "macro" ? <Radar /> : <Globe2 />}
                <strong>{monitorTypeLabels[type]}</strong>
                <span>{type === "asset" ? "连接持仓与理由" : type === "macro" ? "利率、通胀、能源" : "地区、政策与冲突"}</span>
              </button>
            ))}
          </div>
          <div className="monitor-form-grid">
            <label>监控名称<input onChange={(event) => setName(event.target.value)} placeholder="例如：美联储与科技股估值" value={name} /></label>
            {monitorType === "asset" ? (
              <>
                <label>绑定资产<select onChange={(event) => { setAssetId(event.target.value); setThesisId(""); }} value={assetId}><option value="">选择已录入资产</option>{assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.name} · {asset.symbol}</option>)}</select></label>
                <label>绑定当前投资理由<select onChange={(event) => setThesisId(event.target.value)} value={thesisId}><option value="">不绑定</option>{filteredTheses.map((thesis) => <option key={thesis.id} value={thesis.id}>{thesis.title}</option>)}</select></label>
              </>
            ) : null}
            <label className="monitor-wide">监控关键词<input onChange={(event) => setKeywords(event.target.value)} placeholder={monitorType === "asset" ? "可选；资产名和代码会自动加入" : "用逗号分隔，例如：Federal Reserve, 利率, inflation"} value={keywords} /></label>
            <label>地区<input onChange={(event) => setRegions(event.target.value)} placeholder="中国、美国、欧洲、中东" value={regions} /></label>
            <label>影响渠道<input onChange={(event) => setRiskChannels(event.target.value)} placeholder="利率、能源、制裁、供应链" value={riskChannels} /></label>
            <label>最低提醒等级<select onChange={(event) => setMinSeverity(Number(event.target.value))} value={minSeverity}>{[1, 2, 3, 4, 5].map((level) => <option key={level} value={level}>{level} / 5{level === 3 ? " · 推荐" : ""}</option>)}</select></label>
            <label className="monitor-check"><input checked={notifyEnabled} onChange={(event) => setNotifyEnabled(event.target.checked)} type="checkbox" /><span><strong>主动提醒</strong><small>遵守全局静默时段和语音隐私设置</small></span></label>
          </div>
          <div className="monitor-form-actions"><button className="primary-button" disabled={busy === "create" || !name.trim()} onClick={() => void saveRule()} type="button">{busy === "create" ? "建立中…" : "启动监控"}</button><button className="quiet-button" onClick={() => { resetForm(); setShowForm(false); }} type="button">取消</button></div>
        </section>
      ) : null}

      <nav className="monitor-tabs" aria-label="监控中心视图">
        <button className={view === "events" ? "is-active" : ""} onClick={() => setView("events")} type="button">事件流 <span>{events.length}</span></button>
        <button className={view === "rules" ? "is-active" : ""} onClick={() => setView("rules")} type="button">监控项 <span>{rules.length}</span></button>
      </nav>

      {view === "events" ? (
        <section className="monitor-events">
          {events.length ? events.map((event) => (
            <article className={`monitor-event direction-${event.impact_direction}`} key={event.id}>
              <div className="monitor-event-rail"><span>{event.severity}</span><i>{Array.from({ length: 5 }, (_, index) => <b className={index < event.severity ? "is-on" : ""} key={index} />)}</i><small>IMPACT</small></div>
              <div className="monitor-event-body">
                <div className="monitor-event-meta"><span>{event.rule_name}</span><i>{directionLabels[event.impact_direction]}</i><time>{timeLabel(event.detected_at)}</time></div>
                <h2>{event.news_title}</h2>
                <div className="monitor-source"><span>{event.source_name}</span><a href={event.source_url} rel="noreferrer" target="_blank">核对原文 <ExternalLink size={13} /></a></div>
                <div className="monitor-impact-grid"><div><span>事实摘要</span><p>{event.fact_summary}</p></div><div><span>为什么与你有关</span><p>{event.why_relevant}</p></div><div className="monitor-impact-wide"><span>可能的影响路径</span><p>{event.impact_mechanism}</p></div></div>
                <div className="monitor-watch-next"><strong>下一步观察</strong>{event.watch_next.map((item) => <span key={item}>{item}</span>)}</div>
                <div className="monitor-event-footer"><div>{event.matched_terms.map((term) => <span key={term}>{term}</span>)}</div><aside><button disabled={busy === event.id} onClick={() => void actOnEvent(event, "dismiss")} type="button"><X size={14} />忽略</button><button disabled={busy === event.id} onClick={() => void actOnEvent(event, "acknowledge")} type="button"><Check size={14} />已确认</button></aside></div>
              </div>
            </article>
          )) : <div className="monitor-empty"><Radar /><h2>雷达正在运行</h2><p>建立监控项后，Jarvis 会把有来源的投资与国际事件放到这里。</p><button className="primary-button" onClick={() => setShowForm(true)} type="button">建立第一个监控</button></div>}
        </section>
      ) : (
        <section className="monitor-rule-grid">
          {rules.length ? rules.map((rule) => (
            <article className={!rule.enabled ? "is-paused" : ""} key={rule.id}>
              <div className="monitor-rule-head"><span>{rule.monitor_type === "asset" ? <Activity /> : rule.monitor_type === "macro" ? <Radar /> : <Globe2 />}</span><div><small>{monitorTypeLabels[rule.monitor_type]}</small><h2>{rule.name}</h2></div><i>{rule.enabled ? "ACTIVE" : "PAUSED"}</i></div>
              {rule.asset_name ? <p className="monitor-rule-target">{rule.asset_name} · {rule.asset_symbol}</p> : null}
              <div className="monitor-rule-terms">{[...rule.keywords, ...rule.regions, ...rule.risk_channels].slice(0, 10).map((term) => <span key={term}>{term}</span>)}</div>
              <dl><div><dt>未确认事件</dt><dd>{rule.new_event_count}</dd></div><div><dt>提醒阈值</dt><dd>{rule.min_severity}/5</dd></div><div><dt>上次检查</dt><dd>{timeLabel(rule.last_evaluated_at)}</dd></div></dl>
              <footer><button disabled={busy === rule.id} onClick={() => void toggleRule(rule)} type="button">{rule.enabled ? "暂停监控" : "恢复监控"}</button><button aria-label="移除监控" disabled={busy === rule.id} onClick={() => void removeRule(rule)} type="button"><Trash2 size={15} /></button></footer>
            </article>
          )) : <div className="monitor-empty"><BellRing /><h2>还没有监控项</h2><p>可以从一个资产或一个国际主题开始。</p></div>}
        </section>
      )}
    </main>
  );
}
