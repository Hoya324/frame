"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  ONBOARDING_STEPS,
  clearOnboardingProgress,
  hasSeenOnboarding,
  markOnboardingSeen,
  readOnboardingProgress,
  writeOnboardingProgress,
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

  // Progress is persisted imperatively in each action (not via a reactive
  // effect) so writes are deterministic and never clobber a just-restored value.
  const goTo = useCallback((index: number) => {
    setStepIndex(index);
    setActive(true);
    writeOnboardingProgress({ active: true, stepIndex: index });
  }, []);

  const start = useCallback(() => goTo(0), [goTo]);

  const finish = useCallback(() => {
    markOnboardingSeen();
    clearOnboardingProgress();
    setActive(false);
  }, []);

  const next = useCallback(() => {
    if (stepIndex >= total - 1) {
      finish();
      return;
    }
    goTo(stepIndex + 1);
  }, [stepIndex, total, finish, goTo]);

  const prev = useCallback(() => goTo(Math.max(0, stepIndex - 1)), [goTo, stepIndex]);
  const skip = useCallback(() => finish(), [finish]);

  // On mount: resume an in-progress tour (survives the hard navigations that a
  // static-export + service-worker setup can trigger between tabs), otherwise
  // auto-start once on the first visit to the discover route.
  useEffect(() => {
    const saved = readOnboardingProgress();
    if (saved?.active) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStepIndex(Math.min(Math.max(0, saved.stepIndex), total - 1));
      setActive(true);
      return;
    }
    if (pathname === "/" && !hasSeenOnboarding()) {
      goTo(0);
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
