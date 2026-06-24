import React, { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { CompositeNavigationProp } from "@react-navigation/native";
import type { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useTranslation } from "react-i18next";
import { useBridge } from "../bridge/BridgeProvider";
import { BridgeSetupGuide } from "../components/BridgeSetupGuide";
import type { RootParamList } from "../navigation/navigationRef";
import type { SettingsStackParamList } from "../navigation/types";
import { derivePetState } from "../pet/derivePetState";
import { GifRenderer } from "../pet/GifRenderer";
import { useConnectionStore } from "../store/connection";
import { usePetProfile } from "../store/petProfile";
import { useSnapshotStore } from "../store/snapshot";

type HomeNav = CompositeNavigationProp<
  BottomTabNavigationProp<RootParamList, "Home">,
  NativeStackNavigationProp<SettingsStackParamList>
>;

export function HomeScreen() {
  const { t } = useTranslation();
  const navigation = useNavigation<HomeNav>();
  const { connect } = useBridge();
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const lastApproveAt = useSnapshotStore((s) => s.lastApproveAt);
  const status = useConnectionStore((s) => s.status);
  const reconnectGaveUp = useConnectionStore((s) => s.reconnectGaveUp);
  const petName = usePetProfile((s) => s.profile.name);
  const connected = status === "connected";
  const connecting = status === "connecting";
  const showSetupGuide = !connected && !connecting;

  const petState = derivePetState(
    snapshot,
    connected,
    lastApproveAt ?? undefined,
  );
  const pending = snapshot?.pending?.[0] ?? null;

  const banner = useMemo(() => {
    if (reconnectGaveUp) return t("home.reconnectGaveUp");
    if (connecting) return t("home.connecting");
    if (!connected) return t("home.notConnected");
    if (pending) return pending.title;
    if (snapshot?.assistant_msg) return snapshot.assistant_msg;
    if (snapshot?.project) {
      return `${snapshot.project} · ${snapshot.branch ?? t("common.main")}`;
    }
    return t("home.watching");
  }, [connected, connecting, pending, reconnectGaveUp, snapshot, t]);

  const showConnectCta = reconnectGaveUp && !connected && !connecting;

  return (
    <View style={styles.container}>
      <View style={[styles.banner, !connected && styles.bannerOff]}>
        <Text style={styles.bannerText} numberOfLines={3}>
          {banner}
        </Text>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator
      >
        <View style={styles.petArea}>
          <Text style={styles.petName}>{petName}</Text>
          <GifRenderer state={petState} size={200} />
          <Text style={styles.stateLabel}>{t(`petStates.${petState}`)}</Text>
          {snapshot && connected ? (
            <Text style={styles.stats}>
              {t("home.stats", {
                running: snapshot.running,
                waiting: snapshot.waiting,
                total: snapshot.total,
              })}
            </Text>
          ) : null}
          {showConnectCta ? (
            <Pressable style={styles.connectBtn} onPress={() => connect()}>
              <Text style={styles.connectBtnText}>{t("home.tapConnect")}</Text>
            </Pressable>
          ) : null}
        </View>

        {showSetupGuide ? (
          <View style={styles.guideWrap}>
            <BridgeSetupGuide compact />
            <Pressable
              style={styles.guideLink}
              onPress={() => navigation.navigate("Settings", { screen: "BridgeSetup" })}
            >
              <Text style={styles.guideLinkText}>{t("home.openBridgeGuide")}</Text>
            </Pressable>
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f9fafb" },
  banner: {
    backgroundColor: "#dbeafe",
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  bannerOff: { backgroundColor: "#e5e7eb" },
  bannerText: { fontSize: 14, color: "#1e3a8a" },
  scroll: { flex: 1 },
  scrollContent: { flexGrow: 1, paddingBottom: 24 },
  petArea: { alignItems: "center", justifyContent: "center", gap: 12, paddingVertical: 24 },
  petName: { fontSize: 22, fontWeight: "700", color: "#111827" },
  stateLabel: { fontSize: 16, fontWeight: "600" },
  stats: { fontSize: 13, color: "#6b7280" },
  connectBtn: {
    marginTop: 8,
    backgroundColor: "#2563eb",
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
  },
  connectBtnText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  guideWrap: { paddingHorizontal: 16, gap: 10 },
  guideLink: { alignItems: "center", paddingVertical: 8 },
  guideLinkText: { fontSize: 14, color: "#2563eb", fontWeight: "600" },
});
