import React, { useEffect, useMemo, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { derivePetState } from "../pet/derivePetState";
import { GifRenderer } from "../pet/GifRenderer";
import { useConnectionStore } from "../store/connection";
import { useSnapshotStore } from "../store/snapshot";
import { ApprovalModal } from "../components/ApprovalModal";
import { useBridge } from "../bridge/BridgeProvider";

export function HomeScreen() {
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const status = useConnectionStore((s) => s.status);
  const connected = status === "connected";
  const { sendIntent } = useBridge();
  const [recentApproveAt, setRecentApproveAt] = useState<number | undefined>();
  const prevPendingId = useRef<string | undefined>();

  const petState = derivePetState(snapshot, connected, recentApproveAt);
  const pending = snapshot?.pending?.[0] ?? null;

  useEffect(() => {
    const id = pending?.id;
    if (id && id !== prevPendingId.current) {
      prevPendingId.current = id;
    }
  }, [pending?.id]);

  const banner = useMemo(() => {
    if (!connected) return "Not connected to bridge";
    if (pending) return pending.title;
    if (snapshot?.assistant_msg) return snapshot.assistant_msg;
    if (snapshot?.project) return `${snapshot.project} · ${snapshot.branch ?? "main"}`;
    return "Watching sessions…";
  }, [connected, pending, snapshot]);

  return (
    <View style={styles.container}>
      <View style={[styles.banner, !connected && styles.bannerOff]}>
        <Text style={styles.bannerText} numberOfLines={2}>
          {banner}
        </Text>
      </View>

      <View style={styles.petArea}>
        <GifRenderer state={petState} size={200} />
        <Text style={styles.stateLabel}>{petState}</Text>
        {snapshot ? (
          <Text style={styles.stats}>
            {snapshot.running} running · {snapshot.waiting} waiting · {snapshot.total} total
          </Text>
        ) : null}
      </View>

      <ApprovalModal
        pending={pending}
        onSend={(intent) => {
          sendIntent(intent);
          setRecentApproveAt(Date.now());
        }}
      />
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
  petArea: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12 },
  stateLabel: { fontSize: 16, fontWeight: "600", textTransform: "capitalize" },
  stats: { fontSize: 13, color: "#6b7280" },
});
