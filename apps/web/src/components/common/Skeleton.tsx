import { cn } from "@/lib/utils";

type SkeletonProps = {
  className?: string;
};

/** 加载骨架，带柔和流光。 */
export function Skeleton({ className }: SkeletonProps) {
  return <span aria-hidden="true" className={cn("skeleton", className)} />;
}
