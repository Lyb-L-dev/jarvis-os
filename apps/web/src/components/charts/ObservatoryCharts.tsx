"use client";

import { useEffect, useState } from "react";

import {
  getObservatoryMetrics,
  type ObservatoryMetricsResponse,
} from "@/lib/api";

import { EChart } from "./EChart";

export function ObservatoryCharts() {
  const [metrics, setMetrics] = useState<ObservatoryMetricsResponse | null>(
    null,
  );

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const data = await getObservatoryMetrics(controller.signal);
        if (!disposed) setMetrics(data);
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

  if (!metrics || metrics.by_day.length < 2) return null;

  const average =
    metrics.avg_duration_ms != null
      ? `${(metrics.avg_duration_ms / 1000).toFixed(1)}s`
      : "—";

  return (
    <section className="chart-panel">
      <div className="chart-panel-head">
        <div>
          <small>RUN METRICS · 近 14 天</small>
          <h3>运行趋势</h3>
        </div>
        <span className="chart-panel-note">
          成功率 {(metrics.success_rate * 100).toFixed(0)}% · 平均 {average}
        </span>
      </div>
      <EChart
        height={210}
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
            data: metrics.by_day.map((point) => point.date.slice(5)),
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
              name: "成功",
              type: "bar",
              stack: "runs",
              data: metrics.by_day.map((point) => point.succeeded),
              itemStyle: { color: "#62e4aa" },
              barMaxWidth: 16,
            },
            {
              name: "失败",
              type: "bar",
              stack: "runs",
              data: metrics.by_day.map((point) => point.failed),
              itemStyle: { color: "#ff667a" },
              barMaxWidth: 16,
            },
          ],
        }}
      />
    </section>
  );
}
