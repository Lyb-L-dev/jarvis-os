import { useState } from "react";

import {
  createGoal,
  createMilestone,
  type Goal,
  type GrowthArea,
} from "@/lib/api";

import {
  runAction,
  type GrowthFeedback,
} from "@/components/growth/growth-utils";

export function useGoalForm({
  feedback,
  refresh,
  goals,
}: {
  feedback: GrowthFeedback;
  refresh: () => Promise<void>;
  goals: Goal[];
}) {
  const [milestoneGoalId, setMilestoneGoalId] = useState<string | null>(null);
  const [milestoneTitle, setMilestoneTitle] = useState("");
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [goalTitle, setGoalTitle] = useState("");
  const [goalDescription, setGoalDescription] = useState("");
  const [goalArea, setGoalArea] = useState<GrowthArea>("career");
  const [goalDate, setGoalDate] = useState("");

  async function addGoal() {
    const title = goalTitle.trim();
    if (!title) return;
    await runAction(
      feedback,
      refresh,
      "create-goal",
      () =>
        createGoal({
          title,
          description: goalDescription.trim() || undefined,
          area: goalArea,
          target_date: goalDate || undefined,
        }),
      "长期目标已创建。",
    );
    setGoalTitle("");
    setGoalDescription("");
    setGoalDate("");
    setShowGoalForm(false);
  }

  async function addMilestone(goalId: string) {
    const title = milestoneTitle.trim();
    if (!title) return;
    await runAction(
      feedback,
      refresh,
      `milestone-${goalId}`,
      () =>
        createMilestone(goalId, {
          title,
          order_index:
            (goals.find((goal) => goal.id === goalId)?.milestones.length ?? 0) +
            1,
        }),
      "里程碑已添加。",
    );
    setMilestoneTitle("");
    setMilestoneGoalId(null);
  }

  return {
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
  };
}

export type GoalForm = ReturnType<typeof useGoalForm>;
