type CommandTelemetryTone = "cyan" | "green" | "violet" | "amber" | "red";

export type CommandTelemetryItem = {
  label: string;
  value: string | number;
  detail?: string;
  tone?: CommandTelemetryTone;
};

type CommandTelemetryProps = {
  items: CommandTelemetryItem[];
  label?: string;
};

export function CommandTelemetry({
  items,
  label = "模块实时状态",
}: CommandTelemetryProps) {
  return (
    <section className="command-telemetry" aria-label={label}>
      {items.map((item, index) => (
        <article
          className={`command-telemetry-item telemetry-${item.tone ?? "cyan"}`}
          key={`${item.label}-${index}`}
        >
          <div>
            <span>
              {String(index + 1).padStart(2, "0")} / {item.label}
            </span>
            <i aria-hidden="true" />
          </div>
          <strong>{item.value}</strong>
          {item.detail ? <small>{item.detail}</small> : null}
        </article>
      ))}
    </section>
  );
}
