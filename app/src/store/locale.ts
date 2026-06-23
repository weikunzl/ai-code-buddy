import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";
import i18n from "../i18n";
import type { LocalePreference } from "../i18n/resolveLocale";
import { resolveLocale } from "../i18n/resolveLocale";

type LocaleState = {
  preference: LocalePreference;
  setPreference: (preference: LocalePreference) => void;
};

function applyLocale(preference: LocalePreference): void {
  void i18n.changeLanguage(resolveLocale(preference));
}

export const useLocaleStore = create(
  persist<LocaleState>(
    (set) => ({
      preference: "auto",
      setPreference: (preference) => {
        applyLocale(preference);
        set({ preference });
      },
    }),
    {
      name: "buddy-locale",
      storage: createJSONStorage(() => AsyncStorage),
      onRehydrateStorage: () => (state) => {
        if (state) applyLocale(state.preference);
      },
    },
  ),
);
