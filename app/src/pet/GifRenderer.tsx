import React from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import type { PetState } from "@protocol/index";
import { usePetProfile } from "../store/petProfile";

const PLACEHOLDER_COLORS: Record<PetState, string> = {
  sleep: "#6b7280",
  idle: "#3b82f6",
  busy: "#f59e0b",
  attention: "#ef4444",
  celebrate: "#22c55e",
  dizzy: "#a855f7",
  heart: "#ec4899",
};

const STATE_LABELS: Record<PetState, string> = {
  sleep: "Zzz",
  idle: "Idle",
  busy: "Busy",
  attention: "!",
  celebrate: "★",
  dizzy: "@",
  heart: "♥",
};

type Props = {
  state: PetState;
  size?: number;
};

export function GifRenderer({ state, size = 160 }: Props) {
  const uri = usePetProfile((s) => s.profile.states[state]);

  if (uri) {
    return (
      <Image
        source={{ uri }}
        style={{ width: size, height: size }}
        resizeMode="contain"
      />
    );
  }

  return (
    <View
      style={[
        styles.placeholder,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: PLACEHOLDER_COLORS[state],
        },
      ]}
    >
      <Text style={styles.label}>{STATE_LABELS[state]}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  placeholder: {
    alignItems: "center",
    justifyContent: "center",
  },
  label: {
    color: "#fff",
    fontSize: 32,
    fontWeight: "700",
  },
});
