import {
  BookOpenCheck,
  BrainCircuit,
  Layers3,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";

import { AIStatus, type AIState } from "@/components/ai/AIStatus";

import type { ConversationDetail, ModelMode } from "@/lib/api";

export function ChatWorkspaceInspector({
  workspaceState,
  activeMode,
  detail,
  useKnowledge,
  sensitive,
}: {
  workspaceState: AIState;
  activeMode: { value: ModelMode; label: string; detail: string };
  detail: ConversationDetail | null;
  useKnowledge: boolean;
  sensitive: boolean;
}) {
  return (
    <aside className="workspace-inspector">
      <div className="workspace-core-presence">
        <span>今天的脉络</span>
        <AIStatus state={workspaceState} />
      </div>

      <div className="workspace-inspector-section">
        <span>当前对话</span>
        <div className="workspace-context-list">
          <div>
            <BrainCircuit aria-hidden="true" />
            <span>模型路由</span>
            <strong>{activeMode.label}</strong>
            <small>{activeMode.detail}</small>
          </div>
          <div>
            <Layers3 aria-hidden="true" />
            <span>对话上下文</span>
            <strong>{detail?.message_count ?? 0} MSG</strong>
            <small>
              {detail?.has_summary ? "摘要上下文已启用" : "保留原始上下文"}
            </small>
          </div>
          <div>
            <BookOpenCheck aria-hidden="true" />
            <span>知识边界</span>
            <strong>{useKnowledge ? "增强开启" : "未启用"}</strong>
            <small>按照笔记权限检索</small>
          </div>
          <div>
            <LockKeyhole aria-hidden="true" />
            <span>隐私边界</span>
            <strong>{sensitive ? "仅本地" : "标准"}</strong>
            <small>
              {sensitive ? "内容不会发送云端" : "按模型路由处理"}
            </small>
          </div>
        </div>
      </div>

      <div className="workspace-boundary-note">
        <ShieldCheck aria-hidden="true" />
        <div>
          <strong>数据与执行边界</strong>
          <p>
            Jarvis 会展示模型、知识来源和执行结果，但不会暴露私人推理正文，
            也不会未经确认执行高风险操作。
          </p>
        </div>
      </div>
    </aside>
  );
}
