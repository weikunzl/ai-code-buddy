import React, { useCallback, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import type { PetState } from "@protocol/index";
import { translateErrorKey } from "../i18n";
import { usePetProfile } from "../store/petProfile";
import { GifRenderer } from "../pet/GifRenderer";
import { ImportGifError, importPetGif } from "../pet/importGif";
import { playBuddySound } from "../audio/SoundPlayer";
import { useConnectionStore } from "../store/connection";

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
  const { t } = useTranslation();
  const profile = usePetProfile((s) => s.profile);
  const setStateGif = usePetProfile((s) => s.setStateGif);
  const soundsMuted = useConnectionStore((s) => s.soundsMuted);
  const [busyState, setBusyState] = useState<PetState | null>(null);

  const pickGif = useCallback(
    async (state: PetState) => {
      setBusyState(state);
      try {
        void playBuddySound("ui_click", soundsMuted);
        const uri = await importPetGif(state);
        if (uri) setStateGif(state, uri);
      } catch (err) {
        const message =
          err instanceof ImportGifError
            ? translateErrorKey(err.code) ?? err.code
            : String(err);
        Alert.alert(t("petEditor.importFailed"), message);
      } finally {
        setBusyState(null);
      }
    },
    [setStateGif, soundsMuted, t],
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{profile.name}</Text>
      <Text style={styles.hint}>{t("petEditor.hint", { name: profile.name })}</Text>

      {PET_STATES.map((state) => (
        <View key={state} style={styles.row}>
          <GifRenderer state={state} size={64} />
          <View style={styles.info}>
            <Text style={styles.stateName}>{t(`petStates.${state}`)}</Text>
            <Text style={styles.stateDesc} numberOfLines={3}>
              {profile.states[state]
                ? t("petEditor.customGif")
                : t(`petStateDesc.${state}`)}
            </Text>
          </View>
          {profile.states[state] ? (
            <Pressable onPress={() => setStateGif(state, null)}>
              <Text style={styles.clear}>{t("common.clear")}</Text>
            </Pressable>
          ) : null}
          <Pressable
            style={[styles.pickBtn, busyState === state && styles.pickBusy]}
            onPress={() => pickGif(state)}
            disabled={busyState !== null}
          >
            <Text style={styles.pickText}>
              {busyState === state ? "…" : t("common.pick")}
            </Text>
          </Pressable>
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
  stateName: { fontSize: 15, fontWeight: "600" },
  stateDesc: { fontSize: 12, color: "#6b7280", marginTop: 4, lineHeight: 17 },
  clear: { color: "#ef4444", fontSize: 14 },
  pickBtn: {
    backgroundColor: "#2563eb",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
  },
  pickBusy: { opacity: 0.5 },
  pickText: { color: "#fff", fontWeight: "600", fontSize: 13 },
});
