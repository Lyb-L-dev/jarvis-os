"use client";

import { ArrowLeft, ArrowRight, FlaskConical } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import styles from "@/app/v3-prototype.module.css";

export type PrototypeVariant = {
  key: "A" | "B" | "C";
  name: string;
};

export function PrototypeSwitcher({
  current,
  variants,
}: {
  current: PrototypeVariant["key"];
  variants: PrototypeVariant[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentIndex = variants.findIndex((variant) => variant.key === current);

  function select(offset: number) {
    const nextIndex = (currentIndex + offset + variants.length) % variants.length;
    const params = new URLSearchParams(searchParams.toString());
    params.set("variant", variants[nextIndex].key);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, [contenteditable='true']")) return;
      if (event.key === "ArrowLeft") select(-1);
      if (event.key === "ArrowRight") select(1);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  if (process.env.NODE_ENV === "production") return null;
  const variant = variants[currentIndex] ?? variants[0];

  return (
    <div className={styles.switcher} role="navigation" aria-label="原型方向切换">
      <span className={styles.switcherMark} title="仅开发环境可见">
        <FlaskConical aria-hidden="true" />
      </span>
      <button aria-label="上一个方向" onClick={() => select(-1)} type="button">
        <ArrowLeft aria-hidden="true" />
      </button>
      <div>
        <small>V3-4B THROWAWAY PROTOTYPE</small>
        <strong>{variant.key} · {variant.name}</strong>
      </div>
      <button aria-label="下一个方向" onClick={() => select(1)} type="button">
        <ArrowRight aria-hidden="true" />
      </button>
    </div>
  );
}
