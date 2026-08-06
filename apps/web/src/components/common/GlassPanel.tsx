import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type GlassPanelProps = {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

/** 玻璃面板容器：标题 + 可选操作区 + 内容。 */
export function GlassPanel({
  title,
  description,
  actions,
  children,
  className,
}: GlassPanelProps) {
  return (
    <section className={cn("glass-panel", className)}>
      {title || actions ? (
        <header className="glass-panel-head">
          <div>
            {title ? <h3 className="glass-panel-title">{title}</h3> : null}
            {description ? (
              <p className="glass-panel-desc">{description}</p>
            ) : null}
          </div>
          {actions ? <div className="glass-panel-actions">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}
