"use client";

import { useEffect, useState } from "react";

import { getGrowthProgress, type GrowthProgressResponse } from "@/lib/api";

import { EChart } from "./EChart";

export function GrowthCharts() {
  const [progress, setProgress] = useState<GrowthProgressResponse | null>(null);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const data = await getGrowthProgress(controller.signal);
        if (!disposed) setProgress(data);
      } catch {
        // 图表为附加视图，失败静默
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 60_000);
    return () => {
      disposed = true;
      controller.abort();
      window.clearInterval(timer);
    };
  }, []);

  if (!progress || progress.weekly_minutes.length < 2) return null;

  return (
    <section className="chart-panel">
      <div className="chart-panel-head">
        <div>
          <small>WEEKLY INPUT · 近 8 周</small>
          <h3>投入时间与目标进度</h3>
        </div>
        <span className="chart-panel-note">分钟 / 目标完成度</span>
      </div>
      <EChart
        height={190}
        option={{
          tooltip: {
            trigger: "axis",
            backgroundColor: "rgba(16,20,26,0.92)",
            borderColor: "rgba(255,255,255,0.1)",
            textStyle: { color: "#f4f4f5", fontSize: 11 },
          },
          grid: { left: 8, right: 8, top: 18, bottom: 0, containLabel: true },
          xAxis: {
            type: "category",
            data: progress.weekly_minutes.map((point) => point.date.slice(5)),
            axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
            axisLabel: { color: "#63667a", fontSize: 10 },
          },
          yAxis: {
            type: "value",
            splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
            axisLabel: { color: "#63667a", fontSize: 10 },
          },
          series: [
            {
              name: "投入分钟",
              type: "bar",
              data: progress.weekly_minutes.map((point) => point.minutes),
              itemStyle: {
                color: "#22d3ee",
                borderRadius: [4, 4, 0, 0],
              },
              barMaxWidth: 22,
            },
          ],
        }}
      />
      {progress.goals.length ? (
        <div className="chart-goal-list">
          {progress.goals.slice(0, 4).map((goal) => (
            <div className="chart-goal-row" key={goal.goal_id}>
              <div>
                <strong>{goal.title}</strong>
                <small>
                  {goal.completed_milestones}/{goal.total_milestones} 里程碑
                </small>
              </div>
              <span className="chart-goal-track">
                <i style={{ width: `${Math.round(goal.progress * 100)}%` }} />
              </span>
              <b>{Math.round(goal.progress * 100)}%</b>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
