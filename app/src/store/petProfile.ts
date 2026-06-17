import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import AsyncStorage from "@react-native-async-storage/async-storage";
import type { PetState } from "@protocol/index";

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
      profile: { id: "default", name: "Buddy", states: {} },
      setStateGif: (state, uri) =>
        set({
          profile: {
            ...get().profile,
            states: { ...get().profile.states, [state]: uri },
          },
        }),
      setName: (name) => set({ profile: { ...get().profile, name } }),
    }),
    { name: "pet-profile", storage: createJSONStorage(() => AsyncStorage) },
  ),
);
