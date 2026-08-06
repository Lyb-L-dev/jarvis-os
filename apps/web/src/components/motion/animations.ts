import type { Transition, Variants } from "motion/react";

export const jarvisSpring: Transition = {
  damping: 28,
  stiffness: 260,
  type: "spring",
};

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    transition: jarvisSpring,
    y: 0,
  },
};

export const staggerChildren: Variants = {
  hidden: {},
  visible: {
    transition: {
      delayChildren: 0.04,
      staggerChildren: 0.055,
    },
  },
};
