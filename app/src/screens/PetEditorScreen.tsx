import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { PetState } from "@protocol/index";
import { usePetProfile } from "../store/petProfile";
import { GifRenderer } from "../pet/GifRenderer";

const PET_STATES: PetState[] = [
  "sleep",
  "idle",
  "busy",
  "attention",
  "celebrate",
  "dizzy",
  "heart",
];

export function PetEditorScreen() {
  const profile = usePetProfile((s) => s.profile);
  const setStateGif = usePetProfile((s) => s.setStateGif);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{profile.name}</Text>
      <Text style={styles.hint}>
        GIF picker coming soon. Clear a custom GIF to use the colored placeholder.
      </Text>

      {PET_STATES.map((state) => (
        <View key={state} style={styles.row}>
          <GifRenderer state={state} size={64} />
          <View style={styles.info}>
            <Text style={styles.stateName}>{state}</Text>
            <Text style={styles.uri} numberOfLines={1}>
              {profile.states[state] ?? "default placeholder"}
            </Text>
          </View>
          {profile.states[state] ? (
            <Pressable onPress={() => setStateGif(state, null)}>
              <Text style={styles.clear}>Clear</Text>
            </Pressable>
          ) : null}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 16 },
  title: { fontSize: 20, fontWeight: "700", marginBottom: 8 },
  hint: { fontSize: 13, color: "#6b7280", marginBottom: 16 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#e5e7eb",
  },
  info: { flex: 1 },
  stateName: { fontSize: 15, fontWeight: "600", textTransform: "capitalize" },
  uri: { fontSize: 11, color: "#9ca3af", marginTop: 2 },
  clear: { color: "#ef4444", fontSize: 14 },
});
