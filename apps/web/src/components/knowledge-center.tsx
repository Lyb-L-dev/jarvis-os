"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { CommandTelemetry } from "@/components/command-telemetry";
import { SemanticIndexPanel } from "@/components/semantic-index-panel";

import {
  acceptKnowledgeInsight,
  archiveAutomaticKnowledge,
  archiveKnowledgeCapture,
  archiveKnowledgeSource,
  configureKnowledgeVault,
  discardKnowledgeCapture,
  extractKnowledgeInsights,
  getKnowledgeStatus,
  ignoreKnowledgeInsight,
  listKnowledgeArchiveCandidates,
  listKnowledgeArchiveRecords,
  listKnowledgeCaptures,
  listKnowledgeDocuments,
  listKnowledgeInsights,
  scanKnowledgeVault,
  updateKnowledgeCapture,
  updateKnowledgeDocument,
  type KnowledgeArchiveCandidate,
  type KnowledgeArchiveRecord,
  type KnowledgeCaptureDraft,
  type KnowledgeDocument,
  type KnowledgeInsightCandidate,
  type KnowledgeVaultStatus,
} from "@/lib/api";

const TYPE_LABELS: Record<string, string> = {
  inbox: "收件箱",
  memory: "长期记忆",
  conversation: "对话",
  intelligence: "情报",
  english: "英语",
  investment: "投资研究",
  weekly_review: "周复盘",
  review: "待审核",
  archive: "归档",
  other: "其他",
};

const SOURCE_LABELS: Record<string, string> = {
  memory: "长期记忆",
  daily_brief: "每日情报",
  weekly_review: "周复盘",
  english_session: "英语会话",
  investment_thesis: "投资理由",
  investment_review: "投资复盘",
};

const ARCHIVE_STATUS_LABELS: Record<string, string> = {
  synced: "已同步",
  conflict: "待审核冲突",
  user_modified: "用户已修改",
  missing: "目标文件缺失",
};

const INSIGHT_TYPE_LABELS: Record<
  KnowledgeInsightCandidate["candidate_type"],
  string
> = {
  memory: "长期记忆",
  task: "行动任务",
  question: "待核验问题",
};

function formatDate(value?: string | null) {
  if (!value) return "尚未扫描";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function KnowledgeCenter() {
  const [status, setStatus] = useState<KnowledgeVaultStatus | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [candidates, setCandidates] = useState<KnowledgeArchiveCandidate[]>([]);
  const [archiveRecords, setArchiveRecords] = useState<
    KnowledgeArchiveRecord[]
  >([]);
  const [captures, setCaptures] = useState<KnowledgeCaptureDraft[]>([]);
  const [insights, setInsights] = useState<KnowledgeInsightCandidate[]>([]);
  const [vaultPath, setVaultPath] = useState("");
  const [query, setQuery] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const nextStatus = await getKnowledgeStatus(signal);
      setStatus(nextStatus);
      setVaultPath(nextStatus.vault_path ?? "");
      if (nextStatus.configured) {
        const [
          nextDocuments,
          nextCandidates,
          nextRecords,
          nextCaptures,
          nextInsights,
        ] =
          await Promise.all([
            listKnowledgeDocuments("", "", signal),
            listKnowledgeArchiveCandidates(signal),
            listKnowledgeArchiveRecords(signal),
            listKnowledgeCaptures(signal),
            listKnowledgeInsights(signal),
          ]);
        setDocuments(nextDocuments);
        setCandidates(nextCandidates);
        setArchiveRecords(nextRecords);
        setCaptures(nextCaptures);
        setInsights(nextInsights);
      }
      setError(null);
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "无法读取知识库状态。");
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

  async function connectVault(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!vaultPath.trim()) return;
    setBusy("connect");
    setNotice(null);
    setError(null);
    try {
      const nextStatus = await configureKnowledgeVault(vaultPath.trim());
      setStatus(nextStatus);
      setVaultPath(nextStatus.vault_path ?? vaultPath.trim());
      setDocuments(await listKnowledgeDocuments());
      setNotice("Vault 已连接，只会访问其中的 Jarvis/ 子目录。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "连接 Vault 失败。");
    } finally {
      setBusy(null);
    }
  }

  async function scanVault() {
    setBusy("scan");
    setNotice(null);
    setError(null);
    try {
      const result = await scanKnowledgeVault();
      await load();
      setNotice(
        `扫描完成：新增 ${result.created}，更新 ${result.updated}，未变化 ${result.unchanged}，移除 ${result.removed}。`,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "扫描失败。");
    } finally {
      setBusy(null);
    }
  }

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("search");
    setError(null);
    try {
      setDocuments(await listKnowledgeDocuments(query, documentType));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "搜索失败。");
    } finally {
      setBusy(null);
    }
  }

  async function runAutomaticArchive() {
    setBusy("auto-archive");
    setNotice(null);
    setError(null);
    try {
      const result = await archiveAutomaticKnowledge();
      await load();
      setNotice(
        `自动归档完成：处理 ${result.processed} 项，新增 ${result.created}，更新 ${result.updated}，冲突 ${result.conflicts}。`,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "自动归档失败。");
    } finally {
      setBusy(null);
    }
  }

  async function archiveCandidate(candidate: KnowledgeArchiveCandidate) {
    setBusy(candidate.source_id);
    setNotice(null);
    setError(null);
    try {
      const result = await archiveKnowledgeSource(
        candidate.source_type,
        candidate.source_id,
      );
      await load();
      if (result.status === "conflict") {
        setNotice("检测到 Obsidian 手工修改，新版本已放入 _review，原笔记未覆盖。");
      } else if (result.status === "unchanged") {
        setNotice("内容没有变化，没有重复创建文件。");
      } else {
        setNotice(`已${result.status === "created" ? "创建" : "更新"} Obsidian 笔记。`);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "归档失败。");
    } finally {
      setBusy(null);
    }
  }

  async function updateDocumentPermission(
    document: KnowledgeDocument,
    field: "retrieval_enabled" | "cloud_allowed",
    value: boolean,
  ) {
    if (
      field === "cloud_allowed" &&
      value &&
      !window.confirm(
        "允许云端后，这篇笔记的相关摘录可能发送给 MiMo 或经你确认后的 DeepSeek。\n\n确定允许吗？",
      )
    ) {
      return;
    }
    setBusy(`permission-${document.id}`);
    setNotice(null);
    setError(null);
    try {
      const updated = await updateKnowledgeDocument(document.id, {
        [field]: value,
      });
      setDocuments((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      const nextStatus = await getKnowledgeStatus();
      setStatus(nextStatus);
      setNotice(
        field === "cloud_allowed"
          ? value
            ? "已允许这篇笔记用于云端回答。"
            : "这篇笔记现在仅能由本地模型使用。"
          : value
            ? "这篇笔记已加入对话检索。"
            : "这篇笔记已退出对话检索。",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "更新笔记权限失败。");
    } finally {
      setBusy(null);
    }
  }

  function editCapture(
    captureId: string,
    changes: Partial<Pick<KnowledgeCaptureDraft, "title" | "content">>,
  ) {
    setCaptures((current) =>
      current.map((item) =>
        item.id === captureId
          ? { ...item, ...changes, insights_extracted_at: null }
          : item,
      ),
    );
  }

  async function saveCapture(capture: KnowledgeCaptureDraft) {
    setBusy(`capture-save-${capture.id}`);
    setNotice(null);
    setError(null);
    try {
      const updated = await updateKnowledgeCapture(capture.id, {
        title: capture.title,
        content: capture.content,
      });
      setCaptures((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice("知识草稿已保存，尚未写入 Obsidian。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存知识草稿失败。");
    } finally {
      setBusy(null);
    }
  }

  async function confirmCapture(capture: KnowledgeCaptureDraft) {
    setBusy(`capture-archive-${capture.id}`);
    setNotice(null);
    setError(null);
    try {
      await updateKnowledgeCapture(capture.id, {
        title: capture.title,
        content: capture.content,
      });
      const result = await archiveKnowledgeCapture(capture.id);
      await load();
      setNotice(
        result.status === "conflict"
          ? "原笔记已被修改，新版本已放入 _review，原文件没有覆盖。"
          : "知识草稿已确认并写入 Obsidian/Conversations。",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "归档知识草稿失败。");
    } finally {
      setBusy(null);
    }
  }

  async function discardCapture(capture: KnowledgeCaptureDraft) {
    if (!window.confirm("放弃这份草稿？原始对话不会被删除。")) return;
    setBusy(`capture-discard-${capture.id}`);
    setNotice(null);
    setError(null);
    try {
      await discardKnowledgeCapture(capture.id);
      setCaptures((current) =>
        current.filter((item) => item.id !== capture.id),
      );
      setNotice("草稿已放弃，原始对话保持不变。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "放弃知识草稿失败。");
    } finally {
      setBusy(null);
    }
  }

  async function extractInsights(capture: KnowledgeCaptureDraft) {
    setBusy(`capture-extract-${capture.id}`);
    setNotice(null);
    setError(null);
    try {
      const updated =
        capture.status === "archived"
          ? capture
          : await updateKnowledgeCapture(capture.id, {
              title: capture.title,
              content: capture.content,
            });
      const extracted = await extractKnowledgeInsights(updated.id);
      await load();
      setNotice(
        extracted.length
          ? `本地 Qwen 已提出 ${extracted.length} 条候选，请逐条确认。`
          : "本地 Qwen 没有发现足够明确、值得长期保留的内容。",
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "本地提炼知识候选失败。",
      );
    } finally {
      setBusy(null);
    }
  }

  async function acceptInsight(candidate: KnowledgeInsightCandidate) {
    setBusy(`insight-accept-${candidate.id}`);
    setNotice(null);
    setError(null);
    try {
      await acceptKnowledgeInsight(candidate.id);
      setInsights((current) =>
        current.filter((item) => item.id !== candidate.id),
      );
      setNotice(
        candidate.candidate_type === "memory"
          ? "已保存为经过你确认的长期记忆。"
          : candidate.candidate_type === "task"
            ? "已创建成长任务，可在任务页面继续管理。"
            : "已创建待核验任务，结论不会被当成已确认事实。",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认知识候选失败。");
    } finally {
      setBusy(null);
    }
  }

  async function ignoreInsight(candidate: KnowledgeInsightCandidate) {
    setBusy(`insight-ignore-${candidate.id}`);
    setNotice(null);
    setError(null);
    try {
      await ignoreKnowledgeInsight(candidate.id);
      setInsights((current) =>
        current.filter((item) => item.id !== candidate.id),
      );
      setNotice("这条候选已忽略，不会进入记忆或任务。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "忽略知识候选失败。");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="knowledge-center">
      <CommandTelemetry
        label="知识库实时状态"
        items={[
          {
            label: "BRIDGE",
            value: status?.connected ? "已连接" : "未连接",
            detail: "Obsidian · Jarvis/ 受限目录",
            tone: status?.connected ? "green" : "red",
          },
          {
            label: "DOCUMENTS",
            value: status?.document_count ?? 0,
            detail: `${status?.retrieval_enabled_count ?? 0} 篇参与检索`,
          },
          {
            label: "DRAFT QUEUE",
            value: captures.length,
            detail: "对话知识待确认",
            tone: captures.length ? "amber" : "cyan",
          },
          {
            label: "CLOUD GATE",
            value: status?.cloud_allowed_count ?? 0,
            detail: "逐篇明确授权",
            tone: "violet",
          },
        ]}
      />

      <SemanticIndexPanel compact />

      <section className="panel knowledge-connection-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">OBSIDIAN KNOWLEDGE BRIDGE</div>
            <h3>本地知识库连接</h3>
          </div>
          <span
            className={`knowledge-state ${
              status?.connected ? "connected" : "disconnected"
            }`}
          >
            {status?.connected ? "已连接" : "未连接"}
          </span>
        </div>

        <form className="knowledge-connect-form" onSubmit={connectVault}>
          <label>
            <span>Obsidian Vault 路径</span>
            <input
              onChange={(event) => setVaultPath(event.target.value)}
              placeholder="例如 F:\Obsidian\MyVault"
              value={vaultPath}
            />
          </label>
          <button disabled={busy !== null || !vaultPath.trim()} type="submit">
            {busy === "connect" ? "验证中…" : "验证并连接"}
          </button>
          <button
            className="primary-action"
            disabled={busy !== null || !status?.connected}
            onClick={() => void scanVault()}
            type="button"
          >
            {busy === "scan" ? "扫描中…" : "立即扫描"}
          </button>
        </form>

        <div className="knowledge-summary-grid">
          <article>
            <span>受限根目录</span>
            <strong>{status?.root_folder ?? "Jarvis"}/</strong>
            <small>不会读取 Vault 其他笔记或 .obsidian</small>
          </article>
          <article>
            <span>已索引笔记</span>
            <strong>{status?.document_count ?? 0}</strong>
            <small>目前仅扫描 Markdown</small>
          </article>
          <article>
            <span>对话检索</span>
            <strong>{status?.retrieval_enabled_count ?? 0} 篇</strong>
            <small>本地模式可以使用已启用笔记</small>
          </article>
          <article>
            <span>云端授权</span>
            <strong>{status?.cloud_allowed_count ?? 0} 篇</strong>
            <small>只有这些笔记可发送给 MiMo / DeepSeek</small>
          </article>
          <article>
            <span>最近扫描</span>
            <strong>{formatDate(status?.last_scanned_at)}</strong>
            <small>手工修改后可重新扫描</small>
          </article>
        </div>

        {status?.allowed_directories.length ? (
          <div className="knowledge-directory-list">
            {status.allowed_directories.map((directory) => (
              <code key={directory}>Jarvis/{directory}</code>
            ))}
          </div>
        ) : null}
        {notice ? <div className="backup-notice success">{notice}</div> : null}
        {error ? <div className="backup-notice error">{error}</div> : null}
        {status?.last_error ? (
          <div className="backup-notice warning">{status.last_error}</div>
        ) : null}
      </section>

      <section className="panel knowledge-capture-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">CONVERSATION KNOWLEDGE CAPTURE</div>
            <h3>对话知识草稿</h3>
          </div>
          <span>{captures.length} 份待确认</span>
        </div>

        <p className="knowledge-capture-intro">
          草稿只由本地 Qwen 生成。你可以修改后确认写入 Obsidian，也可以放弃；
          未确认草稿不会进入对话检索。已归档但尚未提炼的内容仍会保留提炼入口。
        </p>

        <div className="knowledge-capture-list">
          {captures.length ? (
            captures.map((capture) => (
              <article className="knowledge-capture-card" key={capture.id}>
                <div className="knowledge-capture-meta">
                  <span>{capture.message_count} 条对话消息</span>
                  <small>
                    {capture.status === "archived"
                      ? "已写入 Obsidian，尚未提炼"
                      : capture.status === "conflict"
                      ? "存在冲突，修改后可重新确认"
                      : "仅本地草稿"}
                  </small>
                </div>
                <input
                  aria-label="知识草稿标题"
                  disabled={busy !== null || capture.status === "archived"}
                  maxLength={200}
                  onChange={(event) =>
                    editCapture(capture.id, { title: event.target.value })
                  }
                  value={capture.title}
                />
                <textarea
                  aria-label="知识草稿内容"
                  disabled={busy !== null || capture.status === "archived"}
                  maxLength={20000}
                  onChange={(event) =>
                    editCapture(capture.id, { content: event.target.value })
                  }
                  rows={12}
                  value={capture.content}
                />
                <div className="knowledge-capture-actions">
                  <button
                    className="insight-action"
                    disabled={
                      busy !== null ||
                      Boolean(capture.insights_extracted_at) ||
                      !capture.title.trim() ||
                      !capture.content.trim()
                    }
                    onClick={() => void extractInsights(capture)}
                    type="button"
                  >
                    {busy === `capture-extract-${capture.id}`
                      ? "本地提炼中…"
                      : capture.insights_extracted_at
                        ? "已完成提炼"
                        : "提取记忆与行动"}
                  </button>
                  <button
                    disabled={
                      busy !== null ||
                      capture.status === "archived" ||
                      !capture.title.trim() ||
                      !capture.content.trim()
                    }
                    onClick={() => void saveCapture(capture)}
                    type="button"
                  >
                    {busy === `capture-save-${capture.id}`
                      ? "保存中…"
                      : "保存草稿"}
                  </button>
                  <button
                    className="primary-action"
                    disabled={
                      busy !== null ||
                      capture.status === "archived" ||
                      !capture.title.trim() ||
                      !capture.content.trim()
                    }
                    onClick={() => void confirmCapture(capture)}
                    type="button"
                  >
                    {busy === `capture-archive-${capture.id}`
                      ? "写入中…"
                      : "确认并写入 Obsidian"}
                  </button>
                  <button
                    className="danger-action"
                    disabled={busy !== null || capture.status === "archived"}
                    onClick={() => void discardCapture(capture)}
                    type="button"
                  >
                    放弃草稿
                  </button>
                </div>
              </article>
            ))
          ) : (
            <div className="backup-empty">
              暂无草稿。在 Chat 右上角点击“沉淀知识”后，本地 Qwen 会在这里生成
              一份可编辑草稿。
            </div>
          )}
        </div>
      </section>

      <section className="panel knowledge-insight-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">LOCAL KNOWLEDGE DISTILLATION</div>
            <h3>知识提炼候选</h3>
          </div>
          <span>{insights.length} 条待确认</span>
        </div>

        <p className="knowledge-capture-intro">
          候选只由本地 Qwen 从知识草稿中提取。系统不会自动写入长期记忆或创建任务；
          只有你逐条确认后，候选才会生效。
        </p>

        <div className="knowledge-insight-list">
          {insights.length ? (
            insights.map((candidate) => (
              <article className="knowledge-insight-card" key={candidate.id}>
                <div className="knowledge-insight-meta">
                  <span>{INSIGHT_TYPE_LABELS[candidate.candidate_type]}</span>
                  <small>来源：{candidate.source_title}</small>
                </div>
                <h4>{candidate.title}</h4>
                <p>{candidate.content}</p>
                {candidate.rationale ? (
                  <div className="knowledge-insight-rationale">
                    提炼理由：{candidate.rationale}
                  </div>
                ) : null}
                <div className="knowledge-insight-actions">
                  <button
                    className="primary-action"
                    disabled={busy !== null}
                    onClick={() => void acceptInsight(candidate)}
                    type="button"
                  >
                    {busy === `insight-accept-${candidate.id}`
                      ? "确认中…"
                      : candidate.candidate_type === "memory"
                        ? "保存为长期记忆"
                        : candidate.candidate_type === "task"
                          ? "创建成长任务"
                          : "创建核验任务"}
                  </button>
                  <button
                    disabled={busy !== null}
                    onClick={() => void ignoreInsight(candidate)}
                    type="button"
                  >
                    {busy === `insight-ignore-${candidate.id}`
                      ? "忽略中…"
                      : "忽略"}
                  </button>
                </div>
              </article>
            ))
          ) : (
            <div className="backup-empty">
              暂无待确认候选。先在上方知识草稿中点击“提取记忆与行动”。
            </div>
          )}
        </div>
      </section>

      <section className="panel knowledge-archive-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">CONTROLLED ARCHIVE</div>
            <h3>受控归档</h3>
          </div>
          <button
            className="primary-action"
            disabled={busy !== null || !status?.connected}
            onClick={() => void runAutomaticArchive()}
            type="button"
          >
            {busy === "auto-archive" ? "归档中…" : "同步记忆与每日情报"}
          </button>
        </div>

        <div className="knowledge-archive-summary">
          <article>
            <span>自动归档</span>
            <strong>已确认记忆 · 每日情报</strong>
            <small>后台定期同步，重复内容不会重复建文件</small>
          </article>
          <article>
            <span>手动确认</span>
            <strong>{candidates.length} 项候选</strong>
            <small>周复盘、英语和投资研究由你决定</small>
          </article>
          <article>
            <span>需要处理</span>
            <strong>
              {
                archiveRecords.filter((record) =>
                  ["conflict", "user_modified", "missing"].includes(
                    record.status,
                  ),
                ).length
              }{" "}
              项
            </strong>
            <small>用户修改永远不会被静默覆盖</small>
          </article>
        </div>

        <div className="knowledge-candidate-list">
          <div className="knowledge-list-title">
            <h4>手动归档候选</h4>
            <span>最近 {candidates.length} 项</span>
          </div>
          {candidates.length ? (
            candidates.map((candidate) => (
              <article className="knowledge-candidate" key={candidate.source_id}>
                <div>
                  <span>
                    {SOURCE_LABELS[candidate.source_type] ?? candidate.source_type}
                  </span>
                  <h4>{candidate.title}</h4>
                  <p>{candidate.summary}</p>
                  {candidate.archive_status ? (
                    <small>
                      {ARCHIVE_STATUS_LABELS[candidate.archive_status] ??
                        candidate.archive_status}
                    </small>
                  ) : null}
                </div>
                <button
                  disabled={busy !== null}
                  onClick={() => void archiveCandidate(candidate)}
                  type="button"
                >
                  {busy === candidate.source_id
                    ? "处理中…"
                    : candidate.archive_status
                      ? "检查更新"
                      : "归档"}
                </button>
              </article>
            ))
          ) : (
            <div className="backup-empty">
              暂无需要手动归档的周复盘、英语会话或投资研究。
            </div>
          )}
        </div>

        {archiveRecords.some((record) => record.status !== "synced") ? (
          <div className="knowledge-review-list">
            <div className="knowledge-list-title">
              <h4>冲突与待审核</h4>
              <span>不会自动覆盖</span>
            </div>
            {archiveRecords
              .filter((record) => record.status !== "synced")
              .map((record) => (
                <article className="knowledge-review-row" key={record.id}>
                  <div>
                    <strong>
                      {SOURCE_LABELS[record.source_type] ?? record.source_type}
                    </strong>
                    <code>{record.target_relative_path}</code>
                    <span>
                      {ARCHIVE_STATUS_LABELS[record.status] ?? record.status}
                    </span>
                  </div>
                  <div>
                    <a href={record.target_obsidian_uri}>打开原笔记</a>
                    {record.review_obsidian_uri ? (
                      <a href={record.review_obsidian_uri}>打开待审核版本</a>
                    ) : null}
                  </div>
                </article>
              ))}
          </div>
        ) : null}
      </section>

      <section className="panel knowledge-search-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">LOCAL SEARCH</div>
            <h3>搜索知识笔记</h3>
          </div>
          <span>{documents.length} 条结果</span>
        </div>

        <form className="knowledge-search-form" onSubmit={search}>
          <input
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索标题、路径或正文"
            value={query}
          />
          <select
            onChange={(event) => setDocumentType(event.target.value)}
            value={documentType}
          >
            <option value="">全部类型</option>
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <button disabled={busy !== null} type="submit">
            {busy === "search" ? "搜索中…" : "搜索"}
          </button>
        </form>

        <div className="knowledge-document-list">
          {documents.length ? (
            documents.map((document) => (
              <article className="knowledge-document" key={document.id}>
                <div>
                  <span>{TYPE_LABELS[document.document_type] ?? "其他"}</span>
                  <h4>{document.title}</h4>
                  <code>{document.relative_path}</code>
                  <p>{document.content_preview || "这篇笔记暂时没有正文。"}</p>
                </div>
                <div className="knowledge-document-action">
                  <small>{formatDate(document.file_modified_at)}</small>
                  <div className="knowledge-permission-actions">
                    <button
                      className={document.retrieval_enabled ? "active" : ""}
                      disabled={busy !== null}
                      onClick={() =>
                        void updateDocumentPermission(
                          document,
                          "retrieval_enabled",
                          !document.retrieval_enabled,
                        )
                      }
                      type="button"
                    >
                      {document.retrieval_enabled ? "参与对话检索" : "不参与检索"}
                    </button>
                    <button
                      className={document.cloud_allowed ? "cloud-active" : ""}
                      disabled={busy !== null}
                      onClick={() =>
                        void updateDocumentPermission(
                          document,
                          "cloud_allowed",
                          !document.cloud_allowed,
                        )
                      }
                      type="button"
                    >
                      {document.cloud_allowed ? "允许云端" : "仅限本地"}
                    </button>
                  </div>
                  <a href={document.obsidian_uri}>在 Obsidian 中打开</a>
                </div>
              </article>
            ))
          ) : (
            <div className="backup-empty">
              {status?.connected
                ? "Jarvis/ 中还没有可搜索的 Markdown，或当前筛选没有结果。"
                : "连接 Vault 后即可扫描和搜索。"}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
