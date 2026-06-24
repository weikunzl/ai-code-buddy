import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import { CollapsibleFaq } from "./CollapsibleFaq";

const FAQ_IDS = [
  "wifi",
  "lanIp",
  "installCli",
  "installHooks",
  "wsError",
  "ports",
  "sessions",
  "notifications",
  "restart",
] as const;

export function HelpFaqSection() {
  const { t } = useTranslation();

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>{t("help.title")}</Text>
      <Text style={styles.subtitle}>{t("help.subtitle")}</Text>
      {FAQ_IDS.map((id) => (
        <CollapsibleFaq
          key={id}
          question={t(`help.faq.${id}.q`)}
          answer={t(`help.faq.${id}.a`)}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingTop: 4 },
  title: { fontSize: 16, fontWeight: "600", color: "#111827", marginBottom: 4 },
  subtitle: { fontSize: 12, color: "#6b7280", lineHeight: 18, marginBottom: 4 },
});
