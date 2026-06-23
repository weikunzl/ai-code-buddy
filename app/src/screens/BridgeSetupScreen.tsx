import React, { useLayoutEffect } from "react";
import { Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useTranslation } from "react-i18next";
import { BridgeSetupGuide } from "../components/BridgeSetupGuide";
import { useOnboardingStore } from "../store/onboarding";
import type { SettingsStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<SettingsStackParamList, "BridgeSetup">;

function CommandBlock({ command }: { command: string }) {
  return (
    <View style={styles.cmdBox}>
      <Text style={styles.cmdText} selectable>
        {command}
      </Text>
    </View>
  );
}

export function BridgeSetupScreen({ navigation }: Props) {
  const { t } = useTranslation();
  const setBridgeGuideSeen = useOnboardingStore((s) => s.setBridgeGuideSeen);

  function finish() {
    setBridgeGuideSeen(true);
    if (navigation.canGoBack()) {
      navigation.goBack();
    } else {
      navigation.navigate("SettingsMain");
    }
  }

  useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <Pressable onPress={finish} hitSlop={8} style={styles.headerClose}>
          <Text style={styles.headerCloseText}>{t("bridgeSetup.done")}</Text>
        </Pressable>
      ),
    });
  }, [navigation, t]);

  function openSettings() {
    setBridgeGuideSeen(true);
    navigation.navigate("SettingsMain");
  }

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.intro}>{t("bridgeSetup.screenIntro")}</Text>

      <BridgeSetupGuide />

      <View style={styles.hooksCard}>
        <Text style={styles.hooksTitle}>{t("bridgeSetup.hooksTitle")}</Text>
        <Text style={styles.hooksBody}>{t("bridgeSetup.hooksBody")}</Text>
        <Text style={styles.step}>{t("bridgeSetup.hooksStep1")}</Text>
        <CommandBlock command={t("bridgeSetup.cmdCloneRepo")} />
        <Text style={styles.step}>{t("bridgeSetup.hooksStep2")}</Text>
        <CommandBlock command={t("bridgeSetup.cmdInstallDesktop")} />
        <Text style={styles.hint}>{t("bridgeSetup.hooksHint")}</Text>
      </View>

      <Pressable style={styles.primaryBtn} onPress={openSettings}>
        <Text style={styles.primaryBtnText}>{t("bridgeSetup.openSettings")}</Text>
      </Pressable>
      <Pressable style={styles.secondaryBtn} onPress={finish}>
        <Text style={styles.secondaryBtnText}>{t("bridgeSetup.done")}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  headerClose: { paddingHorizontal: 4 },
  headerCloseText: { color: "#2563eb", fontSize: 16, fontWeight: "600" },
  scroll: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 20, paddingBottom: 40, gap: 16 },
  intro: { fontSize: 14, color: "#4b5563", lineHeight: 21 },
  hooksCard: {
    backgroundColor: "#f8fafc",
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#e2e8f0",
    padding: 14,
    gap: 8,
  },
  hooksTitle: { fontSize: 15, fontWeight: "700", color: "#1e293b" },
  hooksBody: { fontSize: 13, color: "#64748b", lineHeight: 19 },
  step: { fontSize: 13, color: "#334155", lineHeight: 20, marginTop: 4 },
  hint: { fontSize: 12, color: "#64748b", lineHeight: 18 },
  cmdBox: {
    backgroundColor: "#0f172a",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  cmdText: {
    fontFamily: Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" }),
    fontSize: 12,
    color: "#e2e8f0",
    lineHeight: 18,
  },
  primaryBtn: {
    backgroundColor: "#2563eb",
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: "center",
  },
  primaryBtnText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  secondaryBtn: {
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  secondaryBtnText: { color: "#6b7280", fontWeight: "500", fontSize: 14 },
});
