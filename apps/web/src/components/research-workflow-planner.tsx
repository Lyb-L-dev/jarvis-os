"use client";

import {
  addResearchIntelligenceSource,
  addResearchManualSource,
  archiveKnowledgeSource,
  cancelResearchWorkflow,
  createResearchGrowthPreview,
  listResearchWorkflows,
  resumeResearchWorkflow,
  startResearchWorkflow,
  updateResearchReport,
  type KnowledgeArchiveOutcome,
  type NewsCategory,
  type NewsItem,
  type ResearchModelPreference,
  type ResearchReport,
  type ResearchWorkflowRun,
} from "@/lib/api";
import { AnimatePresence, motion } from "motion/react";
import { ExternalLink, FileCheck2, FlaskConical, ShieldCheck } from "lucide-react";
import { splitLines } from "@/lib/utils";
import { useEffect, useMemo, useState } from "react";

type Props = {
  candidateItems: NewsItem[];
  onReloadIntelligence?: () => void | Promise<void>;
};

const activeStatuses = new Set([
  "created",
  "running",
  "waiting_for_sources",
  "waiting_for_model_approval",
  "waiting_for_report_review",
]);

const categoryOptions: Array<[NewsCategory | "", string]> = [
  ["", "自动判断"],
  ["ai", "AI"],
  ["technology", "科技"],
  ["international", "国际动态"],
  ["investment", "投资信息"],
  ["career", "职业发展"],
];

const providerNames: Record<string, string> = {
  deepseek: "DeepSeek",
  mimo: "MiMo",
  ollama: "本地 Qwen",
};

function statusText(status: ResearchWorkflowRun["status"]) {
  return {
    created: "正在建立研究",
    running: "正在执行",
    waiting_for_sources: "等待补充来源",
    waiting_for_model_approval: "等待模型授权",
    waiting_for_report_review: "等待审核报告",
    completed: "报告已确认",
    rejected: "报告已放弃",
    cancelled: "研究已取消",
    failed: "研究中断",
  }[status];
}

function providerName(provider?: string | null) {
  if (!provider) return "尚未选择";
  return providerNames[provider] ?? provider;
}

export function ResearchWorkflowPlanner({
  candidateItems,
  onReloadIntelligence,
}: Props) {
  const [run, setRun] = useState<ResearchWorkflowRun | null>(null);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [archiveOutcome, setArchiveOutcome] =
    useState<KnowledgeArchiveOutcome | null>(null);

  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState("");
  const [category, setCategory] = useState<NewsCategory | "">("");
  const [maxSources, setMaxSources] = useState(8);
  const [modelPreference, setModelPreference] =
    useState<ResearchModelPreference>("auto");
  const [cloudAllowed, setCloudAllowed] = useState(true);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);

  const [manualTitle, setManualTitle] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const [manualSourceName, setManualSourceName] = useState("");
  const [manualExcerpt, setManualExcerpt] = useState("");
  const [manualTrust, setManualTrust] = useState(3);

  useEffect(() => {
    const controller = new AbortController();
    void listResearchWorkflows(controller.signal)
      .then((runs) => {
        const current = runs.find((item) => activeStatuses.has(item.status));
        const latest = current ?? runs[0] ?? null;
        setRun(latest);
        setReport(latest?.report ? structuredClone(latest.report) : null);
        setShowCreate(runs.length === 0);
      })
      .catch((loadError) => {
        if (loadError instanceof DOMException && loadError.name === "AbortError") {
          return;
        }
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Research Agent 暂时无法恢复。",
        );
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const researchStep = useMemo(() => {
    if (!run) return 0;
    if (run.status === "waiting_for_sources") return 1;
    if (run.status === "waiting_for_model_approval") return 2;
    if (run.status === "waiting_for_report_review") return 3;
    if (run.status === "completed") return 4;
    return 0;
  }, [run]);

  const sourceByKey = useMemo(
    () => new Map(run?.sources.map((source) => [source.citation_key, source]) ?? []),
    [run],
  );

  const availableItems = useMemo(() => {
    const existingUrls = new Set(run?.sources.map((source) => source.canonical_url));
    return candidateItems
      .filter((item) => !item.duplicate_of_id && item.status !== "ignored")
      .filter((item) => !existingUrls.has(item.canonical_url))
      .slice(0, 12);
  }, [candidateItems, run]);

  async function perform(
    key: string,
    action: () => Promise<ResearchWorkflowRun>,
    success?: string,
  ) {
    setBusy(key);
    setError(null);
    setNotice(null);
    try {
      const next = await action();
      setRun(next);
      setReport(next.report ? structuredClone(next.report) : null);
      setShowCreate(false);
      if (success) setNotice(success);
    } catch (actionError) {
      setError(
        actionError instanceof Error ? actionError.message : "研究操作未完成。",
      );
    } finally {
      setBusy(null);
    }
  }

  function toggleSelected(itemId: string) {
    setSelectedItems((current) =>
      current.includes(itemId)
        ? current.filter((id) => id !== itemId)
        : current.length < maxSources
          ? [...current, itemId]
          : current,
    );
  }

  function startResearch() {
    if (question.trim().length < 3) {
      setError("请先填写一个明确的研究问题。 ");
      return;
    }
    void perform(
      "start",
      () =>
        startResearchWorkflow({
          question: question.trim(),
          scope: scope.trim() || undefined,
          category: category || undefined,
          max_sources: maxSources,
          source_item_ids: selectedItems,
          model_preference: modelPreference,
          cloud_allowed: cloudAllowed,
        }),
      "研究计划已建立；只有来源足够时才会进入模型阶段。",
    );
  }

  function addIntelligenceItem(item: NewsItem) {
    if (!run) return;
    void perform(
      `source-${item.id}`,
      () => addResearchIntelligenceSource(run.id, item.id),
      "已加入一个公开情报来源。",
    );
  }

  function addManualSource() {
    if (!run) return;
    if (
      !manualTitle.trim() ||
      !manualSourceName.trim() ||
      !manualUrl.trim() ||
      manualExcerpt.trim().length < 20
    ) {
      setError("请完整填写来源名称、标题、公开链接和至少 20 字原文摘录。 ");
      return;
    }
    void perform(
      "manual-source",
      () =>
        addResearchManualSource(run.id, {
          title: manualTitle.trim(),
          url: manualUrl.trim(),
          source_name: manualSourceName.trim(),
          excerpt: manualExcerpt.trim(),
          trust_score: manualTrust,
        }),
      "公开来源已通过地址安全检查并加入研究。",
    );
  }

  function updateReportCollection(
    field: "facts" | "viewpoints" | "inferences",
    index: number,
    value: string,
  ) {
    if (!report) return;
    setReport({
      ...report,
      [field]: report[field].map((item, itemIndex) =>
        itemIndex === index ? { ...item, statement: value } : item,
      ),
    });
  }

  async function saveReport() {
    if (!run || !report) return null;
    const next = await updateResearchReport(run.id, {
      title: report.title,
      executive_summary: report.executive_summary,
      facts: report.facts,
      viewpoints: report.viewpoints,
      inferences: report.inferences,
      uncertainties: report.uncertainties,
      recommended_actions: report.recommended_actions,
    });
    setRun(next);
    setReport(next.report ? structuredClone(next.report) : null);
    return next;
  }

  async function confirmReport() {
    if (!run || !report) return;
    if (
      !window.confirm(
        "确认后，这份草稿会成为正式研究报告；本次确认不会写入 Obsidian，也不会触发任何交易或外部账号操作。是否继续？",
      )
    ) {
      return;
    }
    setBusy("confirm-report");
    setError(null);
    setNotice(null);
    try {
      const saved = await saveReport();
      if (!saved) return;
      const next = await resumeResearchWorkflow(saved.id, "approve_report");
      setRun(next);
      setReport(next.report ? structuredClone(next.report) : null);
      setNotice("正式研究报告已确认；尚未写入 Obsidian。 ");
    } catch (actionError) {
      setError(
        actionError instanceof Error ? actionError.message : "报告确认未完成。",
      );
    } finally {
      setBusy(null);
    }
  }

  async function archiveReport() {
    if (!run?.report) return;
    if (
      !window.confirm(
        "这一步会在你已配置的 Obsidian Vault 中创建研究报告 Markdown 文件。确认写入吗？",
      )
    ) {
      return;
    }
    setBusy("archive");
    setError(null);
    setNotice(null);
    try {
      const outcome = await archiveKnowledgeSource("research_report", run.report.id);
      setArchiveOutcome(outcome);
      setRun({
        ...run,
        report: {
          ...run.report,
          status:
            outcome.status === "conflict" || outcome.status === "user_modified"
              ? "conflict"
              : "archived",
          archive_path: outcome.target_relative_path,
          archived_at: new Date().toISOString(),
        },
      });
      setNotice(
        outcome.status === "conflict" || outcome.status === "user_modified"
          ? "检测到 Obsidian 中的人工修改，新版本已放入审核区。"
          : "研究报告已写入 Obsidian。",
      );
    } catch (actionError) {
      setError(
        actionError instanceof Error ? actionError.message : "Obsidian 归档未完成。",
      );
    } finally {
      setBusy(null);
    }
  }

  async function proposeGrowthDraft() {
    if (!run?.report) return;
    setBusy("orchestration-preview");
    setError(null);
    setNotice(null);
    try {
      await createResearchGrowthPreview(run.report.id);
      setNotice("成长任务草稿的编排计划已生成。请在 Approval Center 审阅；通过前不会启动编排。 ");
    } catch (actionError) {
      setError(
        actionError instanceof Error
          ? actionError.message
          : "编排计划预览未生成。",
      );
    } finally {
      setBusy(null);
    }
  }

  function CitationLinks({ refs }: { refs: string[] }) {
    return (
      <span className="research-citations">
        {refs.map((ref) => {
          const source = sourceByKey.get(ref);
          return source ? (
            <a href={source.canonical_url} key={ref} rel="noreferrer" target="_blank">
              [{ref}]
            </a>
          ) : (
            <span key={ref}>[{ref}]</span>
          );
        })}
      </span>
    );
  }

  return (
    <motion.section
      animate={{ opacity: 1, y: 0 }}
      className="panel growth-workflow research-workflow"
      initial={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.28 }}
    >
      <div className="growth-workflow-head">
        <div>
          <div className="eyebrow">LANGGRAPH · SOURCE GROUNDED</div>
          <h2>Research Agent</h2>
          <p>先建立计划与来源，再生成可追溯草稿；事实、观点、推断分区呈现。</p>
        </div>
        {run ? (
          <div className={`growth-workflow-state workflow-${run.status}`}>
            <i />
            {statusText(run.status)}
          </div>
        ) : null}
      </div>

      {run ? (
        <div className="growth-workflow-steps" aria-label="研究工作流进度">
          {["研究问题", "核验来源", "模型决策", "审核报告", "正式报告"].map(
            (label, index) => (
              <div className={index <= researchStep ? "step-active" : ""} key={label}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <small>{label}</small>
              </div>
            ),
          )}
        </div>
      ) : null}

      {error ? <div className="growth-feedback growth-error">{error}</div> : null}
      {notice ? <div className="growth-feedback">{notice}</div> : null}
      {loading ? <div className="growth-workflow-loading">Jarvis 正在恢复研究进度…</div> : null}

      <AnimatePresence mode="wait">
        {!loading && (showCreate || !run) ? (
          <motion.div
            animate={{ opacity: 1 }}
            className="research-create"
            exit={{ opacity: 0 }}
            initial={{ opacity: 0 }}
            key="research-create"
          >
            <div className="research-create-fields">
              <label className="workflow-objective">
                你想研究什么？
                <textarea
                  maxLength={4000}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="例如：最近 AI Agent 行业有哪些可核验的重要变化？"
                  value={question}
                />
              </label>
              <label className="workflow-constraints">
                研究范围（可选）
                <textarea
                  maxLength={8000}
                  onChange={(event) => setScope(event.target.value)}
                  placeholder="例如：优先官方来源，关注技术与产业影响，不生成投资建议"
                  value={scope}
                />
              </label>
              <label>
                情报类别
                <select
                  onChange={(event) => setCategory(event.target.value as NewsCategory | "")}
                  value={category}
                >
                  {categoryOptions.map(([value, label]) => (
                    <option key={value || "all"} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                最多来源
                <input
                  max={12}
                  min={2}
                  onChange={(event) => setMaxSources(Number(event.target.value))}
                  type="number"
                  value={maxSources}
                />
              </label>
            </div>

            <div className="research-source-picker">
              <header>
                <div>
                  <strong>选择现有公开情报</strong>
                  <small>可先不选；Jarvis 会尝试从情报中心匹配，少于 2 个唯一来源时自动暂停。</small>
                </div>
                <span>{selectedItems.length} / {maxSources}</span>
              </header>
              <div>
                {candidateItems.slice(0, 10).map((item) => (
                  <button
                    className={selectedItems.includes(item.id) ? "source-selected" : ""}
                    key={item.id}
                    onClick={() => toggleSelected(item.id)}
                    type="button"
                  >
                    <span>{item.source_name}</span>
                    <strong>{item.title}</strong>
                  </button>
                ))}
                {candidateItems.length === 0 ? <p>情报中心还没有可选来源。</p> : null}
              </div>
            </div>

            <div className="workflow-model-choice">
              <strong>研究模型</strong>
              <div>
                {(
                  [
                    ["auto", "Jarvis 决策", "多来源综合建议 DeepSeek，但付费调用前必须再次确认"],
                    ["deep", "DeepSeek", "适合冲突分析，会消耗钱包余额并再次请求授权"],
                    ["mimo", "MiMo", "使用 Token Plan，适合常规信息归纳"],
                    ["local", "本地 Qwen", "资料不离开电脑，复杂综合能力可能较低"],
                  ] as Array<[ResearchModelPreference, string, string]>
                ).map(([value, title, detail]) => (
                  <button
                    className={modelPreference === value ? "model-active" : ""}
                    key={value}
                    onClick={() => setModelPreference(value)}
                    type="button"
                  >
                    <span>{title}</span>
                    <small>{detail}</small>
                  </button>
                ))}
              </div>
            </div>
            <label className="workflow-cloud-check">
              <input
                checked={cloudAllowed}
                onChange={(event) => setCloudAllowed(event.target.checked)}
                type="checkbox"
              />
              <span>
                允许把研究问题、范围和公开来源摘录发给所选云模型
                <small>关闭后强制使用本地 Qwen；不会发送凭据、私有文件或投资交易数据。</small>
              </span>
            </label>
            <button
              className="primary-button workflow-start"
              disabled={busy !== null || question.trim().length < 3}
              onClick={startResearch}
              type="button"
            >
              {busy === "start" ? "正在建立…" : "建立研究计划"}
            </button>
          </motion.div>
        ) : null}

        {!loading && run && !showCreate ? (
          <motion.div animate={{ opacity: 1 }} initial={{ opacity: 0 }} key={run.id}>
            <div className="research-question-band">
              <FlaskConical size={17} />
              <div>
                <span>RESEARCH QUESTION</span>
                <strong>{run.request.question}</strong>
                {run.request.scope ? <p>{run.request.scope}</p> : null}
              </div>
              <small>{run.sources.length} 个唯一来源 · {run.checkpoint_backend === "postgres" ? "可恢复" : "临时恢复"}</small>
            </div>

            <div className="research-source-ledger">
              <header>
                <div>
                  <span>SOURCE LEDGER</span>
                  <h3>已核验来源</h3>
                </div>
                <small>每条来源都有固定引用编号；重复网址和重复内容不会重复计数。</small>
              </header>
              <div className="research-source-list">
                {run.sources.map((source) => (
                  <a href={source.canonical_url} key={source.id} rel="noreferrer" target="_blank">
                    <span>{source.citation_key}</span>
                    <div>
                      <strong>{source.title}</strong>
                      <small>{source.source_name} · 可信度 {source.trust_score}/5</small>
                    </div>
                    <ExternalLink size={14} />
                  </a>
                ))}
                {run.sources.length === 0 ? <p>暂时没有符合条件的来源。</p> : null}
              </div>
            </div>

            {run.status === "waiting_for_sources" ? (
              <div className="research-source-review">
                <div className="research-source-options">
                  <header>
                    <div>
                      <span>补充情报中心来源</span>
                      <small>至少需要 2 个不同网址且内容不重复的来源。</small>
                    </div>
                    <button
                      className="ghost-button"
                      disabled={busy !== null}
                      onClick={() => void onReloadIntelligence?.()}
                      type="button"
                    >
                      重新读取情报
                    </button>
                  </header>
                  <div>
                    {availableItems.map((item) => (
                      <button
                        disabled={busy !== null}
                        key={item.id}
                        onClick={() => addIntelligenceItem(item)}
                        type="button"
                      >
                        <span>{item.source_name}</span>
                        <strong>{item.title}</strong>
                        <small>加入来源</small>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="research-manual-source">
                  <span>手动补充公开来源</span>
                  <div>
                    <label>来源名称<input onChange={(event) => setManualSourceName(event.target.value)} value={manualSourceName} /></label>
                    <label>标题<input onChange={(event) => setManualTitle(event.target.value)} value={manualTitle} /></label>
                    <label className="manual-url">公开链接<input onChange={(event) => setManualUrl(event.target.value)} placeholder="https://" type="url" value={manualUrl} /></label>
                    <label>可信度<select onChange={(event) => setManualTrust(Number(event.target.value))} value={manualTrust}>{[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}/5</option>)}</select></label>
                    <label className="manual-excerpt">来源原文摘录<textarea onChange={(event) => setManualExcerpt(event.target.value)} placeholder="请粘贴至少 20 字、可由该链接核验的原文摘录" value={manualExcerpt} /></label>
                  </div>
                  <button className="ghost-button" disabled={busy !== null} onClick={addManualSource} type="button">{busy === "manual-source" ? "正在核验…" : "核验并加入"}</button>
                </div>
                <button
                  className="primary-button research-continue"
                  disabled={busy !== null || run.sources.length < 2}
                  onClick={() => void perform("sources-ready", () => resumeResearchWorkflow(run.id, "sources_ready"), "来源集合已确认。")}
                  type="button"
                >
                  来源够了，继续研究
                </button>
              </div>
            ) : null}

            {run.status === "waiting_for_model_approval" ? (
              <div className="growth-workflow-decision research-model-gate">
                <div className="workflow-decision-code">PAID MODEL CHECKPOINT</div>
                <h3>是否授权本次 Research Agent 使用 DeepSeek？</h3>
                <p>作用：综合多个公开来源、识别冲突，并更严格地区分事实、观点和推断。DeepSeek 使用钱包余额计费，本页不会静默调用。</p>
                <div className="workflow-disclosure">
                  <div><span>发送内容</span><strong>研究问题、范围、公开来源摘录</strong></div>
                  <div><span>授权步骤</span><strong>生成报告、校验引用</strong></div>
                  <div><span>不会发送</span><strong>API Key、私有文件、交易凭据</strong></div>
                </div>
                <div className="workflow-decision-actions">
                  <button className="primary-button" disabled={busy !== null} onClick={() => void perform("deepseek", () => resumeResearchWorkflow(run.id, "approve_deepseek"), "本次 DeepSeek 授权已记录。") } type="button">确认使用 DeepSeek</button>
                  <button disabled={busy !== null} onClick={() => void perform("mimo", () => resumeResearchWorkflow(run.id, "use_mimo"), "已改用 MiMo Token Plan。") } type="button">改用 MiMo</button>
                  <button disabled={busy !== null} onClick={() => void perform("local", () => resumeResearchWorkflow(run.id, "use_local"), "已改用本地 Qwen。") } type="button">仅本地处理</button>
                </div>
              </div>
            ) : null}

            {run.status === "waiting_for_report_review" && report ? (
              <div className="research-report-draft">
                <header>
                  <div>
                    <span>EDITABLE DRAFT · {providerName(run.provider_used)}</span>
                    <h3>审核研究报告</h3>
                  </div>
                  <small>所有事实引用必须指向上方来源；保存时后端会再次校验。</small>
                </header>
                <label>报告标题<input onChange={(event) => setReport({ ...report, title: event.target.value })} value={report.title} /></label>
                <label>执行摘要<textarea onChange={(event) => setReport({ ...report, executive_summary: event.target.value })} value={report.executive_summary} /></label>

                <section className="research-report-section facts">
                  <span>01 · 来源事实</span>
                  {report.facts.map((fact, index) => (
                    <div key={`${fact.source_refs.join("-")}-${index}`}>
                      <textarea onChange={(event) => updateReportCollection("facts", index, event.target.value)} value={fact.statement} />
                      <CitationLinks refs={fact.source_refs} />
                    </div>
                  ))}
                </section>
                <section className="research-report-section viewpoints">
                  <span>02 · 来源观点</span>
                  {report.viewpoints.map((viewpoint, index) => (
                    <div key={`${viewpoint.source_refs.join("-")}-${index}`}>
                      <small>{viewpoint.attribution}</small>
                      <textarea onChange={(event) => updateReportCollection("viewpoints", index, event.target.value)} value={viewpoint.statement} />
                      <CitationLinks refs={viewpoint.source_refs} />
                    </div>
                  ))}
                </section>
                <section className="research-report-section inferences">
                  <span>03 · Jarvis 推断</span>
                  {report.inferences.map((inference, index) => (
                    <div key={`${inference.basis_refs.join("-")}-${index}`}>
                      <small>置信度：{inference.confidence}</small>
                      <textarea onChange={(event) => updateReportCollection("inferences", index, event.target.value)} value={inference.statement} />
                      <CitationLinks refs={inference.basis_refs} />
                    </div>
                  ))}
                </section>
                <div className="research-report-lists">
                  <label>不确定性（每行一项）<textarea onChange={(event) => setReport({ ...report, uncertainties: splitLines(event.target.value) })} value={report.uncertainties.join("\n")} /></label>
                  <label>建议的下一步研究（每行一项）<textarea onChange={(event) => setReport({ ...report, recommended_actions: splitLines(event.target.value) })} value={report.recommended_actions.join("\n")} /></label>
                </div>
                <div className="research-report-actions">
                  <button disabled={busy !== null} onClick={() => void perform("save-report", async () => (await saveReport()) as ResearchWorkflowRun, "报告草稿已保存并通过引用校验。") } type="button">保存草稿</button>
                  <button className="primary-button" disabled={busy !== null} onClick={() => void confirmReport()} type="button">{busy === "confirm-report" ? "正在确认…" : "确认正式报告"}</button>
                  <button disabled={busy !== null} onClick={() => void perform("reject-report", () => resumeResearchWorkflow(run.id, "reject_report"), "报告草稿已放弃。") } type="button">放弃草稿</button>
                </div>
              </div>
            ) : null}

            {run.status === "completed" && run.report ? (
              <div className="growth-workflow-outcome research-outcome">
                <ShieldCheck size={22} />
                <div>
                  <span>FORMAL REPORT · {providerName(run.report.provider_used)}</span>
                  <h3>{run.report.title}</h3>
                  <p>{run.report.executive_summary}</p>
                  <small>已确认，但不会自动写入 Obsidian。投资相关内容不构成投资建议，也不会触发交易。</small>
                </div>
                <button disabled={busy !== null} onClick={() => void proposeGrowthDraft()} type="button"><FlaskConical size={15} />{busy === "orchestration-preview" ? "正在生成计划…" : "生成成长草稿计划"}</button>
                {run.report.status === "archived" || archiveOutcome ? (
                  <a className="primary-button" href={archiveOutcome?.target_obsidian_uri} rel="noreferrer">在 Obsidian 打开</a>
                ) : (
                  <button className="primary-button" disabled={busy !== null} onClick={() => void archiveReport()} type="button"><FileCheck2 size={15} />{busy === "archive" ? "正在写入…" : "确认归档到 Obsidian"}</button>
                )}
              </div>
            ) : null}

            {run.status === "rejected" || run.status === "cancelled" || run.status === "failed" ? (
              <div className="growth-workflow-outcome"><div><span>WORKFLOW CLOSED</span><h3>{statusText(run.status)}</h3><p>没有创建正式报告，也没有写入 Obsidian。</p></div></div>
            ) : null}

            {run.status === "completed" || run.status === "rejected" || run.status === "cancelled" || run.status === "failed" ? (
              <button className="ghost-button research-new" onClick={() => { setRun(null); setReport(null); setArchiveOutcome(null); setShowCreate(true); setSelectedItems([]); setNotice(null); }} type="button">开始新的研究</button>
            ) : (
              <button className="growth-workflow-cancel" disabled={busy !== null} onClick={() => void perform("cancel", () => cancelResearchWorkflow(run.id), "研究工作流已取消。") } type="button">取消本次研究</button>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}
