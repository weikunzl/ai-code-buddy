import React from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { useSnapshotStore } from "../store/snapshot";

type SessionRow = {
  sid?: string;
  project?: string;
  branch?: string;
  phase?: string;
  model?: string;
  last?: string;
};

export function SessionsScreen() {
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const sessions = (snapshot?.sessions ?? []) as SessionRow[];

  return (
    <View style={styles.container}>
      <FlatList
        data={sessions}
        keyExtractor={(item, index) => item.sid ?? String(index)}
        ListEmptyComponent={
          <Text style={styles.empty}>No sessions yet. Connect to the bridge on your LAN.</Text>
        }
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={styles.project}>{item.project ?? item.sid ?? "session"}</Text>
            <Text style={styles.meta}>
              {[item.branch, item.phase, item.model].filter(Boolean).join(" · ")}
            </Text>
            {item.last ? <Text style={styles.last}>{item.last}</Text> : null}
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  empty: { padding: 24, color: "#6b7280", textAlign: "center" },
  row: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#e5e7eb",
  },
  project: { fontSize: 16, fontWeight: "600" },
  meta: { fontSize: 13, color: "#6b7280", marginTop: 4 },
  last: { fontSize: 12, color: "#9ca3af", marginTop: 4 },
});
