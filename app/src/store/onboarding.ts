import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";

type OnboardingState = {
  bridgeGuideSeen: boolean;
  setBridgeGuideSeen: (seen: boolean) => void;
};

export const useOnboardingStore = create(
  persist<OnboardingState>(
    (set) => ({
      bridgeGuideSeen: false,
      setBridgeGuideSeen: (bridgeGuideSeen) => set({ bridgeGuideSeen }),
    }),
    {
      name: "buddy-onboarding",
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);
