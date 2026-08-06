"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import Globe, { type GlobeInstance } from "globe.gl";
import * as maplibregl from "maplibre-gl";
import * as THREE from "three";
import { feature } from "topojson-client";
import worldAtlas from "world-atlas/countries-110m.json";

import { Badge } from "@/components/common/Badge";
import { listNewsItems, type NewsItem } from "@/lib/api";

const CATEGORY_COLOR: Record<string, string> = {
  ai: "#6366f1",
  career: "#3b82f6",
  technology: "#22d3ee",
  english: "#62e4aa",
  investment: "#f6bd68",
  international: "#ff667a",
};

const CATEGORY_LABEL: Record<string, string> = {
  ai: "AI",
  career: "职业",
  technology: "技术",
  english: "英语",
  investment: "投资",
  international: "国际",
};

type ViewMode = "globe" | "map" | "unlocated" | "grid";

type LocatedPoint = {
  lat: number;
  lng: number;
  color: string;
  title: string;
  country: string;
  item: NewsItem;
};

const GRID_WIDTH = 860;
const GRID_HEIGHT = 420;

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      canvas.getContext("webgl2") || canvas.getContext("webgl"),
    );
  } catch {
    return false;
  }
}

export function WorldView() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [webglOk] = useState(() => webglAvailable());
  const [view, setView] = useState<ViewMode>(() =>
    webglAvailable() ? "globe" : "grid",
  );
  const [selected, setSelected] = useState<NewsItem | null>(null);
  const globeContainerRef = useRef<HTMLDivElement | null>(null);
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const globeInstanceRef = useRef<GlobeInstance | null>(null);
  const mapInstanceRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const data = await listNewsItems({ signal: controller.signal });
        if (!disposed) setItems(data);
      } catch {
        // 附加视图，失败静默
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

  const located = useMemo(
    () =>
      items.filter(
        (item): item is NewsItem & { geo: NonNullable<NewsItem["geo"]> } =>
          Boolean(item.geo),
      ),
    [items],
  );
  const points: LocatedPoint[] = useMemo(
    () =>
      located.map((item) => ({
        lat: item.geo.lat,
        lng: item.geo.lng,
        color: CATEGORY_COLOR[item.category] ?? "#22d3ee",
        title: item.title,
        country: item.geo.country,
        item,
      })),
    [located],
  );
  const unlocated = useMemo(
    () => items.filter((item) => !item.geo),
    [items],
  );

  useEffect(() => {
    if (view !== "globe" || !globeContainerRef.current || !webglOk) return;
    const container = globeContainerRef.current;
    const globeFactory = Globe as unknown as (
      element: HTMLElement,
    ) => GlobeInstance;
    const globe = globeFactory(container)
      .backgroundColor("rgba(0,0,0,0)")
      .showAtmosphere(true)
      .atmosphereColor("#22d3ee")
      .atmosphereAltitude(0.16)
      .showGraticules(true)
      .graticulesColor("rgba(34,211,238,0.14)")
      .showGlobe(true)
      .globeImageUrl(null)
      .pointOfView({ lat: 18, lng: 10, altitude: 2.3 })
      .pointsData(points)
      .pointLat((point: LocatedPoint) => point.lat)
      .pointLng((point: LocatedPoint) => point.lng)
      .pointColor((point: LocatedPoint) => point.color)
      .pointAltitude(0.02)
      .pointRadius(0.35)
      .onPointClick((point: LocatedPoint) => setSelected(point.item));
    const material = new THREE.MeshPhongMaterial({
      color: "#0c2230",
      emissive: "#0b2a38",
      emissiveIntensity: 0.55,
      transparent: true,
      opacity: 0.92,
    });
    globe.globeMaterial(material);

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (width && height) globe.width(width).height(height);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    globeInstanceRef.current = globe;

    return () => {
      observer.disconnect();
      globeInstanceRef.current = null;
      try {
        globe._destructor?.();
      } catch {
        // 清理失败不影响页面
      }
    };
  }, [view, points, webglOk]);

  useEffect(() => {
    if (view !== "map" || !mapContainerRef.current || !webglOk) return;
    const container = mapContainerRef.current;
    const topology = worldAtlas as unknown as {
      objects: { countries: object };
    };
    const countries = feature(
      topology as never,
      topology.objects.countries as never,
    );
    const features = points.map((point, index) => ({
      type: "Feature",
      properties: { color: point.color, title: point.title, index },
      geometry: { type: "Point", coordinates: [point.lng, point.lat] },
    }));
    const map = new maplibregl.Map({
      container,
      attributionControl: false,
      center: [0, 22],
      zoom: 1.05,
      style: {
        version: 8,
        sources: {
          countries: { type: "geojson", data: countries },
          points: {
            type: "geojson",
            data: { type: "FeatureCollection", features },
          },
        },
        layers: [
          {
            id: "bg",
            type: "background",
            paint: { "background-color": "#07070a" },
          },
          {
            id: "countries-fill",
            type: "fill",
            source: "countries",
            paint: { "fill-color": "#0d1822", "fill-opacity": 0.85 },
          },
          {
            id: "countries-border",
            type: "line",
            source: "countries",
            paint: {
              "line-color": "rgba(34,211,238,0.22)",
              "line-width": 0.6,
            },
          },
          {
            id: "points",
            type: "circle",
            source: "points",
            paint: {
              "circle-radius": 4.5,
              "circle-color": ["get", "color"],
              "circle-opacity": 0.95,
              "circle-blur": 0.25,
              "circle-stroke-color": "rgba(255,255,255,0.4)",
              "circle-stroke-width": 0.5,
            },
          },
        ],
      } as never,
    });
    map.on("click", "points", (event: maplibregl.MapLayerMouseEvent) => {
      const featureItem = event.features?.[0];
      const index = featureItem?.properties?.index as number | undefined;
      if (index != null && points[index]) setSelected(points[index].item);
    });
    map.on("load", () => map.resize());
    mapInstanceRef.current = map;
    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [view, points, webglOk]);

  return (
    <section className="worldview-panel">
      <div className="worldview-head">
        <div>
          <small>GLOBAL VIEW · 全球动态</small>
          <h3>国际动态分布</h3>
        </div>
        <div className="worldview-tabs">
          <button
            className={view === "globe" ? "is-active" : ""}
            onClick={() => setView(webglOk ? "globe" : "grid")}
            type="button"
          >
            3D 地球 {located.length}
          </button>
          <button
            className={view === "map" ? "is-active" : ""}
            onClick={() => setView(webglOk ? "map" : "grid")}
            type="button"
          >
            2D 地图 {located.length}
          </button>
          <button
            className={view === "unlocated" ? "is-active" : ""}
            onClick={() => setView("unlocated")}
            type="button"
          >
            未定位 {unlocated.length}
          </button>
        </div>
      </div>

      {view === "globe" ? (
        <div className="worldview-globe" ref={globeContainerRef} />
      ) : null}

      {view === "map" ? (
        <div className="worldview-map-canvas" ref={mapContainerRef} />
      ) : null}

      {view === "grid" ? (
        <div className="worldview-map">
          <svg
            aria-label="全球情报分布（降级网格视图）"
            role="img"
            viewBox={`0 0 ${GRID_WIDTH} ${GRID_HEIGHT}`}
          >
            <g className="worldview-grid">
              {Array.from({ length: 13 }, (_, index) => index * 30).map(
                (lng) => (
                  <line
                    key={`lng-${lng}`}
                    x1={(lng / 360) * GRID_WIDTH}
                    x2={(lng / 360) * GRID_WIDTH}
                    y1="0"
                    y2={GRID_HEIGHT}
                  />
                ),
              )}
              {Array.from({ length: 7 }, (_, index) => index * 30).map(
                (lat) => (
                  <line
                    key={`lat-${lat}`}
                    x1="0"
                    x2={GRID_WIDTH}
                    y1={(lat / 180) * GRID_HEIGHT}
                    y2={(lat / 180) * GRID_HEIGHT}
                  />
                ),
              )}
            </g>
            {located.map((item) => {
              const geo = item.geo;
              const x = ((geo.lng + 180) / 360) * GRID_WIDTH;
              const y = ((90 - geo.lat) / 180) * GRID_HEIGHT;
              const color = CATEGORY_COLOR[item.category] ?? "#22d3ee";
              const radius = 3 + Math.min(4, item.relevance_score * 2);
              return (
                <g
                  className="worldview-dot"
                  key={item.id}
                  onClick={() => setSelected(item)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      setSelected(item);
                    }
                  }}
                  role="button"
                  style={{ color }}
                  tabIndex={0}
                >
                  <circle
                    cx={x}
                    cy={y}
                    fill={color}
                    opacity="0.16"
                    r={radius * 3}
                  />
                  <circle cx={x} cy={y} fill={color} r={radius} />
                  <title>
                    {item.title} · {geo.country}
                  </title>
                </g>
              );
            })}
          </svg>
          <p className="worldview-note">
            当前设备不支持 WebGL，已降级为网格视图。
          </p>
        </div>
      ) : null}

      {view === "unlocated" ? (
        <ul className="worldview-list">
          {unlocated.length ? (
            unlocated.slice(0, 30).map((item) => (
              <li key={item.id}>
                <div>
                  <strong>{item.title}</strong>
                  <small>
                    {item.source_name}
                    {item.published_at
                      ? ` · ${new Date(item.published_at).toLocaleDateString("zh-CN")}`
                      : ""}
                  </small>
                </div>
                <Badge
                  tone={item.category === "international" ? "danger" : "neutral"}
                >
                  {CATEGORY_LABEL[item.category] ?? item.category}
                </Badge>
              </li>
            ))
          ) : (
            <li className="worldview-empty">暂无未定位条目</li>
          )}
        </ul>
      ) : null}

      {selected ? (
        <div className="worldview-detail">
          <span
            className="worldview-detail-dot"
            style={{ background: CATEGORY_COLOR[selected.category] }}
          />
          <div>
            <strong>{selected.title}</strong>
            <p>
              {selected.geo
                ? `${selected.geo.country} · ${selected.source_name}`
                : selected.source_name}
              {" · "}
              {selected.summary.slice(0, 140)}
            </p>
          </div>
          <a href={selected.url} rel="noreferrer" target="_blank">
            查看原文
          </a>
        </div>
      ) : null}
    </section>
  );
}
