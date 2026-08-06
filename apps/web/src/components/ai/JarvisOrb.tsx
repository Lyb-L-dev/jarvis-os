"use client";

import { motion, useReducedMotion } from "motion/react";

import {
  AI_STATE_META,
  AIStatus,
  type AIState,
} from "@/components/ai/AIStatus";
import {
  aiStateToLogomark,
  JarvisLogomark,
} from "@/components/brand/JarvisLogomark";

const particlePositions = [
  { left: "11%", top: "31%" },
  { left: "17%", top: "67%" },
  { left: "26%", top: "15%" },
  { left: "32%", top: "82%" },
  { left: "48%", top: "7%" },
  { left: "52%", top: "91%" },
  { left: "69%", top: "14%" },
  { left: "73%", top: "83%" },
  { left: "84%", top: "34%" },
  { left: "89%", top: "62%" },
  { left: "8%", top: "51%" },
  { left: "93%", top: "48%" },
];

const speakingBars = [0.45, 0.82, 0.58, 1, 0.68, 0.9, 0.5];

type JarvisOrbProps = {
  state: AIState;
};

export function JarvisOrb({ state }: JarvisOrbProps) {
  const reducedMotion = useReducedMotion();
  const meta = AI_STATE_META[state];
  const active = state !== "idle" && state !== "error";
  const ringDuration =
    state === "thinking" ? 8 : state === "listening" ? 13 : 22;

  return (
    <div
      aria-label={`Jarvis AI Core：${meta.label}`}
      className={`jarvis-orb jarvis-orb-${state}`}
    >
      <div className="jarvis-orb-visual">
        <motion.div
          animate={
            reducedMotion
              ? undefined
              : {
                  opacity: active ? [0.4, 0.78, 0.4] : [0.28, 0.48, 0.28],
                  scale: active ? [0.94, 1.08, 0.94] : [0.97, 1.035, 0.97],
                }
          }
          className="jarvis-orb-aura"
          transition={{
            duration: state === "thinking" ? 1.8 : 4.8,
            ease: "easeInOut",
            repeat: Number.POSITIVE_INFINITY,
          }}
        />

        {[0, 1, 2].map((ring) => (
          <motion.div
            animate={
              reducedMotion
                ? undefined
                : { rotate: ring % 2 === 0 ? 360 : -360 }
            }
            className={`jarvis-orb-ring jarvis-orb-ring-${ring + 1}`}
            key={ring}
            transition={{
              duration: ringDuration + ring * 7,
              ease: "linear",
              repeat: Number.POSITIVE_INFINITY,
            }}
          >
            <span />
            <i />
          </motion.div>
        ))}

        <div className="jarvis-orb-particles" aria-hidden="true">
          {particlePositions.map((position, index) => (
            <motion.i
              animate={
                reducedMotion
                  ? undefined
                  : {
                      opacity: active
                        ? [0.18, 0.9, 0.18]
                        : [0.12, 0.48, 0.12],
                      scale: active ? [0.7, 1.35, 0.7] : [0.8, 1.08, 0.8],
                    }
              }
              key={`${position.left}-${position.top}`}
              style={position}
              transition={{
                delay: index * 0.17,
                duration: state === "thinking" ? 1.4 : 3.2,
                ease: "easeInOut",
                repeat: Number.POSITIVE_INFINITY,
              }}
            />
          ))}
        </div>

        {state === "listening"
          ? [0, 1, 2].map((wave) => (
              <motion.span
                animate={
                  reducedMotion
                    ? undefined
                    : { opacity: [0.45, 0], scale: [0.72, 1.28] }
                }
                className="jarvis-listening-wave"
                key={wave}
                transition={{
                  delay: wave * 0.55,
                  duration: 1.7,
                  ease: "easeOut",
                  repeat: Number.POSITIVE_INFINITY,
                }}
              />
            ))
          : null}

        <motion.div
          animate={
            reducedMotion
              ? undefined
              : {
                  scale:
                    state === "thinking"
                      ? [0.96, 1.04, 0.96]
                      : [0.985, 1.018, 0.985],
                }
          }
          className="jarvis-orb-core"
          transition={{
            duration: state === "thinking" ? 1.45 : 4,
            ease: "easeInOut",
            repeat: Number.POSITIVE_INFINITY,
          }}
        >
          <div className="jarvis-orb-core-glass" />
          <JarvisLogomark
            className="jarvis-orb-mark"
            state={aiStateToLogomark(state)}
          />

          {state === "speaking" ? (
            <div className="jarvis-speaking-wave" aria-hidden="true">
              {speakingBars.map((height, index) => (
                <motion.i
                  animate={
                    reducedMotion
                      ? undefined
                      : { scaleY: [0.3, height, 0.3] }
                  }
                  key={`${height}-${index}`}
                  transition={{
                    delay: index * 0.08,
                    duration: 0.62,
                    ease: "easeInOut",
                    repeat: Number.POSITIVE_INFINITY,
                  }}
                />
              ))}
            </div>
          ) : null}
        </motion.div>

        <span className="jarvis-orb-axis jarvis-orb-axis-x" />
        <span className="jarvis-orb-axis jarvis-orb-axis-y" />
      </div>

      <AIStatus state={state} />
    </div>
  );
}

export type { AIState };
