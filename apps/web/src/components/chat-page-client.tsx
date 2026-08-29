"use client";

import { useEffect, useState } from "react";

import { ChatWorkspace } from "@/components/chat-workspace";
import { DesktopFileHandoff } from "@/components/desktop-file-handoff";
import { TwinWorkspacePrototype } from "@/components/prototypes/twin-workspace-prototype";

type ChatRouteOptions = {
  variant: string | null;
  workspace: string | null;
};

const defaultOptions: ChatRouteOptions = {
  variant: null,
  workspace: null,
};

export function ChatPageClient() {
  const [options, setOptions] = useState<ChatRouteOptions>(defaultOptions);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      setOptions({
        variant: params.get("variant"),
        workspace: params.get("workspace"),
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  if (
    process.env.NODE_ENV !== "production" &&
    options.variant &&
    ["A", "B", "C"].includes(options.variant.toUpperCase())
  ) {
    return <TwinWorkspacePrototype />;
  }

  const convergenceEnabled =
    process.env.NEXT_PUBLIC_V3_PAGE_CONVERGENCE_ENABLED === "true" ||
    (process.env.NODE_ENV !== "production" && options.workspace === "twin");

  return (
    <>
      <ChatWorkspace layout={convergenceEnabled ? "twin" : "timeline"} />
      <DesktopFileHandoff />
    </>
  );
}
