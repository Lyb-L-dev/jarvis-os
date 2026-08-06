"use client";

import { useEffect, useState } from "react";

import { getCostOverview, type CostOverview } from "@/lib/api";

import { EChart } from "./EChart";

export function CostCharts() {
  const [overview, setOverview] = useState<CostOverview | null>(null);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const data = await getCostOverview(30, controller.signal);
        if (!disposed) setOverview(data);
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

  const daily = overview?.daily ?? [];
  if (daily.length < 2) return null;

  return (
    <section className="chart-panel">
      <div className="chart-panel-head">
        <div>
          <small>TREND · 近 30 天</small>
          <h3>调用趋势</h3>
        </div>
        <span className="chart-panel-note">Token 与 DeepSeek 估算费用</span>
      </div>
      <EChart
        height={230}
        option={{
          tooltip: {
            trigger: "axis",
            backgroundColor: "rgba(16,20,26,0.92)",
            borderColor: "rgba(255,255,255,0.1)",
            textStyle: { color: "#f4f4f5", fontSize: 11 },
          },
          legend: {
            top: 0,
            textStyle: { color: "#8b8f9c", fontSize: 11 },
          },
          grid: { left: 8, right: 8, top: 34, bottom: 0, containLabel: true },
          xAxis: {
            type: "category",
            data: daily.map((point) => point.date.slice(5)),
            axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
            axisLabel: { color: "#63667a", fontSize: 10 },
          },
          yAxis: [
            {
              type: "value",
              name: "Token",
              nameTextStyle: { color: "#63667a", fontSize: 10 },
              splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
              axisLabel: { color: "#63667a", fontSize: 10 },
            },
            {
              type: "value",
              name: "费用 ¥",
              nameTextStyle: { color: "#63667a", fontSize: 10 },
              splitLine: { show: false },
              axisLabel: { color: "#63667a", fontSize: 10 },
            },
          ],
          series: [
            {
              name: "Token",
              type: "line",
              smooth: true,
              symbol: "none",
              data: daily.map((point) => point.total_tokens),
              lineStyle: { width: 2, color: "#22d3ee" },
              itemStyle: { color: "#22d3ee" },
              areaStyle: { color: "rgba(34,211,238,0.08)" },
            },
            {
              name: "DeepSeek 估算",
              type: "line",
              smooth: true,
              symbol: "none",
              yAxisIndex: 1,
              data: daily.map((point) => point.deepseek_estimated_cost),
              lineStyle: { width: 2, color: "#f6bd68" },
              itemStyle: { color: "#f6bd68" },
            },
          ],
        }}
      />
    </section>
  );
}
