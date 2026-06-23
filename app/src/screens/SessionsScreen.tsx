import React, { useCallback, useMemo } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import type { PendingItem } from "@protocol/index";
import { useBridge } from "../bridge/BridgeProvider";
import { BridgeSetupGuide } from "../components/BridgeSetupGuide";
import { useConnectionStore } from "../store/connection";
import { useSnapshotStore } from "../store/snapshot";

type SessionRow = {
  sid?: string;
  project?: string;
  branch?: string;
  phase?: string;
  model?: string;
  last?: string;
  dirty?: number;
  focused?: boolean;
};

function EmptyState({
  connected,
  activityOnly,
}: {
  connected: boolean;
  activityOnly?: boolean;
}) {
  const { t } = useTranslation();
  if (!connected) {
    return (
      <View style={styles.emptyBox}>
        <Text style={styles.emptyTitle}>{t("sessions.notConnectedTitle")}</Text>
        <View style={styles.guideWrap}>
          <BridgeSetupGuide compact />
        </View>
      </View>
    );
  }
  if (activityOnly) {
    return (
      <View style={styles.emptyBox}>
        <Text style={styles.emptyTitle}>{t("sessions.activityOnlyTitle")}</Text>
        <Text style={styles.empty}>{t("sessions.activityOnlyBody")}</Text>
      </View>
    );
  }
  return (
    <View style={styles.emptyBox}>
      <Text style={styles.emptyTitle}>{t("sessions.emptyTitle")}</Text>
      <Text style={styles.empty}>{t("sessions.emptyBody")}</Text>
    </View>
  );
}

function PendingCard({ item }: { item: PendingItem }) {
  const { t } = useTranslation();
  return (
    <View style={[styles.row, styles.pendingRow]}>
      <Text style={styles.pendingBadge}>{t("sessions.pendingBadge")}</Text>
      <Text style={styles.project}>{item.title}</Text>
      <Text style={styles.meta}>{item.kind}</Text>
      {item.body ? <Text style={styles.last}>{item.body}</Text> : null}
    </View>
  );
}

function SessionCard({
  item,
  onFocus,
}: {
  item: SessionRow;
  onFocus: (sid: string) => void;
}) {
  const { t } = useTranslation();
  const sid = item.sid ?? "";
  const focused = Boolean(item.focused);

  return (
    <Pressable
      style={({ pressed }) => [
        styles.row,
        focused && styles.focusedRow,
        pressed && !focused && styles.rowPressed,
      ]}
      disabled={!sid || focused}
      onPress={() => onFocus(sid)}
      accessibilityRole="button"
      accessibilityState={{ selected: focused, disabled: !sid || focused }}
      accessibilityLabel={t("sessions.focusSession", {
        name: item.project ?? sid ?? t("common.session"),
      })}
    >
      <Text style={styles.project}>
        {item.project ?? item.sid ?? t("common.session")}
        {focused ? ` ${t("sessions.focusedMark")}` : ""}
      </Text>
      <Text style={styles.meta}>
        {[item.branch, item.phase, item.model].filter(Boolean).join(" · ")}
      </Text>
      {item.last ? <Text style={styles.last}>{item.last}</Text> : null}
      {!focused && sid ? (
        <Text style={styles.tapHint}>{t("sessions.tapToSwitch")}</Text>
      ) : null}
    </Pressable>
  );
}

export function SessionsScreen() {
  const { t } = useTranslation();
  const { sendIntent } = useBridge();
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const focusSession = useSnapshotStore((s) => s.focusSession);
  const status = useConnectionStore((s) => s.status);
  const connected = status === "connected";

  const sessions = (snapshot?.sessions ?? []) as SessionRow[];
  const pending = snapshot?.pending ?? [];

  const summary = useMemo(() => {
    if (!snapshot || !connected) return null;
    return t("sessions.summary", {
      total: snapshot.total ?? 0,
      running: snapshot.running ?? 0,
      waiting: snapshot.waiting ?? 0,
    });
  }, [snapshot, connected, t]);

  const handleFocus = useCallback(
    (sid: string) => {
      if (!connected || !sid) return;
      focusSession(sid);
      sendIntent({ cmd: "focus", sid });
    },
    [connected, focusSession, sendIntent],
  );

  const entries = snapshot?.entries ?? [];
  const showList = sessions.length > 0 || pending.length > 0;
  const activityOnly = connected && !showList && entries.length > 0;

  return (
    <View style={styles.container}>
      {connected && summary ? (
        <View style={styles.summary}>
          <Text style={styles.summaryText}>{summary}</Text>
          {snapshot?.msg ? <Text style={styles.summaryMsg}>{snapshot.msg}</Text> : null}
        </View>
      ) : null}

      {pending.length > 0 ? (
        <View>
          <Text style={styles.section}>{t("sessions.sectionPending")}</Text>
          {pending.map((p) => (
            <PendingCard key={p.id} item={p} />
          ))}
        </View>
      ) : null}

      {sessions.length > 0 ? (
        <>
          <Text style={styles.section}>{t("sessions.sectionSessions")}</Text>
          {sessions.length > 1 ? (
            <Text style={styles.sectionHint}>{t("sessions.switchHint")}</Text>
          ) : null}
          <FlatList
            data={sessions}
            keyExtractor={(item, index) => item.sid ?? String(index)}
            renderItem={({ item }) => (
              <SessionCard item={item} onFocus={handleFocus} />
            )}
          />
        </>
      ) : null}

      {!showList ? <EmptyState connected={connected} activityOnly={activityOnly} /> : null}

      {connected && entries.length > 0 ? (
        <View style={styles.entries}>
          <Text style={styles.section}>{t("sessions.sectionActivity")}</Text>
          {entries.map((line, i) => (
            <Text key={`${line}-${i}`} style={styles.entryLine}>
              {line}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  summary: {
    backgroundColor: "#eff6ff",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#dbeafe",
  },
  summaryText: { fontSize: 14, fontWeight: "600", color: "#1e40af" },
  summaryMsg: { fontSize: 13, color: "#3b82f6", marginTop: 4 },
  section: {
    fontSize: 12,
    fontWeight: "700",
    color: "#9ca3af",
    textTransform: "uppercase",
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  sectionHint: {
    fontSize: 12,
    color: "#6b7280",
    paddingHorizontal: 16,
    paddingBottom: 4,
  },
  emptyBox: { padding: 16 },
  guideWrap: { marginTop: 12 },
  emptyTitle: { fontSize: 16, fontWeight: "600", color: "#374151", marginBottom: 8, textAlign: "center" },
  empty: { color: "#6b7280", textAlign: "center", lineHeight: 20, fontSize: 14 },
  row: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#e5e7eb",
  },
  rowPressed: { backgroundColor: "#f3f4f6" },
  focusedRow: { backgroundColor: "#f0fdf4" },
  pendingRow: { backgroundColor: "#fff7ed" },
  pendingBadge: { fontSize: 11, fontWeight: "700", color: "#c2410c", marginBottom: 4 },
  project: { fontSize: 16, fontWeight: "600" },
  meta: { fontSize: 13, color: "#6b7280", marginTop: 4 },
  last: { fontSize: 12, color: "#9ca3af", marginTop: 4 },
  tapHint: { fontSize: 11, color: "#2563eb", marginTop: 6 },
  entries: { paddingBottom: 24 },
  entryLine: { fontSize: 12, color: "#6b7280", paddingHorizontal: 16, paddingVertical: 4 },
});
