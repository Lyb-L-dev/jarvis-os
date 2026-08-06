import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium outline-none transition-[color,background-color,border-color,box-shadow,transform] duration-200 focus-visible:ring-2 focus-visible:ring-cyan-300/45 disabled:pointer-events-none disabled:opacity-45 active:scale-[0.98] [&_svg]:pointer-events-none [&_svg]:size-4",
  {
    variants: {
      variant: {
        default:
          "border border-cyan-300/20 bg-cyan-300/10 text-cyan-50 shadow-[0_10px_28px_rgba(34,211,238,0.08)] hover:border-cyan-300/35 hover:bg-cyan-300/15",
        secondary:
          "border border-white/8 bg-white/[0.055] text-zinc-100 hover:border-white/14 hover:bg-white/[0.085]",
        outline:
          "border border-white/10 bg-transparent text-zinc-200 hover:border-cyan-300/25 hover:bg-cyan-300/[0.06] hover:text-cyan-50",
        ghost:
          "border border-transparent bg-transparent text-zinc-400 hover:bg-white/[0.055] hover:text-zinc-100",
        danger:
          "border border-rose-400/20 bg-rose-400/10 text-rose-100 hover:border-rose-400/35 hover:bg-rose-400/15",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-12 rounded-2xl px-6",
        icon: "size-10 p-0",
      },
    },
    defaultVariants: {
      size: "default",
      variant: "default",
    },
  },
);

function Button({
  asChild = false,
  className,
  size,
  variant,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) {
  const Comp = asChild ? Slot : "button";

  return (
    <Comp
      className={cn(buttonVariants({ className, size, variant }))}
      data-slot="button"
      {...props}
    />
  );
}

export { Button, buttonVariants };
