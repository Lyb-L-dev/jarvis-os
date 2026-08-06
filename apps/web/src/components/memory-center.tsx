"use client";

import {
  confirmMemory,
  createMemory,
  deleteMemory,
  getMemoryStats,
  listMemories,
  rejectMemory,
  updateMemory,
  type Memory,
  type MemoryStats,
  type MemoryStatus,
  type MemoryType,
} from "@/lib/api";
import { motion } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MemoryGalaxy } from "@/components/memory/MemoryGalaxy";
import { SemanticIndexPanel } from "@/components/semantic-index-panel";

const memoryTypes: Array<{ value: MemoryType; label: string }> = [
  { value: "profile", label: "个人资料" },
  { value: "preference", label: "偏好习惯" },
  { value: "episodic", label: "经历事件" },
  { value: "skill", label: "技能" },
  { value: "english", label: "英语学习" },
  { value: "career", label: "职业发展" },
  { value: "investment", label: "投资" },
  { value: "conversation_summary", label: "对话摘要" },
];

const statusLabels: Record<MemoryStatus, string> = {
  pending: "待确认",
  active: "使用中",
  inactive: "已停用",
  rejected: "已忽略",
  superseded: "已替代",
  deleted: "已删除",
};

const sourceLabels: Record<string, string> = {
  manual: "手动录入",
  conversation_manual: "从对话手动保存",
  conversation_auto: "从对话自动提取",
};

function typeLabel(value: MemoryType) {
  return memoryTypes.find((item) => item.value === value)?.label ?? value;
}

function memoryTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function MemoryCenter() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [allMemories, setAllMemories] = useState<Memory[]>([]);
  const [stats, setStats] = useState<MemoryStats>({
    pending: 0,
    active: 0,
    inactive: 0,
    total: 0,
  });
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<MemoryStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<MemoryType | "all">("all");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newContent, setNewContent] = useState("");
  const [newType, setNewType] = useState<MemoryType>("profile");
  const [newImportance, setNewImportance] = useState(3);
  const [newCloudAllowed, setNewCloudAllowed] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      try {
        const [items, galaxyItems, nextStats] = await Promise.all([
          listMemories({
            query,
            status: statusFilter,
            memoryType: typeFilter,
            signal,
          }),
          listMemories({ signal }),
          getMemoryStats(signal),
        ]);
        setMemories(items);
        setAllMemories(galaxyItems);
        setStats(nextStats);
        setError(null);
      } catch (loadError) {
        if (
          loadError instanceof DOMException &&
          loadError.name === "AbortError"
        ) {
          return;
        }
        setError(
          loadError instanceof Error ? loadError.message : "读取记忆失败",
        );
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [query, statusFilter, typeFilter],
  );

  const selectedMemory = useMemo(
    () =>
      memories.find((memory) => memory.id === selectedMemoryId) ??
      memories[0] ??
      null,
    [memories, selectedMemoryId],
  );

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      void load(controller.signal);
    }, 200);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [load]);

  async function runAction(
    memoryId: string,
    action: () => Promise<unknown>,
    successMessage: string,
  ) {
    setBusyId(memoryId);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(successMessage);
      await load();
    } catch (actionError) {
      setError(
        actionError instanceof Error ? actionError.message : "操作失败",
      );
    } finally {
      setBusyId(null);
    }
  }

  async function addMemory() {
    const content = newContent.trim();
    if (!content || busyId) return;
    setBusyId("new");
    setError(null);
    try {
      await createMemory({
        memory_type: newType,
        content,
        importance: newImportance,
        cloud_allowed: newCloudAllowed,
      });
      setNewContent("");
      setNewType("profile");
      setNewImportance(3);
      setNewCloudAllowed(false);
      setShowAdd(false);
      setNotice("长期记忆已保存。");
      await load();
    } catch (createError) {
      setError(
        createError instanceof Error ? createError.message : "新增记忆失败",
      );
    } finally {
      setBusyId(null);
    }
  }

  async function saveEdit(memory: Memory) {
    const content = editContent.trim();
    if (!content) return;
    await runAction(
      memory.id,
      () => updateMemory(memory.id, { content }),
      "记忆内容已更新，并保留了修改记录。",
    );
    setEditingId(null);
  }

  function askDelete(memory: Memory) {
    if (
      window.confirm(
        "确定删除这条长期记忆吗？\n\n删除后 Jarvis 不会再使用它。",
      )
    ) {
      void runAction(
        memory.id,
        () => deleteMemory(memory.id),
        "记忆已删除，Jarvis 不会再使用。",
      );
    }
  }

  function toggleCloud(memory: Memory) {
    if (
      !memory.cloud_allowed &&
      !window.confirm(
        "允许云端使用后，这条记忆可能随相关问题发送给 MiMo 或 DeepSeek。确定开启吗？",
      )
    ) {
      return;
    }
    void runAction(
      memory.id,
      () =>
        updateMemory(memory.id, {
          cloud_allowed: !memory.cloud_allowed,
        }),
      memory.cloud_allowed
        ? "已改为仅本机使用。"
        : "已允许在相关云端对话中使用。",
    );
  }

  return (
    <main className="dashboard memory-page memory-galaxy-page">
      <header className="memory-core-header">
        <div className="memory-core-title">
          <div className="memory-core-eyebrow">
            <i aria-hidden="true" />
            <span>CONTROLLED LONG-TERM MEMORY</span>
          </div>
          <h1>
            Memory <span>Galaxy</span>
          </h1>
          <p>Jarvis 对你的理解在这里生长，同时始终由你决定哪些记忆可以被使用。</p>
        </div>

        <div className="memory-core-state">
          <div className="memory-core-symbol" aria-hidden="true">
            <i />
            <motion.span
              animate={{ rotate: 360 }}
              transition={{ duration: 7, ease: "linear", repeat: Infinity }}
            />
          </div>
          <div>
            <span>LONG-TERM CORE</span>
            <strong>{stats.active} 条记忆已连接</strong>
            <small>LOCAL FIRST · HUMAN CONTROLLED</small>
          </div>
        </div>

        <button
          className="primary-button"
          onClick={() => setShowAdd((current) => !current)}
          type="button"
        >
          {showAdd ? "收起录入" : "+ 添加记忆"}
        </button>
      </header>

      <SemanticIndexPanel />

      <div className="specialist-section-label memory-section-label">
        <div>
          <span>MEMORY HEALTH</span>
          <strong>长期记忆状态</strong>
        </div>
        <p>只有你确认并启用的内容，才会参与 Jarvis 的回答</p>
      </div>

      <section className="memory-stats specialist-metrics" aria-label="记忆统计">
        <article>
          <span>全部记忆</span>
          <strong>{stats.total}</strong>
        </article>
        <article className="memory-stat-pending">
          <span>等待确认</span>
          <strong>{stats.pending}</strong>
        </article>
        <article className="memory-stat-active">
          <span>正在使用</span>
          <strong>{stats.active}</strong>
        </article>
        <article>
          <span>已停用</span>
          <strong>{stats.inactive}</strong>
        </article>
      </section>

      {showAdd ? (
        <section className="panel memory-add-panel">
          <div>
            <div className="eyebrow">MANUAL MEMORY</div>
            <h2>手动录入一条可靠记忆</h2>
          </div>
          <textarea
            aria-label="新记忆内容"
            maxLength={4000}
            onChange={(event) => setNewContent(event.target.value)}
            placeholder="例如：我更喜欢先看到结论，再看详细解释。"
            rows={3}
            value={newContent}
          />
          <div className="memory-form-row">
            <label>
              类型
              <select
                onChange={(event) =>
                  setNewType(event.target.value as MemoryType)
                }
                value={newType}
              >
                {memoryTypes.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              重要程度
              <select
                onChange={(event) =>
                  setNewImportance(Number(event.target.value))
                }
                value={newImportance}
              >
                {[1, 2, 3, 4, 5].map((value) => (
                  <option key={value} value={value}>
                    {value} / 5
                  </option>
                ))}
              </select>
            </label>
            <label className="memory-cloud-check">
              <input
                checked={newCloudAllowed}
                onChange={(event) =>
                  setNewCloudAllowed(event.target.checked)
                }
                type="checkbox"
              />
              允许在云端对话中使用
            </label>
            <button
              className="primary-button"
              disabled={!newContent.trim() || busyId === "new"}
              onClick={() => void addMemory()}
              type="button"
            >
              {busyId === "new" ? "保存中…" : "保存记忆"}
            </button>
          </div>
          <p className="memory-safety-note">
            密码、API Key、验证码、完整证件号、银行卡号和私钥会被系统拒绝保存。
          </p>
        </section>
      ) : null}

      <section className="memory-toolbar">
        <div className="memory-search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="搜索记忆"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索记忆内容"
            type="search"
            value={query}
          />
        </div>
        <select
          aria-label="按状态筛选"
          onChange={(event) =>
            setStatusFilter(event.target.value as MemoryStatus | "all")
          }
          value={statusFilter}
        >
          <option value="all">全部状态</option>
          <option value="pending">等待确认</option>
          <option value="active">正在使用</option>
          <option value="inactive">已停用</option>
          <option value="rejected">已忽略</option>
        </select>
        <select
          aria-label="按类型筛选"
          onChange={(event) =>
            setTypeFilter(event.target.value as MemoryType | "all")
          }
          value={typeFilter}
        >
          <option value="all">全部类型</option>
          {memoryTypes.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </section>

      {error ? <div className="memory-feedback memory-feedback-error">{error}</div> : null}
      {notice ? <div className="memory-feedback">{notice}</div> : null}

      <section className="memory-galaxy-layout" aria-live="polite">
        <MemoryGalaxy
          activeType={typeFilter}
          loading={loading}
          memories={allMemories}
          onSelectType={(type) => {
            setTypeFilter(type);
            setSelectedMemoryId(null);
          }}
        />

        <aside className="memory-inspector">
          <header className="memory-inspector-header">
            <div>
              <span>MEMORY DETAIL</span>
              <h2>
                {selectedMemory
                  ? typeLabel(selectedMemory.memory_type)
                  : "记忆观察台"}
              </h2>
            </div>
            <span>{memories.length} SIGNALS</span>
          </header>

          {selectedMemory ? (
            <article
              className={`memory-inspector-detail memory-card-${selectedMemory.status}`}
            >
              <div className="memory-card-head">
                <div>
                  <span className="memory-type">
                    {typeLabel(selectedMemory.memory_type)}
                  </span>
                  <span
                    className={`memory-status memory-status-${selectedMemory.status}`}
                  >
                    {statusLabels[selectedMemory.status]}
                  </span>
                </div>
                <time>{memoryTime(selectedMemory.updated_at)}</time>
              </div>

              {editingId === selectedMemory.id ? (
                <textarea
                  aria-label="编辑记忆内容"
                  autoFocus
                  maxLength={4000}
                  onChange={(event) => setEditContent(event.target.value)}
                  rows={5}
                  value={editContent}
                />
              ) : (
                <p>{selectedMemory.content}</p>
              )}

              <div className="memory-detail-properties">
                <div>
                  <span>SOURCE</span>
                  <strong>
                    {sourceLabels[selectedMemory.source_type] ??
                      selectedMemory.source_type}
                  </strong>
                </div>
                <div>
                  <span>CONFIDENCE</span>
                  <strong>{Math.round(selectedMemory.confidence * 100)}%</strong>
                </div>
                <div>
                  <span>IMPORTANCE</span>
                  <strong>{selectedMemory.importance} / 5</strong>
                </div>
              </div>

              <button
                className={`memory-cloud-boundary ${
                  selectedMemory.cloud_allowed ? "cloud-enabled" : ""
                }`}
                disabled={busyId === selectedMemory.id}
                onClick={() => toggleCloud(selectedMemory)}
                type="button"
              >
                <span>{selectedMemory.cloud_allowed ? "☁" : "⌂"}</span>
                <div>
                  <strong>
                    {selectedMemory.cloud_allowed ? "云端可用" : "仅本机使用"}
                  </strong>
                  <small>
                    {selectedMemory.cloud_allowed
                      ? "相关问题可能发送给 MiMo 或 DeepSeek"
                      : "内容不会离开这台电脑"}
                  </small>
                </div>
              </button>

              <div className="memory-actions">
                {selectedMemory.status === "pending" ? (
                  <>
                    <button
                      className="memory-confirm-button"
                      disabled={busyId === selectedMemory.id}
                      onClick={() =>
                        void runAction(
                          selectedMemory.id,
                          () => confirmMemory(selectedMemory.id),
                          "候选记忆已确认，今后可用于相关回答。",
                        )
                      }
                      type="button"
                    >
                      ✓ 确认使用
                    </button>
                    <button
                      disabled={busyId === selectedMemory.id}
                      onClick={() =>
                        void runAction(
                          selectedMemory.id,
                          () => rejectMemory(selectedMemory.id),
                          "候选记忆已忽略。",
                        )
                      }
                      type="button"
                    >
                      忽略
                    </button>
                  </>
                ) : null}

                {editingId === selectedMemory.id ? (
                  <>
                    <button
                      className="memory-confirm-button"
                      disabled={
                        !editContent.trim() || busyId === selectedMemory.id
                      }
                      onClick={() => void saveEdit(selectedMemory)}
                      type="button"
                    >
                      保存修改
                    </button>
                    <button onClick={() => setEditingId(null)} type="button">
                      取消
                    </button>
                  </>
                ) : (
                  <button
                    disabled={busyId === selectedMemory.id}
                    onClick={() => {
                      setEditingId(selectedMemory.id);
                      setEditContent(selectedMemory.content);
                    }}
                    type="button"
                  >
                    编辑
                  </button>
                )}

                {selectedMemory.status === "active" ? (
                  <button
                    disabled={busyId === selectedMemory.id}
                    onClick={() =>
                      void runAction(
                        selectedMemory.id,
                        () =>
                          updateMemory(selectedMemory.id, { status: "inactive" }),
                        "记忆已停用，Jarvis 暂时不会使用。",
                      )
                    }
                    type="button"
                  >
                    停用
                  </button>
                ) : null}

                {selectedMemory.status === "inactive" ? (
                  <button
                    className="memory-confirm-button"
                    disabled={busyId === selectedMemory.id}
                    onClick={() =>
                      void runAction(
                        selectedMemory.id,
                        () =>
                          updateMemory(selectedMemory.id, { status: "active" }),
                        "记忆已重新启用。",
                      )
                    }
                    type="button"
                  >
                    重新启用
                  </button>
                ) : null}

                <button
                  className="memory-delete-button"
                  disabled={busyId === selectedMemory.id}
                  onClick={() => askDelete(selectedMemory)}
                  type="button"
                >
                  删除
                </button>
              </div>
            </article>
          ) : (
            <div className="memory-inspector-empty">
              <div aria-hidden="true">◎</div>
              <strong>{loading ? "正在同步记忆…" : "你的记忆系统已准备好"}</strong>
              <p>
                {loading
                  ? "Jarvis 正在读取本地长期记忆。"
                  : "添加第一条记忆，或在对话中说“请记住……”。"}
              </p>
              {!loading ? (
                <button onClick={() => setShowAdd(true)} type="button">
                  添加第一条记忆
                </button>
              ) : null}
            </div>
          )}

          <section className="memory-signal-index">
            <header>
              <span>VISIBLE SIGNALS</span>
              <small>按当前搜索和筛选显示</small>
            </header>
            <div>
              {memories.map((memory) => (
                <button
                  aria-current={
                    selectedMemory?.id === memory.id ? "true" : undefined
                  }
                  key={memory.id}
                  onClick={() => setSelectedMemoryId(memory.id)}
                  type="button"
                >
                  <i className={`memory-signal-${memory.status}`} />
                  <span>
                    <strong>{typeLabel(memory.memory_type)}</strong>
                    <small>{memory.content}</small>
                  </span>
                  <time>{memoryTime(memory.updated_at)}</time>
                </button>
              ))}
              {!loading && memories.length === 0 ? (
                <p>当前轨道没有符合条件的记忆。</p>
              ) : null}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}
