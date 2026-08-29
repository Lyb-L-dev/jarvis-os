"use client";

import { useCallback, useEffect, useState } from "react";

import {
  commitLearningDayPlan,
  createLearningScheduleBlock,
  deactivateLearningScheduleBlock,
  getLearningDayStatus,
  getLearningScheduleBlocks,
  previewLearningDayPlan,
  type LearningDayPlanDraft,
  type LearningDayStatusView,
  type LearningScheduleBlockView,
} from "@/lib/api/learning";

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

const KIND_OPTIONS = [
  { value: "study", label: "学习" },
  { value: "practice", label: "实践" },
  { value: "career", label: "求职" },
  { value: "routine", label: "日常" },
] as const;

const KIND_LABELS: Record<string, string> = {
  study: "学习",
  practice: "实践",
  career: "求职",
  routine: "日常",
};

function minutesToTime(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function timeToMinutes(value: string): number {
  const [hours, minutes] = value.split(":").map(Number);
  return (hours || 0) * 60 + (minutes || 0);
}

export function LearningSchedule() {
  const [loadError, setLoadError] = useState<string | null>(null);
  const [blocks, setBlocks] = useState<LearningScheduleBlockView[]>([]);
  const [dayStatus, setDayStatus] = useState<LearningDayStatusView | null>(null);
  const [draft, setDraft] = useState<LearningDayPlanDraft | null>(null);

  const [weekday, setWeekday] = useState(0);
  const [startTime, setStartTime] = useState("09:30");
  const [endTime, setEndTime] = useState("11:30");
  const [kind, setKind] = useState<"study" | "practice" | "career" | "routine">("study");
  const [label, setLabel] = useState("");

  const [minimumDay, setMinimumDay] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [blockList, status] = await Promise.all([
      getLearningScheduleBlocks(),
      getLearningDayStatus(),
    ]);
    setBlocks(blockList);
    setDayStatus(status);
  }, []);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const [blockList, status] = await Promise.all([
          getLearningScheduleBlocks(),
          getLearningDayStatus(),
        ]);
        if (cancelled) return;
        setBlocks(blockList);
        setDayStatus(status);
      } catch (cause) {
        if (!cancelled) {
          setLoadError(cause instanceof Error ? cause.message : "连接失败");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <div className="learning-state">
        学习日程不可用：{loadError}
        （确认 .env 已打开 <code>v5_learning_schedule_enabled</code> 并重启 API）
      </div>
    );
  }

  return (
    <div className="learning-workspace">
      {error ? <div className="learning-error">{error}</div> : null}

      <section className="panel learning-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">TODAY · ADAPTIVE PLAN</div>
            <h3>今日任务</h3>
          </div>
          {dayStatus ? (
            <span className="learning-verification-status">
              {dayStatus.mode === "minimum_day" ? "Minimum Day" : dayStatus.mode === "normal" ? "正常" : "未生成"}
              {" · "}
              {dayStatus.completed_count}/{dayStatus.total_count} 已完成
            </span>
          ) : null}
        </div>

        {dayStatus && dayStatus.tasks.length > 0 ? (
          <ul className="learning-queue">
            {dayStatus.tasks.map((task) => (
              <li key={task.id} className="learning-queue-card">
                <div className="learning-module-head">
                  <strong className={task.status === "done" ? "learning-task-done" : ""}>
                    {task.title}
                  </strong>
                  <span className="learning-module-meta">
                    {task.status === "done" ? "✓ 已完成" : "进行中"} · 约 {task.estimated_minutes} 分钟
                  </span>
                </div>
                <p className="learning-concepts">
                  计划写入成长中心账本，执行与计时请在 /growth 处理。
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="learning-hint">
            今天还没有生成计划。先在下方配置作息块，然后「生成预览」确认内容，再「提交计划」。
          </p>
        )}

        <div className="learning-plan-actions">
          <label className="learning-minimum-toggle">
            <input
              type="checkbox"
              checked={minimumDay}
              onChange={(event) => setMinimumDay(event.target.checked)}
            />
            Minimum Day（25 分钟学习 + 25 分钟实践 + 1 个求职动作）
          </label>
          <button
            type="button"
            className="ghost-button"
            disabled={busy}
            onClick={() =>
              run(async () => {
                setDraft(await previewLearningDayPlan({ minimum_day: minimumDay }));
                await refresh();
              })
            }
          >
            生成预览
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={busy || !draft}
            onClick={() =>
              run(async () => {
                await commitLearningDayPlan({ minimum_day: minimumDay });
                setDraft(null);
                await refresh();
              })
            }
          >
            提交计划
          </button>
        </div>

        {draft ? (
          <div className="learning-draft">
            {draft.auto_minimum ? (
              <p className="learning-item-feedback">
                昨日计划未执行，已自动切换 Minimum Day：目标是不断档，不是补偿失败。
              </p>
            ) : null}
            <ul className="learning-queue">
              {draft.items.map((item, index) => (
                <li key={index} className="learning-queue-card">
                  <div className="learning-module-head">
                    <strong>{item.title}</strong>
                    <span className="learning-module-meta">
                      {KIND_LABELS[item.kind] ?? item.kind} · 约 {item.estimated_minutes} 分钟
                    </span>
                  </div>
                  <p className="learning-concepts">{item.detail}</p>
                </li>
              ))}
            </ul>
            <p className="learning-hint">{draft.generation_note}</p>
          </div>
        ) : null}
      </section>

      <section className="panel learning-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">AVAILABILITY · WEEKLY</div>
            <h3>作息块设置</h3>
          </div>
        </div>
        {blocks.length === 0 ? (
          <p className="learning-hint">
            还没有作息块。按星期几配置固定安排，例如周一 09:30–11:30 学习。
          </p>
        ) : (
          <ul className="learning-module-list">
            {blocks.map((block) => (
              <li key={block.id} className="learning-block-row">
                <span className="learning-block-time">
                  {WEEKDAYS[block.weekday]}{" "}
                  {minutesToTime(block.start_minutes)}–{minutesToTime(block.end_minutes)}
                </span>
                <span className="learning-grade-chip">{KIND_LABELS[block.kind] ?? block.kind}</span>
                {block.label ? (
                  <span className="learning-block-label">{block.label}</span>
                ) : null}
                <button
                  type="button"
                  className="ghost-button"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      await deactivateLearningScheduleBlock(block.id);
                      await refresh();
                    })
                  }
                >
                  停用
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="learning-block-form">
          <select
            className="learning-input learning-select"
            value={weekday}
            onChange={(event) => setWeekday(Number(event.target.value))}
          >
            {WEEKDAYS.map((name, index) => (
              <option key={index} value={index}>
                {name}
              </option>
            ))}
          </select>
          <input
            type="time"
            className="learning-input"
            value={startTime}
            onChange={(event) => setStartTime(event.target.value)}
          />
          <input
            type="time"
            className="learning-input"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
          />
          <select
            className="learning-input learning-select"
            value={kind}
            onChange={(event) =>
              setKind(event.target.value as "study" | "practice" | "career" | "routine")
            }
          >
            {KIND_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            className="learning-input"
            placeholder="备注，例如 上午学习"
            value={label}
            maxLength={80}
            onChange={(event) => setLabel(event.target.value)}
          />
          <button
            type="button"
            className="primary-button"
            disabled={busy || startTime >= endTime}
            onClick={() =>
              run(async () => {
                await createLearningScheduleBlock({
                  weekday,
                  start_minutes: timeToMinutes(startTime),
                  end_minutes: timeToMinutes(endTime),
                  kind,
                  label: label.trim(),
                });
                setLabel("");
                await refresh();
              })
            }
          >
            添加作息块
          </button>
        </div>
      </section>
    </div>
  );
}
