import type { Goal, GrowthArea } from "@/lib/api";

import { areaOptions } from "@/components/growth/growth-utils";
import { GrowthGoalCard } from "@/components/growth/growth-goal-card";
import type { GoalForm } from "@/components/growth/use-goal-form";

export function GrowthGoalsView({
  goals,
  busy,
  goalForm,
  doAction,
  onAddTaskToGoal,
}: {
  goals: Goal[];
  busy: string | null;
  goalForm: GoalForm;
  doAction: (
    key: string,
    action: () => Promise<unknown>,
    success: string,
  ) => void;
  onAddTaskToGoal: (goal: Goal) => void;
}) {
  const {
    milestoneGoalId,
    setMilestoneGoalId,
    milestoneTitle,
    setMilestoneTitle,
    showGoalForm,
    setShowGoalForm,
    goalTitle,
    setGoalTitle,
    goalDescription,
    setGoalDescription,
    goalArea,
    setGoalArea,
    goalDate,
    setGoalDate,
    addGoal,
    addMilestone,
  } = goalForm;

  return (
    <section className="growth-goals-view">
      <div className="growth-goals-toolbar">
        <div>
          <div className="eyebrow">LONG-TERM DIRECTION</div>
          <h2>长期目标与里程碑</h2>
        </div>
        <button
          className="primary-button"
          onClick={() => setShowGoalForm((current) => !current)}
          type="button"
        >
          {showGoalForm ? "取消" : "+ 新建目标"}
        </button>
      </div>

      {showGoalForm ? (
        <div className="panel growth-goal-form">
          <label>
            目标名称
            <input
              aria-label="目标名称"
              onChange={(event) => setGoalTitle(event.target.value)}
              placeholder="例如：成为 AI 应用工程师"
              value={goalTitle}
            />
          </label>
          <label>
            领域
            <select
              onChange={(event) =>
                setGoalArea(event.target.value as GrowthArea)
              }
              value={goalArea}
            >
              {areaOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            目标日期
            <input
              onChange={(event) => setGoalDate(event.target.value)}
              type="date"
              value={goalDate}
            />
          </label>
          <label className="growth-form-wide">
            说明
            <input
              onChange={(event) => setGoalDescription(event.target.value)}
              placeholder="为什么重要，以及完成的判断标准"
              value={goalDescription}
            />
          </label>
          <button
            className="primary-button"
            disabled={!goalTitle.trim() || busy === "create-goal"}
            onClick={() => void addGoal()}
            type="button"
          >
            创建长期目标
          </button>
        </div>
      ) : null}

      <div className="growth-goal-list">
        {goals.length ? (
          goals.map((goal) => (
            <GrowthGoalCard
              doAction={doAction}
              goal={goal}
              key={goal.id}
              milestoneGoalId={milestoneGoalId}
              setMilestoneGoalId={setMilestoneGoalId}
              milestoneTitle={milestoneTitle}
              setMilestoneTitle={setMilestoneTitle}
              onAddMilestone={(goalId) => void addMilestone(goalId)}
              onCancelMilestone={() => setMilestoneGoalId(null)}
              onAddTaskToGoal={onAddTaskToGoal}
            />
          ))
        ) : (
          <div className="growth-large-empty">
            <strong>还没有长期目标</strong>
            <p>先建立一个真正重要的方向，再逐步拆成里程碑和任务。</p>
          </div>
        )}
      </div>
    </section>
  );
}
