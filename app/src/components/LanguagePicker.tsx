import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";
import type { LocalePreference } from "../i18n/resolveLocale";
import { useLocaleStore } from "../store/locale";

const OPTIONS: { value: LocalePreference; labelKey: string }[] = [
  { value: "auto", labelKey: "settings.languageAuto" },
  { value: "en", labelKey: "settings.languageEn" },
  { value: "zh", labelKey: "settings.languageZh" },
  { value: "ko", labelKey: "settings.languageKo" },
  { value: "ru", labelKey: "settings.languageRu" },
];

export function LanguagePicker() {
  const { t } = useTranslation();
  const preference = useLocaleStore((s) => s.preference);
  const setPreference = useLocaleStore((s) => s.setPreference);

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{t("settings.language")}</Text>
      <View style={styles.row}>
        {OPTIONS.map((opt) => {
          const active = preference === opt.value;
          return (
            <Pressable
              key={opt.value}
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => setPreference(opt.value)}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>
                {t(opt.labelKey)}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 16 },
  label: { fontSize: 15, color: "#374151", marginBottom: 8 },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 16,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipActive: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
  chipText: { fontSize: 13, color: "#374151" },
  chipTextActive: { color: "#fff", fontWeight: "600" },
});
