import {
  Brain,
  ChevronRight,
  Languages,
  Route,
  WalletCards,
} from "lucide-react";
import Link from "next/link";

type GrowthCardProps = {
  activeMemories: number;
  activePositions: number;
  completedTasks: number;
  dueReviews: number;
  taskCount: number;
  weekMinutes: number;
};

export function GrowthCard({
  activeMemories,
  activePositions,
  completedTasks,
  dueReviews,
  taskCount,
  weekMinutes,
}: GrowthCardProps) {
  const progress =
    taskCount > 0 ? Math.round((completedTasks / taskCount) * 100) : 0;

  const signals = [
    {
      href: "/growth",
      icon: Route,
      label: "今日推进",
      value: taskCount > 0 ? `${completedTasks}/${taskCount}` : "待规划",
    },
    {
      href: "/english",
      icon: Languages,
      label: "英语复习",
      value: `${dueReviews} 项`,
    },
    {
      href: "/memory",
      icon: Brain,
      label: "长期记忆",
      value: `${activeMemories} 条`,
    },
    {
      href: "/investment",
      icon: WalletCards,
      label: "关注持仓",
      value: `${activePositions} 项`,
    },
  ];

  return (
    <section className="cc-growth-card">
      <div className="cc-section-heading">
        <div>
          <span>PERSONAL TRAJECTORY</span>
          <h2>你的成长轨迹</h2>
        </div>
        <strong>{Math.round((weekMinutes / 60) * 10) / 10}h 本周投入</strong>
      </div>

      <div className="cc-progress-orbit">
        <div
          aria-label={`今日任务完成度 ${progress}%`}
          className="cc-progress-ring"
          style={{ "--progress": `${progress * 3.6}deg` } as React.CSSProperties}
        >
          <div>
            <strong>{progress}%</strong>
            <span>今日进度</span>
          </div>
        </div>
        <p>
          {taskCount > 0
            ? "Jarvis 正在根据你的实际完成情况更新今日节奏。"
            : "今天还没有确认任务。可以让 Jarvis 帮你规划一个可执行的起点。"}
        </p>
      </div>

      <div className="cc-personal-signals">
        {signals.map((signal) => {
          const Icon = signal.icon;
          return (
            <Link href={signal.href} key={signal.href}>
              <Icon aria-hidden="true" strokeWidth={1.6} />
              <div>
                <span>{signal.label}</span>
                <strong>{signal.value}</strong>
              </div>
              <ChevronRight aria-hidden="true" />
            </Link>
          );
        })}
      </div>
    </section>
  );
}
