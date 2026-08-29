import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.JARVIS_NEXT_DIST_DIR || ".next",
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_V3_PAGE_CONVERGENCE_ENABLED:
      process.env.NEXT_PUBLIC_V3_PAGE_CONVERGENCE_ENABLED ??
      process.env.V3_PAGE_CONVERGENCE_ENABLED ??
      "false",
  },
  ...(process.env.JARVIS_STATIC_EXPORT === "1"
    ? { output: "export", trailingSlash: true }
    : {}),
};

export default nextConfig;
