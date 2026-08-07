"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  confirmMemoryCandidate,
  getMemoryCandidates,
  ignoreMemoryCandidate,
  isMemoryNetworkUnavailable,
  mergeMemoryCandidate,
  runMemoryExtraction,
  type MemoryCandidateKind,
  type MemoryEntityDTO,
  type MemoryNetworkCandidatesResponse,
} from "@/lib/api";

type CandidateRow = {
  key: string;
  id: string;
  kind: MemoryCandidateKind;
  title: string;
  detail: string;
  source: string;
  confidence?: number;
  importance?: number;
  happenedAt?: string;
};

function shortId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    memory: "已确认记忆",
    growth: "成长计划",
    english: "英语学习",
    intelligence: "情报",
    investment: "投资",
    conversation: "对话",
    manual: "手动",
  };
  return labels[source] ?? source;
}

/**
 * V3-1 memory candidate confirmation card.
 *
 * Renders extracted entity / relation / event candidates inside the dialog
 * workspace and lets the user confirm, ignore or merge them (merge is entity
 * only). Candidates never enter retrieval/context until confirmed; this card
 * is that confirmation gate.
 *
 * Degradation: when the backend returns 404 (feature flag off) or is
 * unreachable, the panel renders nothing and the classic chat view keeps
 * working untouched.
 */
export function MemoryCandidatePanel() {
  const [candidates, setCandidates] =
    useState<MemoryNetworkCandidatesResponse | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [mergingId, setMergingId] = useState<string | null>(null);
  const [mergeTarget, setMergeTarget] = useState<string>("");
  const [activeEntities, setActiveEntities] = useState<MemoryEntityDTO[]>([]);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const payload = await getMemoryCandidates("candidate", signal);
      setCandidates(payload);
    } catch (error) {
      if (isMemoryNetworkUnavailable(error)) {
        setDisabled(true);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function bootstrap(): Promise<void> {
      await refresh(controller.signal);
    }
    void bootstrap();
    return () => controller.abort();
  }, [refresh]);

  const rows: CandidateRow[] = useMemo(() => {
    if (candidates === null) return [];
    const nameById = new Map(
      candidates.entities.map((entity) => [entity.id, entity.name]),
    );
    const entityRows: CandidateRow[] = candidates.entities.map((entity) => ({
      key: `entity:${entity.id}`,
      id: entity.id,
      kind: "entity",
      title: entity.name,
      detail: entity.entity_type,
      source: sourceLabel(entity.source_kind),
      importance: entity.importance,
    }));
    const relationRows: CandidateRow[] = candidates.relations.map(
      (relation) => {
        const fromName = nameById.get(relation.from_entity_id) ?? shortId(relation.from_entity_id);
        const toName = nameById.get(relation.to_entity_id) ?? shortId(relation.to_entity_id);
        return {
          key: `relation:${relation.id}`,
          id: relation.id,
          kind: "relation" as const,
          title: relation.relation_type,
          detail: `${fromName} → ${toName}`,
          source: sourceLabel(relation.source_kind),
          confidence: relation.confidence,
        };
      },
    );
    const eventRows: CandidateRow[] = candidates.events.map((event) => ({
      key: `event:${event.id}`,
      id: event.id,
      kind: "event",
      title: event.summary,
      detail: event.event_type,
      source: sourceLabel(event.source_kind),
      happenedAt: event.happened_at,
    }));
    return [...entityRows, ...relationRows, ...eventRows];
  }, [candidates]);

  const hasCandidates = rows.length > 0;

  async function openMergePicker(entity: CandidateRow): Promise<void> {
    setNotice(null);
    setMergingId(entity.id);
    setMergeTarget("");
    try {
      const payload = await getMemoryCandidates("active");
      const targets = payload.entities.filter((item) => item.id !== entity.id);
      setActiveEntities(targets);
      if (targets.length > 0) setMergeTarget(targets[0].id);
    } catch {
      setActiveEntities([]);
      setNotice("无法加载可合并的实体");
      setMergingId(null);
    }
  }

  async function runExtraction(): Promise<void> {
    setExtracting(true);
    setNotice(null);
    try {
      const result = await runMemoryExtraction("all");
      await refresh();
      const total =
        result.created.entities +
        result.created.relations +
        result.created.events;
      setNotice(
        total > 0
          ? `抽取完成：新增实体 ${result.created.entities}、关系 ${result.created.relations}、事件 ${result.created.events}`
          : result.degraded
            ? "抽取完成，但非结构化抽取暂不可用（本地模型未就绪）"
            : "抽取完成：没有新的候选",
      );
    } catch (error) {
      if (isMemoryNetworkUnavailable(error)) setDisabled(true);
      else setNotice("抽取失败，请稍后重试");
    } finally {
      setExtracting(false);
    }
  }

  async function mutate(
    row: CandidateRow,
    action: "confirm" | "ignore",
  ): Promise<void> {
    setBusyId(row.id);
    setNotice(null);
    try {
      if (action === "confirm") await confirmMemoryCandidate(row.id);
      else await ignoreMemoryCandidate(row.id);
      await refresh();
      setNotice(action === "confirm" ? "已确认" : "已忽略");
    } catch {
      setNotice("操作失败，请稍后重试");
    } finally {
      setBusyId(null);
    }
  }

  async function doMerge(): Promise<void> {
    if (mergingId === null || mergeTarget === "") return;
    setBusyId(mergingId);
    setNotice(null);
    try {
      const result = await mergeMemoryCandidate(mergingId, mergeTarget);
      await refresh();
      setNotice(
        result.merged_ids.length > 0
          ? `已合并，迁移 ${result.merged_ids.length} 条关系`
          : "已合并",
      );
    } catch {
      setNotice("合并失败，请稍后重试");
    } finally {
      setBusyId(null);
      setMergingId(null);
      setActiveEntities([]);
    }
  }

  if (disabled || candidates === null || !hasCandidates) {
    return null;
  }

  return (
    <section
      className="memory-candidate-panel dialog-workspace-panel"
      aria-label="记忆候选确认"
    >
      <div className="dialog-workspace-cards">
        <div className="dialog-card memory-candidate-card">
          <div className="memory-candidate-header">
            <h3>记忆候选</h3>
            <div className="memory-candidate-header-actions">
              <button
                type="button"
                className="memory-candidate-action"
                disabled={extracting}
                onClick={() => void runExtraction()}
              >
                {extracting ? "抽取中…" : "抽取"}
              </button>
              <button
                type="button"
                className="memory-candidate-action"
                disabled={extracting}
                onClick={() => void refresh()}
              >
                刷新
              </button>
            </div>
          </div>
          <ul className="memory-candidate-list">
            {rows.map((row) => (
              <li key={row.key} className="memory-candidate-item">
                <div className="memory-candidate-main">
                  <span className="memory-candidate-kind">{row.kind}</span>
                  <div className="memory-candidate-text">
                    <strong>{row.title}</strong>
                    <span className="memory-candidate-detail">
                      {row.detail} · {row.source}
                      {row.confidence !== undefined
                        ? ` · 置信度 ${Math.round(row.confidence * 100)}%`
                        : ""}
                      {row.importance !== undefined
                        ? ` · 重要度 ${row.importance}/5`
                        : ""}
                      {row.happenedAt
                        ? ` · ${new Date(row.happenedAt).toLocaleDateString("zh-CN")}`
                        : ""}
                    </span>
                  </div>
                </div>
                <div className="memory-candidate-actions">
                  {mergingId === row.id ? (
                    <div className="memory-merge-picker">
                      <select
                        value={mergeTarget}
                        onChange={(event) => setMergeTarget(event.target.value)}
                        disabled={activeEntities.length === 0 || busyId !== null}
                        aria-label="合并目标实体"
                      >
                        {activeEntities.length === 0 ? (
                          <option value="">没有可合并的实体</option>
                        ) : (
                          activeEntities.map((entity) => (
                            <option key={entity.id} value={entity.id}>
                              {entity.name}
                            </option>
                          ))
                        )}
                      </select>
                      <button
                        type="button"
                        className="memory-candidate-action memory-candidate-action-primary"
                        disabled={mergeTarget === "" || busyId !== null}
                        onClick={() => void doMerge()}
                      >
                        合并
                      </button>
                      <button
                        type="button"
                        className="memory-candidate-action"
                        disabled={busyId !== null}
                        onClick={() => {
                          setMergingId(null);
                          setActiveEntities([]);
                        }}
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="memory-candidate-action memory-candidate-action-primary"
                        disabled={busyId !== null}
                        onClick={() => void mutate(row, "confirm")}
                      >
                        确认
                      </button>
                      {row.kind === "entity" ? (
                        <button
                          type="button"
                          className="memory-candidate-action"
                          disabled={busyId !== null}
                          onClick={() => void openMergePicker(row)}
                        >
                          合并
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="memory-candidate-action"
                        disabled={busyId !== null}
                        onClick={() => void mutate(row, "ignore")}
                      >
                        忽略
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
          {notice ? <p className="memory-candidate-notice">{notice}</p> : null}
        </div>
      </div>
    </section>
  );
}
