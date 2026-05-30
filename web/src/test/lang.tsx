import { render, type RenderOptions } from "@testing-library/react";
import { LanguageProvider } from "@/components/LanguageProvider";
import type { ReactElement } from "react";

// Render a component tree wrapped in LanguageProvider (defaults to ko).
export function renderWithLang(ui: ReactElement, options?: RenderOptions) {
  return render(ui, {
    wrapper: ({ children }) => <LanguageProvider>{children}</LanguageProvider>,
    ...options,
  });
}
