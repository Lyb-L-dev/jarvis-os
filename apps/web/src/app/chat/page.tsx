import { ChatWorkspace } from "@/components/chat-workspace";
import { TwinWorkspacePrototype } from "@/components/prototypes/twin-workspace-prototype";

type ChatPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function ChatPage({ searchParams }: ChatPageProps) {
  const params = await searchParams;
  const requested = Array.isArray(params.variant)
    ? params.variant[0]
    : params.variant;
  const requestedWorkspace = Array.isArray(params.workspace)
    ? params.workspace[0]
    : params.workspace;

  if (
    process.env.NODE_ENV !== "production" &&
    requested &&
    ["A", "B", "C"].includes(requested.toUpperCase())
  ) {
    return <TwinWorkspacePrototype />;
  }

  const convergenceEnabled =
    process.env.V3_PAGE_CONVERGENCE_ENABLED === "true" ||
    (process.env.NODE_ENV !== "production" && requestedWorkspace === "twin");

  return <ChatWorkspace layout={convergenceEnabled ? "twin" : "timeline"} />;
}
