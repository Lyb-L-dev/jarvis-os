"use client";

import { useEffect, useState } from "react";

import {
  getInvestmentPerformance,
  type InvestmentPerformanceResponse,
} from "@/lib/api";

import { EChart } from "./EChart";

export function InvestmentCharts() {
  const [performance, setPerformance] =
    useState<InvestmentPerformanceResponse | null>(null);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const data = await getInvestmentPerformance(controller.signal);
        if (!disposed) setPerformance(data);
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

  const series = performance?.series ?? [];
  const withPoints = series.filter((item) => item.points.length > 1);
  if (!withPoints.length) return null;

  const palette = ["#22d3ee", "#a5f3fc", "#6366f1", "#f6bd68"];

  return (
    <section className="chart-panel">
      <div className="chart-panel-head">
        <div>
          <small>PERFORMANCE · 累计投入成本</small>
          <h3>投入曲线</h3>
        </div>
        <span className="chart-panel-note">
          {withPoints
            .map(
              (item) =>
                `${item.currency} ${item.current_market_value != null ? item.current_market_value.toLocaleString("zh-CN") : "—"}`,
            )
            .join(" · ")}
        </span>
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
            data: withPoints[0].points.map((point) => point.date.slice(5)),
            axisLine: { lineStyle: { color: "rgba(255,255,255,0.1)" } },
            axisLabel: { color: "#63667a", fontSize: 10 },
          },
          yAxis: {
            type: "value",
            splitLine: { lineStyle: { color: "rgba(255,255,255,0.05)" } },
            axisLabel: { color: "#63667a", fontSize: 10 },
          },
          series: withPoints.map((item, index) => ({
            name: item.currency,
            type: "line",
            smooth: true,
            symbol: "none",
            data: item.points.map((point) => point.cost),
            lineStyle: {
              width: 2,
              color: palette[index % palette.length],
            },
            itemStyle: { color: palette[index % palette.length] },
          })),
        }}
      />
    </section>
  );
}
