import React, { useEffect, useState } from "react";
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { BUDDY_WS_PORT, buildBridgeUrl, parseBridgeUrl } from "../bridge/bridgeUrl";
import { translateErrorKey } from "../i18n";
import { LanguagePicker } from "../components/LanguagePicker";
import { HelpFaqSection } from "../components/HelpFaqSection";
import { PetNameEditor } from "../components/PetNameEditor";
import { useConnectionStore } from "../store/connection";
import { useBridge } from "../bridge/BridgeProvider";
import type { SettingsStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<SettingsStackParamList, "SettingsMain">;

function SettingsSection({
  children,
  first,
}: {
  children: React.ReactNode;
  first?: boolean;
}) {
  return (
    <View style={[styles.section, !first && styles.sectionBorder]}>
      {children}
    </View>
  );
}

export function SettingsScreen({ navigation }: Props) {
  const { t } = useTranslation();
  const bridgeUrl = useConnectionStore((s) => s.bridgeUrl);
  const status = useConnectionStore((s) => s.status);
  const lastError = useConnectionStore((s) => s.lastError);
  const setBridgeUrl = useConnectionStore((s) => s.setBridgeUrl);
  const soundsMuted = useConnectionStore((s) => s.soundsMuted);
  const setSoundsMuted = useConnectionStore((s) => s.setSoundsMuted);
  const { connect, disconnect } = useBridge();

  const parsed = parseBridgeUrl(bridgeUrl);
  const [host, setHost] = useState(parsed.host);
  const [port, setPort] = useState(parsed.port || String(BUDDY_WS_PORT));

  useEffect(() => {
    const p = parseBridgeUrl(bridgeUrl);
    setHost(p.host);
    setPort(p.port || String(BUDDY_WS_PORT));
  }, [bridgeUrl]);

  const connected = status === "connected";
  const busy = status === "connecting";
  const fullUrl = buildBridgeUrl(host, port);
  const errorText = translateErrorKey(lastError);

  function handleConnect() {
    setBridgeUrl(fullUrl);
    setTimeout(() => connect(), 0);
  }

  function openBridgeGuide() {
    navigation.navigate("BridgeSetup");
  }

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator
      persistentScrollbar={Platform.OS === "android"}
      keyboardShouldPersistTaps="handled"
      nestedScrollEnabled
    >
      <Pressable
        style={styles.guideBanner}
        onPress={openBridgeGuide}
        accessibilityRole="button"
      >
        <Ionicons name="laptop-outline" size={20} color="#2563eb" />
        <Text style={styles.guideBannerText}>{t("settings.openBridgeGuide")}</Text>
        <Ionicons name="chevron-forward" size={18} color="#9ca3af" />
      </Pressable>

      <SettingsSection first>
        <Text style={styles.label}>{t("settings.bridgeTitle", { port: BUDDY_WS_PORT })}</Text>
        <Text style={styles.hint}>
          {t("settings.bridgeHint", { port: BUDDY_WS_PORT })}
        </Text>

        <Text style={styles.fieldLabel}>{t("settings.lanIp")}</Text>
        <TextInput
          style={styles.input}
          value={host}
          onChangeText={setHost}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="192.168.1.10"
          editable={!busy}
        />

        <Text style={styles.fieldLabel}>{t("settings.port")}</Text>
        <TextInput
          style={styles.input}
          value={port}
          onChangeText={setPort}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder={String(BUDDY_WS_PORT)}
          keyboardType="number-pad"
          editable={!busy}
        />

        <Text style={styles.preview}>
          {t("settings.urlPreview", { url: fullUrl || t("common.emDash") })}
        </Text>

        <Pressable
          style={[styles.btn, connected ? styles.disconnect : styles.connect, busy && styles.disabled]}
          onPress={() => (connected ? disconnect() : handleConnect())}
          disabled={busy || (!connected && !host.trim())}
        >
          <Text style={styles.btnText}>
            {busy ? t("common.connecting") : connected ? t("common.disconnect") : t("common.connect")}
          </Text>
        </Pressable>

        <Text style={styles.status}>
          {t("settings.status", { status: t(`connectionStatus.${status}`) })}
        </Text>
        {errorText ? <Text style={styles.error}>{errorText}</Text> : null}
      </SettingsSection>

      <SettingsSection>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>{t("settings.sounds")}</Text>
          <Switch value={!soundsMuted} onValueChange={(on) => setSoundsMuted(!on)} />
        </View>
        <Text style={styles.hint}>{t("settings.soundsHint")}</Text>
      </SettingsSection>

      <SettingsSection>
        <LanguagePicker />
      </SettingsSection>

      <SettingsSection>
        <PetNameEditor />
      </SettingsSection>

      <SettingsSection>
        <Pressable style={styles.link} onPress={() => navigation.navigate("PetEditor")}>
          <Text style={styles.linkText}>{t("settings.editGifs")}</Text>
        </Pressable>
      </SettingsSection>

      <SettingsSection>
        <HelpFaqSection />
      </SettingsSection>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#fff" },
  content: { paddingHorizontal: 20, paddingBottom: 32, paddingTop: 12 },
  guideBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: "#eff6ff",
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#bfdbfe",
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 4,
  },
  guideBannerText: {
    flex: 1,
    fontSize: 15,
    fontWeight: "600",
    color: "#1d4ed8",
  },
  section: {
    paddingVertical: 16,
  },
  sectionBorder: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#e5e7eb",
  },
  label: { fontSize: 16, fontWeight: "600", marginBottom: 4 },
  hint: { fontSize: 12, color: "#6b7280", marginBottom: 0, lineHeight: 18 },
  fieldLabel: { fontSize: 13, fontWeight: "500", marginBottom: 4, marginTop: 8, color: "#374151" },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 8,
  },
  preview: { fontSize: 12, color: "#6b7280", marginTop: 4, marginBottom: 12 },
  btn: {
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: "center",
    marginTop: 4,
    marginBottom: 8,
  },
  connect: { backgroundColor: "#2563eb" },
  disconnect: { backgroundColor: "#6b7280" },
  disabled: { opacity: 0.6 },
  btnText: { color: "#fff", fontWeight: "600" },
  status: { fontSize: 14, color: "#374151", marginBottom: 4 },
  error: { fontSize: 13, color: "#b91c1c", lineHeight: 18, marginBottom: 8 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  rowLabel: { fontSize: 15, color: "#374151" },
  link: { paddingVertical: 4 },
  linkText: { fontSize: 16, color: "#2563eb" },
});
