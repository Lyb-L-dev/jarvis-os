/**
 * Computer-use API client.
 */

import { API_BASE_URL, request } from "./client";

export type ComputerStageInfo = {
  stage: number;
  label: string;
  allowed: string[];
  enabled: boolean;
};

export type ComputerUseStatus = {
  stage: number;
  ladder: ComputerStageInfo[];
  sandbox_root: string;
  permanent_blocks: string[];
  tools: Record<string, boolean>;
};

export type ComputerPlanStep = {
  tool_id: string;
  action: string;
  risk_level: string;
  requires_approval: boolean;
  target: string;
  preview_hint: string;
  blocked_by_stage?: boolean;
};

export type ComputerPlanResult = {
  instruction: string;
  generated_at: string;
  stage: number;
  steps: ComputerPlanStep[];
  note: string;
};

export async function getComputerUseStatus(
  signal?: AbortSignal,
): Promise<ComputerUseStatus> {
  return request<ComputerUseStatus>(
    `${API_BASE_URL}/computer-use/status`,
    {
      cache: "no-store",
      signal,
      action: "读取受控电脑操作状态",
    },
  );
}

export async function generateComputerPlan(
  instruction: string,
  signal?: AbortSignal,
): Promise<ComputerPlanResult> {
  return request<ComputerPlanResult>(
    `${API_BASE_URL}/computer-use/plan`,
    {
      method: "POST",
      body: { instruction },
      signal,
      action: "生成操作计划",
    },
  );
}
