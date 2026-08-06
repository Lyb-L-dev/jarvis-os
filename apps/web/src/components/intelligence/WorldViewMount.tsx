"use client";

import dynamic from "next/dynamic";

const WorldView = dynamic(
  () => import("./WorldView").then((module) => module.WorldView),
  { loading: () => null, ssr: false },
);

export function WorldViewMount() {
  return <WorldView />;
}
