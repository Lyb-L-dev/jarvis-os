import { cn } from "@/lib/utils";

export type StatusTone =
  | "neutral"
  | "idle"
  | "listen"
  | "think"
  | "execute"
  | "alert"
  | "success"
  | "warning"
  | "danger"
  | "violet"
  | "blue";

const TONE_CLASS: Record<StatusTone, string> = {
  neutral: "status-tone-neutral",
  idle: "status-tone-idle",
  listen: "status-tone-listen",
  think: "status-tone-think",
  execute: "status-tone-execute",
  alert: "status-tone-alert",
  success: "status-tone-success",
  warning: "status-tone-warning",
  danger: "status-tone-danger",
  violet: "status-tone-violet",
  blue: "status-tone-blue",
};

type StatusDotProps = {
  tone?: StatusTone;
  pulse?: boolean;
  label?: string;
  className?: string;
};

/** J-Core 状态灯：颜色 + 可选呼吸。 */
export function StatusDot({
  tone = "neutral",
  pulse = false,
  label,
  className,
}: StatusDotProps) {
  return (
    <i
      aria-label={label}
      className={cn(
        "status-dot",
        TONE_CLASS[tone],
        pulse && "status-dot-pulse",
        className,
      )}
    />
  );
}
