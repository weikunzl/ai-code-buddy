import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { PetState } from "@protocol/index";
import { DEFAULT_PET_NAME, normalizePetName } from "../constants/product";

export type PetProfile = {
  id: string;
  name: string;
  states: Partial<Record<PetState, string | null>>;
};

type PetProfileState = {
  profile: PetProfile;
  setStateGif: (state: PetState, uri: string | null) => void;
  setName: (name: string) => void;
};

export const usePetProfile = create(
  persist<PetProfileState>(
    (set, get) => ({
      profile: { id: "default", name: DEFAULT_PET_NAME, states: {} },
      setStateGif: (state, uri) =>
        set({
          profile: {
            ...get().profile,
            states: { ...get().profile.states, [state]: uri },
          },
        }),
      setName: (name) =>
        set({ profile: { ...get().profile, name: normalizePetName(name) } }),
    }),
    {
      name: "pet-profile",
      storage: createJSONStorage(() => AsyncStorage),
      version: 1,
      migrate: (persisted, version) => {
        const state = persisted as PetProfileState;
        if (version < 1 && state.profile?.name === "Buddy") {
          state.profile.name = DEFAULT_PET_NAME;
        }
        return state;
      },
    },
  ),
);
