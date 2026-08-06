import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata, Viewport } from "next";

import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/sidebar";
import { AppHeader } from "@/components/app-header";

// 本地中文字体（思源黑体 Noto Sans SC，随应用打包，完全离线）
import "@fontsource/noto-sans-sc/latin-400.css";
import "@fontsource/noto-sans-sc/latin-500.css";
import "@fontsource/noto-sans-sc/latin-600.css";
import "@fontsource/noto-sans-sc/chinese-simplified-400.css";
import "@fontsource/noto-sans-sc/chinese-simplified-500.css";
import "@fontsource/noto-sans-sc/chinese-simplified-600.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jarvis OS",
  description: "Personal AI Operating System",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  colorScheme: "dark",
  themeColor: "#09090b",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      className={`${GeistSans.variable} ${GeistMono.variable} dark`}
      lang="zh-CN"
    >
      <body>
        <Providers>
          <div className="app-shell">
            <Sidebar />
            <AppHeader />
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
