import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { deviceLocale } from "./resolveLocale";
import { resources } from "./resources";

void i18n.use(initReactI18next).init({
  resources,
  lng: deviceLocale(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  compatibilityJSON: "v4",
});

export default i18n;

export function translateErrorKey(code: string | null | undefined): string | null {
  if (!code) return null;
  const key = `errors.${code}`;
  return i18n.exists(key) ? i18n.t(key) : code;
}
