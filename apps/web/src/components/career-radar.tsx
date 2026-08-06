"use client";

import {
  AlertTriangle,
  BriefcaseBusiness,
  Camera,
  CheckCircle2,
  ExternalLink,
  Globe2,
  Plus,
  Radar,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  careerEvidenceScreenshotUrl,
  createCareerSandbox,
  createCareerSource,
  getCareerOverview,
  runCareerResearch,
  type CareerOverview,
  type CareerSource,
} from "@/lib/api";

function timestamp(value?: string | null) {
  if (!value) return "尚未运行";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function sourceLabel(source: CareerSource) {
  return source.source_kind === "sandbox" ? "安全演练" : "官方来源";
}

function splitHosts(value: string) {
  return [...new Set(value.split(/[，,\s]+/).map((item) => item.trim().toLowerCase()).filter(Boolean))];
}

export function CareerRadar() {
  const [overview, setOverview] = useState<CareerOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showSourceForm, setShowSourceForm] = useState(false);
  const [sourceName, setSourceName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [startUrl, setStartUrl] = useState("");
  const [allowedHosts, setAllowedHosts] = useState("");
  const [scopeConfirmed, setScopeConfirmed] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      setOverview(await getCareerOverview(signal));
      setError(null);
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === "AbortError") return;
      setError(loadError instanceof Error ? loadError.message : "读取求职雷达失败");
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

  const sandbox = useMemo(
    () => overview?.sources.find((source) => source.source_kind === "sandbox"),
    [overview],
  );
  const latestRunBySource = useMemo(
    () => new Map(overview?.runs.map((run) => [run.source_id, run]) ?? []),
    [overview],
  );

  async function ensureSandbox() {
    if (busy) return;
    setBusy("sandbox-create");
    setError(null);
    try {
      await createCareerSandbox();
      setNotice("安全演练来源已就绪。它只使用本地测试页面，不访问真实网站。" );
      await load();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "建立安全演练失败");
    } finally {
      setBusy(null);
    }
  }

  async function runSource(source: CareerSource) {
    if (busy) return;
    setBusy(source.id);
    setError(null);
    setNotice(
      source.source_kind === "sandbox"
        ? "正在验证页面指令隔离、岗位提取与证据留存…"
        : "正在一次性只读会话中核对公开招聘页面…",
    );
    try {
      const run = await runCareerResearch(source.id, { query: "AI 应用与 Agent 岗位", max_pages: source.source_kind === "sandbox" ? 1 : 3 });
      setNotice(
        run.status === "completed"
          ? `研究完成：${run.pages_visited} 个来源页面，${run.opportunities_found} 个结构化岗位，识别 ${run.injection_signal_count} 个不可信指令信号。`
          : `研究未完成：${run.error_message ?? "请检查 Browser Worker 状态"}`,
      );
      await load();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "岗位研究失败");
    } finally {
      setBusy(null);
    }
  }

  async function saveSource() {
    if (busy || !scopeConfirmed) return;
    let startHost = "";
    try {
      startHost = new URL(startUrl).hostname.toLowerCase();
    } catch {
      setError("请输入完整的 https:// 招聘页面地址。" );
      return;
    }
    setBusy("source-create");
    setError(null);
    try {
      await createCareerSource({
        name: sourceName.trim(),
        company_name: companyName.trim(),
        start_url: startUrl.trim(),
        allowed_hosts: splitHosts(allowedHosts || startHost),
        confirmed_read_only_scope: true,
      });
      setSourceName("");
      setCompanyName("");
      setStartUrl("");
      setAllowedHosts("");
      setScopeConfirmed(false);
      setShowSourceForm(false);
      setNotice("来源已加入精确域名白名单。Jarvis 仍不会登录、上传简历或投递。" );
      await load();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "添加来源失败");
    } finally {
      setBusy(null);
    }
  }

  if (loading && !overview) {
    return <main className="career-page"><div className="career-loading"><Radar /> Jarvis 正在校准职业雷达…</div></main>;
  }

  const providerReady = overview?.provider.status === "ready";
  const safeBoundary = overview?.provider.read_only && overview.provider.isolated_context && !overview.provider.credentials_configured && !overview.provider.uploads_enabled && !overview.provider.submissions_enabled;

  return (
    <main className="career-page">
      <header className="career-hero">
        <div>
          <span>SPRINT 31 · ISOLATED CAREER INTELLIGENCE</span>
          <h1>职业机会 <em>雷达</em></h1>
          <p>只读研究公开招聘页面，用你的职业档案解释匹配证据，并保留来源、时间与截图。</p>
        </div>
        <div className="career-hero-actions">
          <button className="ghost-button" onClick={() => setShowSourceForm((value) => !value)} type="button"><Plus size={16} /> 添加来源</button>
          {!sandbox ? <button className="primary-button" disabled={Boolean(busy)} onClick={() => void ensureSandbox()} type="button"><ShieldCheck size={16} /> 建立安全演练</button> : <button className="primary-button" disabled={Boolean(busy) || !providerReady} onClick={() => void runSource(sandbox)} type="button"><RefreshCw className={busy === sandbox.id ? "is-spinning" : ""} size={16} /> {busy === sandbox.id ? "演练中" : "运行安全演练"}</button>}
        </div>
      </header>

      <section className={`career-core ${providerReady ? "is-ready" : "is-offline"}`}>
        <div className="career-orb" aria-hidden="true"><i /><i /><span><BriefcaseBusiness /></span></div>
        <div>
          <small>BROWSER WORKER</small>
          <h2>{providerReady ? "隔离只读引擎在线" : "隔离引擎尚未启用"}</h2>
          <p>{overview?.provider.detail ?? (providerReady ? "每次任务使用全新浏览器上下文，结束后立即销毁。" : "启用后先运行安全演练，再添加真实招聘来源。")}</p>
        </div>
        <dl>
          <div><dt>SESSION</dt><dd>{overview?.provider.persistent_profile ? "PERSISTENT" : "EPHEMERAL"}</dd></div>
          <div><dt>NETWORK</dt><dd>{overview?.provider.loopback_only ? "LOOPBACK" : "CHECK"}</dd></div>
          <div><dt>BOUNDARY</dt><dd>{safeBoundary ? "VERIFIED" : "CHECK"}</dd></div>
        </dl>
      </section>

      <section className="career-safety-grid">
        <article><ShieldCheck /><div><strong>精确域名白名单</strong><span>每次跳转重新校验 DNS 与公网地址</span></div></article>
        <article><Camera /><div><strong>可核对证据</strong><span>来源、时间、内容哈希与本地截图</span></div></article>
        <article><AlertTriangle /><div><strong>页面指令隔离</strong><span>Prompt Injection 只标记，不执行</span></div></article>
        <article><CheckCircle2 /><div><strong>零账号操作</strong><span>不登录、不上传、不下载、不投递</span></div></article>
      </section>

      {error ? <div className="career-feedback is-error">{error}</div> : null}
      {notice ? <div className="career-feedback">{notice}</div> : null}

      {showSourceForm ? (
        <section className="career-source-form">
          <header><div><span>ALLOWLIST A PUBLIC SOURCE</span><h2>添加官方招聘入口</h2></div><button className="quiet-button" onClick={() => setShowSourceForm(false)} type="button">收起</button></header>
          <div className="career-form-grid">
            <label>来源名称<input onChange={(event) => setSourceName(event.target.value)} placeholder="例如：某公司 Careers" value={sourceName} /></label>
            <label>公司名称<input onChange={(event) => setCompanyName(event.target.value)} placeholder="用于岗位归属" value={companyName} /></label>
            <label className="career-form-wide">招聘入口<input onChange={(event) => { setStartUrl(event.target.value); try { if (!allowedHosts) setAllowedHosts(new URL(event.target.value).hostname); } catch { /* 等待完整 URL */ } }} placeholder="https://careers.example.com/jobs" value={startUrl} /></label>
            <label className="career-form-wide">允许访问的精确域名<input onChange={(event) => setAllowedHosts(event.target.value)} placeholder="careers.example.com；如跳到官方 ATS，可再明确加入其域名" value={allowedHosts} /><small>不支持 *.example.com，也不会自动信任子域名。</small></label>
          </div>
          <label className="career-confirm"><input checked={scopeConfirmed} onChange={(event) => setScopeConfirmed(event.target.checked)} type="checkbox" /><span><strong>我确认这只是公开招聘页面的只读研究</strong><small>不会登录、上传简历、下载附件、填写表单或提交申请。</small></span></label>
          <footer><button className="primary-button" disabled={!scopeConfirmed || !sourceName.trim() || !startUrl.trim() || Boolean(busy)} onClick={() => void saveSource()} type="button">加入白名单</button></footer>
        </section>
      ) : null}

      <section className="career-section">
        <header><div><span>SOURCE VECTORS</span><h2>已批准的公开来源</h2></div><small>{overview?.sources.length ?? 0} SOURCES</small></header>
        <div className="career-source-grid">
          {overview?.sources.length ? overview.sources.map((source) => {
            const latest = latestRunBySource.get(source.id);
            return <article key={source.id}>
              <header><span className={source.source_kind}>{sourceLabel(source)}</span><i>{source.last_error ? "需检查" : source.last_checked_at ? "已核对" : "待运行"}</i></header>
              <Globe2 />
              <h3>{source.name}</h3>
              <p>{source.company_name || source.allowed_hosts[0]}</p>
              <code>{source.allowed_hosts.join(" · ")}</code>
              <dl><div><dt>上次运行</dt><dd>{timestamp(source.last_checked_at)}</dd></div><div><dt>岗位</dt><dd>{latest?.opportunities_found ?? 0}</dd></div><div><dt>注入信号</dt><dd>{latest?.injection_signal_count ?? 0}</dd></div></dl>
              {source.last_error ? <small className="career-source-error">{source.last_error}</small> : null}
              <button disabled={Boolean(busy) || !providerReady} onClick={() => void runSource(source)} type="button"><RefreshCw className={busy === source.id ? "is-spinning" : ""} size={14} /> {busy === source.id ? "研究中" : "只读研究"}</button>
            </article>;
          }) : <div className="career-empty"><Radar /><h3>还没有来源</h3><p>先建立本地安全演练，确认隔离边界后再添加真实招聘入口。</p></div>}
        </div>
      </section>

      <section className="career-section">
        <header><div><span>PROFILE MATCH</span><h2>与你相关的岗位</h2></div><small>DETERMINISTIC · NO PAID MODEL</small></header>
        <div className="career-opportunity-grid">
          {overview?.opportunities.length ? overview.opportunities.map((item) => <article className={`match-${item.match_level}`} key={item.id}>
            <div className="career-score"><strong>{item.match_level === "unknown" ? "—" : item.match_score}</strong><span>{item.match_level.toUpperCase()}</span></div>
            <div className="career-job-body">
              <header><span>{item.company}</span><time>{timestamp(item.last_seen_at)}</time></header>
              <h3>{item.title}</h3>
              <p>{item.location || "地点未标注"} · {item.employment_type || "类型未标注"}</p>
              <div className="career-tags">{item.skills.map((skill) => <span key={skill}>{skill}</span>)}</div>
              <section><strong>匹配依据</strong>{item.match_reasons.map((reason) => <p key={reason}>{reason}</p>)}</section>
              {item.missing_skills.length ? <section className="career-gap"><strong>待补能力</strong><p>{item.missing_skills.join(" · ")}</p></section> : null}
              <footer><a href={item.source_url} rel="noreferrer" target="_blank">核对原始岗位 <ExternalLink size={13} /></a><span>只提供来源，不代替你投递</span></footer>
            </div>
          </article>) : <div className="career-empty"><BriefcaseBusiness /><h3>岗位空间尚为空</h3><p>运行来源后，只有带结构化 JobPosting 证据的岗位才会进入这里。</p></div>}
        </div>
      </section>

      <section className="career-section">
        <header><div><span>EVIDENCE LEDGER</span><h2>来源证据</h2></div><small>{overview?.evidence.length ?? 0} CAPTURES</small></header>
        <div className="career-evidence-grid">
          {overview?.evidence.length ? overview.evidence.map((item) => <article key={item.id}>
            <header><span>HTTP {item.http_status}</span><time>{timestamp(item.fetched_at)}</time></header>
            <h3>{item.title || "未命名招聘页面"}</h3>
            <p>{item.text_excerpt.slice(0, 220)}</p>
            {item.injection_signals.length ? <div className="career-injection"><AlertTriangle size={14} /><span>已隔离 {item.injection_signals.length} 个页面指令信号</span></div> : <div className="career-evidence-clean"><ShieldCheck size={14} /><span>未发现明显页面指令</span></div>}
            <footer><code>{item.content_sha256.slice(0, 12)}…</code>{item.screenshot_available ? <a href={careerEvidenceScreenshotUrl(item.id)} rel="noreferrer" target="_blank"><Camera size={14} /> 查看证据截图</a> : null}</footer>
          </article>) : <div className="career-empty"><Camera /><h3>尚无证据快照</h3><p>每次研究都会记录来源时间、内容哈希和本地截图。</p></div>}
        </div>
      </section>
    </main>
  );
}
