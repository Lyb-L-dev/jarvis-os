"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  // 对话即控制中枢：首页直接进入对话工作台（V3-4b 收敛方向）。
  // 静态导出不支持服务端 redirect()，用客户端 replace。
  useEffect(() => {
    router.replace("/chat");
  }, [router]);

  return null;
}
