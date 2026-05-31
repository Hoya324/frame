import { render, type RenderOptions } from "@testing-library/react";
import { LanguageProvider } from "@/components/LanguageProvider";
import type { ReactElement } from "react";
import type { Locale } from "@/lib/i18n";

// LanguageProvider reads the persisted locale on mount; seed it for tests.
export function renderWithLang(
  ui: ReactElement,
  options?: RenderOptions & { locale?: Locale },
) {
  if (options?.locale) {
    window.localStorage.setItem("frame.locale", options.locale);
  } else {
    window.localStorage.removeItem("frame.locale");
  }
  return render(ui, {
    wrapper: ({ children }) => <LanguageProvider>{children}</LanguageProvider>,
    ...options,
  });
}
