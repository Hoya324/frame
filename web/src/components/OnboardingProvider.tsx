"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  ONBOARDING_STEPS,
  hasSeenOnboarding,
  markOnboardingSeen,
  type OnboardingStep,
} from "@/lib/onboarding";

interface OnboardingCtx {
  active: boolean;
  step: OnboardingStep | null;
  stepIndex: number;
  total: number;
  isSwipeStep: boolean;
  start: () => void;
  next: () => void;
  prev: () => void;
  skip: () => void;
}

const Ctx = createContext<OnboardingCtx | null>(null);

export function OnboardingProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  const total = ONBOARDING_STEPS.length;
  const step = active ? ONBOARDING_STEPS[stepIndex] ?? null : null;

  // Navigate to the step's route when it differs from where we are. Kept in an
  // effect (not the handlers) so it reacts to whichever step we land on.
  useEffect(() => {
    if (!active || !step) return;
    if (pathname !== step.route) router.push(step.route);
  }, [active, step, pathname, router]);

  const start = useCallback(() => {
    setStepIndex(0);
    setActive(true);
  }, []);

  const finish = useCallback(() => {
    markOnboardingSeen();
    setActive(false);
  }, []);

  const next = useCallback(() => {
    if (stepIndex >= total - 1) {
      finish();
      return;
    }
    setStepIndex((i) => i + 1);
  }, [stepIndex, total, finish]);

  const prev = useCallback(() => setStepIndex((i) => Math.max(0, i - 1)), []);
  const skip = useCallback(() => finish(), [finish]);

  // Auto-start once on the first visit to the discover route.
  useEffect(() => {
    if (pathname === "/" && !hasSeenOnboarding()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActive(true);
    }
    // run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<OnboardingCtx>(
    () => ({
      active,
      step,
      stepIndex,
      total,
      isSwipeStep: step?.kind === "swipe",
      start,
      next,
      prev,
      skip,
    }),
    [active, step, stepIndex, total, start, next, prev, skip],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// Safe no-op default so components outside the provider (or in tests) don't throw.
const NOOP: OnboardingCtx = {
  active: false,
  step: null,
  stepIndex: 0,
  total: ONBOARDING_STEPS.length,
  isSwipeStep: false,
  start: () => {},
  next: () => {},
  prev: () => {},
  skip: () => {},
};

export function useOnboarding(): OnboardingCtx {
  return useContext(Ctx) ?? NOOP;
}
