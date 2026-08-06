import type { ComponentType, ReactNode } from "react";

import { Inbox } from "lucide-react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  title: string;
  description?: ReactNode;
  icon?: ComponentType<{ size?: number; strokeWidth?: number }>;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
};

/** 空态：图标 + 标题 + 可选说明与操作。 */
export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  compact,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn("empty-state", compact && "empty-state-compact", className)}>
      {compact ? null : (
        <span className="empty-state-icon">
          <Icon size={20} strokeWidth={1.5} />
        </span>
      )}
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {action ? <div className="empty-state-action">{action}</div> : null}
    </div>
  );
}
