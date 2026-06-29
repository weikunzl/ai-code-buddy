import React, { useCallback, useEffect, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";
import type { PendingItem } from "@protocol/index";
import type { DeviceIntent } from "@protocol/index";
import { resolveIdeI18nKey } from "../bridge/resolveIde";
import { resolveContextSession } from "../bridge/sessionContext";
import { useSnapshotStore } from "../store/snapshot";

type Props = {
  pending: PendingItem | null;
  onSend: (intent: DeviceIntent) => void;
  onDismiss?: () => void;
  sendError?: string | null;
};

const APPROVAL_KINDS = new Set([
  "permission",
  "single_choice",
  "multi_choice",
  "free_text_required",
]);

export function ApprovalModal({ pending, onSend, onDismiss, sendError }: Props) {
  const { t } = useTranslation();
  const snapshot = useSnapshotStore((s) => s.snapshot);
  const contextSession = resolveContextSession(snapshot, pending);
  const [selected, setSelected] = useState<string[]>([]);
  const visible = pending !== null && APPROVAL_KINDS.has(pending.kind);

  useEffect(() => {
    setSelected([]);
  }, [pending?.id]);

  const denyPermission = useCallback(() => {
    if (!pending) return;
    onSend({ cmd: "permission", id: pending.id, decision: "skip" });
  }, [pending, onSend]);

  const allowPermission = useCallback(() => {
    if (!pending) return;
    onSend({ cmd: "permission", id: pending.id, decision: "allow" });
  }, [pending, onSend]);

  const runPermission = useCallback(() => {
    if (!pending) return;
    onSend({ cmd: "permission", id: pending.id, decision: "run" });
  }, [pending, onSend]);

  const submitChoice = useCallback(
    (choiceId: string) => {
      if (!pending) return;
      onSend({ cmd: "answer", id: pending.id, choice: choiceId });
    },
    [pending, onSend],
  );

  const submitMulti = useCallback(() => {
    if (!pending || selected.length === 0) return;
    onSend({ cmd: "answer", id: pending.id, choices: selected });
  }, [pending, selected, onSend]);

  if (!visible || !pending) return null;

  return (
    <Modal visible animationType="slide" transparent onRequestClose={onDismiss}>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>{pending.title}</Text>
          {contextSession?.project ? (
            <Text style={styles.sessionLine} numberOfLines={2}>
              {t("home.activeProject", {
                project: contextSession.project,
                branch: contextSession.branch ?? t("common.main"),
              })}
              {" · "}
              {t(resolveIdeI18nKey(contextSession.model))}
            </Text>
          ) : null}
          <ScrollView style={styles.bodyScroll}>
            <Text style={styles.body}>{pending.body}</Text>
          </ScrollView>

          {sendError ? <Text style={styles.error}>{sendError}</Text> : null}

          {pending.kind === "permission" && (
            <View style={styles.row}>
              <Pressable style={[styles.btn, styles.deny]} onPress={denyPermission}>
                <Text style={styles.btnText}>{t("approval.skip")}</Text>
              </Pressable>
              <Pressable style={[styles.btn, styles.allow]} onPress={allowPermission}>
                <Text style={styles.btnText}>{t("approval.allow")}</Text>
              </Pressable>
              <Pressable style={[styles.btn, styles.run]} onPress={runPermission}>
                <Text style={styles.btnText}>{t("approval.run")}</Text>
              </Pressable>
            </View>
          )}

          {(pending.kind === "single_choice" || pending.kind === "multi_choice") &&
            pending.options?.map((opt) => {
              const isMulti = pending.kind === "multi_choice";
              const picked = selected.includes(opt.id);
              return (
                <Pressable
                  key={opt.id}
                  style={[styles.option, picked && styles.optionPicked]}
                  onPress={() => {
                    if (isMulti) {
                      setSelected((prev) =>
                        picked ? prev.filter((id) => id !== opt.id) : [...prev, opt.id],
                      );
                    } else {
                      submitChoice(opt.id);
                    }
                  }}
                >
                  <Text style={styles.optionLabel}>{opt.label}</Text>
                  {opt.desc ? <Text style={styles.optionDesc}>{opt.desc}</Text> : null}
                </Pressable>
              );
            })}

          {pending.kind === "multi_choice" && (
            <Pressable
              style={[styles.btn, styles.approve, selected.length === 0 && styles.disabled]}
              disabled={selected.length === 0}
              onPress={submitMulti}
            >
              <Text style={styles.btnText}>{t("common.submit")}</Text>
            </Pressable>
          )}

          {pending.kind === "free_text_required" && (
            <Text style={styles.hint}>{t("approval.freeTextHint")}</Text>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  card: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 20,
    maxHeight: "80%",
  },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 8 },
  sessionLine: { fontSize: 13, color: "#4b5563", marginBottom: 8 },
  bodyScroll: { maxHeight: 160, marginBottom: 16 },
  body: { fontSize: 14, color: "#374151" },
  error: { fontSize: 13, color: "#dc2626", marginBottom: 12 },
  row: { flexDirection: "row", gap: 8 },
  btn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  run: { backgroundColor: "#2563eb" },
  allow: { backgroundColor: "#059669" },
  deny: { backgroundColor: "#6b7280" },
  disabled: { opacity: 0.4 },
  btnText: { color: "#fff", fontWeight: "600" },
  option: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  optionPicked: { borderColor: "#2563eb", backgroundColor: "#eff6ff" },
  optionLabel: { fontSize: 16, fontWeight: "600" },
  optionDesc: { fontSize: 12, color: "#6b7280", marginTop: 4 },
  hint: { fontSize: 13, color: "#6b7280", fontStyle: "italic" },
});
