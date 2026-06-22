import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useTranslation } from "react-i18next";
import { DEFAULT_PET_NAME, MAX_PET_NAME_LENGTH, PRODUCT_NAME } from "../constants/product";
import { usePetProfile } from "../store/petProfile";

export function PetNameEditor() {
  const { t } = useTranslation();
  const petName = usePetProfile((s) => s.profile.name);
  const setName = usePetProfile((s) => s.setName);
  const [draft, setDraft] = useState(petName);

  useEffect(() => {
    setDraft(petName);
  }, [petName]);

  function commit() {
    setName(draft);
  }

  function reset() {
    setDraft(DEFAULT_PET_NAME);
    setName(DEFAULT_PET_NAME);
  }

  const canReset = petName !== DEFAULT_PET_NAME;

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{t("settings.petName")}</Text>
      <Text style={styles.hint}>{t("settings.petNameHint", { product: PRODUCT_NAME })}</Text>
      <TextInput
        style={styles.input}
        value={draft}
        onChangeText={setDraft}
        onBlur={commit}
        onSubmitEditing={commit}
        maxLength={MAX_PET_NAME_LENGTH}
        autoCapitalize="words"
        autoCorrect={false}
        returnKeyType="done"
        placeholder={DEFAULT_PET_NAME}
      />
      {canReset ? (
        <Pressable onPress={reset}>
          <Text style={styles.reset}>
            {t("settings.resetPetName", { name: DEFAULT_PET_NAME })}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 16 },
  label: { fontSize: 15, fontWeight: "500", color: "#374151", marginBottom: 4 },
  hint: { fontSize: 12, color: "#6b7280", marginBottom: 8, lineHeight: 18 },
  input: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 8,
  },
  reset: { fontSize: 13, color: "#2563eb" },
});
