import React from "react";
import { Platform, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { BUDDY_WS_PORT } from "../bridge/bridgeUrl";

function CommandBlock({ command }: { command: string }) {
  return (
    <View style={styles.cmdBox}>
      <Text style={styles.cmdText} selectable>
        {command}
      </Text>
    </View>
  );
}

type Props = {
  /** Shorter copy for home / sessions empty states */
  compact?: boolean;
};

export function BridgeSetupGuide({ compact = false }: Props) {
  const { t } = useTranslation();
  const port = String(BUDDY_WS_PORT);

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{t("bridgeSetup.title")}</Text>
      <Text style={styles.subtitle}>{t("bridgeSetup.subtitle")}</Text>

      {!compact ? (
        <>
          <Text style={styles.step}>{t("bridgeSetup.step0")}</Text>
          <CommandBlock command={t("bridgeSetup.cmdNpmInstall")} />
          <Text style={styles.step}>{t("bridgeSetup.step1")}</Text>
        </>
      ) : null}

      <Text style={styles.step}>{compact ? t("bridgeSetup.stepCompact") : t("bridgeSetup.step2")}</Text>
      <CommandBlock command={t("bridgeSetup.cmdRestart")} />
      {!compact ? (
        <Text style={styles.cmdHint}>{t("bridgeSetup.cmdRestartHint")}</Text>
      ) : null}

      {!compact ? (
        <>
          <CommandBlock command={t("bridgeSetup.cmdStart")} />
          <Text style={styles.cmdHint}>{t("bridgeSetup.cmdStartHint")}</Text>

          <Text style={styles.stepAlt}>{t("bridgeSetup.stepCloneAlt")}</Text>
          <CommandBlock command={t("bridgeSetup.cmdCloneRestart")} />
          <CommandBlock command={t("bridgeSetup.cmdCloneStart")} />
          <CommandBlock command={t("bridgeSetup.cmdManual", { port })} />
        </>
      ) : null}

      <Text style={styles.step}>{t("bridgeSetup.step3")}</Text>
      <Text style={styles.step}>{t("bridgeSetup.step4", { port })}</Text>
      <CommandBlock command={t("bridgeSetup.wsExample", { port })} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: "#f8fafc",
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#e2e8f0",
    padding: 14,
    gap: 8,
  },
  title: { fontSize: 15, fontWeight: "700", color: "#1e293b" },
  subtitle: { fontSize: 13, color: "#64748b", lineHeight: 19, marginBottom: 4 },
  step: { fontSize: 13, color: "#334155", lineHeight: 20 },
  stepAlt: { fontSize: 13, color: "#475569", lineHeight: 20, marginTop: 4 },
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
  cmdHint: { fontSize: 12, color: "#64748b", lineHeight: 17, marginBottom: 4 },
});
