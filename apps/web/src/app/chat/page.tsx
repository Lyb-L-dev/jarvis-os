import { ChatWorkspace } from "@/components/chat-workspace";
import { ChatV3Prototype } from "@/app/chat/v3-chat-prototype";

export default async function ChatPage({
  searchParams,
}: {
  searchParams: Promise<{ variant?: string }>;
}) {
  const { variant } = await searchParams;
  if (
    process.env.NODE_ENV !== "production" &&
    (variant === "A" || variant === "B" || variant === "C")
  ) {
    return <ChatV3Prototype variant={variant} />;
  }
  return <ChatWorkspace />;
}
