import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import type { PendingItem } from "@protocol/index";
import type { DeviceIntent } from "@protocol/index";

type Props = {
  pending: PendingItem | null;
  onSend: (intent: DeviceIntent) => void;
  onDismiss?: () => void;
};

const APPROVAL_KINDS = new Set([
  "permission",
  "single_choice",
  "multi_choice",
  "free_text_required",
]);

export function ApprovalModal({ pending, onSend, onDismiss }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const visible = pending !== null && APPROVAL_KINDS.has(pending.kind);

  useEffect(() => {
    setSelected([]);
  }, [pending?.id]);

  const approvePermission = useCallback(() => {
    if (!pending) return;
    onSend({ cmd: "permission", id: pending.id, decision: "once" });
  }, [pending, onSend]);

  const denyPermission = useCallback(() => {
    if (!pending) return;
    onSend({ cmd: "permission", id: pending.id, decision: "deny" });
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
          <ScrollView style={styles.bodyScroll}>
            <Text style={styles.body}>{pending.body}</Text>
          </ScrollView>

          {pending.kind === "permission" && (
            <View style={styles.row}>
              <Pressable style={[styles.btn, styles.deny]} onPress={denyPermission}>
                <Text style={styles.btnText}>Deny</Text>
              </Pressable>
              <Pressable style={[styles.btn, styles.approve]} onPress={approvePermission}>
                <Text style={styles.btnText}>Allow once</Text>
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
              <Text style={styles.btnText}>Submit</Text>
            </Pressable>
          )}

          {pending.kind === "free_text_required" && (
            <Text style={styles.hint}>Free-text prompts require IDE input for now.</Text>
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
  bodyScroll: { maxHeight: 160, marginBottom: 16 },
  body: { fontSize: 14, color: "#374151" },
  row: { flexDirection: "row", gap: 12 },
  btn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  approve: { backgroundColor: "#2563eb" },
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
