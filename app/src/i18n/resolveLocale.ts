import * as Localization from "expo-localization";
import type { AppLocale } from "./resources";

export type LocalePreference = "auto" | AppLocale;

const SUPPORTED: AppLocale[] = ["en", "zh", "ko", "ru"];

export function deviceLocale(): AppLocale {
  const code = Localization.getLocales()[0]?.languageCode?.toLowerCase() ?? "en";
  if (code.startsWith("zh")) return "zh";
  if (code.startsWith("ko")) return "ko";
  if (code.startsWith("ru")) return "ru";
  return "en";
}

export function resolveLocale(preference: LocalePreference): AppLocale {
  if (preference === "auto") return deviceLocale();
  return preference;
}

export function isAppLocale(value: string): value is AppLocale {
  return (SUPPORTED as string[]).includes(value);
}
