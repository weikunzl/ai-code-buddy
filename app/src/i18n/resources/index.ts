import en from "./en";
import ko from "./ko";
import ru from "./ru";
import zh from "./zh";

export const resources = {
  en: { translation: en },
  zh: { translation: zh },
  ko: { translation: ko },
  ru: { translation: ru },
} as const;

export type AppLocale = keyof typeof resources;
